"""Normalized trigger domain models matching dataset/triggers_seed.json."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class TriggerState(BaseModel):
    """Normalized trigger event state."""
    model_config = ConfigDict(extra="allow")

    id: str
    scope: str
    kind: str
    source: str
    merchant_id: str
    customer_id: Optional[str] = None
    payload: dict[str, Any]
    urgency: int
    suppression_key: str
    expires_at: Optional[str] = None

    # Demonstrated convenience accessors (read directly from payload without inventing new schema)
    @property
    def top_item_id(self) -> Optional[str]:
        return self.payload.get("top_item_id")

    @property
    def metric(self) -> Optional[str]:
        return self.payload.get("metric")

    @property
    def delta_pct(self) -> Optional[float]:
        val = self.payload.get("delta_pct")
        return float(val) if val is not None else None

    @property
    def window(self) -> Optional[str]:
        return self.payload.get("window")

    @property
    def service_due(self) -> Optional[str]:
        return self.payload.get("service_due")

    @property
    def available_slots(self) -> Optional[list[dict[str, Any]]]:
        return self.payload.get("available_slots")

    @property
    def days_remaining(self) -> Optional[int]:
        val = self.payload.get("days_remaining")
        return int(val) if val is not None else None

    @property
    def plan(self) -> Optional[str]:
        return self.payload.get("plan")

    @property
    def match(self) -> Optional[str]:
        return self.payload.get("match")

    @property
    def venue(self) -> Optional[str]:
        return self.payload.get("venue")

    @property
    def affected_batches(self) -> Optional[list[str]]:
        return self.payload.get("affected_batches")

    @property
    def molecule(self) -> Optional[str]:
        return self.payload.get("molecule")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TriggerState:
        """Create a TriggerState from a raw dictionary."""
        return cls.model_validate(data)
