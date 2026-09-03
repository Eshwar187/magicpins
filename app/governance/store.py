"""Thread-safe outreach history store and atomic check-and-record governance engine."""

from __future__ import annotations

import hashlib
import threading
from typing import Dict, List, Optional

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.decide import Decision
from app.composer.message import ComposedMessage
from app.governance.models import (
    OutreachDecision,
    OutreachDisposition,
    OutreachRecord,
)
from app.governance.policy import evaluate_outreach, get_tenant_key


class OutreachStore:
    """Thread-safe in-memory outreach store for atomic check-and-record governance."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._history: List[OutreachRecord] = []
        self._send_count = 0
        self._suppress_count = 0

    def evaluate_and_record(
        self,
        decision: Decision,
        composed: ComposedMessage,
        now: str,
        category: Optional[CategoryProfile] = None,
        merchant: Optional[MerchantState] = None,
        trigger: Optional[TriggerState] = None,
        customer: Optional[CustomerStateModel] = None,
    ) -> OutreachDecision:
        """Atomically evaluate outreach eligibility and record transmission if eligible."""
        with self._lock:
            # 1. Evaluate policy against history
            outreach_decision = evaluate_outreach(
                decision=decision,
                composed=composed,
                now=now,
                history=self._history,
                category=category,
                merchant=merchant,
                trigger=trigger,
                customer=customer,
            )

            # 2. Record outreach ONLY if permitted to SEND
            if outreach_decision.disposition == OutreachDisposition.SEND:
                target_scope = decision.target_scope or composed.target_scope or "merchant"
                merchant_id = merchant.merchant_id if merchant else composed.merchant_id
                customer_id = customer.customer_id if customer else composed.customer_id
                supp_key = composed.suppression_key or (trigger.suppression_key if trigger else "")
                tenant_key = get_tenant_key(target_scope, merchant_id, customer_id)

                # Deterministic record ID
                token = f"{tenant_key}:{supp_key}:{now}:{composed.conversation_id}"
                record_id = f"outreach_{hashlib.sha256(token.encode()).hexdigest()[:16]}"

                record = OutreachRecord(
                    record_id=record_id,
                    tenant_key=tenant_key,
                    merchant_id=merchant_id,
                    customer_id=customer_id,
                    action_type=composed.action_type.value if hasattr(composed.action_type, "value") else str(composed.action_type),
                    target_scope=target_scope,
                    suppression_key=supp_key,
                    simulated_at=now,
                    conversation_id=composed.conversation_id,
                    trigger_id=trigger.id if trigger else "",
                    urgency=trigger.urgency if trigger else 1,
                )
                self._history.append(record)
                self._send_count += 1
            else:
                self._suppress_count += 1

            return outreach_decision

    def get_history(self, tenant_key: Optional[str] = None) -> List[OutreachRecord]:
        """Return a copy of the outreach history, optionally filtered by tenant key."""
        with self._lock:
            if tenant_key:
                return [r for r in self._history if r.tenant_key == tenant_key]
            return list(self._history)

    def counts(self) -> Dict[str, int]:
        """Return current governance counts."""
        with self._lock:
            return {
                "sent": self._send_count,
                "suppressed": self._suppress_count,
                "history_length": len(self._history),
            }

    def clear(self) -> None:
        """Reset the outreach history store."""
        with self._lock:
            self._history.clear()
            self._send_count = 0
            self._suppress_count = 0
