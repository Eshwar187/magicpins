"""Fact extraction and provenance package."""

from app.domain.facts.fact import Fact
from app.domain.facts.extractor import extract_facts
from app.domain.facts.fingerprint import compute_canonical_fingerprint
from app.domain.facts.inventory import format_fact_inventory

__all__ = [
    "Fact",
    "extract_facts",
    "compute_canonical_fingerprint",
    "format_fact_inventory",
]
