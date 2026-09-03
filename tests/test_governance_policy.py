"""Unit tests for Phase 5.2 outreach governance: exact deduplication and consent."""

from app.domain.models.customer import Consent, CustomerIdentity, CustomerPreferences, CustomerStateModel, Relationship
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decide import Decision
from app.composer.message import ComposedMessage
from app.governance.models import (
    OutreachDisposition,
    OutreachRecord,
    SuppressionReasonCode,
)
from app.governance.policy import (
    evaluate_outreach,
    get_tenant_key,
)


def make_test_decision(action_type=ActionType.PROMOTE_DELIVERY_OFFER, target_scope="merchant", trigger_id="trg_1"):
    return Decision(
        action_type=action_type,
        action=action_type.value,
        target_scope=target_scope,
        trigger_id=trigger_id,
        score=85.0,
        primary_reason="Test primary reason",
        evidence_facts=(),
    )


def make_test_composed(
    action="send",
    action_type=ActionType.PROMOTE_DELIVERY_OFFER,
    body="Test message body with details.",
    cta="binary_yes_no",
    suppression_key="event:delivery:m_001:2026-04-26",
    merchant_id="m_001",
    customer_id=None,
    target_scope="merchant",
    trigger_id="trg_1",
):
    return ComposedMessage(
        conversation_id=f"conv_{merchant_id}_{suppression_key}",
        merchant_id=merchant_id,
        customer_id=customer_id,
        target_scope=target_scope,
        trigger_id=trigger_id,
        send_as="vera",
        action=action,
        action_type=action_type,
        template_name="test_template_v1",
        template_params=["param1"],
        body=body,
        cta=cta,
        suppression_key=suppression_key,
        rationale="Test rationale",
    )


def test_first_send_allowed():
    """Verify first outreach with empty history returns SEND and ELIGIBLE."""
    decision = make_test_decision()
    composed = make_test_composed()
    res = evaluate_outreach(
        decision=decision,
        composed=composed,
        now="2026-04-26T10:00:00Z",
        history=[],
    )
    assert res.disposition == OutreachDisposition.SEND
    assert res.reason_code == SuppressionReasonCode.ELIGIBLE


def test_exact_duplicate_suppressed_no_cooldown_expiry():
    """Verify exact suppression key is suppressed indefinitely with zero cooldown expiry."""
    decision = make_test_decision()
    composed = make_test_composed(suppression_key="research:dentists:2026-W17")
    
    # Prior send at T0
    record = OutreachRecord(
        record_id="rec_1",
        tenant_key="m:m_001",
        merchant_id="m_001",
        action_type=decision.action_type.value,
        target_scope="merchant",
        suppression_key="research:dentists:2026-W17",
        simulated_at="2026-04-26T10:00:00Z",
        conversation_id="conv_1",
        trigger_id="trg_1",
    )
    
    # Test at T0 (immediate duplicate)
    r_t0 = evaluate_outreach(decision, composed, "2026-04-26T10:00:00Z", [record])
    assert r_t0.disposition == OutreachDisposition.SUPPRESS
    assert r_t0.reason_code == SuppressionReasonCode.DUPLICATE_SUPPRESSED

    # Test at T0 + 1 day
    r_1d = evaluate_outreach(decision, composed, "2026-04-27T10:00:00Z", [record])
    assert r_1d.disposition == OutreachDisposition.SUPPRESS
    assert r_1d.reason_code == SuppressionReasonCode.DUPLICATE_SUPPRESSED

    # Test at T0 + 7 days
    r_7d = evaluate_outreach(decision, composed, "2026-05-03T10:00:00Z", [record])
    assert r_7d.disposition == OutreachDisposition.SUPPRESS
    assert r_7d.reason_code == SuppressionReasonCode.DUPLICATE_SUPPRESSED

    # Test at T0 + 30 days
    r_30d = evaluate_outreach(decision, composed, "2026-05-26T10:00:00Z", [record])
    assert r_30d.disposition == OutreachDisposition.SUPPRESS
    assert r_30d.reason_code == SuppressionReasonCode.DUPLICATE_SUPPRESSED

    # Test at T0 + 1 year (no decay/expiry!)
    r_1y = evaluate_outreach(decision, composed, "2027-04-26T10:00:00Z", [record])
    assert r_1y.disposition == OutreachDisposition.SUPPRESS
    assert r_1y.reason_code == SuppressionReasonCode.DUPLICATE_SUPPRESSED


