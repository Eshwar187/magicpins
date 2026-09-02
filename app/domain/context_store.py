"""Thread-safe context store with versioning and scope isolation."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState


class StoreStatus(str, Enum):
    """Outcome of storing a context payload."""
    STORED = "stored"
    IDEMPOTENT_NOOP = "idempotent_noop"
    STALE_VERSION = "stale_version"


@dataclass(frozen=True)
class StoreResult:
    """Detailed result of context ingestion."""
    status: StoreStatus
    current_version: int
    ack_id: Optional[str] = None
    reason: Optional[str] = None

    @property
    def accepted(self) -> bool:
        """HTTP-level accepted flag: True for stored or idempotent no-op."""
        return self.status in (StoreStatus.STORED, StoreStatus.IDEMPOTENT_NOOP)


@dataclass
class StoredContext:
    """Raw context envelope as delivered by the judge or external systems."""
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: Optional[str] = None


class ContextStore:
    """Thread-safe in-memory store for category, merchant, customer, and trigger contexts.
    
    Preserves exact raw payloads and exposes typed normalized models on demand.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._contexts: Dict[Tuple[str, str], StoredContext] = {}

    def store(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        delivered_at: Optional[str] = None,
    ) -> StoreResult:
        """Ingests a context with atomic versioning semantics.
        
        - If new_version > current: replaces existing entry.
        - If new_version == current and identical payload: idempotent no-op.
        - If new_version == current and different payload: conflict rejection.
        - If new_version < current: stale version rejection.
        """
        key = (scope, context_id)
        with self._lock:
            existing = self._contexts.get(key)
            if existing is None:
                self._contexts[key] = StoredContext(
                    scope=scope,
                    context_id=context_id,
                    version=version,
                    payload=payload,
                    delivered_at=delivered_at,
                )
                return StoreResult(
                    status=StoreStatus.STORED,
                    current_version=version,
                    ack_id=f"ack_{context_id}_v{version}",
                )

            if version > existing.version:
                self._contexts[key] = StoredContext(
                    scope=scope,
                    context_id=context_id,
                    version=version,
                    payload=payload,
                    delivered_at=delivered_at,
                )
                return StoreResult(
                    status=StoreStatus.STORED,
                    current_version=version,
                    ack_id=f"ack_{context_id}_v{version}",
                )

            if version == existing.version:
                if existing.payload == payload:
                    return StoreResult(
                        status=StoreStatus.IDEMPOTENT_NOOP,
                        current_version=version,
                        ack_id=f"ack_{context_id}_v{version}",
                    )
                # Same version but payload changed -> version conflict
                return StoreResult(
                    status=StoreStatus.STALE_VERSION,
                    current_version=existing.version,
                    reason="version_payload_conflict",
                )

            # version < existing.version
            return StoreResult(
                status=StoreStatus.STALE_VERSION,
                current_version=existing.version,
                reason="stale_version",
            )

    def get_stored(self, scope: str, context_id: str) -> Optional[StoredContext]:
        """Retrieve the raw stored context envelope if present."""
        with self._lock:
            return self._contexts.get((scope, context_id))

    def get_raw(self, scope: str, context_id: str) -> Optional[dict[str, Any]]:
        """Retrieve the raw payload dictionary if present."""
        with self._lock:
            ctx = self._contexts.get((scope, context_id))
            return ctx.payload if ctx else None

    def get_category(self, slug: str) -> Optional[CategoryProfile]:
        """Retrieve and normalize a CategoryProfile by slug."""
        raw = self.get_raw("category", slug)
        return CategoryProfile.from_dict(raw) if raw else None

    def get_merchant(self, merchant_id: str) -> Optional[MerchantState]:
        """Retrieve and normalize a MerchantState by merchant_id."""
        raw = self.get_raw("merchant", merchant_id)
        return MerchantState.from_dict(raw) if raw else None

    def get_customer(self, customer_id: str) -> Optional[CustomerStateModel]:
        """Retrieve and normalize a CustomerStateModel by customer_id."""
        raw = self.get_raw("customer", customer_id)
        return CustomerStateModel.from_dict(raw) if raw else None

    def get_trigger(self, trigger_id: str) -> Optional[TriggerState]:
        """Retrieve and normalize a TriggerState by trigger_id."""
        raw = self.get_raw("trigger", trigger_id)
        return TriggerState.from_dict(raw) if raw else None

    def counts(self) -> dict[str, int]:
        """Counts of loaded contexts grouped by scope (for /v1/healthz)."""
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        with self._lock:
            for (scope, _), _ in self._contexts.items():
                counts[scope] = counts.get(scope, 0) + 1
        return counts

    def clear(self) -> None:
        """Wipes all stored context (for test isolation and teardown)."""
        with self._lock:
            self._contexts.clear()
