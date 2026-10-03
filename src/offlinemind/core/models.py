"""Data models representing knowledge facts, history, conflict items, and search results."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import hashlib
import uuid


def generate_id() -> str:
    """Generates a UUID4 string."""
    return str(uuid.uuid4())


def get_current_iso_time() -> str:
    """Returns current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def compute_hash(entity: str, attribute: str, value: str) -> str:
    """Computes a SHA-256 hash for fact deduplication."""
    content = f"{entity.strip().lower()}:{attribute.strip().lower()}:{value.strip()}".encode("utf-8")
    return hashlib.sha256(content).hexdigest()


@dataclass
class Fact:
    """Represents a discrete knowledge unit."""
    entity: str
    attribute: str
    value: str
    source: str
    id: str = field(default_factory=generate_id)
    category: str = "general"
    confidence: float = 1.0
    source_priority: int = 50
    version: int = 1
    status: str = "ACTIVE"  # ACTIVE, ARCHIVED, NEEDS_REVIEW
    created_at: str = field(default_factory=get_current_iso_time)
    updated_at: str = field(default_factory=get_current_iso_time)
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = compute_hash(self.entity, self.attribute, self.value)

    @classmethod
    def from_row(cls, row: Any) -> Fact:
        """Constructs Fact from sqlite3.Row or dict."""
        return cls(
            id=row["id"],
            entity=row["entity"],
            attribute=row["attribute"],
            value=row["value"],
            category=row["category"],
            confidence=float(row["confidence"]),
            source=row["source"],
            source_priority=int(row["source_priority"]),
            version=int(row["version"]),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            content_hash=row["content_hash"] or "",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity": self.entity,
            "attribute": self.attribute,
            "value": self.value,
            "category": self.category,
            "confidence": self.confidence,
            "source": self.source,
            "source_priority": self.source_priority,
            "version": self.version,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "content_hash": self.content_hash,
        }


@dataclass
class FactHistoryEntry:
    """Represents an immutable historical audit record of a fact mutation."""
    fact_id: str
    entity: str
    attribute: str
    old_value: Optional[str]
    new_value: str
    source: str
    version: int
    change_reason: str
    timestamp: str = field(default_factory=get_current_iso_time)
    history_id: Optional[int] = None

    @classmethod
    def from_row(cls, row: Any) -> FactHistoryEntry:
        return cls(
            history_id=row["history_id"],
            fact_id=row["fact_id"],
            entity=row["entity"],
            attribute=row["attribute"],
            old_value=row["old_value"],
            new_value=row["new_value"],
            source=row["source"],
            version=int(row["version"]),
            change_reason=row["change_reason"] or "",
            timestamp=row["timestamp"],
        )


@dataclass
class ReviewQueueItem:
    """Represents an ambiguous update requiring manual review."""
    entity: str
    attribute: str
    incoming_value: str
    incoming_source: str
    conflict_reason: str
    id: Optional[int] = None
    fact_id: Optional[str] = None
    current_value: Optional[str] = None
    current_source: Optional[str] = None
    current_confidence: Optional[float] = None
    incoming_confidence: Optional[float] = None
    status: str = "PENDING"  # PENDING, RESOLVED_ACCEPTED, RESOLVED_REJECTED
    created_at: str = field(default_factory=get_current_iso_time)
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None

    @classmethod
    def from_row(cls, row: Any) -> ReviewQueueItem:
        return cls(
            id=row["id"],
            fact_id=row["fact_id"],
            entity=row["entity"],
            attribute=row["attribute"],
            current_value=row["current_value"],
            incoming_value=row["incoming_value"],
            current_source=row["current_source"],
            incoming_source=row["incoming_source"],
            current_confidence=float(row["current_confidence"]) if row["current_confidence"] is not None else None,
            incoming_confidence=float(row["incoming_confidence"]) if row["incoming_confidence"] is not None else None,
            conflict_reason=row["conflict_reason"],
            status=row["status"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
            resolution_notes=row["resolution_notes"],
        )


@dataclass
class SearchResult:
    """Represents a matched fact with relevance scoring."""
    fact: Fact
    score: float
    match_type: str  # "exact", "fts", "fuzzy"


@dataclass
class Answer:
    """Structured answer returned to the user."""
    text: str
    facts_used: List[Fact]
    provenance: str
    model_used: str  # "ollama:phi3:mini", "rule-based-retrieval", etc.
    confidence: float
    history_note: Optional[str] = None
