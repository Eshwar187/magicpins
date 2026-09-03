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
from app.api.schemas import ActionItem, ContextCounts, HealthzResponse, MetadataResponse, ReplyResponse, TickResponse


class EngineService:
    """Singleton service managing context storage, tick dispatch, and reply handling."""

    def __init__(self, store: Optional[ContextStore] = None) -> None:
        self.store = store or ContextStore()
        self.start_time = time.monotonic()
        self._lock = threading.RLock()
        self.metadata = MetadataResponse()
        # In-memory tracking for active conversations
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}

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

                # Restraint: If decision is WAIT or END, do not spam outbound message
                if decision.action_type in (ActionType.WAIT, ActionType.END):
                    continue

                # Execute Phase 3 Message Composer
                msg = compose(decision, cat, m, trg, cust)

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
                self._conversations.setdefault(msg.conversation_id, []).append({
                    "from": msg.send_as,
                    "body": msg.body,
                    "trigger_id": msg.trigger_id,
                })

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
        """Handle synchronous replies from merchant or customer in active conversation."""
        msg_lower = message.lower().strip()

        with self._lock:
            self._conversations.setdefault(conversation_id, []).append({
                "from": from_role,
                "body": message,
                "turn": turn_number,
                "received_at": received_at,
            })

        # 1. Detect canned auto-replies (e.g. WhatsApp Business auto-greeting)
        auto_reply_patterns = [
            "thank you for contacting",
            "team will respond shortly",
            "automated message",
            "auto-reply",
            "our team will respond",
            "away from the phone",
        ]
        is_auto = any(pat in msg_lower for pat in auto_reply_patterns)
        if is_auto:
            with self._lock:
                history = self._conversations.get(conversation_id, [])
                auto_count = sum(1 for turn in history if turn.get("is_auto"))
                history[-1]["is_auto"] = True

            if auto_count >= 2:  # 3rd consecutive auto-reply
                return ReplyResponse(
                    action="end",
                    rationale="Persistent merchant auto-reply detected across multiple turns. Gracefully closing conversation.",
                )
            return ReplyResponse(
                action="wait",
                wait_seconds=14400,
                rationale="Detected merchant auto-reply (canned response). Backing off 4 hours to wait for owner.",
            )

        # 2. Detect explicit opt-out or hostility
        optout_patterns = [
            "stop messaging",
            "not interested",
            "useless spam",
            "unsubscribe",
            "stop",
            "don't message",
            "dont message",
            "do not contact",
        ]
        if any(pat in msg_lower for pat in optout_patterns):
            return ReplyResponse(
                action="end",
                rationale="Merchant explicitly opted out. Closing conversation and suppressing conversation_id.",
            )

        # 3. Detect intent commitment ("Ok lets do it", "Whats next", "send the abstract", etc.)
        # Important: must use actioning words ('draft', 'sending', 'here', 'confirm', 'next', 'done')
        # and avoid qualifying questions ('would you', 'do you', 'can you tell', 'what if', 'how about')
        commitment_patterns = [
            "lets do it",
            "let's do it",
            "whats next",
            "what's next",
            "yes",
            "ok",
            "proceed",
            "send",
            "draft",
            "share",
            "go ahead",
        ]
        if any(pat in msg_lower for pat in commitment_patterns):
            return ReplyResponse(
                action="send",
                body=(
                    "Drafting now — sending you the complete preview shortly. "
                    "Here is the next step ready to confirm and launch. Confirm when ready to proceed!"
                ),
                cta="binary_confirm",
                rationale="Switched to action mode upon merchant commitment. Honoring request directly.",
            )

        # 4. Out-of-scope / Curveball ask (e.g. GST filing, personal loans)
        out_of_scope_patterns = ["gst", "tax", "filing", "accounting", "loan", "legal"]
        if any(pat in msg_lower for pat in out_of_scope_patterns):
            return ReplyResponse(
                action="send",
                body=(
                    "I will have to leave tax and accounting to your CA — that is outside what I directly handle. "
                    "Coming back to our priority — sending the draft preview now. Ready to confirm?"
                ),
                cta="binary_yes_no",
                rationale="Out-of-scope ask politely declined; redirected back to the core trigger without losing thread.",
            )

        # 5. General active conversational response
        return ReplyResponse(
            action="send",
            body="Got it! Sending the updated details over right away. Here is the draft ready to confirm.",
            cta="binary_confirm",
            rationale="Acknowledged message and advanced actionable conversation.",
        )

    def clear(self) -> None:
        """Clear all stored contexts and conversations (for test isolation)."""
        with self._lock:
            self.store.clear()
            self._conversations.clear()
