"""Performance benchmark measuring HTTP request latency across 100 representative requests."""

import json
from pathlib import Path
import statistics
import time
from tests.client import TestClient

from app.main import app
from app.api.routes import get_service

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


def test_api_performance_100_requests():
    """Benchmark end-to-end latency for 100 tick requests."""
    service = get_service()
    service.clear()
    client = TestClient(app)

    # 1. Setup context
    with open(DATASET_DIR / "categories" / "restaurants.json", "r", encoding="utf-8") as f:
        cat_data = json.load(f)
    client.post("/v1/context", json={"scope": "category", "context_id": "restaurants", "version": 1, "payload": cat_data})

    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        merchants = {m["merchant_id"]: m for m in json.load(f)["merchants"]}
    m_data = merchants["m_005_pizzajunction_restaurant_delhi"]
    client.post("/v1/context", json={"scope": "merchant", "context_id": m_data["merchant_id"], "version": 1, "payload": m_data})

    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        triggers = {t["id"]: t for t in json.load(f)["triggers"]}
    trg_data = triggers["trg_010_ipl_match_delhi"]
    client.post("/v1/context", json={"scope": "trigger", "context_id": trg_data["id"], "version": 1, "payload": trg_data})

    latencies_ms = []
    error_count = 0

    for _ in range(100):
        t0 = time.perf_counter()
        resp = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trg_data["id"]]})
        elapsed = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed)
        if resp.status_code != 200:
            error_count += 1

    mean_lat = statistics.mean(latencies_ms)
    median_lat = statistics.median(latencies_ms)
    p95_lat = statistics.quantiles(latencies_ms, n=20)[18]  # 95th percentile
    max_lat = max(latencies_ms)

    print(f"\n--- LATENCY BENCHMARK (100 runs) ---")
    print(f"Mean: {mean_lat:.2f}ms | Median: {median_lat:.2f}ms | P95: {p95_lat:.2f}ms | Max: {max_lat:.2f}ms | Errors: {error_count}")

    # Latency must be comfortably sub-second (usually < 10ms in-process)
    assert mean_lat < 100.0
    assert p95_lat < 200.0
    assert error_count == 0
