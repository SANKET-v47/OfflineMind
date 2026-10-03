"""Knowledge Engine managing facts, versioning, search, and audit history."""

from __future__ import annotations
import json
import re
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from offlinemind.db.connection import DatabaseManager
from offlinemind.core.models import (
    Fact,
    FactHistoryEntry,
    ReviewQueueItem,
    SearchResult,
    compute_hash,
    get_current_iso_time,
)
from offlinemind.core.conflict_resolver import ConflictResolver, ResolutionAction

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "what", "is", "my", "the", "a", "an", "of", "and", "or", "in", "at", "for",
    "tell", "me", "about", "who", "where", "when", "how", "please", "can", "you",
    "give", "current", "name"
}


class KnowledgeEngine:
    """Core knowledge retrieval and persistence engine."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def add_fact(
        self,
        entity: str,
        attribute: str,
        value: str,
        source: str,
        source_priority: int = 50,
        category: str = "general",
        confidence: float = 1.0,
    ) -> Fact:
        """Adds a new fact to the knowledge base."""
        fact = Fact(
            entity=entity.strip(),
            attribute=attribute.strip(),
            value=value.strip(),
            source=source.strip(),
            source_priority=source_priority,
            category=category.strip(),
            confidence=confidence,
        )

        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO facts (
                    id, entity, attribute, value, category, confidence,
                    source, source_priority, version, status, created_at, updated_at, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    fact.id,
                    fact.entity,
                    fact.attribute,
                    fact.value,
                    fact.category,
                    fact.confidence,
                    fact.source,
                    fact.source_priority,
                    fact.version,
                    fact.status,
                    fact.created_at,
                    fact.updated_at,
                    fact.content_hash,
                ),
            )
            # Record initial history
            conn.execute(
                """INSERT INTO fact_history (
                    fact_id, entity, attribute, old_value, new_value, source, version, change_reason, timestamp
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, 'Initial creation', ?);""",
                (
                    fact.id,
                    fact.entity,
                    fact.attribute,
                    fact.value,
                    fact.source,
                    fact.version,
                    fact.created_at,
                ),
            )
        return fact

    def get_fact(self, entity: str, attribute: str) -> Optional[Fact]:
        """Retrieves active fact for given entity and attribute."""
        row = self.db.fetchone(
            """SELECT * FROM facts 
               WHERE LOWER(entity) = LOWER(?) AND LOWER(attribute) = LOWER(?) AND status = 'ACTIVE';""",
            (entity.strip(), attribute.strip()),
        )
        return Fact.from_row(row) if row else None

    def get_fact_by_id(self, fact_id: str) -> Optional[Fact]:
        """Retrieves fact by its primary ID."""
        row = self.db.fetchone("SELECT * FROM facts WHERE id = ?;", (fact_id,))
        return Fact.from_row(row) if row else None

    def update_fact(
        self,
        fact_id: str,
        new_value: str,
        source: str,
        source_priority: int = 50,
        reason: str = "Knowledge update",
        new_confidence: float = 1.0,
        updated_at: Optional[str] = None,
    ) -> Fact:
        """Safely updates a fact and writes an immutable entry into fact_history."""
        current = self.get_fact_by_id(fact_id)
        if not current:
            raise ValueError(f"Fact with ID '{fact_id}' not found.")

        now_str = updated_at or get_current_iso_time()
        new_version = current.version + 1
        new_hash = compute_hash(current.entity, current.attribute, new_value)

        with self.db.transaction() as conn:
            # 1. Archive prior state to fact_history
            conn.execute(
                """INSERT INTO fact_history (
                    fact_id, entity, attribute, old_value, new_value, source, version, change_reason, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    current.id,
                    current.entity,
                    current.attribute,
                    current.value,
                    new_value.strip(),
                    source.strip(),
                    current.version,
                    reason,
                    now_str,
                ),
            )
            # 2. Update active fact
            conn.execute(
                """UPDATE facts SET
                    value = ?,
                    source = ?,
                    source_priority = ?,
                    confidence = ?,
                    version = ?,
                    updated_at = ?,
                    content_hash = ?
                WHERE id = ?;""",
                (
                    new_value.strip(),
                    source.strip(),
                    source_priority,
                    new_confidence,
                    new_version,
                    now_str,
                    new_hash,
                    fact_id,
                ),
            )

        updated_fact = self.get_fact_by_id(fact_id)
        if not updated_fact:
            raise RuntimeError("Failed to retrieve fact after update.")
        return updated_fact

    def apply_incoming_fact(self, incoming: Fact) -> Tuple[ResolutionAction, str]:
        """Evaluates an incoming fact and applies conflict resolution rules."""
        current = self.get_fact(incoming.entity, incoming.attribute)
        action, reason = ConflictResolver.resolve(incoming, current)

        if action == ResolutionAction.INSERT_NEW:
            self.add_fact(
                entity=incoming.entity,
                attribute=incoming.attribute,
                value=incoming.value,
                source=incoming.source,
                source_priority=incoming.source_priority,
                category=incoming.category,
                confidence=incoming.confidence,
            )
            logger.info("Inserted new fact: (%s, %s) = '%s'", incoming.entity, incoming.attribute, incoming.value)

        elif action == ResolutionAction.UPDATE_WIN:
            assert current is not None
            self.update_fact(
                fact_id=current.id,
                new_value=incoming.value,
                source=incoming.source,
                source_priority=incoming.source_priority,
                reason=reason,
                new_confidence=incoming.confidence,
                updated_at=incoming.updated_at,
            )
            logger.info("Updated fact (%s, %s): '%s' -> '%s' (Reason: %s)", current.entity, current.attribute, current.value, incoming.value, reason)

        elif action == ResolutionAction.NEEDS_REVIEW:
            with self.db.transaction() as conn:
                conn.execute(
                    """INSERT INTO review_queue (
                        fact_id, entity, attribute, current_value, incoming_value,
                        current_source, incoming_source, current_confidence, incoming_confidence,
                        conflict_reason, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?);""",
                    (
                        current.id if current else None,
                        incoming.entity,
                        incoming.attribute,
                        current.value if current else None,
                        incoming.value,
                        current.source if current else None,
                        incoming.source,
                        current.confidence if current else None,
                        incoming.confidence,
                        reason,
                        get_current_iso_time(),
                    ),
                )
            logger.warning("Quarantined conflict to review queue: (%s, %s) '%s' vs '%s'", incoming.entity, incoming.attribute, current.value if current else "None", incoming.value)

        elif action == ResolutionAction.NO_CHANGE:
            logger.debug("Fact unchanged: (%s, %s)", incoming.entity, incoming.attribute)

        elif action == ResolutionAction.REJECT_INFERIOR:
            logger.info("Rejected inferior fact: (%s, %s) incoming value '%s' rejected. %s", incoming.entity, incoming.attribute, incoming.value, reason)

        return action, reason

    def get_history(
        self,
        entity: Optional[str] = None,
        attribute: Optional[str] = None,
        fact_id: Optional[str] = None,
    ) -> List[FactHistoryEntry]:
        """Retrieves audit history sorted by timestamp descending."""
        clauses = []
        params = []
        if fact_id:
            clauses.append("fact_id = ?")
            params.append(fact_id)
        if entity:
            clauses.append("LOWER(entity) = LOWER(?)")
            params.append(entity.strip())
        if attribute:
            clauses.append("LOWER(attribute) = LOWER(?)")
            params.append(attribute.strip())

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM fact_history {where} ORDER BY timestamp DESC, history_id DESC;"
        rows = self.db.fetchall(sql, params)
        return [FactHistoryEntry.from_row(r) for r in rows]

    def get_review_queue(self, status: str = "PENDING") -> List[ReviewQueueItem]:
        """Fetches pending conflict items from the review queue."""
        rows = self.db.fetchall(
            "SELECT * FROM review_queue WHERE status = ? ORDER BY created_at DESC;",
            (status,),
        )
        return [ReviewQueueItem.from_row(r) for r in rows]

    def resolve_review(self, item_id: int, accept_incoming: bool, notes: str = "") -> bool:
        """Manually resolves an item in the review queue."""
        row = self.db.fetchone("SELECT * FROM review_queue WHERE id = ?;", (item_id,))
        if not row:
            return False

        item = ReviewQueueItem.from_row(row)
        now_str = get_current_iso_time()
        new_status = "RESOLVED_ACCEPTED" if accept_incoming else "RESOLVED_REJECTED"

        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE review_queue SET status = ?, resolved_at = ?, resolution_notes = ? WHERE id = ?;",
                (new_status, now_str, notes, item_id),
            )
            if accept_incoming:
                if item.fact_id:
                    # Update existing fact
                    self.update_fact(
                        fact_id=item.fact_id,
                        new_value=item.incoming_value,
                        source=item.incoming_source,
                        source_priority=75,
                        reason=f"Manual resolution: {notes}",
                        new_confidence=item.incoming_confidence or 1.0,
                    )
                else:
                    # Add new fact
                    self.add_fact(
                        entity=item.entity,
                        attribute=item.attribute,
                        value=item.incoming_value,
                        source=item.incoming_source,
                        source_priority=75,
                        confidence=item.incoming_confidence or 1.0,
                    )
        return True

    def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Multi-stage search: Exact/Attribute matching -> FTS5 BM25 -> Token overlap."""
        cleaned_query = query.strip()
        tokens = [t for t in re.findall(r"\w+", cleaned_query.lower()) if t not in STOP_WORDS]
        results: Dict[str, SearchResult] = {}

        # 1. Direct Entity/Attribute check
        active_facts_rows = self.db.fetchall("SELECT * FROM facts WHERE status = 'ACTIVE';")
        active_facts = [Fact.from_row(r) for r in active_facts_rows]

        query_lower = cleaned_query.lower()
        for f in active_facts:
            e_lower = f.entity.lower()
            a_lower = f.attribute.lower()
            # If both entity and attribute are mentioned in query
            if e_lower in query_lower and a_lower in query_lower:
                results[f.id] = SearchResult(fact=f, score=1.0, match_type="exact")
            elif e_lower in query_lower or a_lower in query_lower:
                results[f.id] = SearchResult(fact=f, score=0.8, match_type="entity_attribute")

        # 2. FTS5 full-text search
        if tokens:
            # Construct FTS query using OR between tokens
            fts_query = " OR ".join([f'"{tok}"*' for tok in tokens])
            try:
                fts_rows = self.db.fetchall(
                    """SELECT rowid, rank FROM facts_fts 
                       WHERE facts_fts MATCH ? 
                       ORDER BY rank 
                       LIMIT ?;""",
                    (fts_query, limit * 2),
                )
                for r in fts_rows:
                    fact_row = self.db.fetchone(
                        "SELECT * FROM facts WHERE rowid = ? AND status = 'ACTIVE';",
                        (r["rowid"],),
                    )
                    if fact_row:
                        f = Fact.from_row(fact_row)
                        if f.id not in results:
                            # FTS rank is negative (lower = better)
                            bm25_score = 0.5 + min(0.4, 1.0 / (abs(r["rank"]) + 1.0))
                            results[f.id] = SearchResult(fact=f, score=bm25_score, match_type="fts")
            except Exception as e:
                logger.debug("FTS query failed on '%s': %s", fts_query, e)

        # 3. Fallback token overlap scoring if few results
        if len(results) < limit:
            q_token_set = set(tokens) if tokens else set(re.findall(r"\w+", query_lower))
            for f in active_facts:
                if f.id in results:
                    continue
                f_tokens = set(re.findall(r"\w+", f"{f.entity} {f.attribute} {f.value} {f.category}".lower()))
                overlap = len(q_token_set & f_tokens)
                if overlap > 0:
                    score = overlap / max(1, len(q_token_set))
                    results[f.id] = SearchResult(fact=f, score=min(0.7, score * 0.7), match_type="fuzzy")

        sorted_results = sorted(results.values(), key=lambda r: r.score, reverse=True)
        return sorted_results[:limit]

    def count_facts(self) -> int:
        """Returns total active facts in database."""
        row = self.db.fetchone("SELECT COUNT(*) FROM facts WHERE status = 'ACTIVE';")
        return row[0] if row else 0

    def seed_initial_data(self, seed_path: Optional[Path | str] = None) -> int:
        """Seeds initial default facts if database is empty."""
        if self.count_facts() > 0:
            return 0

        default_facts = [
            {
                "entity": "College",
                "attribute": "name",
                "value": "Royal Institute of Technology",
                "category": "education",
                "source": "Student Handbook 2025",
                "source_priority": 50,
                "confidence": 1.0,
            },
            {
                "entity": "College",
                "attribute": "location",
                "value": "Cambridge, Massachusetts",
                "category": "education",
                "source": "Student Handbook 2025",
                "source_priority": 50,
                "confidence": 1.0,
            },
            {
                "entity": "College",
                "attribute": "motto",
                "value": "Mens et Manus",
                "category": "education",
                "source": "Official Website",
                "source_priority": 60,
                "confidence": 1.0,
            },
            {
                "entity": "User",
                "attribute": "major",
                "value": "Computer Science & Engineering",
                "category": "personal",
                "source": "User Profile",
                "source_priority": 90,
                "confidence": 1.0,
            },
            {
                "entity": "User",
                "attribute": "graduation_year",
                "value": "2027",
                "category": "personal",
                "source": "User Profile",
                "source_priority": 90,
                "confidence": 1.0,
            },
        ]

        if seed_path and Path(seed_path).exists():
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        default_facts = data
                    elif isinstance(data, dict) and "facts" in data:
                        default_facts = data["facts"]
            except Exception as e:
                logger.warning("Failed to load seed file %s, using defaults: %s", seed_path, e)

        count = 0
        for item in default_facts:
            self.add_fact(
                entity=item["entity"],
                attribute=item["attribute"],
                value=item["value"],
                source=item.get("source", "Seed Data"),
                source_priority=item.get("source_priority", 50),
                category=item.get("category", "general"),
                confidence=item.get("confidence", 1.0),
            )
            count += 1
        logger.info("Seeded %d initial facts.", count)
        return count
