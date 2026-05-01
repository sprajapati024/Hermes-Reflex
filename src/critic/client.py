"""LLM critic client for Hermes Reflex.

This module provides the public ``critic()`` function. It builds the critic
prompt, calls a cheap JSON-only model, parses the response, retries transient
errors, and always returns a ``CriticDecision``.

Provider selection:
  HERMES_REFLEX_CRITIC_PROVIDER = auto | openai | minimax  (default: auto)
  OPENAI_API_KEY                = OpenAI key for the OpenAI chat-completions path
  MINIMAX_API_KEY               = MiniMax key for the Anthropic-compatible path
  HERMES_REFLEX_CRITIC_MODEL    = explicit model override
  HERMES_REFLEX_OPENAI_MODEL    = OpenAI model override, default gpt-4o-mini
  HERMES_REFLEX_MINIMAX_MODEL   = MiniMax model override, default MiniMax-M2.7
  HERMES_REFLEX_MAX_TOKENS      = max output tokens, default 512
  HERMES_REFLEX_TEMPERATURE     = sampling temperature, default 0.1

``auto`` tries OpenAI first for backward compatibility, then MiniMax when the
OpenAI path is missing/invalid. This keeps Reflex operational on Shirin's
current Hermes VPS, where MiniMax is configured but the OpenAI key may be absent
or stale.
"""

from __future__ import annotations

import os
import re
import time
import typing as t
from dataclasses import dataclass
from functools import lru_cache

import anthropic
import openai

from . import prompt as prompt_module
from .decision import CriticDecision
from .parser import ParseError, parse_critic_response


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_PROVIDER = os.environ.get("HERMES_REFLEX_CRITIC_PROVIDER", "auto").strip().lower()
_OPENAI_MODEL = os.environ.get("HERMES_REFLEX_OPENAI_MODEL", "gpt-4o-mini")
_MINIMAX_MODEL = os.environ.get("HERMES_REFLEX_MINIMAX_MODEL", "MiniMax-M2.7")
_MODEL_OVERRIDE = os.environ.get("HERMES_REFLEX_CRITIC_MODEL")
_MAX_TOKENS = int(os.environ.get("HERMES_REFLEX_MAX_TOKENS", "512"))
_TEMPERATURE = float(os.environ.get("HERMES_REFLEX_TEMPERATURE", "0.1"))
_MAX_RETRIES = 3
_RETRY_DELAY_BASE = 1.0  # seconds
_MINIMAX_BASE_URL = os.environ.get(
    "HERMES_REFLEX_MINIMAX_BASE_URL",
    "https://api.minimax.io/anthropic",
).rstrip("/")


# ---------------------------------------------------------------------------
# Client singletons
# ---------------------------------------------------------------------------

@dataclass
class _RetryLog:
    attempt: int
    waited: float
    error: str
    provider: str = "openai"


