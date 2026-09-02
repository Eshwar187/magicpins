"""Normalized merchant domain models matching dataset/merchants_seed.json."""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MerchantIdentity(BaseModel):
    """Core identity and locality of a merchant."""
    model_config = ConfigDict(extra="allow")

    name: str
    city: str
    locality: str
    place_id: str
    verified: bool
    languages: List[str] = Field(default_factory=list)
    owner_first_name: Optional[str] = None
    established_year: Optional[int] = None


class Subscription(BaseModel):
    """Merchant subscription plan status and validity."""
    model_config = ConfigDict(extra="allow")

    status: str
    plan: str
    days_remaining: Optional[int] = None
    days_since_expiry: Optional[int] = None
    renewed_at: Optional[str] = None


class Delta7d(BaseModel):
    """Week-over-week performance percentage deltas."""
    model_config = ConfigDict(extra="allow")

    views_pct: Optional[float] = None
    calls_pct: Optional[float] = None
    ctr_pct: Optional[float] = None


class PerformanceSnapshot(BaseModel):
    """30-day performance snapshot metrics with 7-day deltas.
    
    IMPORTANT: Missing values remain None and must never be converted to 0.
    """
    model_config = ConfigDict(extra="allow")

    window_days: int = 30
    views: Optional[int] = None
    calls: Optional[int] = None
    directions: Optional[int] = None
    ctr: Optional[float] = None
    leads: Optional[int] = None
    delta_7d: Optional[Delta7d] = None


class MerchantOffer(BaseModel):
    """Catalog offer belonging to a merchant."""
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    status: str
    started: Optional[str] = None
    ended: Optional[str] = None


class ConversationTurn(BaseModel):
    """Historical conversation turn between merchant and Vera."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    ts: str
    from_role: str = Field(alias="from")
    body: str
    engagement: Optional[str] = None


class ReviewTheme(BaseModel):
    """Aggregated customer review sentiment cluster."""
    model_config = ConfigDict(extra="allow")

    theme: str
    sentiment: str
    occurrences_30d: int
    common_quote: Optional[str] = None


class MerchantState(BaseModel):
    """Normalized merchant state."""
    model_config = ConfigDict(extra="allow")

    merchant_id: str
    category_slug: str
    identity: MerchantIdentity
    subscription: Subscription
    performance: PerformanceSnapshot
    offers: List[MerchantOffer] = Field(default_factory=list)
    conversation_history: List[ConversationTurn] = Field(default_factory=list)
    customer_aggregate: dict[str, Any] = Field(default_factory=dict)
    signals: List[str] = Field(default_factory=list)
    review_themes: List[ReviewTheme] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MerchantState:
        """Create a MerchantState from a raw dictionary."""
        return cls.model_validate(data)
