"""Synchronization Engine for OfflineMind.
Orchestrates verified pre-sync backups, secure payload fetching,
schema validation, atomic conflict-aware updates, and audit logging.
"""

from __future__ import annotations
import json
import logging
import uuid
from typing import List, Dict, Any, Optional
import requests

from offlinemind.config import (
    SYNC_TIMEOUT_SEC,
    ALLOW_INSECURE_HTTP,
    AUTO_SYNC_ON_CONNECT,
)
from offlinemind.db.connection import DatabaseManager
from offlinemind.db.backup import BackupManager
from offlinemind.core.knowledge_engine import KnowledgeEngine
from offlinemind.core.connectivity import ConnectivityMonitor
from offlinemind.core.conflict_resolver import ResolutionAction
from offlinemind.core.models import get_current_iso_time
from offlinemind.sync.validator import FactValidator, validate_sync_url

logger = logging.getLogger(__name__)


class SyncResult:
    """Represents outcome metrics of a synchronization execution."""

    def __init__(
        self,
        sync_id: str,
        source_url: str,
        status: str,
        start_time: str,
        end_time: str,
        facts_checked: int = 0,
        facts_updated: int = 0,
        facts_added: int = 0,
        conflicts_detected: int = 0,
        error_message: Optional[str] = None,
    ):
        self.sync_id = sync_id
        self.source_url = source_url
        self.status = status  # SUCCESS, FAILED, PARTIAL
        self.start_time = start_time
        self.end_time = end_time
        self.facts_checked = facts_checked
        self.facts_updated = facts_updated
        self.facts_added = facts_added
        self.conflicts_detected = conflicts_detected
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sync_id": self.sync_id,
            "source_url": self.source_url,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "facts_checked": self.facts_checked,
            "facts_updated": self.facts_updated,
            "facts_added": self.facts_added,
            "conflicts_detected": self.conflicts_detected,
            "error_message": self.error_message,
        }


