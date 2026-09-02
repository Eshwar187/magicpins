"""Deterministic signal extraction layer derived strictly from grounded context."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState


class SignalType(str, Enum):
    """Catalog of grounded domain signals."""
    # Performance
    PERF_CALLS_DROP_SEVERE = "perf_calls_drop_severe"
    PERF_CALLS_DROP_MODERATE = "perf_calls_drop_moderate"
    PERF_VIEWS_DROP_SEVERE = "perf_views_drop_severe"
    PERF_SPIKE = "perf_spike"
    CTR_BELOW_PEER = "ctr_below_peer"
    CTR_ABOVE_PEER = "ctr_above_peer"

    # Seasonality & Events
    IS_EXPECTED_SEASONAL = "is_expected_seasonal"
    EVENT_TODAY = "event_today"
    EVENT_HOME_VIEWING_SHIFT = "event_home_viewing_shift"
    FESTIVAL_UPCOMING = "festival_upcoming"

    # Merchant State
    HAS_ACTIVE_OFFER = "has_active_offer"
    HAS_DELIVERY_OFFER = "has_delivery_offer"
    UNVERIFIED_LISTING = "unverified_listing"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    HAS_HIGH_RISK_ADULT_COHORT = "has_high_risk_adult_cohort"
    HAS_CHRONIC_RX_COHORT = "has_chronic_rx_cohort"

    # Customer State & Consent
    CUSTOMER_CONSENT_VALID = "customer_consent_valid"
    CUSTOMER_OPTED_OUT = "customer_opted_out"
    CUSTOMER_RECALL_DUE = "customer_recall_due"
    CUSTOMER_REFILL_DUE = "customer_refill_due"
    CUSTOMER_LAPSED = "customer_lapsed"
    CUSTOMER_BRIDAL_WINDOW = "customer_bridal_window"
    CUSTOMER_TRIAL_FOLLOWUP = "customer_trial_followup"

    # Research, Compliance & Planning
    RESEARCH_DIGEST_MATCHED = "research_digest_matched"
    SUPPLY_ALERT_ACTIVE = "supply_alert_active"
    ACTIVE_PLANNING_ACTIVE = "active_planning_active"
    CURIOUS_CADENCE_DUE = "curious_cadence_due"
    COMPETITOR_OPENED = "competitor_opened"
    REVIEW_THEME_EMERGED = "review_theme_emerged"
    MILESTONE_REACHED = "milestone_reached"


@dataclass(frozen=True)
class Signal:
    """A verified, grounded condition extracted from context."""
    signal_type: SignalType
    source_path: str
    value: Any
    description: str

    def __lt__(self, other: Signal) -> bool:
        return self.signal_type.value < other.signal_type.value


def format_pct(val: float) -> str:
    """Canonical formatting for percentage deltas (e.g. 0.18 -> +18%, -0.5 -> -50%)."""
    pct = val * 100
    if pct > 0:
        return f"+{pct:.0f}%" if pct.is_integer() else f"+{pct:.1f}%"
    return f"{pct:.0f}%" if pct.is_integer() else f"{pct:.1f}%"


def extract_signals(
    category: CategoryProfile,
    merchant: MerchantState,
    trigger: TriggerState,
    customer: Optional[CustomerStateModel] = None,
) -> List[Signal]:
    """Extracts deterministic signals from grounded context.
    
    Zero causal guessing: every signal is backed by explicit source attributes.
    """
    signals: List[Signal] = []

    # 1. Performance & Delta Signals
    p = merchant.performance
    d7 = p.delta_7d

    # Calls movement
    calls_pct = None
    if trigger.kind in ("perf_dip", "seasonal_perf_dip") and trigger.metric == "calls":
        calls_pct = trigger.delta_pct
    elif d7 and d7.calls_pct is not None:
        calls_pct = d7.calls_pct

    if calls_pct is not None:
        if calls_pct <= -0.40:
            signals.append(
                Signal(
                    SignalType.PERF_CALLS_DROP_SEVERE,
                    "performance.calls_pct",
                    calls_pct,
                    f"Calls declined severely ({format_pct(calls_pct)})",
                )
            )
        elif calls_pct <= -0.15:
            signals.append(
                Signal(
                    SignalType.PERF_CALLS_DROP_MODERATE,
                    "performance.calls_pct",
                    calls_pct,
                    f"Calls declined moderately ({format_pct(calls_pct)})",
                )
            )

    # Views movement
    views_pct = None
    if trigger.kind in ("perf_dip", "seasonal_perf_dip") and trigger.metric == "views":
        views_pct = trigger.delta_pct
    elif d7 and d7.views_pct is not None:
        views_pct = d7.views_pct

    if views_pct is not None and views_pct <= -0.25:
        signals.append(
            Signal(
                SignalType.PERF_VIEWS_DROP_SEVERE,
                "performance.views_pct",
                views_pct,
                f"Views dropped severely ({format_pct(views_pct)})",
            )
        )

    # Performance Spike
    if trigger.kind == "perf_spike" and trigger.delta_pct is not None:
        signals.append(
            Signal(
                SignalType.PERF_SPIKE,
                "trigger.payload.delta_pct",
                trigger.delta_pct,
                f"Performance spiked ({format_pct(trigger.delta_pct)}) on {trigger.metric}",
            )
        )

    # Peer CTR comparison
    if p.ctr is not None and category.peer_stats.avg_ctr > 0:
        if p.ctr < category.peer_stats.avg_ctr:
            signals.append(
                Signal(
                    SignalType.CTR_BELOW_PEER,
                    "performance.ctr",
                    p.ctr,
                    f"CTR ({p.ctr:.3f}) below peer average ({category.peer_stats.avg_ctr:.3f})",
                )
            )
        else:
            signals.append(
                Signal(
                    SignalType.CTR_ABOVE_PEER,
                    "performance.ctr",
                    p.ctr,
                    f"CTR ({p.ctr:.3f}) at or above peer average ({category.peer_stats.avg_ctr:.3f})",
                )
            )

    # 2. Seasonality & Local Events
    if trigger.kind == "seasonal_perf_dip" or trigger.payload.get("is_expected_seasonal") is True:
        signals.append(
            Signal(
                SignalType.IS_EXPECTED_SEASONAL,
                "trigger.payload.is_expected_seasonal",
                True,
                "Performance dip is explicitly flagged as expected seasonal lull",
            )
        )

    if trigger.kind == "ipl_match_today":
        signals.append(
            Signal(
                SignalType.EVENT_TODAY,
                "trigger.payload.match",
                trigger.payload.get("match"),
                f"IPL Match today: {trigger.payload.get('match')}",
            )
        )
        # Check for home-viewing cover shift (weekend IPL matches shift restaurant dine-in covers)
        is_weeknight = trigger.payload.get("is_weeknight")
        if category.slug == "restaurants" and is_weeknight is False:
            signals.append(
                Signal(
                    SignalType.EVENT_HOME_VIEWING_SHIFT,
                    "trigger.payload.is_weeknight",
                    False,
                    "Weekend IPL match shifts dine-in covers to home-viewing (-12%)",
                )
            )

    if trigger.kind == "festival_upcoming":
        signals.append(
            Signal(
                SignalType.FESTIVAL_UPCOMING,
                "trigger.payload.festival",
                trigger.payload.get("festival"),
                f"Festival approaching: {trigger.payload.get('festival')} in {trigger.payload.get('days_until')} days",
            )
        )

    # 3. Merchant State & Offers
    active_offers = [o for o in merchant.offers if o.status == "active"]
    if len(active_offers) > 0:
        signals.append(
            Signal(
                SignalType.HAS_ACTIVE_OFFER,
                "offers",
                [o.id for o in active_offers],
                f"Merchant has {len(active_offers)} active offer(s)",
            )
        )
        delivery_offers = [
            o for o in active_offers
            if any(k in o.title.lower() for k in ("delivery", "bogo", "buy 1", "get 1", "takeaway", "pack", "online", "special", "combo"))
        ]
        if len(delivery_offers) > 0:
            signals.append(
                Signal(
                    SignalType.HAS_DELIVERY_OFFER,
                    "offers",
                    [o.id for o in delivery_offers],
                    f"Merchant has delivery-suitable active offer: {delivery_offers[0].title}",
                )
            )

    if merchant.identity.verified is False:
        signals.append(
            Signal(
                SignalType.UNVERIFIED_LISTING,
                "identity.verified",
                False,
                "Merchant business profile is unverified on Google/maps",
            )
        )

    sub = merchant.subscription
    if sub.status == "expired":
        signals.append(
            Signal(
                SignalType.SUBSCRIPTION_EXPIRED,
                "subscription.status",
                sub.status,
                f"Subscription is expired ({sub.days_since_expiry} days ago)",
            )
        )
    elif sub.days_remaining is not None and sub.days_remaining <= 14:
        signals.append(
            Signal(
                SignalType.SUBSCRIPTION_EXPIRING,
                "subscription.days_remaining",
                sub.days_remaining,
                f"Subscription expires in {sub.days_remaining} days",
            )
        )

    high_risk_count = merchant.customer_aggregate.get("high_risk_adult_count", 0)
    if high_risk_count > 0:
        signals.append(
            Signal(
                SignalType.HAS_HIGH_RISK_ADULT_COHORT,
                "customer_aggregate.high_risk_adult_count",
                high_risk_count,
                f"Merchant roster has {high_risk_count} high-risk adult patients",
            )
        )

    chronic_rx_count = merchant.customer_aggregate.get("chronic_rx_count", 0)
    if chronic_rx_count > 0:
        signals.append(
            Signal(
                SignalType.HAS_CHRONIC_RX_COHORT,
                "customer_aggregate.chronic_rx_count",
                chronic_rx_count,
                f"Merchant has {chronic_rx_count} active repeat chronic prescription patients",
            )
        )

    # 4. Research, Compliance & Planning Signals
    if trigger.kind in ("research_digest", "cde_opportunity"):
        target_id = trigger.top_item_id or trigger.payload.get("digest_item_id")
        matched = next((d for d in category.digest if d.id == target_id), None)
        if matched:
            signals.append(
                Signal(
                    SignalType.RESEARCH_DIGEST_MATCHED,
                    f"category.digest[{matched.id}]",
                    matched.id,
                    f"Clinical evidence matched: {matched.title} ({matched.source})",
                )
            )

    if trigger.kind == "supply_alert":
        signals.append(
            Signal(
                SignalType.SUPPLY_ALERT_ACTIVE,
                "trigger.payload.affected_batches",
                trigger.affected_batches,
                f"Urgent supply recall on batches {trigger.affected_batches} by {trigger.payload.get('manufacturer')}",
            )
        )

    if trigger.kind == "active_planning_intent":
        signals.append(
            Signal(
                SignalType.ACTIVE_PLANNING_ACTIVE,
                "trigger.payload.intent_topic",
                trigger.payload.get("intent_topic"),
                f"Merchant engaged in active planning on topic: {trigger.payload.get('intent_topic')}",
            )
        )

    if trigger.kind in ("curious_ask_due", "dormant_with_vera"):
        signals.append(
            Signal(
                SignalType.CURIOUS_CADENCE_DUE,
                "trigger.kind",
                trigger.kind,
                "Curiosity check-in cadence window is open",
            )
        )

    if trigger.kind == "competitor_opened":
        signals.append(
            Signal(
                SignalType.COMPETITOR_OPENED,
                "trigger.payload.competitor_name",
                trigger.payload.get("competitor_name"),
                f"Competitor {trigger.payload.get('competitor_name')} opened {trigger.payload.get('distance_km')}km away",
            )
        )

    if trigger.kind == "review_theme_emerged":
        signals.append(
            Signal(
                SignalType.REVIEW_THEME_EMERGED,
                "trigger.payload.theme",
                trigger.payload.get("theme"),
                f"Review theme emerged: {trigger.payload.get('theme')} ({trigger.payload.get('sentiment')})",
            )
        )

    if trigger.kind == "milestone_reached":
        signals.append(
            Signal(
                SignalType.MILESTONE_REACHED,
                "trigger.payload.milestone_value",
                trigger.payload.get("milestone_value"),
                f"Milestone reached: {trigger.payload.get('metric')} = {trigger.payload.get('value_now')}",
            )
        )

    # 5. Customer & Consent Signals
    if customer is not None:
        # Strict consent check
        has_consent_scope = customer.consent.scope is not None and len(customer.consent.scope) > 0
        reminder_opt_in = customer.preferences.reminder_opt_in

        if reminder_opt_in is False or not has_consent_scope:
            signals.append(
                Signal(
                    SignalType.CUSTOMER_OPTED_OUT,
                    "customer.consent",
                    False,
                    "Customer has unrecorded, missing, or explicitly disabled outreach consent",
                )
            )
        else:
            signals.append(
                Signal(
                    SignalType.CUSTOMER_CONSENT_VALID,
                    "customer.consent",
                    True,
                    f"Customer consent valid with scopes: {customer.consent.scope}",
                )
            )

        if trigger.kind == "recall_due":
            signals.append(
                Signal(
                    SignalType.CUSTOMER_RECALL_DUE,
                    "trigger.payload.service_due",
                    trigger.service_due,
                    f"Routine recall due for {trigger.service_due}",
                )
            )

        if trigger.kind == "chronic_refill_due":
            signals.append(
                Signal(
                    SignalType.CUSTOMER_REFILL_DUE,
                    "trigger.payload.molecule_list",
                    trigger.payload.get("molecule_list"),
                    f"Chronic medication refill due: {trigger.payload.get('molecule_list')}",
                )
            )

        if customer.state in ("lapsed_soft", "lapsed_hard") or trigger.kind in ("customer_lapsed_hard", "customer_lapsed_soft"):
            signals.append(
                Signal(
                    SignalType.CUSTOMER_LAPSED,
                    "customer.state",
                    customer.state,
                    f"Customer is in lapsed state ({customer.state})",
                )
            )

        if customer.preferences.wedding_date or trigger.kind == "wedding_package_followup":
            signals.append(
                Signal(
                    SignalType.CUSTOMER_BRIDAL_WINDOW,
                    "customer.preferences.wedding_date",
                    customer.preferences.wedding_date or trigger.payload.get("wedding_date"),
                    "Customer in bridal / wedding preparation window",
                )
            )

        if trigger.kind == "trial_followup":
            signals.append(
                Signal(
                    SignalType.CUSTOMER_TRIAL_FOLLOWUP,
                    "trigger.payload.trial_date",
                    trigger.payload.get("trial_date"),
                    "Customer completed trial session; followup window active",
                )
            )

    signals.sort()
    return signals
