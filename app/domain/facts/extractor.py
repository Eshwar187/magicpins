"""Deterministic fact extractor converting normalized context into grounded facts."""

from __future__ import annotations

from typing import Any, List, Optional, Union

from app.domain.facts.fact import Fact
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.enums import FactType
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState


def extract_facts(
    category: Union[CategoryProfile, dict[str, Any]],
    merchant: Union[MerchantState, dict[str, Any]],
    trigger: Union[TriggerState, dict[str, Any]],
    customer: Optional[Union[CustomerStateModel, dict[str, Any]]] = None,
    category_version: int = 1,
    merchant_version: int = 1,
    trigger_version: int = 1,
    customer_version: int = 1,
) -> List[Fact]:
    """Extracts verifiable, grounded business facts with exact provenance.
    
    Adheres strictly to the Fact Extraction Matrix:
    - Category policy metadata (voice, taboos) is NEVER converted to instance facts.
    - Missing/None values are skipped; never coerced to 0, False, or empty claims.
    - Facts are sorted using a stable, documented sort key for total determinism.
    """
    cat = category if isinstance(category, CategoryProfile) else CategoryProfile.from_dict(category)
    m = merchant if isinstance(merchant, MerchantState) else MerchantState.from_dict(merchant)
    trg = trigger if isinstance(trigger, TriggerState) else TriggerState.from_dict(trigger)
    c = None
    if customer is not None:
        c = customer if isinstance(customer, CustomerStateModel) else CustomerStateModel.from_dict(customer)

    facts: List[Fact] = []

    # =========================================================================
    # 1. MERCHANT FACTS
    # =========================================================================
    m_id = m.merchant_id

    # Identity & Location
    facts.append(
        Fact.create(
            FactType.IDENTITY,
            "merchant.name",
            m.identity.name,
            "merchant",
            m_id,
            merchant_version,
            "identity.name",
        )
    )
    if m.identity.owner_first_name is not None:
        facts.append(
            Fact.create(
                FactType.IDENTITY,
                "merchant.owner_first_name",
                m.identity.owner_first_name,
                "merchant",
                m_id,
                merchant_version,
                "identity.owner_first_name",
            )
        )
    facts.append(
        Fact.create(
            FactType.LOCATION,
            "merchant.locality",
            m.identity.locality,
            "merchant",
            m_id,
            merchant_version,
            "identity.locality",
        )
    )
    facts.append(
        Fact.create(
            FactType.LOCATION,
            "merchant.city",
            m.identity.city,
            "merchant",
            m_id,
            merchant_version,
            "identity.city",
        )
    )
    facts.append(
        Fact.create(
            FactType.IDENTITY,
            "merchant.languages",
            list(m.identity.languages),
            "merchant",
            m_id,
            merchant_version,
            "identity.languages",
        )
    )
    facts.append(
        Fact.create(
            FactType.IDENTITY,
            "merchant.verified",
            m.identity.verified,
            "merchant",
            m_id,
            merchant_version,
            "identity.verified",
        )
    )

    # Subscription
    facts.append(
        Fact.create(
            FactType.SUBSCRIPTION,
            "merchant.subscription.status",
            m.subscription.status,
            "merchant",
            m_id,
            merchant_version,
            "subscription.status",
        )
    )
    facts.append(
        Fact.create(
            FactType.SUBSCRIPTION,
            "merchant.subscription.plan",
            m.subscription.plan,
            "merchant",
            m_id,
            merchant_version,
            "subscription.plan",
        )
    )
    if m.subscription.days_remaining is not None:
        facts.append(
            Fact.create(
                FactType.SUBSCRIPTION,
                "merchant.subscription.days_remaining",
                m.subscription.days_remaining,
                "merchant",
                m_id,
                merchant_version,
                "subscription.days_remaining",
            )
        )
    if m.subscription.days_since_expiry is not None:
        facts.append(
            Fact.create(
                FactType.SUBSCRIPTION,
                "merchant.subscription.days_since_expiry",
                m.subscription.days_since_expiry,
                "merchant",
                m_id,
                merchant_version,
                "subscription.days_since_expiry",
            )
        )

    # Performance
    p = m.performance
    if p.views is not None:
        facts.append(
            Fact.create(
                FactType.METRIC,
                "merchant.performance.views",
                p.views,
                "merchant",
                m_id,
                merchant_version,
                "performance.views",
            )
        )
    if p.calls is not None:
        facts.append(
            Fact.create(
                FactType.METRIC,
                "merchant.performance.calls",
                p.calls,
                "merchant",
                m_id,
                merchant_version,
                "performance.calls",
            )
        )
    if p.directions is not None:
        facts.append(
            Fact.create(
                FactType.METRIC,
                "merchant.performance.directions",
                p.directions,
                "merchant",
                m_id,
                merchant_version,
                "performance.directions",
            )
        )
    if p.ctr is not None:
        facts.append(
            Fact.create(
                FactType.METRIC,
                "merchant.performance.ctr",
                p.ctr,
                "merchant",
                m_id,
                merchant_version,
                "performance.ctr",
            )
        )
    if p.leads is not None:
        facts.append(
            Fact.create(
                FactType.METRIC,
                "merchant.performance.leads",
                p.leads,
                "merchant",
                m_id,
                merchant_version,
                "performance.leads",
            )
        )

    if p.delta_7d is not None:
        d7 = p.delta_7d
        if d7.views_pct is not None:
            facts.append(
                Fact.create(
                    FactType.METRIC_CHANGE,
                    "merchant.performance.delta_7d.views_pct",
                    d7.views_pct,
                    "merchant",
                    m_id,
                    merchant_version,
                    "performance.delta_7d.views_pct",
                )
            )
        if d7.calls_pct is not None:
            facts.append(
                Fact.create(
                    FactType.METRIC_CHANGE,
                    "merchant.performance.delta_7d.calls_pct",
                    d7.calls_pct,
                    "merchant",
                    m_id,
                    merchant_version,
                    "performance.delta_7d.calls_pct",
                )
            )
        if d7.ctr_pct is not None:
            facts.append(
                Fact.create(
                    FactType.METRIC_CHANGE,
                    "merchant.performance.delta_7d.ctr_pct",
                    d7.ctr_pct,
                    "merchant",
                    m_id,
                    merchant_version,
                    "performance.delta_7d.ctr_pct",
                )
            )

    # Offers
    for idx, offer in enumerate(m.offers):
        facts.append(
            Fact.create(
                FactType.OFFER,
                f"merchant.offer.{offer.id}",
                {
                    "id": offer.id,
                    "title": offer.title,
                    "status": offer.status,
                    "started": offer.started,
                    "ended": offer.ended,
                },
                "merchant",
                m_id,
                merchant_version,
                f"offers[{idx}]",
            )
        )

    # Customer Aggregate
    for agg_key in sorted(m.customer_aggregate.keys()):
        val = m.customer_aggregate[agg_key]
        if val is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_COHORT,
                    f"merchant.customer_aggregate.{agg_key}",
                    val,
                    "merchant",
                    m_id,
                    merchant_version,
                    f"customer_aggregate.{agg_key}",
                )
            )

    # Review Themes
    for idx, rt in enumerate(m.review_themes):
        facts.append(
            Fact.create(
                FactType.REVIEW_THEME,
                f"merchant.review_theme.{rt.theme}",
                {
                    "theme": rt.theme,
                    "sentiment": rt.sentiment,
                    "occurrences_30d": rt.occurrences_30d,
                    "common_quote": rt.common_quote,
                },
                "merchant",
                m_id,
                merchant_version,
                f"review_themes[{idx}]",
            )
        )

    # =========================================================================
    # 2. CATEGORY FACTS (Peer Benchmarks & Matched Evidence Only)
    # =========================================================================
    cat_slug = cat.slug

    facts.append(
        Fact.create(
            FactType.PEER_BENCHMARK,
            "category.peer_stats.avg_rating",
            cat.peer_stats.avg_rating,
            "category",
            cat_slug,
            category_version,
            "peer_stats.avg_rating",
        )
    )
    facts.append(
        Fact.create(
            FactType.PEER_BENCHMARK,
            "category.peer_stats.avg_ctr",
            cat.peer_stats.avg_ctr,
            "category",
            cat_slug,
            category_version,
            "peer_stats.avg_ctr",
        )
    )
    facts.append(
        Fact.create(
            FactType.PEER_BENCHMARK,
            "category.peer_stats.avg_calls_30d",
            cat.peer_stats.avg_calls_30d,
            "category",
            cat_slug,
            category_version,
            "peer_stats.avg_calls_30d",
        )
    )
    facts.append(
        Fact.create(
            FactType.PEER_BENCHMARK,
            "category.peer_stats.avg_views_30d",
            cat.peer_stats.avg_views_30d,
            "category",
            cat_slug,
            category_version,
            "peer_stats.avg_views_30d",
        )
    )

    # Matched Digest Evidence
    target_item_id = trg.payload.get("top_item_id") or trg.payload.get("digest_item_id")
    if target_item_id:
        for idx, item in enumerate(cat.digest):
            if item.id == target_item_id:
                facts.append(
                    Fact.create(
                        FactType.RESEARCH_EVIDENCE,
                        "category.digest.matched",
                        {
                            "id": item.id,
                            "kind": item.kind,
                            "title": item.title,
                            "source": item.source,
                            "summary": item.summary,
                            "actionable": item.actionable,
                            "trial_n": item.trial_n,
                            "patient_segment": item.patient_segment,
                            "deadline_iso": item.deadline_iso,
                        },
                        "category",
                        cat_slug,
                        category_version,
                        f"digest[{idx}]",
                    )
                )
                break

    # =========================================================================
    # 3. TRIGGER FACTS
    # =========================================================================
    trg_id = trg.id

    facts.append(
        Fact.create(
            FactType.TRIGGER_METADATA,
            "trigger.kind",
            trg.kind,
            "trigger",
            trg_id,
            trigger_version,
            "kind",
        )
    )
    facts.append(
        Fact.create(
            FactType.TRIGGER_METADATA,
            "trigger.urgency",
            trg.urgency,
            "trigger",
            trg_id,
            trigger_version,
            "urgency",
        )
    )
    facts.append(
        Fact.create(
            FactType.TRIGGER_METADATA,
            "trigger.suppression_key",
            trg.suppression_key,
            "trigger",
            trg_id,
            trigger_version,
            "suppression_key",
        )
    )

    # Individual payload fields
    for p_key in sorted(trg.payload.keys()):
        p_val = trg.payload[p_key]
        if p_val is not None:
            facts.append(
                Fact.create(
                    FactType.TRIGGER_PAYLOAD,
                    f"trigger.payload.{p_key}",
                    p_val,
                    "trigger",
                    trg_id,
                    trigger_version,
                    f"payload.{p_key}",
                )
            )

    # =========================================================================
    # 4. CUSTOMER FACTS (If customer is populated)
    # =========================================================================
    if c is not None:
        c_id = c.customer_id

        facts.append(
            Fact.create(
                FactType.CUSTOMER_IDENTITY,
                "customer.name",
                c.identity.name,
                "customer",
                c_id,
                customer_version,
                "identity.name",
            )
        )
        if c.identity.phone_redacted is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_IDENTITY,
                    "customer.phone_redacted",
                    c.identity.phone_redacted,
                    "customer",
                    c_id,
                    customer_version,
                    "identity.phone_redacted",
                )
            )
        facts.append(
            Fact.create(
                FactType.CUSTOMER_IDENTITY,
                "customer.language_pref",
                c.identity.language_pref,
                "customer",
                c_id,
                customer_version,
                "identity.language_pref",
            )
        )
        if c.identity.age_band is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_IDENTITY,
                    "customer.age_band",
                    c.identity.age_band,
                    "customer",
                    c_id,
                    customer_version,
                    "identity.age_band",
                )
            )
        if c.identity.senior_citizen is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_IDENTITY,
                    "customer.senior_citizen",
                    c.identity.senior_citizen,
                    "customer",
                    c_id,
                    customer_version,
                    "identity.senior_citizen",
                )
            )

        # Relationship
        if c.relationship.visits_total is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_RELATIONSHIP,
                    "customer.visits_total",
                    c.relationship.visits_total,
                    "customer",
                    c_id,
                    customer_version,
                    "relationship.visits_total",
                )
            )
        if c.relationship.lifetime_value is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_RELATIONSHIP,
                    "customer.lifetime_value",
                    c.relationship.lifetime_value,
                    "customer",
                    c_id,
                    customer_version,
                    "relationship.lifetime_value",
                )
            )
        if c.relationship.last_visit is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_RELATIONSHIP,
                    "customer.last_visit",
                    c.relationship.last_visit,
                    "customer",
                    c_id,
                    customer_version,
                    "relationship.last_visit",
                )
            )

        # Lifecycle State
        facts.append(
            Fact.create(
                FactType.CUSTOMER_STATE,
                "customer.state",
                c.state,
                "customer",
                c_id,
                customer_version,
                "state",
            )
        )

        # Preferences
        if c.preferences.preferred_slots is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_PREFERENCE,
                    "customer.preferred_slots",
                    c.preferences.preferred_slots,
                    "customer",
                    c_id,
                    customer_version,
                    "preferences.preferred_slots",
                )
            )
        if c.preferences.channel is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_PREFERENCE,
                    "customer.channel",
                    c.preferences.channel,
                    "customer",
                    c_id,
                    customer_version,
                    "preferences.channel",
                )
            )
        if c.preferences.reminder_opt_in is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_PREFERENCE,
                    "customer.reminder_opt_in",
                    c.preferences.reminder_opt_in,
                    "customer",
                    c_id,
                    customer_version,
                    "preferences.reminder_opt_in",
                )
            )

        # Consent
        if c.consent.opted_in_at is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_CONSENT,
                    "customer.consent.opted_in_at",
                    c.consent.opted_in_at,
                    "customer",
                    c_id,
                    customer_version,
                    "consent.opted_in_at",
                )
            )
        if c.consent.scope is not None:
            facts.append(
                Fact.create(
                    FactType.CUSTOMER_CONSENT,
                    "customer.consent.scope",
                    list(c.consent.scope),
                    "customer",
                    c_id,
                    customer_version,
                    "consent.scope",
                )
            )

    # Return facts sorted deterministically by documented sort_key
    facts.sort()
    return facts
