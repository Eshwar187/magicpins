"""Normalized customer domain models matching dataset/customers_seed.json."""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CustomerIdentity(BaseModel):
    """Customer identity profile."""
    model_config = ConfigDict(extra="allow")

    name: str
    phone_redacted: Optional[str] = None
    language_pref: str
    age_band: Optional[str] = None
    senior_citizen: Optional[bool] = None


class Relationship(BaseModel):
    """Customer relationship history with a specific merchant."""
    model_config = ConfigDict(extra="allow")

    first_visit: Optional[str] = None
    last_visit: Optional[str] = None
    visits_total: Optional[int] = None
    services_received: List[str] = Field(default_factory=list)
    lifetime_value: Optional[float] = None
    chronic_conditions: List[str] = Field(default_factory=list)
    favourite_dish: Optional[str] = None


class CustomerPreferences(BaseModel):
    """Customer booking preferences and communication channels.
    
    IMPORTANT: reminder_opt_in can be True, False, or None (if unrecorded).
    """
    model_config = ConfigDict(extra="allow")

    channel: Optional[str] = None
    preferred_slots: Optional[str] = None
    reminder_opt_in: Optional[bool] = None
    delivery_address: Optional[str] = None
    preferred_stylist: Optional[str] = None
    training_focus: Optional[str] = None
    wedding_date: Optional[str] = None
    family_size: Optional[int] = None
    household_size: Optional[int] = None
    office_nearby: Optional[bool] = None
    health_focus: Optional[str] = None


class Consent(BaseModel):
    """Outreach consent and permitted topics.
    
    IMPORTANT:
    - Missing/null scope is None.
    - Explicit empty list is [].
    - Explicit scope is list[str].
    Never manufacture certainty from missing data.
    """
    model_config = ConfigDict(extra="allow")

    opted_in_at: Optional[str] = None
    scope: Optional[List[str]] = None


class CustomerStateModel(BaseModel):
    """Normalized customer state."""
    model_config = ConfigDict(extra="allow")

    customer_id: str
    merchant_id: str
    identity: CustomerIdentity
    relationship: Relationship
    state: str
    preferences: CustomerPreferences
    consent: Consent

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomerStateModel:
        """Create a CustomerStateModel from a raw dictionary."""
        return cls.model_validate(data)
