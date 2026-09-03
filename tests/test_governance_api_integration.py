"""End-to-end integration and adversarial tests for Phase 5 outreach governance."""

import json
from pathlib import Path
import pytest
from tests.client import TestClient
from app.main import app
from app.api.routes import get_service

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


@pytest.fixture
def populated_client():
    service = get_service()
    service.clear()
    client = TestClient(app)

    for p in (DATASET_DIR / "categories").glob("*.json"):
        with open(p, "r", encoding="utf-8") as f:
            cat_data = json.load(f)
            client.post("/v1/context", json={"scope": "category", "context_id": cat_data["slug"], "version": 1, "payload": cat_data})

    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        for m in json.load(f)["merchants"]:
            client.post("/v1/context", json={"scope": "merchant", "context_id": m["merchant_id"], "version": 1, "payload": m})

    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as f:
        for c in json.load(f)["customers"]:
            client.post("/v1/context", json={"scope": "customer", "context_id": c["customer_id"], "version": 1, "payload": c})

    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        for t in json.load(f)["triggers"]:
            client.post("/v1/context", json={"scope": "trigger", "context_id": t["id"], "version": 1, "payload": t})

    yield client
    service.clear()


def test_sequential_tick_cooldown_lifecycle(populated_client):
    """Verify lifecycle: T1 sends -> duplicate T1 suppresses -> T2 after cooldown sends."""
    trg_id = "trg_018_supply_atorvastatin_recall"  # Supply alert, expires 2026-05-30

    # 1. First tick at T0 -> SEND
    r1 = populated_client.post("/v1/tick", json={"now": "2026-04-26T10:00:00Z", "available_triggers": [trg_id]}).json()
    assert len(r1["actions"]) == 1

    # 2. Immediate re-tick at T0+10min -> SUPPRESS
    r2 = populated_client.post("/v1/tick", json={"now": "2026-04-26T10:10:00Z", "available_triggers": [trg_id]}).json()
    assert r2 == {"actions": []}

    # 3. Tick after 32 days (post-monthly cooldown) -> SEND
    r3 = populated_client.post("/v1/tick", json={"now": "2026-05-29T11:00:00Z", "available_triggers": [trg_id]}).json()
    assert len(r3["actions"]) == 1


def test_merchant_multi_trigger_batch_governance(populated_client):
    """Verify single merchant with multiple triggers in one batch only sends 1 proactive message."""
    # Dr. Meera has trg_001 (research) and trg_022 (cde webinar)
    trgs = ["trg_001_research_digest_dentists", "trg_022_cde_webinar_dentists"]
    resp = populated_client.post("/v1/tick", json={"now": "2026-04-26T10:00:00Z", "available_triggers": trgs}).json()
    # First qualifies, second is suppressed under merchant daily frequency cap
    assert len(resp["actions"]) == 1
    assert resp["actions"][0]["trigger_id"] == "trg_001_research_digest_dentists"


@pytest.mark.parametrize("trg_id", [
    "trg_001_research_digest_dentists",
    "trg_003_recall_due_priya",
    "trg_007_bridal_followup_kavya",
    "trg_008_curious_ask_studio11",
    "trg_010_ipl_match_delhi",
    "trg_013_corporate_thali_planning",
    "trg_014_seasonal_acquisition_dip_powerhouse",
    "trg_015_winback_rashmi",
    "trg_018_supply_atorvastatin_recall",
    "trg_019_chronic_refill_grandfather",
])
def test_canonical_cases_sendable_in_clean_isolation(populated_client, trg_id):
    """Verify each canonical case passes governance when ticked in clean isolation."""
    get_service().governance.clear()
    resp = populated_client.post("/v1/tick", json={"now": "2026-04-26T10:00:00Z", "available_triggers": [trg_id]}).json()
    assert len(resp["actions"]) == 1
    assert resp["actions"][0]["trigger_id"] == trg_id


def test_adversarial_malformed_timestamp(populated_client):
    """Verify malformed simulation timestamp fails safe without unhandled 500 crashes."""
    resp = populated_client.post("/v1/tick", json={"now": "not-a-valid-date", "available_triggers": ["trg_001_research_digest_dentists"]})
    assert resp.status_code == 200
    assert "actions" in resp.json()


def test_adversarial_empty_triggers(populated_client):
    """Verify empty trigger list returns empty actions safely."""
    resp = populated_client.post("/v1/tick", json={"now": "2026-04-26T10:00:00Z", "available_triggers": []})
    assert resp.status_code == 200
    assert resp.json() == {"actions": []}
