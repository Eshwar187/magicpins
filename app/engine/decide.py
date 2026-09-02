"""Authoritative decision engine entrypoint orchestrating Vera's next action."""

from __future__ import annotations

from typing import Any, Optional, Union

from app.domain.facts.extractor import extract_facts
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.candidate_generator import generate_candidates
from app.engine.decision import Decision, DecisionTrace
from app.engine.scorer import rank_and_select_winner
from app.engine.signals import extract_signals


def decide(
    category: Union[CategoryProfile, dict[str, Any]],
    merchant: Union[MerchantState, dict[str, Any]],
    trigger: Union[TriggerState, dict[str, Any]],
    customer: Optional[Union[CustomerStateModel, dict[str, Any]]] = None,
    state: Optional[dict[str, Any]] = None,
    category_version: int = 1,
    merchant_version: int = 1,
    trigger_version: int = 1,
    customer_version: int = 1,
) -> Decision:
    """The central decision function determining what Vera should do right now.
    
    Pipeline:
    1. Normalize domain inputs to typed models
    2. Extract grounded facts with full provenance
    3. Derive grounded signals
    4. Generate candidate actions
    5. Evaluate eligibility & score candidates
    6. Deterministically rank and select winning action
    7. Construct immutable Decision with audit trace
    
    Zero LLM, zero network, zero message-generation.
    """
    # 1. Normalization
    cat = category if isinstance(category, CategoryProfile) else CategoryProfile.from_dict(category)
    m = merchant if isinstance(merchant, MerchantState) else MerchantState.from_dict(merchant)
    trg = trigger if isinstance(trigger, TriggerState) else TriggerState.from_dict(trigger)
    cust = None
    if customer is not None:
        cust = customer if isinstance(customer, CustomerStateModel) else CustomerStateModel.from_dict(customer)

    # 2. Fact Extraction
    facts = extract_facts(
        cat, m, trg, cust,
        category_version=category_version,
        merchant_version=merchant_version,
        trigger_version=trigger_version,
        customer_version=customer_version,
    )

    # 3. Grounded Signal Extraction
    signals = extract_signals(cat, m, trg, cust)

    # 4. Candidate Generation
    candidates = generate_candidates(cat, m, trg, cust, signals, facts)

    # 5. Eligibility & Deterministic Scoring
    winner, evaluations, tie_break_note = rank_and_select_winner(
        candidates, cat, m, trg, cust, signals
    )

    # 6. Audit Trace Construction
    trace = DecisionTrace(
        trigger_kind=trg.kind,
        trigger_id=trg.id,
        derived_signals=tuple(s.signal_type.value for s in signals),
        candidate_evaluations=evaluations,
        winning_action=winner.action_type.value,
        tie_break_applied=tie_break_note,
    )

    # 7. Final Immutable Decision Output
    return Decision(
        action=winner.action_type.value,
        action_type=winner.action_type,
        target_scope=winner.target_scope,
        trigger_id=trg.id,
        score=winner.score,
        primary_reason=winner.primary_reason,
        evidence_facts=winner.evidence_facts,
        derived_signals=tuple(s.signal_type.value for s in signals),
        supporting_offer=winner.supporting_offer,
        next_step=winner.next_step,
        trace=trace,
    )
