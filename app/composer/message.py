"""Typed model representing a composed message output from Phase 3."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.engine.actions import ActionType


class ComposedMessage(BaseModel):
    """Structured message draft produced deterministically from an authoritative Decision."""

    model_config = ConfigDict(frozen=True)

    action: Literal["send", "wait", "end"] = Field(
        ..., description="Delivery action: 'send' for outbound message, 'wait' for backoff, 'end' for conversation termination."
    )
    action_type: ActionType = Field(..., description="Authoritative Phase 2 action type.")
    target_scope: Literal["merchant", "customer"] = Field(..., description="Recipient target scope.")
    send_as: Literal["vera", "merchant_on_behalf"] = Field(
        ..., description="Sender persona identity: 'vera' for merchant communication; 'merchant_on_behalf' for customer."
    )
    body: str = Field(..., description="The rendered, grounded text message.")
    cta: str = Field(..., description="Single primary call-to-action classifier (e.g. binary_yes_no, multi_choice_slot, open_ended, none).")
    suppression_key: str = Field(..., description="Deterministic dedup and suppression key.")
    rationale: str = Field(..., description="Internal explanation of why this message was composed.")
    conversation_id: str = Field(..., description="Unique deterministic conversation identifier.")
    merchant_id: str = Field(..., description="Target merchant identifier.")
    customer_id: Optional[str] = Field(None, description="Target customer identifier if customer-scoped, else None.")
    trigger_id: str = Field(..., description="Trigger identifier prompting this composition.")
    template_name: str = Field(..., description="Identifier of the deterministic template used.")
    template_params: List[str] = Field(default_factory=list, description="List of substituted grounded template parameters.")

    @property
    def message(self) -> str:
        """Alias for body, conforming to challenge specification."""
        return self.body

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "action": self.action,
            "action_type": self.action_type.value,
            "target_scope": self.target_scope,
            "send_as": self.send_as,
            "body": self.body,
            "message": self.body,
            "cta": self.cta,
            "suppression_key": self.suppression_key,
            "rationale": self.rationale,
            "conversation_id": self.conversation_id,
            "merchant_id": self.merchant_id,
            "customer_id": self.customer_id,
            "trigger_id": self.trigger_id,
            "template_name": self.template_name,
            "template_params": list(self.template_params),
        }
