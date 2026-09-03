"""Tests for OutreachStore check-and-record concurrency and multi-tenant isolation."""

import concurrent.futures
from app.engine.actions import ActionType
from app.engine.decide import Decision
from app.composer.message import ComposedMessage
from app.governance.models import OutreachDisposition, SuppressionReasonCode
from app.governance.store import OutreachStore


def make_decision(m_id="m_001", act_type=ActionType.PROMOTE_DELIVERY_OFFER, scope="merchant"):
    return Decision(
        action_type=act_type,
        action=act_type.value,
        target_scope=scope,
        trigger_id="trg_1",
        score=90.0,
        primary_reason="Test",
        evidence_facts=(),
    )


def make_composed(m_id="m_001", c_id=None, key="key_1", scope="merchant", trg_id="trg_1"):
    return ComposedMessage(
        conversation_id=f"conv_{m_id}_{key}",
        merchant_id=m_id,
        customer_id=c_id,
        target_scope=scope,
        trigger_id=trg_id,
        send_as="vera",
        action="send",
        action_type=ActionType.PROMOTE_DELIVERY_OFFER,
        template_name="test_v1",
        template_params=[],
        body="Test message",
        cta="binary_yes_no",
        suppression_key=key,
        rationale="Test",
    )


def test_concurrency_race_single_winner():
    """Verify that 20 simultaneous threads evaluating the same key for the same merchant produce exactly 1 SEND."""
    store = OutreachStore()
    decision = make_decision()
    composed = make_composed(key="concurrent_race_key")
    now = "2026-04-26T10:00:00Z"

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(store.evaluate_and_record, decision, composed, now)
            for _ in range(20)
        ]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    sends = [r for r in results if r.disposition == OutreachDisposition.SEND]
    suppresses = [r for r in results if r.disposition == OutreachDisposition.SUPPRESS]

    assert len(sends) == 1, f"Expected exactly 1 winner, got {len(sends)}"
    assert len(suppresses) == 19
    assert all(r.reason_code == SuppressionReasonCode.DUPLICATE_SUPPRESSED for r in suppresses)
    assert store.counts()["sent"] == 1
    assert store.counts()["suppressed"] == 19


def test_concurrency_different_keys_independent_winners():
    """Verify that 20 concurrent threads across 2 distinct keys produce 1 SEND per key."""
    store = OutreachStore()
    decision = make_decision()
    comp_a = make_composed(key="key_alpha")
    comp_b = make_composed(key="key_beta")
    now = "2026-04-26T10:00:00Z"

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for _ in range(10):
            futures.append(executor.submit(store.evaluate_and_record, decision, comp_a, now))
            futures.append(executor.submit(store.evaluate_and_record, decision, comp_b, now))
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    sends_a = [r for r in results if r.disposition == OutreachDisposition.SEND and r.suppression_key == "key_alpha"]
    sends_b = [r for r in results if r.disposition == OutreachDisposition.SEND and r.suppression_key == "key_beta"]
    suppresses = [r for r in results if r.disposition == OutreachDisposition.SUPPRESS]

    assert len(sends_a) == 1, f"Expected exactly 1 winner for key A, got {len(sends_a)}"
    assert len(sends_b) == 1, f"Expected exactly 1 winner for key B, got {len(sends_b)}"
    assert len(suppresses) == 18
    assert store.counts()["sent"] == 2
    assert store.counts()["suppressed"] == 18


def test_tenant_isolation_identical_key():
    """Verify identical suppression key across Merchant A and Merchant B is allowed for both."""
    store = OutreachStore()
    now = "2026-04-26T10:00:00Z"
    shared_key = "research:dentists:2026-W17"

    d_a = make_decision(m_id="m_001")
    c_a = make_composed(m_id="m_001", key=shared_key)
    res_a = store.evaluate_and_record(d_a, c_a, now)
    assert res_a.disposition == OutreachDisposition.SEND

    # Merchant B with identical suppression key
    d_b = make_decision(m_id="m_002")
    c_b = make_composed(m_id="m_002", key=shared_key)
    res_b = store.evaluate_and_record(d_b, c_b, now)
    assert res_b.disposition == OutreachDisposition.SEND

    assert store.counts()["sent"] == 2
    assert store.counts()["suppressed"] == 0


def test_customer_isolation_same_merchant():
    """Verify customer outreaches under the same merchant are isolated by customer ID."""
    store = OutreachStore()
    now = "2026-04-26T10:00:00Z"

    # Customer A
    d_a = make_decision(m_id="m_001", act_type=ActionType.CUSTOMER_RECALL, scope="customer")
    c_a = make_composed(m_id="m_001", c_id="c_001", key="recall:c_001:6mo", scope="customer")
    from app.domain.models.customer import Consent, CustomerIdentity, CustomerPreferences, CustomerStateModel, Relationship
    cust_a = CustomerStateModel(
        customer_id="c_001", merchant_id="m_001", identity=CustomerIdentity(name="A", language_pref="en"),
        relationship=Relationship(), state="active",
        consent=Consent(scope=["recall_reminders"]), preferences=CustomerPreferences(reminder_opt_in=True)
    )
    res_a = store.evaluate_and_record(d_a, c_a, now, customer=cust_a)
    assert res_a.disposition == OutreachDisposition.SEND

    # Customer B under same merchant
    d_b = make_decision(m_id="m_001", act_type=ActionType.CUSTOMER_RECALL, scope="customer")
    c_b = make_composed(m_id="m_001", c_id="c_002", key="recall:c_002:6mo", scope="customer")
    cust_b = CustomerStateModel(
        customer_id="c_002", merchant_id="m_001", identity=CustomerIdentity(name="B", language_pref="en"),
        relationship=Relationship(), state="active",
        consent=Consent(scope=["recall_reminders"]), preferences=CustomerPreferences(reminder_opt_in=True)
    )
    res_b = store.evaluate_and_record(d_b, c_b, now, customer=cust_b)
    assert res_b.disposition == OutreachDisposition.SEND

    assert store.counts()["sent"] == 2
