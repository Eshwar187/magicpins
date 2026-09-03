"""Phase 6 Conversation Domain Models and State Representations."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    """Explicit lifecycle states for deterministic conversation control."""
    WAITING = "WAITING"
    ACTION = "ACTION"
    ENDED = "ENDED"


class IntentType(str, Enum):
    """Deterministic, typed intent classification taxonomy."""
    HOSTILE_OPT_OUT = "HOSTILE_OPT_OUT"
    ACTIONABLE_INTENT = "ACTIONABLE_INTENT"
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
    CLARIFICATION = "CLARIFICATION"
    NEUTRAL = "NEUTRAL"


class ConversationTurn(BaseModel):
    """Audit record of a single turn in a conversation."""
    turn_number: int
    from_role: str
    message: str
    received_at: str
    is_auto: bool = False
    intent: Optional[IntentType] = None
    action_taken: Optional[str] = None


class ConversationEntity(BaseModel):
    """Authoritative state and turn log for an isolated conversation."""
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    target_scope: str = "merchant"
    state: ConversationState = ConversationState.WAITING
    turn_count: int = 0
    consecutive_auto_replies: int = 0
    last_intent: Optional[IntentType] = None
    last_action: Optional[str] = None
    last_updated_at: str
    turns: List[ConversationTurn] = Field(default_factory=list)


class TransitionResult(BaseModel):
    """Result of state transition and bounded response generation."""
    previous_state: ConversationState
    new_state: ConversationState
    intent: IntentType
    action: str  # "send", "wait", "end"
    wait_seconds: Optional[int] = None
    body: Optional[str] = None
    cta: Optional[str] = None
    rationale: str
