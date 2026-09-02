"""Benchmark for normalization and fact extraction performance."""

import json
from pathlib import Path
import time
import pytest

from app.domain.facts.extractor import extract_facts
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


def test_normalization_and_fact_extraction_benchmark():
    """Benchmark normalization and fact extraction performance across 100 iterations."""
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        raw_cat = json.load(f)
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        raw_m = json.load(f)["merchants"][0]
    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        raw_trg = json.load(f)["triggers"][0]
    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as f:
        raw_cust = json.load(f)["customers"][0]

    iterations = 100

    # 1. Normalization Benchmark
    start_norm = time.perf_counter()
    for _ in range(iterations):
        cat = CategoryProfile.from_dict(raw_cat)
        m = MerchantState.from_dict(raw_m)
        trg = TriggerState.from_dict(raw_trg)
        cust = CustomerStateModel.from_dict(raw_cust)
    norm_duration = (time.perf_counter() - start_norm) / iterations

    # 2. Fact Extraction Benchmark
    cat = CategoryProfile.from_dict(raw_cat)
    m = MerchantState.from_dict(raw_m)
    trg = TriggerState.from_dict(raw_trg)
    cust = CustomerStateModel.from_dict(raw_cust)

    start_extract = time.perf_counter()
    for _ in range(iterations):
        facts = extract_facts(cat, m, trg, cust)
    extract_duration = (time.perf_counter() - start_extract) / iterations

    combined_duration = norm_duration + extract_duration

    print(f"\n--- BENCHMARK RESULTS ({iterations} runs) ---")
    print(f"Normalization latency: {norm_duration * 1000:.3f} ms / call")
    print(f"Fact extraction latency: {extract_duration * 1000:.3f} ms / call")
    print(f"Combined latency: {combined_duration * 1000:.3f} ms / call")

    # Ensure latency is reasonable (well within 30s per-call budget, under 50ms)
    assert combined_duration < 0.050, f"Combined latency {combined_duration*1000:.2f}ms exceeds 50ms threshold"
