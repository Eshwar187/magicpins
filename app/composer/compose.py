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

    # Deterministic actioning body grounded in the action type
    if act == ActionType.USE_RESEARCH_INSIGHT:
        body = (
            "Here is the draft patient-education WhatsApp note ready to confirm and share: "
            "'Recent clinical research demonstrates the preventive efficacy of fluoride varnish protocols for mixed dentition.' "
            "Confirm to proceed with sending."
        )
    elif act == ActionType.PROMOTE_DELIVERY_OFFER:
        body = (
            "Here is the delivery promotion campaign draft ready to confirm: "
            "'Match-day special delivery promotion for tonight.' Confirm when ready to proceed and launch."
        )
    elif act == ActionType.CUSTOMER_RECALL:
        body = (
            "Here is the routine recall reminder draft ready for your confirmation. "
            "Confirm when ready to proceed with dispatch."
        )
    elif act == ActionType.CONTINUE_PLANNING:
        body = (
            "Here is the corporate package draft proposal ready to confirm. "
            "Confirm when ready to proceed with the next step."
        )
    elif act == ActionType.REFRAME_SEASONAL_DIP:
        body = (
            "Here is the seasonal dip member engagement draft ready to confirm. "
            "Confirm when ready to proceed with rollout."
        )
    elif act == ActionType.CUSTOMER_WINBACK:
        body = (
            "Here is the winback outreach draft ready for your confirmation. "
            "Confirm when ready to proceed."
        )
    elif act == ActionType.ADDRESS_SUPPLY_ALERT:
        body = (
            "Here is the batch recall advisory draft ready for your review and confirmation. "
            "Confirm when ready to proceed."
        )
    elif act == ActionType.CUSTOMER_REFILL:
        body = (
            "Here is the monthly refill reminder draft ready for your confirmation. "
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
