"""Tests for trigger normalization and payload accessibility."""

import json
from pathlib import Path
import pytest

from app.domain.models.trigger import TriggerState

TRIGGERS_SEED_FILE = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset" / "triggers_seed.json"


def test_all_seed_triggers_normalize_successfully():
    """Ensure all 25 seed triggers normalize without errors."""
    with open(TRIGGERS_SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)["triggers"]

    assert len(data) == 25
    for raw in data:
        t = TriggerState.from_dict(raw)
        assert t.id == raw["id"]
        assert t.scope in ("merchant", "customer")
        assert t.source in ("external", "internal")
        assert 1 <= t.urgency <= 5
        assert t.suppression_key
        assert isinstance(t.payload, dict)
        assert t.payload == raw["payload"]


def test_demonstrated_payload_accessors():
    """Verify convenience properties on real trigger kinds."""
    with open(TRIGGERS_SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)["triggers"]

    # 1. Research Digest
    t_res = TriggerState.from_dict(next(t for t in data if t["id"] == "trg_001_research_digest_dentists"))
    assert t_res.top_item_id == "d_2026W17_jida_fluoride"

    # 2. Perf Dip
    t_dip = TriggerState.from_dict(next(t for t in data if t["id"] == "trg_004_perf_dip_bharat"))
    assert t_dip.metric == "calls"
    assert t_dip.delta_pct == -0.50
    assert t_dip.window == "7d"

    # 3. Recall Due (Customer scope)
    t_rec = TriggerState.from_dict(next(t for t in data if t["id"] == "trg_003_recall_due_priya"))
    assert t_rec.customer_id == "c_001_priya_for_m001"
    assert t_rec.service_due == "6_month_cleaning"
    assert t_rec.available_slots is not None
    assert len(t_rec.available_slots) == 2

    # 4. Supply Alert
    t_sup = TriggerState.from_dict(next(t for t in data if t["id"] == "trg_018_supply_atorvastatin_recall"))
    assert t_sup.urgency == 5
    assert t_sup.molecule == "atorvastatin"
    assert t_sup.affected_batches == ["AT2024-1102", "AT2024-1108"]


def test_forward_compatible_payload_preservation():
    """Verify that forward-compatible / injected payload fields survive in raw payload."""
    injected_raw = {
        "id": "trg_injected_999",
        "scope": "merchant",
        "kind": "future_unseen_kind",
        "source": "external",
        "merchant_id": "m_001",
        "payload": {
            "custom_future_metric": 42.5,
            "nested_data": {"deep_key": "val"},
        },
        "urgency": 2,
        "suppression_key": "future:m_001",
    }
    t = TriggerState.from_dict(injected_raw)
    assert t.payload["custom_future_metric"] == 42.5
    assert t.payload["nested_data"]["deep_key"] == "val"
