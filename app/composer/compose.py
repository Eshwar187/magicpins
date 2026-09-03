"""Master orchestration module for Phase 3 message composition."""

from typing import Any, Dict, Optional, Union

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decision import Decision
from app.composer.message import ComposedMessage
from app.composer.renderer import render_decision, _build_conversation_id, _build_suppression_key
from app.composer.validators import validate_composed_message


def compose(
    decision: Decision,
    category: Union[CategoryProfile, Dict[str, Any]],
    merchant: Union[MerchantState, Dict[str, Any]],
    trigger: Union[TriggerState, Dict[str, Any]],
    customer: Optional[Union[CustomerStateModel, Dict[str, Any]]] = None,
    state: Optional[Dict[str, Any]] = None,
) -> ComposedMessage:
    """Deterministically transform an authoritative Phase 2 Decision into a composed message draft.

    Args:
        decision: Authoritative decision from Phase 2 decide()
        category: Category profile (normalized or raw dict)
        merchant: Merchant state (normalized or raw dict)
        trigger: Trigger state (normalized or raw dict)
        customer: Optional customer state (normalized or raw dict)
        state: Optional ongoing conversation state

    Returns:
        ComposedMessage: Fully grounded, structured message draft.
    """
    # 1. Normalize Context Inputs if dicts provided
    if isinstance(category, dict):
        category = CategoryProfile.from_dict(category)
    if isinstance(merchant, dict):
        merchant = MerchantState.from_dict(merchant)
    if isinstance(trigger, dict):
        trigger = TriggerState.from_dict(trigger)
    if isinstance(customer, dict):
        customer = CustomerStateModel.from_dict(customer)

    # 2. Enforce Phase 2 Decision Authority (Hard Boundary)
    act = decision.action_type
    target_scope = decision.target_scope
    conv_id = _build_conversation_id(trigger, merchant, customer)
    suppression_key = _build_suppression_key(decision, category, merchant, trigger, customer)
    cid = customer.customer_id if customer else None

    # 3. Handle Non-Outreach Actions (WAIT & END)
    if act == ActionType.WAIT:
        composed = ComposedMessage(
            action="wait",
            action_type=ActionType.WAIT,
            target_scope=target_scope,
            send_as="vera",
            body="",
            cta="none",
            suppression_key=suppression_key,
            rationale=decision.primary_reason or "Standing down based on Phase 2 safety/consent policy",
            conversation_id=conv_id,
            merchant_id=merchant.merchant_id,
            customer_id=cid,
            trigger_id=trigger.id,
            template_name="noop_wait_v1",
            template_params=[],
        )
        return composed

    if act == ActionType.END:
        composed = ComposedMessage(
            action="end",
            action_type=ActionType.END,
            target_scope=target_scope,
            send_as="vera",
            body="",
            cta="none",
            suppression_key=suppression_key,
            rationale=decision.primary_reason or "Conversation terminated by Phase 2 policy",
            conversation_id=conv_id,
            merchant_id=merchant.merchant_id,
            customer_id=cid,
            trigger_id=trigger.id,
            template_name="noop_end_v1",
            template_params=[],
        )
        return composed

    # 4. Render Actionable Decision
    tmpl_name, body, cta, send_as, supp_key, tmpl_params, conv_id = render_decision(
        decision, category, merchant, trigger, customer
    )

    rationale = (
        f"Composed {act.value} for {target_scope} scope. "
        f"Reason: {decision.primary_reason}. "
        f"Grounded in {len(decision.evidence_facts)} verified facts."
    )

    composed = ComposedMessage(
        action="send",
        action_type=act,
        target_scope=target_scope,
        send_as=send_as,
        body=body,
        cta=cta,
        suppression_key=supp_key,
        rationale=rationale,
        conversation_id=conv_id,
        merchant_id=merchant.merchant_id,
        customer_id=cid,
        trigger_id=trigger.id,
        template_name=tmpl_name,
        template_params=tmpl_params,
    )

    # 5. Strict Deterministic Validation
    is_valid, errors = validate_composed_message(
        composed, decision, category, merchant, trigger, customer
    )
    if not is_valid:
        raise ValueError(f"Message composition validation failed: {'; '.join(errors)}")

    return composed


