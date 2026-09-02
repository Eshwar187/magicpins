"""Immutable grounded fact representation with full provenance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from app.domain.facts.fingerprint import canonical_json_dumps, compute_canonical_fingerprint
from app.domain.models.enums import FactType


@dataclass(frozen=True)
class Fact:
    """A grounded, verifiable business fact extracted directly from supplied context.
    
    Contains exact provenance linking it to its source context and path.
    """
    fact_id: str
    fact_type: str
    name: str
    value: Any
    source_scope: str
    source_context_id: str
    source_version: int
    source_path: str
    timestamp: Optional[str] = None

    @classmethod
    def create(
        cls,
        fact_type: FactType | str,
        name: str,
        value: Any,
        source_scope: str,
        source_context_id: str,
        source_version: int,
        source_path: str,
        timestamp: Optional[str] = None,
    ) -> Fact:
        """Factory method computing a deterministic fact_id from provenance and value."""
        ft_val = fact_type.value if isinstance(fact_type, FactType) else str(fact_type)
        identity_payload = {
            "source_scope": source_scope,
            "source_context_id": source_context_id,
            "source_path": source_path,
            "fact_type": ft_val,
            "value": value,
        }
        fact_id = compute_canonical_fingerprint(identity_payload)
        return cls(
            fact_id=fact_id,
            fact_type=ft_val,
            name=name,
            value=value,
            source_scope=source_scope,
            source_context_id=source_context_id,
            source_version=source_version,
            source_path=source_path,
            timestamp=timestamp,
        )

    @property
    def sort_key(self) -> Tuple[str, str, str, str, str]:
        """Documented stable ordering tuple for deterministic fact sorting."""
        return (
            self.source_scope,
            self.source_context_id,
            self.source_path,
            self.fact_type,
            canonical_json_dumps(self.value),
        )

    def __lt__(self, other: Fact) -> bool:
        return self.sort_key < other.sort_key
