"""Response mode instruction templates for Hermes Reflex.

Each mode maps to a short instruction string injected into Hermes's prompt.
These are the ONLY user-facing response specifications — nothing more.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Mode → Hermes instruction mapping
# ---------------------------------------------------------------------------

MODE_INSTRUCTIONS: dict[str, str] = {
    "ALLOW": (
        "Respond normally without mentioning Reflex."
    ),
    "NOTE": (
        "Help the user, but include one short, evidence-based caution based on "
        "Reflex findings. Keep it brief — one sentence max. Do not mention Reflex by name."
    ),
    "CHALLENGE": (
        "Do not immediately comply. First challenge the request using the Reflex "
        "evidence you have. State the concern directly. Then offer one concrete "
        "better action. Allow the user to override if they disagree."
    ),
    "CLARIFY": (
        "Ask one targeted clarification that would resolve the ambiguity, "
        "OR propose the safest constrained path forward. Do not answer the "
        "underlying request until the ambiguity is resolved."
    ),
    "REQUIRE_OVERRIDE": (
        "Do not proceed until the user explicitly overrides this decision. "
        "Explain the conflict clearly. State the recommended alternative. "
        "If the user replies 'override' or explains their reasoning, proceed."
    ),
    "SILENT_LOG": (
        "Respond normally. Do not mention Reflex. Log this for pattern tracking."
    ),
}


def get_hermes_instruction(mode: str) -> str:
    """Return the Hermes instruction string for a given mode.

    Args:
        mode: One of ALLOW, NOTE, CHALLENGE, CLARIFY, REQUIRE_OVERRIDE, SILENT_LOG.

    Returns:
        The instruction string. Empty string for unknown modes (safe default).
    """
    return MODE_INSTRUCTIONS.get(mode, "")
