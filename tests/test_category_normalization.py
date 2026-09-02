"""Tests for category profile normalization across all 5 challenge verticals."""

import json
from pathlib import Path
import pytest

from app.domain.models.category import CategoryProfile

CATEGORIES_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset" / "categories"


def test_all_five_categories_normalize_successfully():
    """Ensure dentists, salons, restaurants, gyms, and pharmacies all load and validate."""
    expected_slugs = {"dentists", "salons", "restaurants", "gyms", "pharmacies"}
    category_files = list(CATEGORIES_DIR.glob("*.json"))
    assert len(category_files) == 5, f"Expected 5 category files, found {len(category_files)}"

    loaded_slugs = set()
    for cat_file in category_files:
        with open(cat_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        profile = CategoryProfile.from_dict(raw)
        assert profile.slug in expected_slugs
        assert profile.display_name
        assert profile.voice.tone
        assert profile.voice.register
        assert len(profile.voice.vocab_allowed) > 0
        assert len(profile.voice.vocab_taboo) > 0
        assert len(profile.offer_catalog) > 0
        assert len(profile.digest) > 0
        assert profile.peer_stats.avg_rating > 0
        assert profile.peer_stats.avg_ctr > 0
        loaded_slugs.add(profile.slug)

    assert loaded_slugs == expected_slugs


def test_dentists_specific_fields():
    """Verify dental vertical clinical fields and taboos."""
    with open(CATEGORIES_DIR / "dentists.json", "r", encoding="utf-8") as f:
        raw = json.load(f)

    profile = CategoryProfile.from_dict(raw)
    assert profile.voice.tone == "peer_clinical"
    assert "guaranteed" in profile.voice.vocab_taboo
    assert "fluoride varnish" in profile.voice.vocab_allowed
    assert profile.peer_stats.retention_6mo_pct == 0.42

    # Check JIDA digest item
    jida_item = next((d for d in profile.digest if d.id == "d_2026W17_jida_fluoride"), None)
    assert jida_item is not None
    assert jida_item.trial_n == 2100
    assert jida_item.patient_segment == "high_risk_adults"
    assert "JIDA Oct 2026, p.14" in jida_item.source


def test_gyms_specific_fields():
    """Verify gym vertical peer stats and coach voice."""
    with open(CATEGORIES_DIR / "gyms.json", "r", encoding="utf-8") as f:
        raw = json.load(f)

    profile = CategoryProfile.from_dict(raw)
    assert profile.voice.tone == "energetic_disciplined"
    assert profile.peer_stats.monthly_churn_pct == 0.08
    assert profile.peer_stats.trial_to_paid_pct == 0.32
    assert "guaranteed weight loss" in profile.voice.vocab_taboo


def test_restaurants_specific_fields():
    """Verify restaurant operator voice and retention."""
    with open(CATEGORIES_DIR / "restaurants.json", "r", encoding="utf-8") as f:
        raw = json.load(f)

    profile = CategoryProfile.from_dict(raw)
    assert profile.voice.tone == "warm_busy_practical"
    assert profile.peer_stats.retention_30d_pct == 0.18
    assert "viral guarantee" in profile.voice.vocab_taboo
