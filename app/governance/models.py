"""Phase 5 Outreach Governance Domain Models."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OutreachDisposition(str, Enum):
    """Whether an outbound message is permitted to be transmitted."""
    SEND = "SEND"
    SUPPRESS = "SUPPRESS"


class SuppressionReasonCode(str, Enum):
    """Deterministic, machine-readable suppression reason taxonomy."""
    ELIGIBLE = "ELIGIBLE"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    MERCHANT_FREQUENCY_CAPPED = "MERCHANT_FREQUENCY_CAPPED"
    CUSTOMER_FREQUENCY_CAPPED = "CUSTOMER_FREQUENCY_CAPPED"
    CONSENT_RESTRICTED = "CONSENT_RESTRICTED"
    DECISION_WAIT_OR_END = "DECISION_WAIT_OR_END"
    INVALID_COMPOSITION = "INVALID_COMPOSITION"
    TENANT_MISMATCH = "TENANT_MISMATCH"


class OutreachRecord(BaseModel):
    """Immutable audit record of an outreach that was actually transmitted."""
    record_id: str
    tenant_key: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    action_type: str
    target_scope: str
    suppression_key: str
    simulated_at: str
    conversation_id: str
    trigger_id: str
    urgency: int = 1


class OutreachAuditTrace(BaseModel):
    """Detailed audit trace explaining policy evaluation for debugging and auditing."""
    trigger_id: str
    target_scope: str
    suppression_key: str
    evaluated_at: str
    rule_applied: str
    last_matching_send: Optional[str] = None
    seconds_since_last_send: Optional[float] = None
    cooldown_window_seconds: Optional[float] = None


class OutreachDecision(BaseModel):
    """Final output of the Phase 5 outreach governance layer."""
    disposition: OutreachDisposition
    reason_code: SuppressionReasonCode
    reason: str
    suppression_key: str
    target_scope: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    simulated_at: str
    previous_outreach_id: Optional[str] = None
    audit_trace: Optional[OutreachAuditTrace] = None
