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
    COOLDOWN_DAILY,
    COOLDOWN_WEEKLY,
    evaluate_outreach,
    get_suppression_cooldown_window,
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


def test_duplicate_suppression_active_cooldown():
    """Verify outreach with identical suppression key within cooldown window is suppressed."""
    decision = make_test_decision()
    composed = make_test_composed(suppression_key="research:dentists:2026-W17")
    
    # Prior send 2 hours ago
    record = OutreachRecord(
        record_id="rec_1",
        tenant_key="m:m_001",
        merchant_id="m_001",
        action_type=decision.action_type.value,
        target_scope="merchant",
        suppression_key="research:dentists:2026-W17",
        simulated_at="2026-04-26T08:00:00Z",
        conversation_id="conv_1",
        trigger_id="trg_1",
    )
    res = evaluate_outreach(
        decision=decision,
        composed=composed,
        now="2026-04-26T10:00:00Z",
        history=[record],
    )
    assert res.disposition == OutreachDisposition.SUPPRESS
    assert res.reason_code == SuppressionReasonCode.COOLDOWN_ACTIVE


def test_expired_cooldown_allowed():
    """Verify outreach with identical suppression key after cooldown window expires is allowed."""
    decision = make_test_decision()
    # Daily key has 86,400s (24h) cooldown
    composed = make_test_composed(suppression_key="event:delivery:m_001:2026-04-26")
    
    # Prior send was 30 hours ago
    record = OutreachRecord(
        record_id="rec_1",
        tenant_key="m:m_001",
        merchant_id="m_001",
        action_type=decision.action_type.value,
        target_scope="merchant",
        suppression_key="event:delivery:m_001:2026-04-26",
        simulated_at="2026-04-25T04:00:00Z",
        conversation_id="conv_1",
        trigger_id="trg_1",
    )
    res = evaluate_outreach(
        decision=decision,
        composed=composed,
        now="2026-04-26T10:00:00Z",
        history=[record],
    )
    assert res.disposition == OutreachDisposition.SEND
    assert res.reason_code == SuppressionReasonCode.ELIGIBLE


def test_merchant_frequency_cap():
    """Verify second proactive message to same merchant within 24h is suppressed under frequency cap."""
    decision = make_test_decision()
    composed = make_test_composed(suppression_key="different_key_curious_ask:m_001")
    
    # Different suppression key, but sent 4 hours ago to same merchant
    record = OutreachRecord(
        record_id="rec_prior",
        tenant_key="m:m_001",
        merchant_id="m_001",
        action_type="some_other_action",
        target_scope="merchant",
        suppression_key="prior_different_key",
        simulated_at="2026-04-26T06:00:00Z",
        conversation_id="conv_prior",
        trigger_id="trg_prior",
    )
    res = evaluate_outreach(
        decision=decision,
        composed=composed,
        now="2026-04-26T10:00:00Z",
        history=[record],
    )
    assert res.disposition == OutreachDisposition.SUPPRESS
    assert res.reason_code == SuppressionReasonCode.MERCHANT_FREQUENCY_CAPPED


def test_urgency_5_emergency_exemption_from_frequency_cap():
    """Verify urgency 5 emergency safety alert bypasses merchant daily frequency cap."""
    decision = make_test_decision(action_type=ActionType.ADDRESS_SUPPLY_ALERT)
    composed = make_test_composed(
        action_type=ActionType.ADDRESS_SUPPLY_ALERT,
        suppression_key="alert:atorvastatin:2026-04",
    )
    trg_urgent = TriggerState.from_dict({
        "id": "trg_alert", "scope": "merchant", "kind": "supply_alert",
        "source": "external", "merchant_id": "m_001", "payload": {},
        "urgency": 5, "suppression_key": "alert:atorvastatin:2026-04"
    })
    
    # Prior proactive outreach sent 2 hours ago
    record = OutreachRecord(
        record_id="rec_prior",
        tenant_key="m:m_001",
        merchant_id="m_001",
        action_type="prior_action",
        target_scope="merchant",
        suppression_key="prior_key",
        simulated_at="2026-04-26T08:00:00Z",
        conversation_id="conv_prior",
        trigger_id="trg_prior",
    )
    res = evaluate_outreach(
        decision=decision,
        composed=composed,
        trigger=trg_urgent,
        now="2026-04-26T10:00:00Z",
        history=[record],
    )
    assert res.disposition == OutreachDisposition.SEND
    assert res.reason_code == SuppressionReasonCode.ELIGIBLE


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


def test_backwards_simulation_time():
    """Verify backwards simulation time is handled safely as duplicate suppression."""
    decision = make_test_decision()
    composed = make_test_composed(suppression_key="test_key")
    record = OutreachRecord(
        record_id="rec_future",
        tenant_key="m:m_001",
        merchant_id="m_001",
        action_type="test",
        target_scope="merchant",
        suppression_key="test_key",
        simulated_at="2026-04-26T12:00:00Z",
        conversation_id="conv_1",
        trigger_id="trg_1",
    )
    res = evaluate_outreach(
        decision=decision,
        composed=composed,
        now="2026-04-26T10:00:00Z",  # Earlier than record!
        history=[record],
    )
    assert res.disposition == OutreachDisposition.SUPPRESS
    assert res.reason_code == SuppressionReasonCode.DUPLICATE_SUPPRESSED
