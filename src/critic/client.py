"""OpenAI client wrapper for the Hermes Reflex critic.

This module provides the `critic()` function — the main public API for calling
the LLM critic layer. It:
1. Assembles the prompt from critic/prompt.py
2. Calls the configured cheap model via the OpenAI SDK
3. Parses the JSON response using critic/parser.py
4. Retries on transient failures (up to 3 attempts)
5. Returns a CriticDecision (never None — falls back to default_allow on error)

Environment variables:
  OPENAI_API_KEY          — required
  HERMES_REFLEX_CRITIC_MODEL — model name, default "gpt-4o-mini"
  HERMES_REFLEX_MAX_TOKENS   — max tokens, default 512
  HERMES_REFLEX_TEMPERATURE  — temperature, default 0.1
"""

from __future__ import annotations

import os
import time
import typing as t
from dataclasses import dataclass
from functools import lru_cache

import openai

from . import prompt as prompt_module
from .decision import CriticDecision
from .parser import ParseError, parse_critic_response


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CRITIC_MODEL = os.environ.get(
    "HERMES_REFLEX_CRITIC_MODEL", "gpt-4o-mini"
)
_MAX_TOKENS = int(os.environ.get("HERMES_REFLEX_MAX_TOKENS", "512"))
_TEMPERATURE = float(os.environ.get("HERMES_REFLEX_TEMPERATURE", "0.1"))
_MAX_RETRIES = 3
_RETRY_DELAY_BASE = 1.0  # seconds


# ---------------------------------------------------------------------------
# OpenAI client (lazy singleton)
# ---------------------------------------------------------------------------

@dataclass
class _RetryLog:
    attempt: int
    waited: float
    error: str


@lru_cache(maxsize=1)
def _get_client() -> openai.OpenAI:
    """Return a cached OpenAI client instance (lazy init)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is not set. "
            "The critic layer requires a valid OpenAI API key."
        )
    return openai.OpenAI(api_key=api_key)


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
    """Call the LLM critic and return a validated CriticDecision.

    This is the main entry point for the critic layer.

    Args:
        user_message: The raw user message being classified.
        rule_result: Output from the rule engine (dict).
        contract_conflict: Output from check_contract_conflict() (dict).
        active_experiments: List of active experiment dicts.
        retrieved_evidence: List of evidence dicts from embedding search.
        recent_patterns: List of recently active pattern dicts.
        model: Override the default critic model.
        max_retries: Override the default max retry count.

    Returns:
        A CriticDecision instance. Never returns None — on all failures
        returns CriticDecision.default_allow() so the pipeline can continue.
    """
    model = model or _CRITIC_MODEL
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

    for attempt in range(1, max_retries + 1):
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=_TEMPERATURE,
                max_tokens=_MAX_TOKENS,
                response_format={"type": "json_object"},
            )

            raw_text = response.choices[0].message.content or ""
            return parse_critic_response(raw_text)

        except (openai.RateLimitError, openai.APIConnectionError) as exc:
            waited = _RETRY_DELAY_BASE * (2 ** (attempt - 1))
            retry_log.append(_RetryLog(attempt=attempt, waited=waited, error=str(exc)))
            if attempt < max_retries:
                time.sleep(waited)
            continue

        except ParseError as exc:
            # Bad JSON from model — worth one retry with a clarifying nudge
            retry_log.append(_RetryLog(attempt=attempt, waited=0, error=f"ParseError: {exc}"))
            if attempt < max_retries:
                # Add a developer hint into the next attempt
                messages.append({
                    "role": "developer",
                    "content": "Reminder: respond with JSON only. Do not add prose outside the JSON block.",
                })
            continue

        except Exception as exc:
            # Unexpected error — log and bail (don't retry unknown exceptions)
            retry_log.append(_RetryLog(attempt=attempt, waited=0, error=str(exc)))
            break

    # All retries exhausted
    _log_critic_failure(
        user_message=user_message,
        model=model,
        retry_log=retry_log,
    )
    return CriticDecision.default_allow()


def _log_critic_failure(
    user_message: str,
    model: str,
    retry_log: list[_RetryLog],
) -> None:
    """Log critic failures for debugging (writes to stderr)."""
    import sys

    entries = [
        f"[Hermes Reflex critic] FAILURE on '{user_message[:80]}' using {model}",
    ]
    for entry in retry_log:
        entries.append(
            f"  Attempt {entry.attempt}: waited={entry.waited:.1f}s error={entry.error}"
        )
    entries.append("  → Returning default ALLOW decision.")
    sys.stderr.write("\n".join(entries) + "\n")
