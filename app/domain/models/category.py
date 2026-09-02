"""Normalized category domain models matching dataset/categories/*.json."""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class VoiceProfile(BaseModel):
    """Voice, tone, and vocabulary governance for a vertical."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    tone: str
    register_style: str = Field(alias="register")
    code_mix: str
    vocab_allowed: List[str] = Field(default_factory=list)
    vocab_taboo: List[str] = Field(default_factory=list)
    salutation_examples: List[str] = Field(default_factory=list)
    tone_examples: List[str] = Field(default_factory=list)

    @property
    def register(self) -> str:
        """Accessor for voice register style."""
        return self.register_style


class OfferTemplate(BaseModel):
    """Canonical service+price offer template in category catalog."""
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    value: str
    audience: str
    type: str


class PeerStats(BaseModel):
    """City/segment benchmarks for peer performance comparisons."""
    model_config = ConfigDict(extra="allow")

    scope: str
    avg_rating: float
    avg_review_count: int
    avg_views_30d: int
    avg_calls_30d: int
    avg_directions_30d: int
    avg_ctr: float
    avg_photos: int
    avg_post_freq_days: int

    # Vertical-specific metrics (preserved as None if absent in category)
    retention_6mo_pct: Optional[float] = None
    retention_3mo_pct: Optional[float] = None
    retention_30d_pct: Optional[float] = None
    monthly_churn_pct: Optional[float] = None
    trial_to_paid_pct: Optional[float] = None
    delivery_share_pct: Optional[float] = None
    repeat_customer_pct: Optional[float] = None


class DigestItem(BaseModel):
    """Curated research, compliance, technology, or trend item."""
    model_config = ConfigDict(extra="allow")

    id: str
    kind: str
    title: str
    source: str
    summary: str
    actionable: str

    # Optional demonstrated context fields
    trial_n: Optional[int] = None
    patient_segment: Optional[str] = None
    deadline_iso: Optional[str] = None
    date: Optional[str] = None
    credits: Optional[int] = None


class PatientContentItem(BaseModel):
    """Reshareable educational content item for customers/patients."""
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    channel: str
    length_seconds: int
    body: str


class SeasonalBeat(BaseModel):
    """Seasonal demand cycle or timing pattern."""
    model_config = ConfigDict(extra="allow")

    month_range: str
    note: str


class TrendSignal(BaseModel):
    """Aggregated search trend or consumer demand pattern."""
    model_config = ConfigDict(extra="allow")

    query: str
    delta_yoy: float
    segment_age: Optional[str] = None
    skew: Optional[str] = None


class CategoryProfile(BaseModel):
    """Normalized vertical category profile."""
    model_config = ConfigDict(extra="allow")

    slug: str
    display_name: str
    voice: VoiceProfile
    offer_catalog: List[OfferTemplate] = Field(default_factory=list)
    peer_stats: PeerStats
    digest: List[DigestItem] = Field(default_factory=list)
    patient_content_library: List[PatientContentItem] = Field(default_factory=list)
    seasonal_beats: List[SeasonalBeat] = Field(default_factory=list)
    trend_signals: List[TrendSignal] = Field(default_factory=list)
    regulatory_authorities: List[str] = Field(default_factory=list)
    professional_journals: List[str] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CategoryProfile:
        """Create a CategoryProfile from a raw dictionary."""
        return cls.model_validate(data)