def test_same_merchant_different_keys_allowed():
    """Verify that different suppression keys for the same merchant send independently without aggregate capping."""
    decision = make_test_decision()
    
    # Prior record for key A
    record_a = OutreachRecord(
        record_id="rec_a",
        tenant_key="m:m_001",
        merchant_id="m_001",
        action_type="some_action",
        target_scope="merchant",
        suppression_key="key_A",
        simulated_at="2026-04-26T10:00:00Z",
        conversation_id="conv_a",
        trigger_id="trg_a",
    )

    # Key B for same merchant just 1 minute later
    composed_b = make_test_composed(suppression_key="key_B")
    r_b = evaluate_outreach(decision, composed_b, "2026-04-26T10:01:00Z", [record_a])
    assert r_b.disposition == OutreachDisposition.SEND
    assert r_b.reason_code == SuppressionReasonCode.ELIGIBLE

    # Key C for same merchant
    record_b = OutreachRecord(
        record_id="rec_b",
        tenant_key="m:m_001",
        merchant_id="m_001",
        action_type="some_action",
        target_scope="merchant",
        suppression_key="key_B",
        simulated_at="2026-04-26T10:01:00Z",
        conversation_id="conv_b",
        trigger_id="trg_b",
    )
    composed_c = make_test_composed(suppression_key="key_C")
    r_c = evaluate_outreach(decision, composed_c, "2026-04-26T10:02:00Z", [record_a, record_b])
    assert r_c.disposition == OutreachDisposition.SEND
    assert r_c.reason_code == SuppressionReasonCode.ELIGIBLE


def test_same_customer_different_keys_allowed():
    """Verify customer can receive distinct outreaches with different suppression keys without aggregate frequency block."""
    decision = make_test_decision(action_type=ActionType.CUSTOMER_RECALL, target_scope="customer")
    cust = CustomerStateModel(
        customer_id="c_001",
        merchant_id="m_001",
        identity=CustomerIdentity(name="Test User", language_pref="english"),
        relationship=Relationship(),
        state="active",
        consent=Consent(scope=["recall_reminders", "followup"]),
        preferences=CustomerPreferences(reminder_opt_in=True),
    )
    record_1 = OutreachRecord(
        record_id="rec_c1",
        tenant_key="c:m_001:c_001",
        merchant_id="m_001",
        customer_id="c_001",
        action_type="customer_recall",
        target_scope="customer",
        suppression_key="key_recall_1",
        simulated_at="2026-04-26T10:00:00Z",
        conversation_id="conv_c1",
        trigger_id="trg_c1",
    )
    composed_2 = make_test_composed(
        action_type=ActionType.CUSTOMER_RECALL,
        target_scope="customer",
        customer_id="c_001",
        suppression_key="key_followup_2",
    )
    res = evaluate_outreach(decision, composed_2, "2026-04-26T10:05:00Z", [record_1], customer=cust)
    assert res.disposition == OutreachDisposition.SEND
    assert res.reason_code == SuppressionReasonCode.ELIGIBLE


def test_same_key_different_merchants_allowed():
    """Verify category-level key sent to Merchant 1 does not suppress Merchant 2."""
    decision = make_test_decision()
    shared_key = "research:dentists:2026-W17"
    
    # Prior send to Merchant 1
    record_m1 = OutreachRecord(
        record_id="rec_m1",
        tenant_key="m:m_001",
        merchant_id="m_001",
        action_type="use_research_insight",
        target_scope="merchant",
        suppression_key=shared_key,
        simulated_at="2026-04-26T10:00:00Z",
        conversation_id="conv_m1",
        trigger_id="trg_1",
    )

    # Evaluation for Merchant 2
    composed_m2 = make_test_composed(merchant_id="m_002", suppression_key=shared_key)
    res = evaluate_outreach(decision, composed_m2, "2026-04-26T10:00:00Z", [record_m1])
    assert res.disposition == OutreachDisposition.SEND
    assert res.reason_code == SuppressionReasonCode.ELIGIBLE