@lru_cache(maxsize=1)
def _get_client() -> openai.OpenAI:
    """Return a cached OpenAI client instance (lazy init)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is not set. "
            "OpenAI critic provider requires a valid OpenAI API key."
        )
    return openai.OpenAI(api_key=api_key)


@lru_cache(maxsize=1)
def _get_minimax_client() -> anthropic.Anthropic:
    """Return a cached MiniMax Anthropic-compatible client instance."""
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "MINIMAX_API_KEY environment variable is not set. "
            "MiniMax critic provider requires a valid MiniMax API key."
        )
    return anthropic.Anthropic(api_key=api_key, base_url=_MINIMAX_BASE_URL)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@t.overload
def critic(
    *,
    user_message: str,
    rule_result: dict,
    contract_conflict: dict,
    active_experiments: list[dict],
    retrieved_evidence: list[dict],
    recent_patterns: list[dict],
) -> CriticDecision: ...


@t.overload
def critic(
    *,
    user_message: str,
    rule_result: dict,
    contract_conflict: dict,
    active_experiments: list[dict],
    retrieved_evidence: list[dict],
    recent_patterns: list[dict],
    model: str | None = None,
    max_retries: int | None = None,
) -> CriticDecision: ...


def critic(
    *,
    user_message: str,
    rule_result: dict,
    contract_conflict: dict,
    active_experiments: list[dict],
    retrieved_evidence: list[dict],
    recent_patterns: list[dict],
    model: str | None = None,
    max_retries: int | None = None,
) -> CriticDecision:
    """Call the configured critic provider and return a validated decision.

    This function never raises. If all providers fail, it returns
    ``CriticDecision.default_allow()`` so the middleware can continue and apply
    deterministic rule/contract fallbacks.
    """
    max_retries = max_retries if max_retries is not None else _MAX_RETRIES
    retry_log: list[_RetryLog] = []

    user_content = prompt_module.build_user_message(
        user_message=user_message,
        rule_result=rule_result,
        contract_conflict=contract_conflict,
        active_experiments=active_experiments,
        retrieved_evidence=retrieved_evidence,
        recent_patterns=recent_patterns,
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": prompt_module.SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    for provider in _provider_candidates():
        provider_model = _model_for_provider(provider, model)
        decision = _try_provider(
            provider=provider,
            model=provider_model,
            messages=messages,
            max_retries=max_retries,
            retry_log=retry_log,
        )
        if decision is not None:
            return decision

    _log_critic_failure(
        user_message=user_message,
        provider_model=_provider_model_label(model),
        retry_log=retry_log,
    )
    return CriticDecision.default_allow()


# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------

def _provider_candidates() -> list[str]:
    """Return the provider order for this call."""
    if _PROVIDER in {"openai", "minimax"}:
        return [_PROVIDER]
    if _PROVIDER not in {"", "auto"}:
        return [_PROVIDER]
    # Backward-compatible order: OpenAI first, MiniMax as operational fallback.
    return ["openai", "minimax"]


def _model_for_provider(provider: str, override: str | None) -> str:
    if override:
        return override
    if _MODEL_OVERRIDE:
        return _MODEL_OVERRIDE
    if provider == "minimax":
        return _MINIMAX_MODEL
    return _OPENAI_MODEL


def _provider_model_label(override: str | None) -> str:
    return ", ".join(f"{p}:{_model_for_provider(p, override)}" for p in _provider_candidates())


def _try_provider(
    *,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    max_retries: int,
    retry_log: list[_RetryLog],
) -> CriticDecision | None:
    for attempt in range(1, max_retries + 1):
        try:
            raw_text = _call_provider(provider=provider, model=model, messages=messages)
            return parse_critic_response(raw_text)

        except _transient_errors() as exc:
            waited = _RETRY_DELAY_BASE * (2 ** (attempt - 1))
            retry_log.append(_RetryLog(attempt=attempt, waited=waited, error=_safe_error(exc), provider=provider))
            if attempt < max_retries:
                time.sleep(waited)
            continue

        except ParseError as exc:
            retry_log.append(_RetryLog(attempt=attempt, waited=0, error=f"ParseError: {_safe_error(exc)}", provider=provider))
            if attempt < max_retries:
                messages.append({
                    "role": "developer",
                    "content": "Reminder: respond with JSON only. Do not add prose outside the JSON block.",
                })
            continue

        except Exception as exc:
            # Missing/invalid credentials or provider-specific hard failures should
            # not consume retries in auto mode. Record them and let the next
            # provider try.
            retry_log.append(_RetryLog(attempt=attempt, waited=0, error=_safe_error(exc), provider=provider))
            break

    return None


def _call_provider(*, provider: str, model: str, messages: list[dict[str, str]]) -> str:
    if provider == "openai":
        return _call_openai(model=model, messages=messages)
    if provider == "minimax":
        return _call_minimax(model=model, messages=messages)
    raise ValueError(f"Unsupported Hermes Reflex critic provider: {provider!r}")


def _call_openai(*, model: str, messages: list[dict[str, str]]) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""


def _call_minimax(*, model: str, messages: list[dict[str, str]]) -> str:
    client = _get_minimax_client()
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    user_messages = [
        {"role": "user", "content": m["content"]}
        for m in messages
        if m.get("role") != "system"
    ]
    response = client.messages.create(
        model=model,
        max_tokens=_MAX_TOKENS,
        temperature=_TEMPERATURE,
        system=system,
        messages=user_messages,
    )
    return "".join(getattr(block, "text", "") for block in response.content)


def _transient_errors() -> tuple[type[BaseException], ...]:
    return (
        openai.RateLimitError,
        openai.APIConnectionError,
        anthropic.RateLimitError,
        anthropic.APIConnectionError,
    )


# ---------------------------------------------------------------------------
# Safe logging
# ---------------------------------------------------------------------------

def _safe_error(exc: BaseException) -> str:
    """Return an exception string with credentials redacted."""
    text = str(exc)
    for env_key in ("OPENAI_API_KEY", "MINIMAX_API_KEY", "ANTHROPIC_API_KEY"):
        value = os.environ.get(env_key) or ""
        if value:
            text = text.replace(value, "[REDACTED]")
    # Redact common OpenAI-style key fragments that SDK errors sometimes echo.
    text = re.sub(r"sk-[A-Za-z0-9_-]{4,}", "sk-[REDACTED]", text)
    text = re.sub(r"mxp-[A-Za-z0-9_-]{4,}", "mxp-[REDACTED]", text)
    return text


def _log_critic_failure(
    user_message: str,
    provider_model: str,
    retry_log: list[_RetryLog],
) -> None:
    """Log critic failures for debugging (writes to stderr)."""
    import sys

    entries = [
        f"[Hermes Reflex critic] FAILURE on '{user_message[:80]}' using {provider_model}",
    ]
    for entry in retry_log:
        entries.append(
            f"  Provider {entry.provider} attempt {entry.attempt}: "
            f"waited={entry.waited:.1f}s error={entry.error}"
        )
    entries.append("  → Returning default ALLOW decision.")
    sys.stderr.write("\n".join(entries) + "\n")
