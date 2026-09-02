"""Decision trace formatter for human-readable audit inspection."""

from __future__ import annotations

from app.engine.decision import DecisionTrace


def format_decision_trace(trace: DecisionTrace) -> str:
    """Renders a clean, human-readable trace of the decision process.
    
    Shows: Trigger, Fired Signals, Evaluated Candidates, Winner, and Rationale.
    """
    lines = ["=== VERA DECISION TRACE ===", ""]
    lines.append(f"Trigger: {trace.trigger_kind} (id: {trace.trigger_id})")
    lines.append("")

    lines.append("Signals Fired:")
    if trace.derived_signals:
        for s in trace.derived_signals:
            lines.append(f"  - {s}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("Candidates Evaluated:")
    for c in trace.candidate_evaluations:
        status_str = f"{c.total_score:.1f} pts" if c.is_eligible else f"INELIGIBLE ({', '.join(c.ineligibility_reasons)})"
        lines.append(f"  - {c.action_type.value:25} [{c.priority_tier.name:22}]: {status_str}")
    lines.append("")

    lines.append(f"Winner: {trace.winning_action}")
    if trace.tie_break_applied:
        lines.append(f"Tie-Break: {trace.tie_break_applied}")
    lines.append("")

    return "\n".join(lines).strip()
