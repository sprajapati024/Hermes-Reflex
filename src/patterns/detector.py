"""Pattern detector for Hermes Reflex.

Given a user message, detects if it matches a known risk pattern.
Returns a list of matching patterns with evidence.
"""

from __future__ import annotations

from ..patterns.evidence import get_evidence_summary


# Risk type → related signal type mapping
RISK_TYPE_SIGNALS = {
    "planning_loop": "planning_loop",
    "ui_avoidance": "ui_avoidance",
    "project_switching": "project_switching",
    "integration_avoidance": "integration_avoidance",
    "overbuild_risk": "overbuild_risk",
    "contract_conflict": "contract_conflict",
    "experiment_conflict": "experiment_conflict",
}


def detect_patterns(
    risk_flags: list[str],
    confidence: float,
    matched_terms: list[str],
) -> list[dict]:
    """Return pattern candidates for detected risk flags.

    Args:
        risk_flags: list of risk type strings (e.g. ["ui_avoidance"])
        confidence: overall confidence score
        matched_terms: terms that triggered the risk

    Returns:
        list of pattern dicts with id, name, risk_type, evidence_count,
        promotion_ready, etc.
    """
    from ..gbrain.paths import get_patterns_root
    from ..gbrain.markdown import read_markdown

    results = []
    patterns_root = get_patterns_root()

    for status in ("active", "watching", "candidate"):
        status_dir = patterns_root / status
        if not status_dir.exists():
            continue
        for f in status_dir.glob("*.md"):
            try:
                data, _ = read_markdown(f)
                pattern_risk = data.get("risk_type", "")
                # Match if any risk_flag is in the pattern's risk_type
                if any(rf in pattern_risk for rf in risk_flags if rf):
                    evidence = get_evidence_summary(data.get("id", ""))
                    results.append(
                        {
                            "id": data.get("id", ""),
                            "name": data.get("name", ""),
                            "status": status,
                            "risk_type": pattern_risk,
                            "confidence": data.get("confidence", 0.0),
                            "evidence_count": evidence.get("signals_in_window", 0),
                            "intervention": data.get("intervention", ""),
                            "promotion_ready": evidence.get(
                                f"{status}_threshold_met", False
                            ),
                            "matched_terms": matched_terms,
                        }
                    )
            except Exception:
                continue

    return results
