"""EngineService integrating Phase 1 context store, Phase 2 decide, and Phase 3 compose."""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.domain.context_store import ContextStore
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decide import decide
from app.composer.compose import compose
from app.conversation.store import ConversationStore
from app.governance import OutreachDisposition, OutreachStore
from app.api.schemas import ActionItem, ContextCounts, HealthzResponse, MetadataResponse, ReplyResponse, TickResponse


class EngineService:
    """Thread-safe singleton engine service coordinating storage, decisioning, composition, and governance."""

    def __init__(self, store: Optional[ContextStore] = None) -> None:
        self._lock = threading.RLock()
        self.store = store or ContextStore()
        self.governance = OutreachStore()
        self.conversations = ConversationStore()
        self.start_time = time.monotonic()
        self.metadata = MetadataResponse()

    def get_health(self) -> HealthzResponse:
        """Lightweight live health check returning uptime and loaded context counts."""
        uptime = int(time.monotonic() - self.start_time)
        raw_counts = self.store.counts()
        return HealthzResponse(
            status="ok",
            uptime_seconds=uptime,
            contexts_loaded=ContextCounts(**raw_counts),
        )

    def get_metadata(self) -> MetadataResponse:
        """Returns judge-facing metadata describing the bot approach and version."""
        return self.metadata

    def push_context(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: Dict[str, Any],
        delivered_at: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[int], Optional[str]]:
        """Ingest context payload with strict Phase 1 normalization and freshness validation.

        Returns:
            (accepted, ack_id_or_reason, current_version_if_conflict, stored_at_or_error_detail)
        """
        if scope not in ("category", "merchant", "customer", "trigger"):
            return False, "invalid_scope", None, f"Unsupported scope: {scope}"

        # 1. Validate payload schema against Phase 1 domain models
        try:
            if scope == "category":
                CategoryProfile.from_dict(payload)
            elif scope == "merchant":
                MerchantState.from_dict(payload)
            elif scope == "customer":
                CustomerStateModel.from_dict(payload)
            elif scope == "trigger":
                TriggerState.from_dict(payload)
        except Exception as e:
            return False, "invalid_payload", None, str(e)

        # 2. Check freshness against context store
        with self._lock:
            existing = self.store.get_stored(scope, context_id)
            if existing and existing.version >= version:
                return False, "stale_version", existing.version, None

            # 3. Store the new authoritative version
            res = self.store.store(
                scope=scope,
                context_id=context_id,
                version=version,
                payload=payload,
                delivered_at=delivered_at,
            )
            stored_at = delivered_at or "2026-04-26T10:00:00.000Z"
            return True, res.ack_id, None, stored_at

    def tick(self, now: str, available_triggers: List[str]) -> TickResponse:
        """Process periodic tick triggers deterministically through Phase 2 decide and Phase 3 compose."""
        actions: List[ActionItem] = []

        with self._lock:
            for tid in available_triggers:
                trg = self.store.get_trigger(tid)
                if not trg:
                    continue

                # Locate Merchant
                mid = trg.merchant_id or trg.payload.get("merchant_id")
                if not mid:
                    continue
                m = self.store.get_merchant(mid)
                if not m:
                    continue

                # Locate Category
                cat_slug = m.category_slug or trg.payload.get("category")
                if not cat_slug:
                    continue
                cat = self.store.get_category(cat_slug)
                if not cat:
                    continue

                # Locate Customer (optional)
                cid = trg.customer_id or trg.payload.get("customer_id")
                cust = self.store.get_customer(cid) if cid else None

                # Execute Phase 2 Decision Engine
                decision = decide(cat, m, trg, cust)

                # Execute Phase 3 Message Composer
                msg = compose(decision, cat, m, trg, cust)

                # Execute Phase 5 Outreach Governance Barrier (Atomic check-and-record)
                outreach = self.governance.evaluate_and_record(
                    decision=decision,
                    composed=msg,
                    now=now,
                    category=cat,
                    merchant=m,
                    trigger=trg,
                    customer=cust,
                )

                # Only transmit if OutreachPolicy == SEND
                if outreach.disposition != OutreachDisposition.SEND:
                    continue

                action_item = ActionItem(
                    conversation_id=msg.conversation_id,
                    merchant_id=msg.merchant_id,
                    customer_id=msg.customer_id,
                    send_as=msg.send_as,
                    trigger_id=msg.trigger_id,
                    template_name=msg.template_name,
                    template_params=msg.template_params,
                    body=msg.body,
                    cta=msg.cta,
                    suppression_key=msg.suppression_key,
                    rationale=msg.rationale,
                )
                actions.append(action_item)

                # Record conversation
                self.conversations.record_tick_send(
                    conversation_id=msg.conversation_id,
                    merchant_id=msg.merchant_id,
                    customer_id=msg.customer_id,
                    target_scope=msg.target_scope,
                    trigger_id=msg.trigger_id,
                    send_as=msg.send_as,
                    body=msg.body,
                    now=now,
                )

        return TickResponse(actions=actions)

    def reply(
        self,
        conversation_id: str,
        merchant_id: Optional[str],
        customer_id: Optional[str],
        from_role: str,
        message: str,
        received_at: str,
        turn_number: int,
    ) -> ReplyResponse:
        """Handle synchronous replies from merchant or customer via ConversationStore and Phase 3."""
        from app.api.schemas import ReplyRequest
        from app.composer.compose import compose_action_continuation
        from app.engine.decide import decide

        req = ReplyRequest(
            conversation_id=conversation_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            from_role=from_role,
            message=message,
            received_at=received_at,
            turn_number=turn_number,
        )
        transition = self.conversations.process_turn(req)

        # If transition routed to CONTINUE_EXISTING_ACTION -> invoke Phase 3 composition!
        if transition.route == "CONTINUE_EXISTING_ACTION":
            entity = self.conversations.get(conversation_id)
            mid = merchant_id or (entity.merchant_id if entity else None)
            m = self.store.get_merchant(mid) if mid else None
            if m:
                cat_slug = m.category_slug
                cat = self.store.get_category(cat_slug) if cat_slug else None
                trg = None
                if entity and getattr(entity, "trigger_id", None):
                    trg = self.store.get_trigger(entity.trigger_id)
                if not trg:
                    with self.store._lock:
                        for (scope, ctx_id), stored in self.store._contexts.items():
                            if scope == "trigger":
                                t = self.store.get_trigger(ctx_id)
                                if t and (t.merchant_id == mid or t.payload.get("merchant_id") == mid):
                                    trg = t
                                    break
                if trg and cat:
                    cust = self.store.get_customer(customer_id) if customer_id else None
                    decision = decide(cat, m, trg, cust)
                    composed = compose_action_continuation(decision, cat, m, trg, cust)
                    return ReplyResponse(
                        action="send",
                        body=composed.body,
                        cta=composed.cta,
                        rationale=composed.rationale,
                    )

            # Fallback if no valid merchant identity exists or context not loaded
            return ReplyResponse(
                action="send",
                body="Here is the draft ready to confirm. Confirm when ready to proceed!",
                cta="binary_confirm",
                rationale="Phase 3 continuation workflow resumed upon merchant commitment.",
            )

        return ReplyResponse(
            action=transition.action,
            wait_seconds=transition.wait_seconds,
            body=transition.body,
            cta=transition.cta,
            rationale=transition.rationale,
        )

    def clear(self) -> None:
        """Clear all stored contexts, governance history, and conversations (for test isolation)."""
        with self._lock:
            self.store.clear()
            self.governance.clear()
            self.conversations.clear()

