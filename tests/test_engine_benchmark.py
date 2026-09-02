"""Performance benchmark for Phase 2 decision intelligence engine."""

import json
from pathlib import Path
import time
import pytest

from app.domain.facts.extractor import extract_facts
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.candidate_generator import generate_candidates
from app.engine.decide import decide
from app.engine.scorer import rank_and_select_winner
from app.engine.signals import extract_signals

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


def test_decision_engine_benchmark():
    """Benchmark signal extraction, candidate generation, scoring, and decide across 100 runs."""
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat = CategoryProfile.from_dict(json.load(f))
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        m = MerchantState.from_dict(json.load(f)["merchants"][0])
    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        trg = TriggerState.from_dict(json.load(f)["triggers"][0])
    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as f:
        cust = CustomerStateModel.from_dict(json.load(f)["customers"][0])

    facts = extract_facts(cat, m, trg, cust)
    iterations = 100

    # 1. Signal Extraction
    t0 = time.perf_counter()
    for _ in range(iterations):
        extract_signals(cat, m, trg, cust)
    sig_latency = (time.perf_counter() - t0) / iterations

    # 2. Candidate Generation
    signals = extract_signals(cat, m, trg, cust)
    t0 = time.perf_counter()
    for _ in range(iterations):
        generate_candidates(cat, m, trg, cust, signals, facts)
    cand_latency = (time.perf_counter() - t0) / iterations

    # 3. Candidate Scoring
    candidates = generate_candidates(cat, m, trg, cust, signals, facts)
    t0 = time.perf_counter()
    for _ in range(iterations):
        rank_and_select_winner(candidates, cat, m, trg, cust, signals)
    score_latency = (time.perf_counter() - t0) / iterations

    # 4. Total decide() End-to-End
    t0 = time.perf_counter()
    for _ in range(iterations):
        decide(cat, m, trg, cust)
    decide_latency = (time.perf_counter() - t0) / iterations

    print(f"\n--- DECISION ENGINE BENCHMARK ({iterations} runs) ---")
    print(f"Signal extraction latency:   {sig_latency * 1000:.3f} ms / call")
    print(f"Candidate generation latency: {cand_latency * 1000:.3f} ms / call")
    print(f"Candidate scoring latency:    {score_latency * 1000:.3f} ms / call")
    print(f"Complete decide() latency:    {decide_latency * 1000:.3f} ms / call")

    # Assert reasonable execution time (well under 50ms)
    assert decide_latency < 0.050, f"Decide latency {decide_latency*1000:.2f}ms exceeds threshold"
