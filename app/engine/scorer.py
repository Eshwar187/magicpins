"""Deterministic candidate scoring, eligibility evaluation, and tie-breaking."""

from __future__ import annotations

from typing import List, Tuple

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ACTION_DEFINITIONS, ActionType, PriorityTier
from app.engine.decision import CandidateAction, CandidateEvaluation
from app.engine.signals import Signal, SignalType


def evaluate_eligibility(
    candidate: CandidateAction,
    category: CategoryProfile,
    merchant: MerchantState,
    trigger: TriggerState,
    customer: CustomerStateModel | None,
    signals: List[Signal],
) -> Tuple[bool, Tuple[str, ...]]:
    """Evaluates whether a candidate action is legally and contextually eligible.
    
    Strict fail-closed checks for category fit, consent, offers, and evidence.
    """
    reasons: List[str] = []
    action_def = ACTION_DEFINITIONS.get(candidate.action_type)
    if not action_def:
        return False, ("unknown_action_type",)

    signal_types = {s.signal_type for s in signals}

    # 0. Scope Alignment Check (Customer triggers evaluate customer actions; merchant triggers evaluate merchant actions)
    if candidate.action_type not in (ActionType.WAIT, ActionType.END):
        if candidate.target_scope != trigger.scope:
            reasons.append(f"scope_mismatch_trigger_{trigger.scope}_candidate_{candidate.target_scope}")

    # 1. Category Constraint Check
    if action_def.allowed_categories is not None:
        if category.slug not in action_def.allowed_categories:
            reasons.append(f"category_{category.slug}_not_permitted")

    # 2. Customer Consent Check (Must fail closed!)
    if action_def.requires_customer_consent:
        if customer is None:
            reasons.append("customer_context_missing")
        elif SignalType.CUSTOMER_OPTED_OUT in signal_types:
            reasons.append("customer_consent_missing_or_opted_out")
        elif SignalType.CUSTOMER_CONSENT_VALID not in signal_types:
            reasons.append("valid_consent_unverified")

    # 3. Active Merchant Offer Check (No expired offers, no category catalog masquerading!)
    if action_def.requires_active_merchant_offer:
        offer = candidate.supporting_offer
        if not offer:
            reasons.append("active_merchant_offer_missing")
        else:
            if offer.get("status") != "active":
                reasons.append("supporting_offer_not_active")
            # Verify offer actually belongs to merchant
            merchant_offer_ids = {o.id for o in merchant.offers}
            if offer.get("id") not in merchant_offer_ids:
                reasons.append("offer_not_owned_by_merchant")

    # Specific delivery offer check
    if candidate.action_type == ActionType.PROMOTE_DELIVERY_OFFER:
        if SignalType.HAS_DELIVERY_OFFER not in signal_types:
            reasons.append("active_delivery_offer_required")

    # 4. Seasonality Preemption: Expected seasonal dips must NOT trigger alarmist interventions
    if candidate.action_type == ActionType.ADDRESS_PERFORMANCE_DIP:
        if SignalType.IS_EXPECTED_SEASONAL in signal_types:
            reasons.append("expected_seasonal_dip_preempts_alarmist_intervention")

    # 5. Evidence Requirement Check (No fabricated actions!)
    if candidate.action_type not in (ActionType.WAIT, ActionType.END):
        if len(candidate.evidence_facts) == 0:
            reasons.append("insufficient_grounded_evidence")

    # 6. Specific Action Prerequisites
    if candidate.action_type == ActionType.USE_RESEARCH_INSIGHT:
        if SignalType.RESEARCH_DIGEST_MATCHED not in signal_types:
            reasons.append("no_matching_clinical_digest_item")

    if candidate.action_type == ActionType.ADDRESS_SUPPLY_ALERT:
        if SignalType.SUPPLY_ALERT_ACTIVE not in signal_types:
            reasons.append("no_active_supply_alert")

    if candidate.action_type == ActionType.CUSTOMER_RECALL:
        if not trigger.available_slots:
            reasons.append("no_open_slots_available_for_recall")

    is_eligible = len(reasons) == 0
    return is_eligible, tuple(reasons)


