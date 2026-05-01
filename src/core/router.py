"""Fast Reflex Router — preflight message classification.

Classifies a message using pre-computed rule/contract results to determine
which pipeline stages are worth running.

Routes:
  BYPASS  — Reflex command; skip entire pipeline (handled upstream)
  SAFE    — No risk detected; return ALLOW immediately
  RISKY   — Rule or contract match; run full pipeline
  UNCLEAR — (reserved) ambiguous; lightweight critic only
"""

from __future__ import annotations

from typing import Any


def route_message(
    user_message: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify the message before running expensive Reflex steps.

    Expects context to contain pre-computed evaluation results so the
    caller controls when rules/contracts are evaluated:
      rule_result:       dict from RuleResult.to_dict()
      contract_conflict: dict from ContractConflict.to_dict()

    Returns:
      route:              "SAFE" | "RISKY" | "UNCLEAR"
      reason:             str — short human-readable explanation
      matched_terms:      list[str]
      requires_retrieval: bool — True if embedding search should run
      requires_critic:    bool — True if LLM critic should run
      recommended_mode:   str — suggested Reflex mode
    """
    context = context or {}

    # --- Rule-based risk signals ----------------------------------------
    rule_result = context.get("rule_result") or {}
    risk_flags: list[str] = list(rule_result.get("risk_flags") or [])
    matched_terms: list[str] = list(rule_result.get("matched_terms") or [])
    recommended_mode: str = str(rule_result.get("recommended_mode") or "ALLOW")

    if risk_flags:
        return {
            "route": "RISKY",
            "reason": f"Rule match: {', '.join(risk_flags)}",
            "matched_terms": matched_terms,
            "requires_retrieval": True,
            "requires_critic": True,
            "recommended_mode": recommended_mode,
        }

    # --- Contract conflict -----------------------------------------------
    contract_conflict = context.get("contract_conflict") or {}
    if contract_conflict.get("conflict"):
        mode = str(contract_conflict.get("recommended_mode") or "REQUIRE_OVERRIDE")
        term = str(contract_conflict.get("matched_term") or "")
        return {
            "route": "RISKY",
            "reason": "Contract conflict detected",
            "matched_terms": [term] if term else [],
            "requires_retrieval": True,
            "requires_critic": True,
            "recommended_mode": mode,
        }

    # --- No risk signals — safe to respond immediately ------------------
    return {
        "route": "SAFE",
        "reason": "No risk detected",
        "matched_terms": [],
        "requires_retrieval": False,
        "requires_critic": False,
        "recommended_mode": "ALLOW",
    }
