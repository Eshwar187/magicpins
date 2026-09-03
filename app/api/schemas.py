"""FastAPI request and response schemas for Phase 4 challenge contract."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# /v1/healthz
# -----------------------------------------------------------------------------
class ContextCounts(BaseModel):
    category: int = 0
    merchant: int = 0
    customer: int = 0
    trigger: int = 0


class HealthzResponse(BaseModel):
    status: Literal["ok"] = "ok"
    uptime_seconds: int
    contexts_loaded: ContextCounts


# -----------------------------------------------------------------------------
# /v1/metadata
# -----------------------------------------------------------------------------
class MetadataResponse(BaseModel):
    team_name: str = "Team Antigravity"
    team_members: List[str] = ["Eshwar"]
    model: str = "deterministic-engine-v1"
    approach: str = "grounded deterministic decision engine + category-aware templating"
    contact_email: str = "eshwar@example.com"
    version: str = "1.0.0"
    submitted_at: str = "2026-04-26T08:00:00Z"


# -----------------------------------------------------------------------------
# /v1/context
# -----------------------------------------------------------------------------
class CtxBody(BaseModel):
    scope: Literal["category", "merchant", "customer", "trigger"]
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: Optional[str] = None


class ContextAckResponse(BaseModel):
    accepted: Literal[True] = True
    ack_id: str
    stored_at: str


class ContextConflictResponse(BaseModel):
    accepted: Literal[False] = False
    reason: str = "stale_version"
    current_version: int


class ContextErrorResponse(BaseModel):
    accepted: Literal[False] = False
    reason: str
    details: Optional[str] = None


# -----------------------------------------------------------------------------
# /v1/tick
# -----------------------------------------------------------------------------
class TickBody(BaseModel):
    now: str
    available_triggers: List[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: Literal["vera", "merchant_on_behalf"]
    trigger_id: str
    template_name: str
    template_params: List[str]
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: List[ActionItem] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# /v1/reply
# -----------------------------------------------------------------------------
class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: Literal["merchant", "customer"] = "merchant"
    message: str
    received_at: str
    turn_number: int = 2


class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[str] = None
    wait_seconds: Optional[int] = None
    rationale: str
