"""Reflex middleware — the central orchestrator for Hermes Reflex.

process_reflex() is the main entry point. It runs this pipeline for every
meaningful user message:

    1. Pause check     — skip if interventions are paused
    2. Rules check     — fast regex risk detection
    3. Contract check  — operating contract conflict detection
    4. Retrieval       — embed query, search evidence
    5. Critic call     — LLM JSON decision
    6. Mode select     — pick response mode
    7. Instruction     — build Hermes instruction
    8. GBrain log      — write decision + signal files

The function NEVER raises — all errors are caught and degraded to ALLOW.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from .schemas import ReflexResult
from .response_modes import get_hermes_instruction

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Commands that bypass Reflex entirely (always ALLOW)
# ---------------------------------------------------------------------------

_REFLEX_COMMANDS = {
    "/checkin",
    "/experiment",
    "/patterns",
    "/reflex",
    "/review",
    "/override",
    "/reflex_pause",
}
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
    """Process one user message through the full Reflex pipeline.

    Args:
        user_message: The raw Telegram message text.
        project: Optional project name to scope evidence retrieval.
        include_reflex_instructions: If False, omits hermes_instruction from result.
        enabled: If False, returns ALLOW immediately. Defaults to True.
        skip_retrieval: Testing aid — skip the embedding retrieval step.
        skip_critic: Testing aid — skip the critic LLM call.

    Returns:
        ReflexResult with mode, evidence, hermes_instruction, and decision_id.
        NEVER returns None — all errors degrade to ALLOW.
    """
    # -----------------------------------------------------------------------
    # 0. Bypass check
    # -----------------------------------------------------------------------
    if _is_reflex_command(user_message):
        return _build_allow_result(
            reason="Reflex command — bypassed",
            include_reflex_instructions=include_reflex_instructions,
        )

    # -----------------------------------------------------------------------
    # 1. Pause check
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
    # 2. Rules check
    # -----------------------------------------------------------------------
    rule_result: dict[str, Any] = {}
    try:
        from .rule_engine import evaluate_rules
        from .operating_contract import load_contract

        contract = load_contract()
        context: dict[str, Any] = {"operating_contract": contract.to_dict()}

        # Load active experiments for rule engine
        from ..gbrain.storage import read_active_experiments
        experiments = read_active_experiments()
        context["active_experiments"] = [e.get("name", "") for e in experiments]

        result = evaluate_rules(user_message, context=context)
        rule_result = result.to_dict()
    except Exception as exc:
        log.warning("[Reflex] rule engine failed: %s", exc)
        rule_result = {"risk_flags": [], "confidence": 0.0, "recommended_mode": "ALLOW", "matched_terms": []}

    # -----------------------------------------------------------------------
    # 3. Contract conflict check
    # -----------------------------------------------------------------------
    contract_conflict: dict[str, Any] = {}
    try:
        from .operating_contract import check_contract_conflict, load_contract
        conflict = check_contract_conflict(user_message)
        contract_conflict = conflict.to_dict()
    except Exception as exc:
        log.warning("[Reflex] contract check failed: %s", exc)
        contract_conflict = {"conflict": False}

    # -----------------------------------------------------------------------
    # 4. Embedding retrieval
    # -----------------------------------------------------------------------
    retrieved_evidence: list[dict[str, Any]] = []
    skip_retrieval = skip_retrieval or _env_truthy("HERMES_REFLEX_SKIP_RETRIEVAL")
    if not skip_retrieval:
        try:
            from ..embeddings.search import search_reflex_memory, retrieve_for_context
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
            retrieved_evidence = []

    # -----------------------------------------------------------------------
    # 5. Recent patterns
    # -----------------------------------------------------------------------
    recent_patterns: list[dict[str, Any]] = []
    try:
        from ..gbrain.storage import read_active_patterns
        recent_patterns = read_active_patterns()
    except Exception as exc:
        log.warning("[Reflex] patterns load failed: %s", exc)

    # -----------------------------------------------------------------------
    # 6. Critic call
    # -----------------------------------------------------------------------
    decision_id: Optional[str] = None
    critic_mode = "ALLOW"
    critic_risk_type = "none"
    critic_confidence = 0.0
    critic_severity = "low"
    critic_reason = ""
    critic_action = ""
    allow_override = True
    mode_raw: dict[str, Any] = {}

    if not skip_critic:
        try:
            from ..critic import critic
            from ..critic.decision import CriticDecision

            # Build active experiments as list of dicts for critic
            active_experiments = []
            try:
                from ..gbrain.storage import read_active_experiments
                active_experiments = read_active_experiments()
            except Exception:
                pass

            decision: CriticDecision = critic(
                user_message=user_message,
                rule_result=rule_result,
                contract_conflict=contract_conflict,
                active_experiments=active_experiments,
                retrieved_evidence=retrieved_evidence,
                recent_patterns=recent_patterns,
            )

            critic_mode = decision.mode
            critic_risk_type = decision.risk_type
            critic_confidence = decision.confidence
            critic_severity = decision.severity
            critic_reason = decision.reason
            critic_action = decision.recommended_action
            allow_override = decision.allow_override
            mode_raw = decision.to_dict()

        except Exception as exc:
            log.warning("[Reflex] critic call failed: %s", exc)
            critic_reason = "Critic unavailable — defaulting to ALLOW."
            # Fall through with ALLOW defaults

    # -----------------------------------------------------------------------
    # 7. Select mode
    # -----------------------------------------------------------------------
    # Deterministic fallback: if the critic is unavailable or permissive but the
    # fast rule engine found a concrete risk, do not fail open. The LLM critic
    # may raise, time out, or return its default ALLOW when credentials are
    # missing; rules and contract checks are local and should still enforce.
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

    # Override: if contract is directly violated, REQUIRE_OVERRIDE takes precedence
    if contract_conflict.get("conflict") and contract_conflict.get("recommended_mode") == "REQUIRE_OVERRIDE":
        critic_mode = "REQUIRE_OVERRIDE"
        critic_risk_type = "contract_conflict"
        critic_confidence = max(critic_confidence, contract_conflict.get("confidence", 0.85))
        critic_reason = contract_conflict.get("constraint", "Contract conflict") + ". " + critic_reason
        allow_override = True  # Always allow override even for contract conflicts

    mode = critic_mode

    # -----------------------------------------------------------------------
    # 8. Build Hermes instruction
    # -----------------------------------------------------------------------
    hermes_instruction = ""
    if include_reflex_instructions:
        hermes_instruction = get_hermes_instruction(mode)
        if critic_action and mode in ("CHALLENGE", "REQUIRE_OVERRIDE", "NOTE", "CLARIFY"):
            hermes_instruction += f" [{critic_action}]"

    # -----------------------------------------------------------------------
    # 9. Log to GBrain
    # -----------------------------------------------------------------------
    try:
        from ..gbrain.storage import write_decision, write_signal
        from datetime import datetime

        dt = datetime.now()

        # Write decision
        decision_id = f"decision_{dt.strftime('%Y%m%d')}_{id(user_message) % 1000000:06d}"

        try:
            write_decision(
                mode=mode,
                risk_type=critic_risk_type,
                confidence=critic_confidence,
                severity=critic_severity,
                evidence_ids=[e.get("id", "") for e in retrieved_evidence],
                reason=critic_reason,
                recommended_action=critic_action,
                allow_override=allow_override,
                user_message=user_message,
                rule_result=rule_result,
                contract_conflict=contract_conflict,
                retrieved_evidence=retrieved_evidence,
                dt=dt,
            )
        except Exception as exc:
            log.warning("[Reflex] write_decision failed: %s", exc)

        # Write signal if not ALLOW/SILENT_LOG
        if mode not in ("ALLOW", "SILENT_LOG"):
            try:
                write_signal(
                    signal_type=mode,
                    source="telegram",
                    project=project,
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

    # -----------------------------------------------------------------------
    # 10. Return result
    # -----------------------------------------------------------------------
    return ReflexResult(
        mode=mode,
        risk_type=critic_risk_type,
        confidence=critic_confidence,
        severity=critic_severity,
        hermes_instruction=hermes_instruction,
        evidence=retrieved_evidence,
        decision_id=decision_id,
        mode_raw=mode_raw,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env_truthy(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _build_allow_result(
    reason: str,
    include_reflex_instructions: bool = True,
) -> ReflexResult:
    """Return a clean ALLOW result for bypass/pause/error cases."""
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
