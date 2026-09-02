"""Deterministic candidate action generator linking grounded context to viable actions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.domain.facts.fact import Fact
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ACTION_DEFINITIONS, ActionType
from app.engine.decision import CandidateAction
from app.engine.signals import Signal, SignalType


def _filter_facts(facts: List[Fact], prefixes: Tuple[str, ...]) -> Tuple[Fact, ...]:
    """Helper to deterministically extract facts matching specific name prefixes."""
    return tuple(f for f in facts if any(f.name.startswith(p) for p in prefixes))


def generate_candidates(
    category: CategoryProfile,
    merchant: MerchantState,
    trigger: TriggerState,
    customer: Optional[CustomerStateModel],
    signals: List[Signal],
    facts: List[Fact],
) -> List[CandidateAction]:
    """Generates all legitimately viable candidate actions given context and signals.
    
    Zero guessing: candidate generation binds grounded facts as evidence.
    """
    signal_types = {s.signal_type for s in signals}
    candidates: List[CandidateAction] = []

    # Identify active merchant offers (NEVER category templates, NEVER expired)
    active_offers = [o for o in merchant.offers if o.status == "active"]
    delivery_offers = [
        o for o in active_offers
        if any(w in o.title.lower() for w in ("delivery", "bogo", "buy 1", "get 1", "takeaway", "pack", "online", "special", "combo"))
    ]
    primary_delivery_offer = delivery_offers[0].model_dump() if delivery_offers else None
    primary_active_offer = active_offers[0].model_dump() if active_offers else None

    # 1. Research Digest Insight
    if trigger.kind in ("research_digest", "cde_opportunity") or SignalType.RESEARCH_DIGEST_MATCHED in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("category.digest.matched", "trigger.payload", "merchant.customer_aggregate.high_risk_adult_count", "merchant.name")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.USE_RESEARCH_INSIGHT,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="draft_patient_education_note",
                primary_reason="Peer-reviewed clinical evidence directly matches merchant patient cohort",
            )
        )

    # 2. Customer Routine Recall
    if trigger.kind == "recall_due" or SignalType.CUSTOMER_RECALL_DUE in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("customer.name", "customer.state", "customer.preferred_slots", "customer.consent.scope",
             "trigger.payload.available_slots", "trigger.payload.service_due", "merchant.offer")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.CUSTOMER_RECALL,
                target_scope="customer",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                supporting_offer=primary_active_offer,
                next_step="invite_to_book_slots",
                primary_reason="Patient routine service recall window is open with concrete slots available",
            )
        )

    # 3. Customer Service Followup
    if trigger.kind in ("wedding_package_followup", "trial_followup") or SignalType.CUSTOMER_BRIDAL_WINDOW in signal_types or SignalType.CUSTOMER_TRIAL_FOLLOWUP in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("customer.name", "customer.preferred_slots", "customer.consent.scope",
             "trigger.payload.wedding_date", "trigger.payload.days_to_wedding", "trigger.payload.trial_date")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.CUSTOMER_FOLLOWUP,
                target_scope="customer",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                supporting_offer=primary_active_offer,
                next_step="confirm_first_package_session",
                primary_reason="Customer completed consultation/trial and is in optimal service preparation window",
            )
        )

    # 4. Merchant Curiosity Cadence Check-in
    if trigger.kind in ("curious_ask_due", "dormant_with_vera") or SignalType.CURIOUS_CADENCE_DUE in signal_types:
        ev_facts = _filter_facts(facts, ("merchant.name", "merchant.owner_first_name", "trigger.kind"))
        candidates.append(
            CandidateAction(
                action_type=ActionType.CURIOUS_ASK,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="inquire_weekly_demand",
                primary_reason="Weekly merchant curiosity cadence open with reciprocity drafting offer",
            )
        )

    # 5. Contrarian Event / Delivery Promotion
    if trigger.kind == "ipl_match_today" or SignalType.EVENT_TODAY in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("trigger.payload.match", "trigger.payload.venue", "trigger.payload.match_time_iso",
             "merchant.name", "merchant.locality", "merchant.offer")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.PROMOTE_DELIVERY_OFFER,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                supporting_offer=primary_delivery_offer,
                next_step="draft_delivery_campaign",
                primary_reason="Match day shifts covers away from dine-in; contrarian pivot to active delivery offer",
            )
        )

    # 6. Continue Active Planning Intent
    if trigger.kind == "active_planning_intent" or SignalType.ACTIVE_PLANNING_ACTIVE in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("trigger.payload.intent_topic", "merchant.name", "merchant.locality")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.CONTINUE_PLANNING,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="deliver_starter_package_structure",
                primary_reason="Merchant requested concrete packaging and pricing assistance on topic",
            )
        )

    # 7. Seasonal Performance Reframe
    if trigger.kind == "seasonal_perf_dip" or SignalType.IS_EXPECTED_SEASONAL in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("trigger.payload.delta_pct", "trigger.payload.metric", "trigger.payload.is_expected_seasonal",
             "merchant.performance.delta_7d", "merchant.customer_aggregate.total_active_members")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.REFRAME_SEASONAL_DIP,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="advise_retention_focus_over_ad_spend",
                primary_reason="Performance decline matches known category seasonal pattern; reframe to member retention",
            )
        )

    # 8. Customer Lapse Winback
    if trigger.kind in ("customer_lapsed_hard", "customer_lapsed_soft") or SignalType.CUSTOMER_LAPSED in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("customer.name", "customer.state", "customer.consent.scope", "customer.visits_total",
             "trigger.payload.days_since_last_visit", "trigger.payload.previous_focus", "merchant.offer")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.CUSTOMER_WINBACK,
                target_scope="customer",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                supporting_offer=primary_active_offer,
                next_step="offer_no_commitment_trial",
                primary_reason="Customer is lapsed; re-engage with tailored no-shame, low-friction trial",
            )
        )

    # 9. Supply Alert / Recall Notice
    if trigger.kind == "supply_alert" or SignalType.SUPPLY_ALERT_ACTIVE in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("trigger.payload.affected_batches", "trigger.payload.manufacturer", "trigger.payload.molecule",
             "merchant.customer_aggregate.chronic_rx_count", "merchant.name")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.ADDRESS_SUPPLY_ALERT,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="draft_patient_replacement_workflow",
                primary_reason="Regulatory / manufacturer batch alert requires customer notification and replacement workflow",
            )
        )

    # 10. Chronic Prescription Refill Reminder
    if trigger.kind == "chronic_refill_due" or SignalType.CUSTOMER_REFILL_DUE in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("customer.name", "customer.consent.scope", "trigger.payload.molecule_list",
             "trigger.payload.stock_runs_out_iso", "merchant.offer")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.CUSTOMER_REFILL,
                target_scope="customer",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                supporting_offer=primary_active_offer,
                next_step="confirm_refill_dispatch",
                primary_reason="Chronic prescription stock runs out soon; confirm dispatch to saved delivery address",
            )
        )

    # 11. Unexpected Performance Dip (Non-seasonal)
    if (trigger.kind == "perf_dip" or SignalType.PERF_CALLS_DROP_SEVERE in signal_types or SignalType.PERF_VIEWS_DROP_SEVERE in signal_types) and SignalType.IS_EXPECTED_SEASONAL not in signal_types:
        ev_facts = _filter_facts(
            facts,
            ("trigger.payload.delta_pct", "trigger.payload.metric", "merchant.performance.delta_7d",
             "merchant.performance.calls", "merchant.performance.views", "merchant.verified")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.ADDRESS_PERFORMANCE_DIP,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="diagnose_and_boost_channel",
                primary_reason="Unexpected performance drop requires immediate channel diagnosis and corrective action",
            )
        )

    # 12. Performance Spike
    if trigger.kind == "perf_spike" or SignalType.PERF_SPIKE in signal_types:
        ev_facts = _filter_facts(facts, ("trigger.payload.delta_pct", "trigger.payload.metric", "merchant.name"))
        candidates.append(
            CandidateAction(
                action_type=ActionType.CAPITALIZE_PERF_SPIKE,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="amplify_winning_channel",
                primary_reason="Strong performance momentum offers opportunity to double down on winning driver",
            )
        )

    # 13. Subscription Renewal
    if trigger.kind in ("renewal_due", "winback_eligible") or (
        trigger.kind in ("curious_ask_due", "dormant_with_vera")
        and (SignalType.SUBSCRIPTION_EXPIRING in signal_types or SignalType.SUBSCRIPTION_EXPIRED in signal_types)
    ):
        ev_facts = _filter_facts(
            facts,
            ("merchant.subscription", "trigger.payload.days_remaining", "trigger.payload.renewal_amount")
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.RENEW_SUBSCRIPTION,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="send_renewal_terms",
                primary_reason="Subscription plan is nearing expiry or expired; present clear renewal terms",
            )
        )

    # 14. Resolve Listing Issue
    if trigger.kind == "gbp_unverified" or (
        trigger.kind in ("curious_ask_due", "dormant_with_vera") and SignalType.UNVERIFIED_LISTING in signal_types
    ):
        ev_facts = _filter_facts(facts, ("merchant.verified", "trigger.payload.estimated_uplift_pct", "merchant.name"))
        candidates.append(
            CandidateAction(
                action_type=ActionType.RESOLVE_LISTING_ISSUE,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="guide_profile_verification",
                primary_reason="Unverified profile loses visibility; verification unlocks local search uplift",
            )
        )

    # 15. Competitor Opened
    if trigger.kind == "competitor_opened" or SignalType.COMPETITOR_OPENED in signal_types:
        ev_facts = _filter_facts(facts, ("trigger.payload.competitor_name", "trigger.payload.distance_km", "merchant.name"))
        candidates.append(
            CandidateAction(
                action_type=ActionType.ADDRESS_COMPETITOR_CHANGE,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                supporting_offer=primary_active_offer,
                next_step="counter_with_defensive_offer",
                primary_reason="New competitor opened nearby; counter with high-relevance local promotion",
            )
        )

    # 16. Review Theme
    if trigger.kind == "review_theme_emerged" or SignalType.REVIEW_THEME_EMERGED in signal_types:
        ev_facts = _filter_facts(facts, ("trigger.payload.theme", "merchant.review_themes", "merchant.name"))
        candidates.append(
            CandidateAction(
                action_type=ActionType.RESPOND_TO_REVIEW_THEME,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="adjust_operations_and_reply",
                primary_reason="Identified recurring customer sentiment theme across recent Google reviews",
            )
        )

    # 17. Milestone
    if trigger.kind == "milestone_reached" or SignalType.MILESTONE_REACHED in signal_types:
        ev_facts = _filter_facts(facts, ("trigger.payload.milestone_value", "trigger.payload.metric", "merchant.name"))
        candidates.append(
            CandidateAction(
                action_type=ActionType.CELEBRATE_MILESTONE,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                next_step="suggest_social_celebration_post",
                primary_reason="Merchant achieved significant order or review count milestone",
            )
        )

    # 18. Festival Campaign
    if trigger.kind == "festival_upcoming" or SignalType.FESTIVAL_UPCOMING in signal_types:
        ev_facts = _filter_facts(facts, ("trigger.payload.festival", "trigger.payload.days_until", "merchant.name"))
        candidates.append(
            CandidateAction(
                action_type=ActionType.PREPARE_FESTIVAL_CAMPAIGN,
                target_scope="merchant",
                supporting_trigger_id=trigger.id,
                evidence_facts=ev_facts,
                supporting_offer=primary_active_offer,
                next_step="schedule_advance_festival_promo",
                primary_reason="Upcoming festival creates seasonal consumer demand spike; prepare in advance",
            )
        )

    # 19. Stand-down / WAIT (Always available as a valid fallback)
    candidates.append(
        CandidateAction(
            action_type=ActionType.WAIT,
            target_scope="merchant" if customer is None else "customer",
            supporting_trigger_id=trigger.id,
            evidence_facts=(),
            next_step="stand_down",
            primary_reason="No proactive action justified by current evidence or consent status",
        )
    )

    return candidates