def score_candidate(
    candidate: CandidateAction,
    category: CategoryProfile,
    trigger: TriggerState,
    signals: List[Signal],
    is_eligible: bool,
) -> Tuple[float, dict[str, float]]:
    """Computes a transparent, deterministic score (0 - 100) for a candidate.
    
    If ineligible, score is strictly 0.0.
    """
    if not is_eligible:
        return 0.0, {
            "trigger_relevance": 0.0,
            "evidence_strength": 0.0,
            "category_fit": 0.0,
            "actionability": 0.0,
            "urgency": 0.0,
        }

    # WAIT fallback has a minimal baseline score
    if candidate.action_type == ActionType.WAIT:
        return 10.0, {
            "trigger_relevance": 5.0,
            "evidence_strength": 0.0,
            "category_fit": 5.0,
            "actionability": 0.0,
            "urgency": 0.0,
        }

    signal_types = {s.signal_type for s in signals}

    # 1. Trigger Relevance (0 - 40)
    trigger_rel = 40.0

    # 2. Evidence Strength (0 - 25)
    # Grounded fact count rewarded up to 5 facts (5 pts each)
    ev_count = len(candidate.evidence_facts)
    evidence_score = min(float(ev_count * 5.0), 25.0)

    # 3. Category Fit (0 - 15)
    action_def = ACTION_DEFINITIONS[candidate.action_type]
    if action_def.allowed_categories and category.slug in action_def.allowed_categories:
        cat_fit = 15.0
    else:
        cat_fit = 10.0

    # 4. Actionability Bonus (0 - 10)
    actionability = 0.0
    if candidate.supporting_offer is not None and candidate.supporting_offer.get("status") == "active":
        actionability += 5.0
    if candidate.next_step:
        actionability += 5.0

    # 5. Urgency Normalized (0 - 10)
    urgency_score = min(max(float(trigger.urgency * 2.0), 2.0), 10.0)

    # Contrarian & Category Boosts
    if candidate.action_type == ActionType.PROMOTE_DELIVERY_OFFER:
        if SignalType.EVENT_HOME_VIEWING_SHIFT in signal_types:
            # High-signal contrarian pivot during home-viewing cover drop
            trigger_rel += 5.0
            cat_fit = 15.0

    if candidate.action_type == ActionType.REFRAME_SEASONAL_DIP:
        if SignalType.IS_EXPECTED_SEASONAL in signal_types:
            trigger_rel += 5.0

    breakdown = {
        "trigger_relevance": trigger_rel,
        "evidence_strength": evidence_score,
        "category_fit": cat_fit,
        "actionability": actionability,
        "urgency": urgency_score,
    }
    total = sum(breakdown.values())
    return total, breakdown


def rank_and_select_winner(
    candidates: List[CandidateAction],
    category: CategoryProfile,
    merchant: MerchantState,
    trigger: TriggerState,
    customer: CustomerStateModel | None,
    signals: List[Signal],
) -> Tuple[CandidateAction, Tuple[CandidateEvaluation, ...], Optional[str]]:
    """Evaluates, scores, and deterministically ranks all candidates.
    
    Tie-breaking hierarchy:
    1. is_eligible (True before False)
    2. total_score descending
    3. priority_tier ascending (Tier 1 > Tier 2 > Tier 3 > Tier 4 > Tier 5)
    4. trigger.urgency descending
    5. action_type.value alphabetical ascending
    """
    evaluations: List[CandidateEvaluation] = []
    scored_candidates: List[CandidateAction] = []

    for c in candidates:
        is_eligible, inelig_reasons = evaluate_eligibility(
            c, category, merchant, trigger, customer, signals
        )
        score, breakdown = score_candidate(c, category, trigger, signals, is_eligible)

        action_def = ACTION_DEFINITIONS[c.action_type]
        evaluations.append(
            CandidateEvaluation(
                action_type=c.action_type,
                target_scope=c.target_scope,
                is_eligible=is_eligible,
                ineligibility_reasons=inelig_reasons,
                priority_tier=action_def.priority_tier,
                total_score=score,
                score_breakdown=breakdown,
                supporting_evidence_count=len(c.evidence_facts),
                rationale=c.primary_reason,
            )
        )
        scored_candidates.append(
            CandidateAction(
                action_type=c.action_type,
                target_scope=c.target_scope,
                supporting_trigger_id=c.supporting_trigger_id,
                evidence_facts=c.evidence_facts,
                supporting_offer=c.supporting_offer,
                next_step=c.next_step,
                is_eligible=is_eligible,
                ineligibility_reasons=inelig_reasons,
                score=score,
                score_breakdown=breakdown,
                primary_reason=c.primary_reason,
            )
        )

    # Sort key for deterministic candidate ranking
    def sort_key(item: CandidateAction):
        action_def = ACTION_DEFINITIONS[item.action_type]
        return (
            1 if item.is_eligible else 0,              # Eligible first
            round(item.score, 4),                      # Score descending
            -int(action_def.priority_tier),            # Priority tier (Tier 1 is highest, so -1 > -2)
            trigger.urgency,                           # Trigger urgency descending
            -len(item.evidence_facts),                 # Evidence count descending
            -ord(item.action_type.value[0]),           # Stable tie-break
        )

    scored_candidates.sort(key=sort_key, reverse=True)
    winner = scored_candidates[0]

    # Detect if a tie-break was applied between top eligible contenders
    tie_break_note = None
    eligible_contenders = [c for c in scored_candidates if c.is_eligible]
    if len(eligible_contenders) > 1:
        if abs(eligible_contenders[0].score - eligible_contenders[1].score) < 1e-4:
            tier1 = ACTION_DEFINITIONS[eligible_contenders[0].action_type].priority_tier.name
            tier2 = ACTION_DEFINITIONS[eligible_contenders[1].action_type].priority_tier.name
            tie_break_note = (
                f"Resolved identical score ({eligible_contenders[0].score:.1f}) via priority tier "
                f"({tier1} vs {tier2})"
            )

    return winner, tuple(evaluations), tie_break_note