class SyncEngine:
    """Coordinates trusted source synchronization with atomic rollback and pre-sync backups."""

    def __init__(
        self,
        db: DatabaseManager,
        knowledge_engine: KnowledgeEngine,
        backup_mgr: BackupManager,
        connectivity: ConnectivityMonitor,
        timeout: float = SYNC_TIMEOUT_SEC,
    ):
        self.db = db
        self.knowledge_engine = knowledge_engine
        self.backup_mgr = backup_mgr
        self.connectivity = connectivity
        self.timeout = timeout

        # Wire auto-sync listener on connection if enabled
        if AUTO_SYNC_ON_CONNECT:
            self.connectivity.on_connect(self._on_connection_restored)

    def _on_connection_restored(self) -> None:
        """Triggered automatically when connectivity is regained."""
        logger.info("Auto-sync triggered by online event.")
        try:
            self.sync_all()
        except Exception as e:
            logger.error("Auto-sync failed: %s", e)

    def add_trusted_source(
        self,
        name: str,
        url: str,
        priority: int = 80,
        source_type: str = "JSON",
    ) -> str:
        """Adds a remote trusted source configuration to the database."""
        source_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO trusted_sources (id, name, url, source_type, priority, is_active)
                   VALUES (?, ?, ?, ?, ?, 1)
                   ON CONFLICT(url) DO UPDATE SET
                   name = excluded.name,
                   priority = excluded.priority,
                   is_active = 1;""",
                (source_id, name.strip(), url.strip(), source_type.strip(), priority),
            )
        logger.info("Added trusted source '%s' (%s)", name, url)
        return source_id

    def list_trusted_sources(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Retrieves configured trusted sources."""
        where = "WHERE is_active = 1" if active_only else ""
        rows = self.db.fetchall(f"SELECT * FROM trusted_sources {where} ORDER BY priority DESC;")
        return [dict(r) for r in rows]

    def sync_source(self, source_url: str, priority: int = 80, source_name: str = "Remote Feed") -> SyncResult:
        """Executes a complete, safe synchronization against a single remote trusted source."""
        sync_id = str(uuid.uuid4())
        start_time = get_current_iso_time()

        # Step 1: Pre-sync snapshot backup for disaster recovery
        try:
            backup_file = self.backup_mgr.create_backup(tag=f"sync_{sync_id[:8]}")
            logger.info("Pre-sync snapshot verified at %s", backup_file.name)
        except Exception as e:
            logger.error("Failed to create pre-sync backup: %s", e)
            return self._record_sync_log(
                SyncResult(
                    sync_id=sync_id,
                    source_url=source_url,
                    status="FAILED",
                    start_time=start_time,
                    end_time=get_current_iso_time(),
                    error_message=f"Pre-sync backup failed: {e}",
                )
            )

        # Step 2: Connectivity verification
        if not self.connectivity.is_online():
            logger.warning("Sync requested while offline. Aborting.")
            return self._record_sync_log(
                SyncResult(
                    sync_id=sync_id,
                    source_url=source_url,
                    status="FAILED",
                    start_time=start_time,
                    end_time=get_current_iso_time(),
                    error_message="Cannot sync: Device is offline or in simulated offline mode.",
                )
            )

        # Step 3: Security & URL validation
        if not validate_sync_url(source_url, allow_insecure_http=ALLOW_INSECURE_HTTP):
            err_msg = f"URL '{source_url}' rejected by security policy (HTTPS required)."
            logger.error(err_msg)
            return self._record_sync_log(
                SyncResult(
                    sync_id=sync_id,
                    source_url=source_url,
                    status="FAILED",
                    start_time=start_time,
                    end_time=get_current_iso_time(),
                    error_message=err_msg,
                )
            )

        # Step 4: Fetch remote feed payload
        try:
            resp = requests.get(source_url, timeout=self.timeout)
            resp.raise_for_status()
            payload = resp.json()
        except (json.JSONDecodeError, requests.exceptions.JSONDecodeError) as e:
            logger.error("Malformed JSON received from %s: %s", source_url, e)
            return self._record_sync_log(
                SyncResult(
                    sync_id=sync_id,
                    source_url=source_url,
                    status="FAILED",
                    start_time=start_time,
                    end_time=get_current_iso_time(),
                    error_message=f"Corrupted or invalid JSON payload: {e}",
                )
            )
        except requests.exceptions.RequestException as e:
            logger.error("Network error during sync with %s: %s", source_url, e)
            return self._record_sync_log(
                SyncResult(
                    sync_id=sync_id,
                    source_url=source_url,
                    status="FAILED",
                    start_time=start_time,
                    end_time=get_current_iso_time(),
                    error_message=f"Network request failed: {e}",
                )
            )

        # Step 5: Payload validation and sanitization
        valid_facts, validation_errors = FactValidator.validate_feed_payload(
            payload=payload,
            fallback_source=source_name,
            fallback_priority=priority,
        )

        if not valid_facts and validation_errors:
            err_msg = f"Validation rejected feed: {'; '.join(validation_errors)}"
            logger.error(err_msg)
            return self._record_sync_log(
                SyncResult(
                    sync_id=sync_id,
                    source_url=source_url,
                    status="FAILED",
                    start_time=start_time,
                    end_time=get_current_iso_time(),
                    error_message=err_msg,
                )
            )

        # Step 6: Atomic SQLite Transaction to apply updates
        facts_checked = 0
        facts_updated = 0
        facts_added = 0
        conflicts_detected = 0

        try:
            with self.db.transaction():
                for fact in valid_facts:
                    facts_checked += 1
                    action, reason = self.knowledge_engine.apply_incoming_fact(fact)
                    if action == ResolutionAction.INSERT_NEW:
                        facts_added += 1
                    elif action == ResolutionAction.UPDATE_WIN:
                        facts_updated += 1
                    elif action == ResolutionAction.NEEDS_REVIEW:
                        conflicts_detected += 1

                # Update last_synced_at on trusted source record
                now_str = get_current_iso_time()
                self.db.execute(
                    "UPDATE trusted_sources SET last_synced_at = ? WHERE url = ?;",
                    (now_str, source_url),
                )

        except Exception as e:
            logger.error("Transaction failed mid-sync; rolled back. Error: %s", e)
            return self._record_sync_log(
                SyncResult(
                    sync_id=sync_id,
                    source_url=source_url,
                    status="FAILED",
                    start_time=start_time,
                    end_time=get_current_iso_time(),
                    error_message=f"Transaction rolled back: {e}",
                )
            )

        status = "PARTIAL" if validation_errors else "SUCCESS"
        err_note = "; ".join(validation_errors) if validation_errors else None

        result = SyncResult(
            sync_id=sync_id,
            source_url=source_url,
            status=status,
            start_time=start_time,
            end_time=get_current_iso_time(),
            facts_checked=facts_checked,
            facts_updated=facts_updated,
            facts_added=facts_added,
            conflicts_detected=conflicts_detected,
            error_message=err_note,
        )
        logger.info(
            "Sync completed [%s]: %d checked, %d updated, %d added, %d conflicts.",
            status, facts_checked, facts_updated, facts_added, conflicts_detected
        )
        return self._record_sync_log(result)

    def sync_all(self) -> List[SyncResult]:
        """Synchronizes across all registered active trusted sources."""
        sources = self.list_trusted_sources(active_only=True)
        results = []
        for s in sources:
            res = self.sync_source(
                source_url=s["url"],
                priority=s.get("priority", 80),
                source_name=s.get("name", "Remote Source"),
            )
            results.append(res)
        return results

    def _record_sync_log(self, result: SyncResult) -> SyncResult:
        """Persists sync audit record to sync_logs table."""
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    """INSERT INTO sync_logs (
                        sync_id, start_time, end_time, status,
                        facts_checked, facts_updated, facts_added,
                        conflicts_detected, error_message, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                    (
                        result.sync_id,
                        result.start_time,
                        result.end_time,
                        result.status,
                        result.facts_checked,
                        result.facts_updated,
                        result.facts_added,
                        result.conflicts_detected,
                        result.error_message,
                        result.source_url,
                    ),
                )
        except Exception as e:
            logger.error("Failed to write sync log entry: %s", e)
        return result

    def get_latest_sync_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent sync audit log entries."""
        rows = self.db.fetchall(
            "SELECT * FROM sync_logs ORDER BY start_time DESC LIMIT ?;",
            (limit,),
        )
        return [dict(r) for r in rows]
