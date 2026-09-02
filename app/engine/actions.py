"""Action taxonomy, priority tiers, and eligibility prerequisites."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Optional, Set


class PriorityTier(IntEnum):
    """Deterministic priority tiers for ranking and tie-breaking.
    
    Tier 1: Critical Compliance & Safety (recalls, supply warnings, legal deadlines)
    Tier 2: Customer Care & Relationship (refill reminders, recalls, winbacks, followups)
    Tier 3: Urgent Merchant Revenue & Operations (dips, contrarian event pivots, planning, renewals)
    Tier 4: Routine Engagement & Nudges (curious asks, seasonal reframes, milestones, listings)
    Tier 5: Fallback (wait, end)
    """
    CRITICAL_COMPLIANCE = 1
    CUSTOMER_CARE = 2
    URGENT_MERCHANT_REVENUE = 3
    ROUTINE_ENGAGEMENT = 4
    FALLBACK = 5


class ActionType(str, Enum):
    """Exhaustive taxonomy of deterministic Vera actions."""
    USE_RESEARCH_INSIGHT = "use_research_insight"
    CUSTOMER_RECALL = "customer_recall"
    CUSTOMER_FOLLOWUP = "customer_followup"
    CURIOUS_ASK = "curious_ask"
    PROMOTE_DELIVERY_OFFER = "promote_delivery_offer"
    CONTINUE_PLANNING = "continue_planning"
    REFRAME_SEASONAL_DIP = "reframe_seasonal_dip"
    CUSTOMER_WINBACK = "customer_winback"
    ADDRESS_SUPPLY_ALERT = "address_supply_alert"
    CUSTOMER_REFILL = "customer_refill"
    ADDRESS_PERFORMANCE_DIP = "address_performance_dip"
    CAPITALIZE_PERF_SPIKE = "capitalize_perf_spike"
    PREPARE_FESTIVAL_CAMPAIGN = "prepare_festival_campaign"
    RENEW_SUBSCRIPTION = "renew_subscription"
    RESOLVE_LISTING_ISSUE = "resolve_listing_issue"
    ADDRESS_COMPETITOR_CHANGE = "address_competitor_change"
    RESPOND_TO_REVIEW_THEME = "respond_to_review_theme"
    CELEBRATE_MILESTONE = "celebrate_milestone"
    WAIT = "wait"
    END = "end"


@dataclass(frozen=True)
class ActionDefinition:
    """Metadata and rules governing action eligibility and execution."""
    action_type: ActionType
    target_scope: str  # "merchant" or "customer"
    priority_tier: PriorityTier
    allowed_categories: Optional[Set[str]] = None  # None means all categories allowed
    requires_customer_consent: bool = False
    requires_active_merchant_offer: bool = False
    is_terminal: bool = False
    description: str = ""


ACTION_DEFINITIONS: dict[ActionType, ActionDefinition] = {
    ActionType.ADDRESS_SUPPLY_ALERT: ActionDefinition(
        action_type=ActionType.ADDRESS_SUPPLY_ALERT,
        target_scope="merchant",
        priority_tier=PriorityTier.CRITICAL_COMPLIANCE,
        allowed_categories={"pharmacies"},
        description="Notify pharmacy merchant of sub-potency/recall batch alert affecting chronic patients",
    ),
    ActionType.CUSTOMER_REFILL: ActionDefinition(
        action_type=ActionType.CUSTOMER_REFILL,
        target_scope="customer",
        priority_tier=PriorityTier.CUSTOMER_CARE,
        allowed_categories={"pharmacies"},
        requires_customer_consent=True,
        description="Remind patient/family that chronic prescriptions are running out soon",
    ),
    ActionType.CUSTOMER_RECALL: ActionDefinition(
        action_type=ActionType.CUSTOMER_RECALL,
        target_scope="customer",
        priority_tier=PriorityTier.CUSTOMER_CARE,
        allowed_categories={"dentists", "salons"},
        requires_customer_consent=True,
        description="Invite patient/client to book routine recall visit into concrete open slots",
    ),
    ActionType.CUSTOMER_FOLLOWUP: ActionDefinition(
        action_type=ActionType.CUSTOMER_FOLLOWUP,
        target_scope="customer",
        priority_tier=PriorityTier.CUSTOMER_CARE,
        allowed_categories={"salons", "gyms"},
        requires_customer_consent=True,
        description="Follow up on completed trial, consultation, or bridal package prep window",
    ),
    ActionType.CUSTOMER_WINBACK: ActionDefinition(
        action_type=ActionType.CUSTOMER_WINBACK,
        target_scope="customer",
        priority_tier=PriorityTier.CUSTOMER_CARE,
        allowed_categories={"gyms", "salons", "restaurants"},
        requires_customer_consent=True,
        description="Re-engage lapsed customer with tailored no-commitment trial or class",
    ),
    ActionType.PROMOTE_DELIVERY_OFFER: ActionDefinition(
        action_type=ActionType.PROMOTE_DELIVERY_OFFER,
        target_scope="merchant",
        priority_tier=PriorityTier.URGENT_MERCHANT_REVENUE,
        allowed_categories={"restaurants"},
        requires_active_merchant_offer=True,
        description="Recommend pivoting to delivery/takeaway special during home-viewing or adverse dine-in events",
    ),
    ActionType.CONTINUE_PLANNING: ActionDefinition(
        action_type=ActionType.CONTINUE_PLANNING,
        target_scope="merchant",
        priority_tier=PriorityTier.URGENT_MERCHANT_REVENUE,
        description="Continue prior planning intent conversation with concrete drafted package/proposal",
    ),
    ActionType.ADDRESS_PERFORMANCE_DIP: ActionDefinition(
        action_type=ActionType.ADDRESS_PERFORMANCE_DIP,
        target_scope="merchant",
        priority_tier=PriorityTier.URGENT_MERCHANT_REVENUE,
        description="Alert merchant to an unexpected metric drop with immediate diagnosis and intervention",
    ),
    ActionType.CAPITALIZE_PERF_SPIKE: ActionDefinition(
        action_type=ActionType.CAPITALIZE_PERF_SPIKE,
        target_scope="merchant",
        priority_tier=PriorityTier.URGENT_MERCHANT_REVENUE,
        description="Capitalize on positive traffic or inquiry momentum",
    ),
    ActionType.RENEW_SUBSCRIPTION: ActionDefinition(
        action_type=ActionType.RENEW_SUBSCRIPTION,
        target_scope="merchant",
        priority_tier=PriorityTier.URGENT_MERCHANT_REVENUE,
        description="Remind merchant of upcoming subscription expiration with renewal value",
    ),
    ActionType.USE_RESEARCH_INSIGHT: ActionDefinition(
        action_type=ActionType.USE_RESEARCH_INSIGHT,
        target_scope="merchant",
        priority_tier=PriorityTier.ROUTINE_ENGAGEMENT,
        allowed_categories={"dentists", "pharmacies", "gyms"},
        description="Share peer-reviewed clinical research digest relevant to merchant patient cohort",
    ),
    ActionType.REFRAME_SEASONAL_DIP: ActionDefinition(
        action_type=ActionType.REFRAME_SEASONAL_DIP,
        target_scope="merchant",
        priority_tier=PriorityTier.ROUTINE_ENGAGEMENT,
        description="Reframe normal seasonal acquisition drop, advise conserving ad spend and focusing on retention",
    ),
    ActionType.CURIOUS_ASK: ActionDefinition(
        action_type=ActionType.CURIOUS_ASK,
        target_scope="merchant",
        priority_tier=PriorityTier.ROUTINE_ENGAGEMENT,
        description="Ask a low-friction question about customer demand with reciprocity promise",
    ),
    ActionType.RESOLVE_LISTING_ISSUE: ActionDefinition(
        action_type=ActionType.RESOLVE_LISTING_ISSUE,
        target_scope="merchant",
        priority_tier=PriorityTier.ROUTINE_ENGAGEMENT,
        description="Alert merchant that GBP/profile is unverified and guide verification for search uplift",
    ),
    ActionType.ADDRESS_COMPETITOR_CHANGE: ActionDefinition(
        action_type=ActionType.ADDRESS_COMPETITOR_CHANGE,
        target_scope="merchant",
        priority_tier=PriorityTier.ROUTINE_ENGAGEMENT,
        description="Recommend defensive local offer to counter a new nearby competitor",
    ),
    ActionType.RESPOND_TO_REVIEW_THEME: ActionDefinition(
        action_type=ActionType.RESPOND_TO_REVIEW_THEME,
        target_scope="merchant",
        priority_tier=PriorityTier.ROUTINE_ENGAGEMENT,
        description="Surface clustered customer review sentiment and recommended operational adjustment",
    ),
    ActionType.CELEBRATE_MILESTONE: ActionDefinition(
        action_type=ActionType.CELEBRATE_MILESTONE,
        target_scope="merchant",
        priority_tier=PriorityTier.ROUTINE_ENGAGEMENT,
        description="Congratulate merchant on volume or rating milestone and suggest social proof sharing",
    ),
    ActionType.PREPARE_FESTIVAL_CAMPAIGN: ActionDefinition(
        action_type=ActionType.PREPARE_FESTIVAL_CAMPAIGN,
        target_scope="merchant",
        priority_tier=PriorityTier.ROUTINE_ENGAGEMENT,
        description="Prepare advance marketing campaign ahead of upcoming festival",
    ),
    ActionType.WAIT: ActionDefinition(
        action_type=ActionType.WAIT,
        target_scope="merchant",
        priority_tier=PriorityTier.FALLBACK,
        description="Stand down; conditions or evidence do not warrant outbound touchpoint",
    ),
    ActionType.END: ActionDefinition(
        action_type=ActionType.END,
        target_scope="merchant",
        priority_tier=PriorityTier.FALLBACK,
        is_terminal=True,
        description="Terminal conversation conclusion",
    ),
}
