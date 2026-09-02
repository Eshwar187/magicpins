"""Domain enumerations and constant values."""

from enum import Enum


class Scope(str, Enum):
    """Context scope enum corresponding to the four context layers."""
    CATEGORY = "category"
    MERCHANT = "merchant"
    CUSTOMER = "customer"
    TRIGGER = "trigger"


class CustomerState(str, Enum):
    """Customer lifecycle states identified across seeds and dataset generator."""
    NEW = "new"
    ACTIVE = "active"
    LAPSED_SOFT = "lapsed_soft"
    LAPSED_HARD = "lapsed_hard"
    CHURNED = "churned"


class SubscriptionStatus(str, Enum):
    """Merchant subscription plan status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    TRIAL = "trial"


class FactType(str, Enum):
    """Taxonomy of grounded business facts extracted from context."""
    IDENTITY = "identity"
    METRIC = "metric"
    METRIC_CHANGE = "metric_change"
    OFFER = "offer"
    LOCATION = "location"
    SUBSCRIPTION = "subscription"
    CUSTOMER_COHORT = "customer_cohort"
    CUSTOMER_IDENTITY = "customer_identity"
    CUSTOMER_RELATIONSHIP = "customer_relationship"
    CUSTOMER_STATE = "customer_state"
    CUSTOMER_PREFERENCE = "customer_preference"
    CUSTOMER_CONSENT = "customer_consent"
    TRIGGER_METADATA = "trigger_metadata"
    TRIGGER_PAYLOAD = "trigger_payload"
    PEER_BENCHMARK = "peer_benchmark"
    RESEARCH_EVIDENCE = "research_evidence"
    REVIEW_THEME = "review_theme"
