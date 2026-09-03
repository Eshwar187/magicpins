"""Deterministic outreach governance policies: deduplication, cooldown, and frequency caps."""

from __future__ import annotations

import re
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
from app.governance.time_utils import calculate_simulation_delta_seconds

# Cooldown constants (seconds)
COOLDOWN_DAILY = 86_400.0          # 24 hours
COOLDOWN_WEEKLY = 604_800.0        # 7 days (168 hours)
COOLDOWN_MONTHLY = 2_592_000.0     # 30 days
COOLDOWN_QUARTERLY = 7_776_000.0   # 90 days


def get_suppression_cooldown_window(suppression_key: str) -> float:
    """Derive deterministic cooldown duration based on suppression key cadence tokens."""
    if not suppression_key:
        return COOLDOWN_WEEKLY

    key_lower = suppression_key.lower()

    # Quarterly e.g. 2026-Q2
    if re.search(r"\d{4}-q\d", key_lower):
        return COOLDOWN_QUARTERLY

    # Monthly e.g. 2026-04
    if re.search(r"\d{4}-\d{2}$", key_lower) or ":30d" in key_lower or ":6mo" in key_lower:
        return COOLDOWN_MONTHLY

    # Daily date e.g. 2026-04-26
    if re.search(r"\d{4}-\d{2}-\d{2}", key_lower):
        return COOLDOWN_DAILY

    # Weekly token e.g. 2026-W17
    if re.search(r"\d{4}-w\d{1,2}", key_lower):
        return COOLDOWN_WEEKLY

    return COOLDOWN_WEEKLY


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
    """Evaluate transmission eligibility against governance, cooldown, and frequency rules.
    
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

    # 4. Exact Suppression Key Cooldown & Deduplication
    cooldown_window = get_suppression_cooldown_window(supp_key)
    matching_key_records = [
        r for r in history
        if r.tenant_key == tenant_key and r.suppression_key == supp_key
    ]

    if matching_key_records:
        latest_match = matching_key_records[-1]
        delta_s = calculate_simulation_delta_seconds(now, latest_match.simulated_at)

        if delta_s is not None and delta_s < 0:
            # Backwards simulation time -> fail safe by suppressing duplicate
            return OutreachDecision(
                disposition=OutreachDisposition.SUPPRESS,
                reason_code=SuppressionReasonCode.DUPLICATE_SUPPRESSED,
                reason=f"Current simulation time {now} is earlier than recorded send {latest_match.simulated_at}.",
                suppression_key=supp_key,
                target_scope=target_scope,
                merchant_id=merchant_id,
                customer_id=customer_id,
                simulated_at=now,
                previous_outreach_id=latest_match.record_id,
            )

        if delta_s is not None and delta_s < cooldown_window:
            return OutreachDecision(
                disposition=OutreachDisposition.SUPPRESS,
                reason_code=SuppressionReasonCode.COOLDOWN_ACTIVE,
                reason=(
                    f"Outreach suppression key '{supp_key}' is active in cooldown "
                    f"({delta_s:.0f}s elapsed < {cooldown_window:.0f}s window)."
                ),
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
                    rule_applied="exact_key_cooldown",
                    last_matching_send=latest_match.simulated_at,
                    seconds_since_last_send=delta_s,
                    cooldown_window_seconds=cooldown_window,
                ),
            )

    # 5. Customer Frequency Cap (Max 1 outreach per 7 days per customer)
    if target_scope == "customer" and customer_id:
        customer_records = [r for r in history if r.customer_id == customer_id and r.merchant_id == merchant_id]
        if customer_records:
            latest_cust = customer_records[-1]
            delta_s = calculate_simulation_delta_seconds(now, latest_cust.simulated_at)
            if delta_s is not None and delta_s >= 0 and delta_s < COOLDOWN_WEEKLY:
                return OutreachDecision(
                    disposition=OutreachDisposition.SUPPRESS,
                    reason_code=SuppressionReasonCode.CUSTOMER_FREQUENCY_CAPPED,
                    reason=(
                        f"Customer '{customer_id}' frequency cap reached: "
                        f"last message sent {delta_s:.0f}s ago (min gap: {COOLDOWN_WEEKLY:.0f}s)."
                    ),
                    suppression_key=supp_key,
                    target_scope=target_scope,
                    merchant_id=merchant_id,
                    customer_id=customer_id,
                    simulated_at=now,
                    previous_outreach_id=latest_cust.record_id,
                    audit_trace=OutreachAuditTrace(
                        trigger_id=trigger.id if trigger else "",
                        target_scope=target_scope,
                        suppression_key=supp_key,
                        evaluated_at=now,
                        rule_applied="customer_frequency_cap",
                        last_matching_send=latest_cust.simulated_at,
                        seconds_since_last_send=delta_s,
                        cooldown_window_seconds=COOLDOWN_WEEKLY,
                    ),
                )

    # 6. Merchant Frequency Cap (Max 1 proactive message per 24 hours per merchant)
    # Emergency Exemption: Urgency == 5 (e.g. drug safety recall alerts) bypass non-safety rate caps.
    urgency = trigger.urgency if trigger else 1
    if target_scope == "merchant" and merchant_id and urgency < 5:
        merchant_records = [
            r for r in history
            if r.merchant_id == merchant_id and r.target_scope == "merchant"
        ]
        if merchant_records:
            latest_m = merchant_records[-1]
            delta_s = calculate_simulation_delta_seconds(now, latest_m.simulated_at)
            if delta_s is not None and delta_s >= 0 and delta_s < COOLDOWN_DAILY:
                return OutreachDecision(
                    disposition=OutreachDisposition.SUPPRESS,
                    reason_code=SuppressionReasonCode.MERCHANT_FREQUENCY_CAPPED,
                    reason=(
                        f"Merchant '{merchant_id}' daily frequency cap reached: "
                        f"last proactive outreach sent {delta_s:.0f}s ago (min gap: {COOLDOWN_DAILY:.0f}s)."
                    ),
                    suppression_key=supp_key,
                    target_scope=target_scope,
                    merchant_id=merchant_id,
                    customer_id=customer_id,
                    simulated_at=now,
                    previous_outreach_id=latest_m.record_id,
                    audit_trace=OutreachAuditTrace(
                        trigger_id=trigger.id if trigger else "",
                        target_scope=target_scope,
                        suppression_key=supp_key,
                        evaluated_at=now,
                        rule_applied="merchant_daily_frequency_cap",
                        last_matching_send=latest_m.simulated_at,
                        seconds_since_last_send=delta_s,
                        cooldown_window_seconds=COOLDOWN_DAILY,
                    ),
                )

    # 7. Passed All Gates -> ELIGIBLE
    return OutreachDecision(
        disposition=OutreachDisposition.SEND,
        reason_code=SuppressionReasonCode.ELIGIBLE,
        reason="Outreach passed all governance, cooldown, and frequency criteria.",
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
