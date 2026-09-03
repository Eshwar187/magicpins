"""Pure timestamp parsing and delta calculation for ISO 8601 simulation strings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def parse_simulation_iso(iso_str: str) -> Optional[datetime]:
    """Parse an ISO 8601 simulation string into a timezone-aware UTC datetime.
    
    Zero wall-clock access. Returns None if unparseable.
    """
    if not iso_str or not isinstance(iso_str, str):
        return None
    try:
        clean = iso_str.strip()
        # Handle trailing Z
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def calculate_simulation_delta_seconds(now_iso: str, past_iso: str) -> Optional[float]:
    """Calculate elapsed seconds between two simulation timestamps: now - past.
    
    Returns None if either timestamp cannot be parsed.
    """
    t_now = parse_simulation_iso(now_iso)
    t_past = parse_simulation_iso(past_iso)
    if t_now is None or t_past is None:
        return None
    return (t_now - t_past).total_seconds()