def compose_action_continuation(
    decision: Decision,
    category: Union[CategoryProfile, Dict[str, Any]],
    merchant: Union[MerchantState, Dict[str, Any]],
    trigger: Union[TriggerState, Dict[str, Any]],
    customer: Optional[Union[CustomerStateModel, Dict[str, Any]]] = None,
) -> ComposedMessage:
    """Compose a deterministic continuation message advancing an approved Phase 2 action."""
    if isinstance(category, dict):
        category = CategoryProfile.from_dict(category)
    if isinstance(merchant, dict):
        merchant = MerchantState.from_dict(merchant)
    if isinstance(trigger, dict):
        trigger = TriggerState.from_dict(trigger)
    if isinstance(customer, dict):
        customer = CustomerStateModel.from_dict(customer)

    act = decision.action_type
    target_scope = decision.target_scope
    conv_id = _build_conversation_id(trigger, merchant, customer)
    suppression_key = _build_suppression_key(decision, category, merchant, trigger, customer)
    cid = customer.customer_id if customer else None

    # Handle Non-Outreach Actions (WAIT & END)
    if act == ActionType.WAIT:
        return ComposedMessage(
            action="wait",
            action_type=ActionType.WAIT,
            target_scope=target_scope,
            send_as="vera",
            body="",
            cta="none",
            suppression_key=suppression_key,
            rationale=decision.primary_reason or "Standing down based on Phase 2 safety policy",
            conversation_id=conv_id,
            merchant_id=merchant.merchant_id,
            customer_id=cid,
            trigger_id=trigger.id,
            template_name="noop_wait_v1",
            template_params=[],
        )

    if act == ActionType.END:
        return ComposedMessage(
            action="end",
            action_type=ActionType.END,
            target_scope=target_scope,
            send_as="vera",
            body="",
            cta="none",
            suppression_key=suppression_key,
            rationale=decision.primary_reason or "Conversation terminated by Phase 2 policy",
            conversation_id=conv_id,
            merchant_id=merchant.merchant_id,
            customer_id=cid,
            trigger_id=trigger.id,
            template_name="noop_end_v1",
            template_params=[],
        )

    payload = trigger.payload if trigger else {}

    # Deterministic actioning body grounded directly in the Phase 2 action and facts
    if act == ActionType.USE_RESEARCH_INSIGHT:
        finding = payload.get("finding_summary") or payload.get("summary") or "preventive procedure protocols"
        pub = payload.get("publication_name") or payload.get("journal") or "recent clinical study"
        body = (
            f"Here is the patient-education summary on {finding} from {pub} ready to confirm and share. "
            "Confirm to proceed with sending."
        )
    elif act == ActionType.PROMOTE_DELIVERY_OFFER:
        match_name = payload.get("match_name") or payload.get("event") or "match-day"
        body = (
            f"Here is the delivery promotion campaign for {match_name} ready to confirm and launch. "
            "Confirm when ready to proceed!"
        )
    elif act == ActionType.CUSTOMER_RECALL:
        cust_name = customer.identity.name if customer else "the customer"
        svc = payload.get("service_due") or payload.get("service") or "routine recall"
        body = (
            f"Here is the {svc} recall reminder ready to dispatch to {cust_name}. "
            "Confirm when ready to proceed with dispatch."
        )
    elif act == ActionType.CONTINUE_PLANNING:
        topic = payload.get("intent_topic") or "catering package"
        body = (
            f"Here is the {topic} proposal ready to confirm and finalize. "
            "Confirm when ready to proceed with the next step."
        )
    elif act == ActionType.REFRAME_SEASONAL_DIP:
        metric = payload.get("metric") or "engagement"
        body = (
            f"Here is the seasonal {metric} campaign proposal ready to confirm. "
            "Confirm when ready to proceed with rollout."
        )
    elif act == ActionType.CUSTOMER_WINBACK:
        cust_name = customer.identity.name if customer else "lapsed customer"
        body = (
            f"Here is the winback outreach message ready to dispatch to {cust_name}. "
            "Confirm when ready to proceed."
        )
    elif act == ActionType.ADDRESS_SUPPLY_ALERT:
        alert_item = payload.get("molecule") or payload.get("item_name") or "affected batch"
        body = (
            f"Here is the verified advisory for {alert_item} ready to dispatch to affected patients. "
            "Confirm when ready to proceed."
        )
    elif act == ActionType.CUSTOMER_REFILL:
        cust_name = customer.identity.name if customer else "the patient"
        med = payload.get("medication_name") or payload.get("condition") or "routine refill"
        body = (
            f"Here is the {med} refill reminder ready to dispatch to {cust_name}. "
            "Confirm when ready to proceed."
        )
    else:
        act_name = act.value.replace("_", " ")
        body = (
            f"Here is the {act_name} draft ready to confirm and launch. "
            "Confirm when ready to proceed!"
        )

    return ComposedMessage(
        action="send",
        action_type=act,
        target_scope=target_scope,
        send_as="vera",
        body=body,
        cta="binary_confirm",
        suppression_key=suppression_key,
        rationale=f"Phase 3 grounded continuation for {act.value}. Advancing approved workflow upon merchant commitment.",
        conversation_id=conv_id,
        merchant_id=merchant.merchant_id,
        customer_id=cid,
        trigger_id=trigger.id,
        template_name=f"continuation_{act.value}_v1",
        template_params=["action_continuation"],
    )

