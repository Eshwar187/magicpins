"""Tests for ContextStore version semantics, scope isolation, and idempotency."""

import pytest
from app.domain.context_store import ContextStore, StoreStatus


def test_context_store_version_lifecycle():
    """Verify version 1 -> stored, v1 -> idempotent no-op, v2 -> replaces, v1 -> cannot overwrite v2."""
    store = ContextStore()

    payload_v1 = {"identity": {"name": "Dr. Meera", "city": "Delhi"}}
    payload_v1_dup = {"identity": {"name": "Dr. Meera", "city": "Delhi"}}
    payload_v2 = {"identity": {"name": "Dr. Meera Updated", "city": "Delhi"}}
    payload_v1_altered = {"identity": {"name": "Tampered V1", "city": "Delhi"}}

    # 1. First push v1 -> STORED
    res1 = store.store("merchant", "m_001", version=1, payload=payload_v1)
    assert res1.status == StoreStatus.STORED
    assert res1.accepted is True
    assert res1.current_version == 1
    assert store.get_raw("merchant", "m_001") == payload_v1

    # 2. Re-push identical v1 -> IDEMPOTENT_NOOP
    res2 = store.store("merchant", "m_001", version=1, payload=payload_v1_dup)
    assert res2.status == StoreStatus.IDEMPOTENT_NOOP
    assert res2.accepted is True
    assert res2.current_version == 1

    # 3. Push v2 -> STORED and replaces v1 atomically
    res3 = store.store("merchant", "m_001", version=2, payload=payload_v2)
    assert res3.status == StoreStatus.STORED
    assert res3.accepted is True
    assert res3.current_version == 2
    assert store.get_raw("merchant", "m_001") == payload_v2

    # 4. Attempt to overwrite v2 with older v1 -> STALE_VERSION rejected
    res4 = store.store("merchant", "m_001", version=1, payload=payload_v1)
    assert res4.status == StoreStatus.STALE_VERSION
    assert res4.accepted is False
    assert res4.current_version == 2
    # Ensure payload still reflects v2!
    assert store.get_raw("merchant", "m_001") == payload_v2


def test_version_reuse_with_different_payload_is_rejected():
    """Verify that pushing the same version with altered payload triggers a version conflict."""
    store = ContextStore()
    payload_a = {"key": "val1"}
    payload_b = {"key": "val2"}

    res1 = store.store("trigger", "trg_1", version=1, payload=payload_a)
    assert res1.status == StoreStatus.STORED

    # Same version 1 but different payload
    res2 = store.store("trigger", "trg_1", version=1, payload=payload_b)
    assert res2.status == StoreStatus.STALE_VERSION
    assert res2.accepted is False
    assert res2.reason == "version_payload_conflict"


def test_scope_isolation():
    """Ensure contexts with identical IDs across different scopes do not collide."""
    store = ContextStore()

    store.store("merchant", "shared_id", version=1, payload={"role": "merchant_data"})
    store.store("customer", "shared_id", version=1, payload={"role": "customer_data"})
    store.store("trigger", "shared_id", version=1, payload={"role": "trigger_data"})

    assert store.get_raw("merchant", "shared_id") == {"role": "merchant_data"}
    assert store.get_raw("customer", "shared_id") == {"role": "customer_data"}
    assert store.get_raw("trigger", "shared_id") == {"role": "trigger_data"}

    counts = store.counts()
    assert counts["merchant"] == 1
    assert counts["customer"] == 1
    assert counts["trigger"] == 1
    assert counts["category"] == 0
