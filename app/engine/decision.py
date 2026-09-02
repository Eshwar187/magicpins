"""Typed, immutable decision representation and audit trace models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.domain.facts.fact import Fact
from app.engine.actions import ActionType, PriorityTier


@dataclass(frozen=True)
class CandidateEvaluation:
    """Detailed scoring and eligibility audit record for a single candidate."""
    action_type: ActionType
    target_scope: str
    is_eligible: bool
    ineligibility_reasons: Tuple[str, ...]
    priority_tier: PriorityTier
    total_score: float
    score_breakdown: Dict[str, float]
    supporting_evidence_count: int
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action_type.value,
            "target_scope": self.target_scope,
            "is_eligible": self.is_eligible,
            "ineligibility_reasons": list(self.ineligibility_reasons),
            "priority_tier": self.priority_tier.name,
            "total_score": round(self.total_score, 2),
            "score_breakdown": {k: round(v, 2) for k, v in self.score_breakdown.items()},
            "supporting_evidence_count": self.supporting_evidence_count,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class DecisionTrace:
    """Deterministic audit trace of signal extraction, candidate evaluation, and winner selection."""
    trigger_kind: str
    trigger_id: str
    derived_signals: Tuple[str, ...]
    candidate_evaluations: Tuple[CandidateEvaluation, ...]
    winning_action: str
    tie_break_applied: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_kind": self.trigger_kind,
            "trigger_id": self.trigger_id,
            "derived_signals": list(self.derived_signals),
            "candidates": [c.to_dict() for c in self.candidate_evaluations],
            "winning_action": self.winning_action,
            "tie_break_applied": self.tie_break_applied,
        }


@dataclass(frozen=True)
class CandidateAction:
    """Internal candidate action evaluated during the decision pipeline."""
    action_type: ActionType
    target_scope: str
    supporting_trigger_id: str
    evidence_facts: Tuple[Fact, ...]
    supporting_offer: Optional[Dict[str, Any]] = None
    next_step: str = ""
    is_eligible: bool = True
    ineligibility_reasons: Tuple[str, ...] = ()
    score: float = 0.0
    score_breakdown: Optional[Dict[str, float]] = None
    primary_reason: str = ""


@dataclass(frozen=True)
class Decision:
    """The authoritative, deterministic outcome of the Vera Decision Engine."""
    action: str
    action_type: ActionType
    target_scope: str
    trigger_id: str
    score: float
    primary_reason: str
    evidence_facts: Tuple[Fact, ...]
    supporting_offer: Optional[Dict[str, Any]] = None
    next_step: str = ""
    derived_signals: Tuple[str, ...] = ()
    trace: Optional[DecisionTrace] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "action_type": self.action_type.value,
            "target_scope": self.target_scope,
            "trigger_id": self.trigger_id,
            "score": round(self.score, 2),
            "primary_reason": self.primary_reason,
            "evidence_count": len(self.evidence_facts),
            "derived_signals": list(self.derived_signals),
            "supporting_offer": self.supporting_offer,
            "next_step": self.next_step,
            "trace": self.trace.to_dict() if self.trace else None,
        }
