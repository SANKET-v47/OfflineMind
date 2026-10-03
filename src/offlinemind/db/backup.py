"""Database backup and restoration manager for OfflineMind.
Ensures point-in-time consistent snapshots using SQLite Online Backup API.
"""

from __future__ import annotations
import sqlite3
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages pre-sync snapshots, rotation, and restoration."""

    def __init__(self, db_path: Path | str, backup_dir: Path | str, max_backups: int = 10):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.max_backups = max_backups

    def create_backup(self, tag: str = "pre_sync") -> Path:
        """Creates a consistent point-in-time snapshot of the database."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        backup_file = self.backup_dir / f"{self.db_path.stem}_{tag}_{timestamp}.db"

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file does not exist at {self.db_path}")

        # Use SQLite Online Backup API for consistency
        src_conn = sqlite3.connect(str(self.db_path))
        dst_conn = sqlite3.connect(str(backup_file))
        try:
            with dst_conn:
                src_conn.backup(dst_conn, pages=100)
            logger.info("Created database snapshot at %s", backup_file)
        finally:
            src_conn.close()
            dst_conn.close()

        # Verify backup integrity
        verify_conn = sqlite3.connect(str(backup_file))
        try:
            cur = verify_conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            res = cur.fetchone()
            if not res or res[0] != "ok":
                backup_file.unlink(missing_ok=True)
                raise RuntimeError(f"Backup verification failed: {res[0] if res else 'Unknown error'}")
        finally:
            verify_conn.close()

        # Rotate old backups
        self._rotate_backups()
        return backup_file

    def _rotate_backups(self) -> None:
        """Keeps only the most recent `max_backups` snapshot files."""
        backups = self.list_backups()
        if len(backups) > self.max_backups:
            to_delete = backups[self.max_backups :]
            for b in to_delete:
                try:
                    b.unlink(missing_ok=True)
                    logger.debug("Pruned old backup: %s", b.name)
                except Exception as e:
                    logger.warning("Failed to remove old backup %s: %s", b, e)

    def list_backups(self) -> List[Path]:
        """Returns all backup files sorted by modification time descending."""
        files = list(self.backup_dir.glob(f"{self.db_path.stem}_*.db"))
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    def get_latest_backup(self) -> Optional[Path]:
        """Returns the most recent backup file if any."""
        backups = self.list_backups()
        return backups[0] if backups else None

    def restore_backup(self, backup_file: Path | str) -> bool:
        """Restores the database from a verified backup file."""
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found at {backup_path}")

        # Verify integrity of backup first
        verify_conn = sqlite3.connect(str(backup_path))
        try:
            cur = verify_conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            res = cur.fetchone()
            if not res or res[0] != "ok":
                raise RuntimeError(f"Cannot restore corrupted backup: {res[0] if res else 'unknown'}")
        finally:
            verify_conn.close()

        # Copy to active database location
        shutil.copy2(str(backup_path), str(self.db_path))
        logger.info("Successfully restored database from %s to %s", backup_path, self.db_path)
        return True