def test_same_customer_id_different_merchants_allowed():
    """Verify tenant isolation across different merchants for the same customer ID."""
    decision = make_test_decision(action_type=ActionType.CUSTOMER_RECALL, target_scope="customer")
    cust_m1 = CustomerStateModel(
        customer_id="c_001", merchant_id="m_001", identity=CustomerIdentity(name="Priya", language_pref="en"),
        relationship=Relationship(), state="active", consent=Consent(scope=["recall_reminders"]),
        preferences=CustomerPreferences(reminder_opt_in=True),
    )
    cust_m2 = CustomerStateModel(
        customer_id="c_001", merchant_id="m_002", identity=CustomerIdentity(name="Priya", language_pref="en"),
        relationship=Relationship(), state="active", consent=Consent(scope=["recall_reminders"]),
        preferences=CustomerPreferences(reminder_opt_in=True),
    )
    shared_key = "recall:c_001:shared"
    record_m1 = OutreachRecord(
        record_id="rec_m1", tenant_key="c:m_001:c_001", merchant_id="m_001", customer_id="c_001",
        action_type="customer_recall", target_scope="customer", suppression_key=shared_key,
        simulated_at="2026-04-26T10:00:00Z", conversation_id="conv_m1", trigger_id="t1"
    )
    composed_m2 = make_test_composed(
        merchant_id="m_002", customer_id="c_001", target_scope="customer", suppression_key=shared_key
    )
    res = evaluate_outreach(decision, composed_m2, "2026-04-26T10:00:00Z", [record_m1], customer=cust_m2)
    assert res.disposition == OutreachDisposition.SEND
    assert res.reason_code == SuppressionReasonCode.ELIGIBLE


def test_cadence_tokens_treated_as_identifiers_not_cooldowns():
    """Verify keys with 2026-W17, 2026-Q2, 2026-04-26, 30d, 6mo are treated purely as exact IDs."""
    decision = make_test_decision()
    keys_to_test = [
        "research:dentists:2026-W17",
        "renewal:m_002:2026-Q2",
        "event:delivery:2026-04-26",
        "dormant:m_004:30d",
        "recall:c_001:6mo",
    ]
    for key in keys_to_test:
        c = make_test_composed(suppression_key=key)
        # 1. First send -> SEND
        r1 = evaluate_outreach(decision, c, "2026-04-26T10:00:00Z", [])
        assert r1.disposition == OutreachDisposition.SEND
        assert r1.reason_code == SuppressionReasonCode.ELIGIBLE

        # 2. Exact match in history -> DUPLICATE_SUPPRESSED
        rec = OutreachRecord(
            record_id=f"rec_{key}", tenant_key="m:m_001", merchant_id="m_001", action_type="test",
            target_scope="merchant", suppression_key=key, simulated_at="2026-04-26T10:00:00Z",
            conversation_id="conv", trigger_id="t"
        )
        r2 = evaluate_outreach(decision, c, "2030-01-01T00:00:00Z", [rec])
        assert r2.disposition == OutreachDisposition.SUPPRESS
        assert r2.reason_code == SuppressionReasonCode.DUPLICATE_SUPPRESSED


def test_customer_opt_out_suppression():
    """Verify customer outreach is suppressed if customer opted out of reminders."""
    decision = make_test_decision(action_type=ActionType.CUSTOMER_RECALL, target_scope="customer")
    composed = make_test_composed(
        action_type=ActionType.CUSTOMER_RECALL,
        target_scope="customer",
        customer_id="c_001",
        suppression_key="recall:c_001:6mo",
    )
    cust_opted_out = CustomerStateModel(
        customer_id="c_001",
        merchant_id="m_001",
        identity=CustomerIdentity(name="Test User", language_pref="english"),
        relationship=Relationship(),
        state="active",
        consent=Consent(scope=["recall_reminders"]),
        preferences=CustomerPreferences(reminder_opt_in=False),
    )
    res = evaluate_outreach(
        decision=decision,
        composed=composed,
        customer=cust_opted_out,
        now="2026-04-26T10:00:00Z",
        history=[],
    )
    assert res.disposition == OutreachDisposition.SUPPRESS
    assert res.reason_code == SuppressionReasonCode.CONSENT_RESTRICTED


def test_wait_and_end_preservation():
    """Verify Phase 2 WAIT and END decisions are always suppressed fail-closed."""
    d_wait = make_test_decision(action_type=ActionType.WAIT)
    msg_wait = make_test_composed(action="wait", action_type=ActionType.WAIT, body="")
    res_wait = evaluate_outreach(decision=d_wait, composed=msg_wait, now="2026-04-26T10:00:00Z", history=[])
    assert res_wait.disposition == OutreachDisposition.SUPPRESS
    assert res_wait.reason_code == SuppressionReasonCode.DECISION_WAIT_OR_END

    d_end = make_test_decision(action_type=ActionType.END)
    msg_end = make_test_composed(action="end", action_type=ActionType.END, body="")
    res_end = evaluate_outreach(decision=d_end, composed=msg_end, now="2026-04-26T10:00:00Z", history=[])
    assert res_end.disposition == OutreachDisposition.SUPPRESS
    assert res_end.reason_code == SuppressionReasonCode.DECISION_WAIT_OR_END
