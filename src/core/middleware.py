"""Reflex middleware — the central orchestrator for Hermes Reflex.

process_reflex() is the main entry point.  It runs an adaptive pipeline that
skips expensive stages for messages that carry no risk signal:

    1. Bypass check      — skip if message is a Reflex command
    2. Pause / enabled   — skip if Reflex is paused or disabled
    3. Rules check       — fast local regex risk detection
    4. Contract check    — operating contract conflict detection
    5. Route             — classify into SAFE / RISKY / UNCLEAR
    6. Decision cache    — return cached result if available (RISKY path)

    SAFE path (steps 7–10 skipped):
    7. Return ALLOW immediately

    RISKY / UNCLEAR path:
    7. Retrieval         — embed query, search evidence (conditional)
    8. Recent patterns   — load active patterns
    9. Critic call       — LLM JSON decision (with hard timeout)
   10. Mode select       — pick response mode; rules enforce if critic allows
   11. Instruction       — build Hermes instruction string
   12. GBrain log        — deferred write of decision + signal files
   13. Cache result      — store in decision cache

The function NEVER raises — all errors are caught and degraded to ALLOW.

New env vars:
  HERMES_REFLEX_CRITIC_TIMEOUT_MS        Critic hard timeout in ms (default 700)
  HERMES_REFLEX_CRITIC_ENABLED           Set to "false" to disable critic (default true)
  HERMES_REFLEX_DECISION_CACHE_TTL_SECONDS TTL for decision cache (default 300)
  HERMES_REFLEX_ASYNC_LOGGING            Set to "true" to defer GBrain writes (default false)
  HERMES_REFLEX_SKIP_RETRIEVAL           Set to "true" to skip embedding search globally
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import os
import queue
import threading
import time
from typing import Any, Optional

from .schemas import ReflexResult
from .response_modes import get_hermes_instruction

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Commands that bypass Reflex entirely (always ALLOW)
# ---------------------------------------------------------------------------

_ALLOW_ALWAYS_PREFIXES = (
    "/checkin",
    "/experiment",
    "/patterns",
    "/reflex",
    "/review",
    "/override",
)


def _is_reflex_command(user_message: str) -> bool:
    """Return True if this message is a Reflex command (bypass check)."""
    msg = user_message.strip().lower()
    return any(msg.startswith(p) for p in _ALLOW_ALWAYS_PREFIXES)


# ---------------------------------------------------------------------------
# Deferred GBrain logging
# ---------------------------------------------------------------------------

_log_queue: queue.SimpleQueue = queue.SimpleQueue()


def _log_worker() -> None:
    while True:
        try:
            task = _log_queue.get()
            if task is None:
                return
            task()
        except Exception as exc:
            log.warning("[Reflex] deferred log task failed: %s", exc)


_log_thread = threading.Thread(target=_log_worker, daemon=True, name="reflex-log-worker")
_log_thread.start()


def log_decision_deferred(fn) -> None:
    """Queue a GBrain write without blocking the response path.

    When HERMES_REFLEX_ASYNC_LOGGING is false (the default) the function runs
    synchronously so existing tests and single-process deployments see writes
    immediately.  Set it to "true" to push writes to the background thread.
    """
    try:
        if _env_truthy("HERMES_REFLEX_ASYNC_LOGGING"):
            _log_queue.put_nowait(fn)
        else:
            fn()
    except Exception as exc:
        log.warning("[Reflex] deferred log enqueue failed: %s", exc)


# ---------------------------------------------------------------------------
# Decision cache
# ---------------------------------------------------------------------------

_decision_cache: dict[str, tuple[float, ReflexResult]] = {}
_cache_lock = threading.Lock()


def _make_cache_key(
    user_message: str,
    contract_hash: str,
    experiment_ids: list[str],
) -> str:
    normalised = " ".join(user_message.strip().lower().split())
    exp_str = ",".join(sorted(str(e) for e in experiment_ids))
    raw = f"{normalised}|{contract_hash}|{exp_str}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str) -> Optional[ReflexResult]:
    with _cache_lock:
        entry = _decision_cache.get(key)
    if entry is None:
        return None
    expiry, result = entry
    if time.monotonic() > expiry:
        with _cache_lock:
            _decision_cache.pop(key, None)
        return None
    return result


def _set_cached(key: str, result: ReflexResult, ttl: int) -> None:
    if result.mode == "REQUIRE_OVERRIDE":
        return
    expiry = time.monotonic() + ttl
    with _cache_lock:
        _decision_cache[key] = (expiry, result)


# ---------------------------------------------------------------------------
# Critic with hard timeout
# ---------------------------------------------------------------------------

def _call_critic_timed(
    *,
    user_message: str,
    rule_result: dict,
    contract_conflict: dict,
    active_experiments: list,
    retrieved_evidence: list,
    recent_patterns: list,
    timeout_ms: int,
):
    """Call the critic LLM with a hard timeout.

    Returns the CriticDecision on success, None on timeout or failure.
    On timeout, the background thread is abandoned (it will finish eventually)
    rather than waited on, so this function returns within timeout_ms + overhead.
    """
    from ..critic import critic

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        critic,
        user_message=user_message,
        rule_result=rule_result,
        contract_conflict=contract_conflict,
        active_experiments=active_experiments,
        retrieved_evidence=retrieved_evidence,
        recent_patterns=recent_patterns,
    )
    # Shut down the executor without waiting so we can enforce the timeout.
    # The submitted thread may still be running after shutdown(wait=False).
    executor.shutdown(wait=False)
    try:
        return future.result(timeout=timeout_ms / 1000.0)
    except concurrent.futures.TimeoutError:
        log.warning("[Reflex] critic timed out after %d ms — using rule fallback", timeout_ms)
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_reflex(
    user_message: str,
    *,
    project: Optional[str] = None,
    include_reflex_instructions: bool = True,
    enabled: Optional[bool] = None,
    skip_retrieval: bool = False,
    skip_critic: bool = False,
) -> ReflexResult:
    """Process one user message through the Reflex adaptive pipeline.

    Args:
        user_message: The raw Telegram message text.
        project: Optional project name to scope evidence retrieval.
        include_reflex_instructions: If False, omits hermes_instruction.
        enabled: If False, returns ALLOW immediately.
        skip_retrieval: Skip the embedding retrieval step (testing/override).
        skip_critic: Skip the critic LLM call (testing/override).

    Returns:
        ReflexResult — NEVER None, all errors degrade to ALLOW.
    """
    # -----------------------------------------------------------------------
    # 0. Bypass check — Reflex commands skip the entire pipeline
    # -----------------------------------------------------------------------
    if _is_reflex_command(user_message):
        return _build_allow_result(
            reason="Reflex command — bypassed",
            include_reflex_instructions=include_reflex_instructions,
        )

    # -----------------------------------------------------------------------
    # 1. Enabled / pause check
    # -----------------------------------------------------------------------
    enabled = enabled if enabled is not None else True
    if not enabled:
        return _build_allow_result(
            reason="Reflex disabled",
            include_reflex_instructions=include_reflex_instructions,
        )

    try:
        from .pause import is_paused
        if is_paused():
            return _build_allow_result(
                reason="Reflex paused",
                include_reflex_instructions=include_reflex_instructions,
            )
    except Exception as exc:
        log.warning("[Reflex] pause check failed: %s", exc)

    # -----------------------------------------------------------------------
    # 2. Fast local checks (rules + contract) — no external calls
    # -----------------------------------------------------------------------
    rule_result: dict[str, Any] = {}
    contract_conflict: dict[str, Any] = {}
    experiments: list[dict] = []

    try:
        from .rule_engine import evaluate_rules
        from .operating_contract import load_contract
        from ..gbrain.storage import read_active_experiments

        contract = load_contract()
        experiments = read_active_experiments()
        context: dict[str, Any] = {
            "operating_contract": contract.to_dict(),
            "active_experiments": [e.get("name", "") for e in experiments],
        }
        result = evaluate_rules(user_message, context=context)
        rule_result = result.to_dict()
    except Exception as exc:
        log.warning("[Reflex] rule engine failed: %s", exc)
        rule_result = {
            "risk_flags": [],
            "confidence": 0.0,
            "recommended_mode": "ALLOW",
            "matched_terms": [],
        }

    try:
        from .operating_contract import check_contract_conflict
        conflict = check_contract_conflict(user_message)
        contract_conflict = conflict.to_dict()
    except Exception as exc:
        log.warning("[Reflex] contract check failed: %s", exc)
        contract_conflict = {"conflict": False}

    # -----------------------------------------------------------------------
    # 3. Route — classify into SAFE / RISKY / UNCLEAR
    # -----------------------------------------------------------------------
    from .router import route_message

    route_info = route_message(
        user_message,
        context={
            "rule_result": rule_result,
            "contract_conflict": contract_conflict,
        },
    )
    route = route_info["route"]

    # -----------------------------------------------------------------------
    # 4. SAFE fast path — return immediately, skip retrieval / critic / logging
    # -----------------------------------------------------------------------
    if route == "SAFE":
        return _build_allow_result(
            reason="Fast path: no risk detected",
            include_reflex_instructions=include_reflex_instructions,
        )

    # -----------------------------------------------------------------------
    # 5. Decision cache (RISKY / UNCLEAR only)
    # -----------------------------------------------------------------------
    cache_ttl = int(os.environ.get("HERMES_REFLEX_DECISION_CACHE_TTL_SECONDS", "300"))
    contract_hash = hashlib.md5(str(contract_conflict).encode()).hexdigest()[:8]
    experiment_ids = [str(e.get("name", "")) for e in experiments]
    cache_key = _make_cache_key(user_message, contract_hash, experiment_ids)

    cached = _get_cached(cache_key)
    if cached is not None:
        log.debug("[Reflex] decision cache hit for message fingerprint")
        return cached

    # -----------------------------------------------------------------------
    # 6. Retrieval — only for RISKY / UNCLEAR paths
    # -----------------------------------------------------------------------
    retrieved_evidence: list[dict[str, Any]] = []
    skip_retrieval = skip_retrieval or _env_truthy("HERMES_REFLEX_SKIP_RETRIEVAL")

    if route_info.get("requires_retrieval") and not skip_retrieval:
        try:
            from ..embeddings.search import search_reflex_memory
            from .config import load_config

            cfg = load_config()
            top_k = cfg.get("retrieval", {}).get("top_k", 8)
            min_score = cfg.get("retrieval", {}).get("min_score", 0.65)

            evidence = search_reflex_memory(
                query=user_message,
                top_k=top_k,
                min_score=min_score,
            )
            retrieved_evidence = [
                {
                    "id": e.get("id", ""),
                    "path": e.get("path", ""),
                    "type": e.get("type", "unknown"),
                    "summary": e.get("summary", ""),
                    "score": float(e.get("score", 0.0)),
                    "title": e.get("title", ""),
                }
                for e in evidence
            ]
        except Exception as exc:
            log.warning("[Reflex] retrieval failed: %s", exc)

    # -----------------------------------------------------------------------
    # 7. Recent patterns
    # -----------------------------------------------------------------------
    recent_patterns: list[dict[str, Any]] = []
    try:
        from ..gbrain.storage import read_active_patterns
        recent_patterns = read_active_patterns()
    except Exception as exc:
        log.warning("[Reflex] patterns load failed: %s", exc)

    # -----------------------------------------------------------------------
    # 8. Critic call — with hard timeout and deterministic fallback
    # -----------------------------------------------------------------------
    critic_mode = "ALLOW"
    critic_risk_type = "none"
    critic_confidence = 0.0
    critic_severity = "low"
    critic_reason = ""
    critic_action = ""
    allow_override = True
    mode_raw: dict[str, Any] = {}

    critic_enabled = not skip_critic and _env_truthy_default(
        "HERMES_REFLEX_CRITIC_ENABLED", default=True
    )
    timeout_ms = int(os.environ.get("HERMES_REFLEX_CRITIC_TIMEOUT_MS", "700"))

    if critic_enabled and route_info.get("requires_critic"):
        try:
            active_experiments: list[dict] = []
            try:
                from ..gbrain.storage import read_active_experiments
                active_experiments = read_active_experiments()
            except Exception:
                active_experiments = experiments  # reuse what we already loaded

            decision = _call_critic_timed(
                user_message=user_message,
                rule_result=rule_result,
                contract_conflict=contract_conflict,
                active_experiments=active_experiments,
                retrieved_evidence=retrieved_evidence,
                recent_patterns=recent_patterns,
                timeout_ms=timeout_ms,
            )

            if decision is not None:
                critic_mode = decision.mode
                critic_risk_type = decision.risk_type
                critic_confidence = decision.confidence
                critic_severity = decision.severity
                critic_reason = decision.reason
                critic_action = decision.recommended_action
                allow_override = decision.allow_override
                mode_raw = decision.to_dict()
            else:
                critic_reason = f"Critic timed out ({timeout_ms} ms) — rule fallback applied."

        except Exception as exc:
            log.warning("[Reflex] critic call failed: %s", exc)
            critic_reason = "Critic unavailable — defaulting to ALLOW."

    # -----------------------------------------------------------------------
    # 9. Select mode — rules enforce when critic is permissive (fail-secure)
    # -----------------------------------------------------------------------
    rule_mode = str(rule_result.get("recommended_mode") or "ALLOW")
    rule_flags = list(rule_result.get("risk_flags") or [])
    if critic_mode == "ALLOW" and rule_mode not in ("", "ALLOW") and rule_flags:
        critic_mode = rule_mode
        critic_risk_type = str(rule_flags[0])
        critic_confidence = max(
            critic_confidence,
            float(rule_result.get("confidence", 0.65) or 0.65),
        )
        critic_severity = "high" if rule_mode == "REQUIRE_OVERRIDE" else "medium"
        matched_terms = ", ".join(str(t) for t in rule_result.get("matched_terms", []) if t)
        critic_reason = (
            f"Local Reflex rule matched {critic_risk_type}"
            + (f" via {matched_terms}." if matched_terms else ".")
            + (f" {critic_reason}" if critic_reason else "")
        )
        critic_action = critic_action or "Pause and check alignment before proceeding."
        allow_override = rule_mode != "REQUIRE_OVERRIDE"

    # Contract REQUIRE_OVERRIDE always takes precedence
    if (
        contract_conflict.get("conflict")
        and contract_conflict.get("recommended_mode") == "REQUIRE_OVERRIDE"
    ):
        critic_mode = "REQUIRE_OVERRIDE"
        critic_risk_type = "contract_conflict"
        critic_confidence = max(critic_confidence, contract_conflict.get("confidence", 0.85))
        critic_reason = (
            str(contract_conflict.get("constraint", "Contract conflict")) + ". " + critic_reason
        )
        allow_override = True

    mode = critic_mode

    # -----------------------------------------------------------------------
    # 10. Build Hermes instruction
    # -----------------------------------------------------------------------
    hermes_instruction = ""
    if include_reflex_instructions:
        hermes_instruction = get_hermes_instruction(mode)
        if critic_action and mode in ("CHALLENGE", "REQUIRE_OVERRIDE", "NOTE", "CLARIFY"):
            hermes_instruction += f" [{critic_action}]"

    # -----------------------------------------------------------------------
    # 11. GBrain logging (deferred / non-blocking)
    # -----------------------------------------------------------------------
    from datetime import datetime

    dt = datetime.now()
    decision_id = f"decision_{dt.strftime('%Y%m%d')}_{id(user_message) % 1000000:06d}"

    _evidence_ids = [e.get("id", "") for e in retrieved_evidence]
    _rule_result_snap = rule_result
    _contract_snap = contract_conflict
    _evidence_snap = retrieved_evidence
    _project = project

    def _write_gbrain():
        try:
            from ..gbrain.storage import write_decision, write_signal

            try:
                write_decision(
                    mode=mode,
                    risk_type=critic_risk_type,
                    confidence=critic_confidence,
                    severity=critic_severity,
                    evidence_ids=_evidence_ids,
                    reason=critic_reason,
                    recommended_action=critic_action,
                    allow_override=allow_override,
                    user_message=user_message,
                    rule_result=_rule_result_snap,
                    contract_conflict=_contract_snap,
                    retrieved_evidence=_evidence_snap,
                    dt=dt,
                )
            except Exception as exc:
                log.warning("[Reflex] write_decision failed: %s", exc)

            if mode not in ("ALLOW", "SILENT_LOG"):
                try:
                    write_signal(
                        signal_type=mode,
                        source="telegram",
                        project=_project,
                        confidence=critic_confidence,
                        severity=critic_severity,
                        evidence=critic_reason,
                        risk_type=critic_risk_type,
                        decision_id=decision_id,
                        dt=dt,
                    )
                except Exception as exc:
                    log.warning("[Reflex] write_signal failed: %s", exc)
        except Exception as exc:
            log.warning("[Reflex] GBrain logging failed: %s", exc)

    log_decision_deferred(_write_gbrain)

    # -----------------------------------------------------------------------
    # 12. Build result and cache it
    # -----------------------------------------------------------------------
    final_result = ReflexResult(
        mode=mode,
        risk_type=critic_risk_type,
        confidence=critic_confidence,
        severity=critic_severity,
        hermes_instruction=hermes_instruction,
        evidence=retrieved_evidence,
        decision_id=decision_id,
        mode_raw=mode_raw,
    )

    _set_cached(cache_key, final_result, cache_ttl)

    return final_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env_truthy(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _env_truthy_default(name: str, *, default: bool) -> bool:
    """Like _env_truthy but with an explicit default for unset variables."""
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _build_allow_result(
    reason: str,
    include_reflex_instructions: bool = True,
) -> ReflexResult:
    """Return a clean ALLOW result for bypass/pause/safe/error cases."""
    instruction = ""
    if include_reflex_instructions:
        instruction = get_hermes_instruction("ALLOW")
    return ReflexResult(
        mode="ALLOW",
        risk_type="none",
        confidence=0.0,
        severity="low",
        hermes_instruction=instruction,
        evidence=[],
        decision_id=None,
        mode_raw={"reason": reason},
    )
