"""Critic prompt definitions for Hermes Reflex.

This module provides:
- SYSTEM_PROMPT: the critic's operating instructions
- build_user_message(): assembles the critic input context
"""

SYSTEM_PROMPT = """You are the Hermes Reflex critic — a fast, evidence-based decision layer.

You do NOT write final responses. You only classify and recommend.

Output rules:
1. Respond with JSON only. No prose, no explanation outside the JSON structure.
2. Pick exactly one mode from: ALLOW, NOTE, CHALLENGE, CLARIFY, REQUIRE_OVERRIDE, SILENT_LOG.
3. confidence is a float between 0.0 and 1.0.
4. risk_type must be one of: none, planning_loop, ui_avoidance, project_switching, integration_avoidance, overbuild_risk, contract_conflict, other.
5. severity must be one of: low, medium, high.
6. evidence_ids is a list of string IDs from the retrieved evidence.
7. reason is a short, factual explanation (1-2 sentences max).
8. recommended_action is ONE concrete next action (imperative mood, e.g. "Ship /patterns first").
9. allow_override is a boolean. Never lie — if the contract or experiment is clearly violated, set this to false.

Decision rules:
- If no risk detected → ALLOW
- If minor risk with weak evidence → NOTE
- If moderate risk with some evidence → CHALLENGE
- If request is ambiguous → CLARIFY
- If request directly violates active contract or experiment → REQUIRE_OVERRIDE (allow_override=false)
- If useful signal but no user-facing action needed → SILENT_LOG

Evidence rule: Prefer lower severity when evidence is weak or contradictory.
Override rule: REQUIRE_OVERRIDE only when contract/experiment is clearly violated."""


def build_user_message(
    user_message: str,
    rule_result: dict,
    contract_conflict: dict,
    active_experiments: list[dict],
    retrieved_evidence: list[dict],
    recent_patterns: list[dict],
) -> str:
    """Build the user message content for the critic.

    Args:
        user_message: The raw user message being classified.
        rule_result: Output from the rule engine.
        contract_conflict: Output from check_contract_conflict().
        active_experiments: List of active experiment dicts with name/status.
        retrieved_evidence: List of evidence dicts from embedding search.
        recent_patterns: List of recently active pattern dicts.

    Returns:
        A formatted string summarising the context for the critic model.
    """
    lines = [
        f"User message: {user_message!r}",
        "",
    ]

    # Rule engine result
    if rule_result.get("risk_flags"):
        lines.append(f"Rule flags: {', '.join(rule_result['risk_flags'])}")
        lines.append(f"Rule confidence: {rule_result.get('confidence', 0.0)}")
        lines.append(f"Rule recommended mode: {rule_result.get('recommended_mode', 'ALLOW')}")
        matched = rule_result.get("matched_terms", [])
        if matched:
            lines.append(f"Rule matched terms: {', '.join(matched)}")
        lines.append("")

    # Contract conflict
    if contract_conflict.get("conflict"):
        lines.append(
            f"CONTRACT CONFLICT: {contract_conflict['constraint']} "
            f"(confidence={contract_conflict.get('confidence', 0.0)})"
        )
        lines.append("")

    # Active experiments
    if active_experiments:
        names = [e.get("name", "?") for e in active_experiments]
        lines.append(f"Active experiments: {', '.join(names)}")
        lines.append("")

    # Retrieved evidence
    if retrieved_evidence:
        lines.append("Retrieved evidence:")
        for ev in retrieved_evidence:
            lines.append(
                f"  [{ev.get('id', '?')}] ({ev.get('type', '?')}) "
                f"score={ev.get('score', 0.0):.2f} — {ev.get('summary', '')[:120]}"
            )
        lines.append("")

    # Recent patterns
    if recent_patterns:
        names = [p.get("name", "?") for p in recent_patterns]
        lines.append(f"Recent patterns: {', '.join(names)}")
        lines.append("")

    return "\n".join(lines)
