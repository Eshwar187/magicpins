"""Debug and testing utility to format a grounded fact inventory."""

from __future__ import annotations

from typing import List

from app.domain.facts.fact import Fact


def format_fact_inventory(facts: List[Fact]) -> str:
    """Renders a clean, human-readable grounded fact inventory with exact provenance.
    
    Used for debugging fact groundings and verifying context fidelity.
    """
    lines: List[str] = ["GROUNDED FACTS", ""]
    for idx, f in enumerate(facts, start=1):
        lines.append(f"{idx}. {f.name} = {f.value}")
        lines.append(f"   type: {f.fact_type}")
        lines.append(
            f"   source: {f.source_scope}:{f.source_context_id} (v{f.source_version}) -> {f.source_path}"
        )
        lines.append(f"   fact_id: {f.fact_id[:16]}...")
        lines.append("")
    return "\n".join(lines).strip()
