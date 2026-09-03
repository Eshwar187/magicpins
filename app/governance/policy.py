"""Deterministic outreach governance policy: exact suppression-key deduplication and consent validation."""

from __future__ import annotations

from typing import List, Optional

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decide import Decision
from app.composer.message import ComposedMessage
from app.governance.models import (
    OutreachAuditTrace,
    OutreachDecision,
    OutreachDisposition,
    OutreachRecord,
    SuppressionReasonCode,
)


def get_tenant_key(target_scope: str, merchant_id: Optional[str], customer_id: Optional[str]) -> str:
    """Compute composite tenant isolation key to prevent cross-tenant collision."""
    if target_scope == "customer" and customer_id:
        return f"c:{merchant_id or 'unknown'}:{customer_id}"
    return f"m:{merchant_id or 'unknown'}"


def evaluate_outreach(
    decision: Decision,
    composed: ComposedMessage,
    now: str,
    history: List[OutreachRecord],
    category: Optional[CategoryProfile] = None,
    merchant: Optional[MerchantState] = None,
    trigger: Optional[TriggerState] = None,
    customer: Optional[CustomerStateModel] = None,
) -> OutreachDecision:
    """Evaluate transmission eligibility against exact deduplication and consent rules.
    
    Zero wall-clock time. Fully deterministic.
    """
    target_scope = decision.target_scope or composed.target_scope or "merchant"
    merchant_id = merchant.merchant_id if merchant else composed.merchant_id
    customer_id = customer.customer_id if customer else composed.customer_id
    supp_key = composed.suppression_key or (trigger.suppression_key if trigger else "")
    tenant_key = get_tenant_key(target_scope, merchant_id, customer_id)

    # 1. Decision WAIT / END preservation
    if decision.action_type in (ActionType.WAIT, ActionType.END) or composed.action in ("wait", "end"):
        return OutreachDecision(
            disposition=OutreachDisposition.SUPPRESS,
            reason_code=SuppressionReasonCode.DECISION_WAIT_OR_END,
            reason="Phase 2 determined to stand down (WAIT/END). Outreach suppressed to honor restraint.",
            suppression_key=supp_key,
            target_scope=target_scope,
            merchant_id=merchant_id,
            customer_id=customer_id,
            simulated_at=now,
            audit_trace=OutreachAuditTrace(
                trigger_id=trigger.id if trigger else "",
                target_scope=target_scope,
                suppression_key=supp_key,
                evaluated_at=now,
                rule_applied="decision_wait_or_end",
            ),
        )

    # 2. Composed Message Structural Validation
    if not composed.body or not composed.body.strip():
        return OutreachDecision(
            disposition=OutreachDisposition.SUPPRESS,
            reason_code=SuppressionReasonCode.INVALID_COMPOSITION,
            reason="Composed message has empty body. Suppressing empty outbound payload.",
            suppression_key=supp_key,
            target_scope=target_scope,
            merchant_id=merchant_id,
            customer_id=customer_id,
            simulated_at=now,
            audit_trace=OutreachAuditTrace(
                trigger_id=trigger.id if trigger else "",
                target_scope=target_scope,
                suppression_key=supp_key,
                evaluated_at=now,
                rule_applied="empty_body_check",
            ),
        )

    if not supp_key:
        return OutreachDecision(
            disposition=OutreachDisposition.SUPPRESS,
            reason_code=SuppressionReasonCode.INVALID_COMPOSITION,
            reason="Missing required suppression key in composed outreach.",
            suppression_key="",
            target_scope=target_scope,
            merchant_id=merchant_id,
            customer_id=customer_id,
            simulated_at=now,
            audit_trace=OutreachAuditTrace(
                trigger_id=trigger.id if trigger else "",
                target_scope=target_scope,
                suppression_key="",
                evaluated_at=now,
                rule_applied="missing_suppression_key",
            ),
        )

    # 3. Customer Consent Validation (Fail-closed)
    if target_scope == "customer":
        if customer is None:
            return OutreachDecision(
                disposition=OutreachDisposition.SUPPRESS,
                reason_code=SuppressionReasonCode.CONSENT_RESTRICTED,
                reason="Customer scope specified but customer context is missing.",
                suppression_key=supp_key,
                target_scope=target_scope,
                merchant_id=merchant_id,
                customer_id=customer_id,
                simulated_at=now,
            )

        if customer.preferences.reminder_opt_in is False:
            return OutreachDecision(
                disposition=OutreachDisposition.SUPPRESS,
                reason_code=SuppressionReasonCode.CONSENT_RESTRICTED,
                reason="Customer explicitly opted out of reminder outreach (reminder_opt_in=False).",
                suppression_key=supp_key,
                target_scope=target_scope,
                merchant_id=merchant_id,
                customer_id=customer_id,
                simulated_at=now,
            )

        if customer.consent is None or (customer.consent.scope is not None and len(customer.consent.scope) == 0):
            return OutreachDecision(
                disposition=OutreachDisposition.SUPPRESS,
                reason_code=SuppressionReasonCode.CONSENT_RESTRICTED,
                reason="Customer has empty or missing consent scope.",
                suppression_key=supp_key,
                target_scope=target_scope,
                merchant_id=merchant_id,
                customer_id=customer_id,
                simulated_at=now,
            )

    # 4. Exact Suppression Key Deduplication (Category A)
    # If the exact (tenant_key, suppression_key) has already been transmitted in history -> DUPLICATE_SUPPRESSED
    matching_key_records = [
        r for r in history
        if r.tenant_key == tenant_key and r.suppression_key == supp_key
    ]

    if matching_key_records:
        latest_match = matching_key_records[-1]
        return OutreachDecision(
            disposition=OutreachDisposition.SUPPRESS,
            reason_code=SuppressionReasonCode.DUPLICATE_SUPPRESSED,
            reason=f"Outreach with suppression key '{supp_key}' was already transmitted for tenant '{tenant_key}'.",
            suppression_key=supp_key,
            target_scope=target_scope,
            merchant_id=merchant_id,
            customer_id=customer_id,
            simulated_at=now,
            previous_outreach_id=latest_match.record_id,
            audit_trace=OutreachAuditTrace(
                trigger_id=trigger.id if trigger else "",
                target_scope=target_scope,
                suppression_key=supp_key,
                evaluated_at=now,
                rule_applied="exact_suppression_key_dedup",
                prior_outreach_id=latest_match.record_id,
                prior_send_timestamp=latest_match.simulated_at,
            ),
        )

    # 5. Passed All Gates -> ELIGIBLE
    return OutreachDecision(
        disposition=OutreachDisposition.SEND,
        reason_code=SuppressionReasonCode.ELIGIBLE,
        reason="Outreach passed all governance, deduplication, and consent criteria.",
        suppression_key=supp_key,
        target_scope=target_scope,
        merchant_id=merchant_id,
        customer_id=customer_id,
        simulated_at=now,
        audit_trace=OutreachAuditTrace(
            trigger_id=trigger.id if trigger else "",
            target_scope=target_scope,
            suppression_key=supp_key,
            evaluated_at=now,
            rule_applied="all_governance_gates_passed",
        ),
    )
