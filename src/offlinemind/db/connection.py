"""Database connection and transaction manager for OfflineMind."""

from __future__ import annotations
import sqlite3
import threading
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Any, List, Dict
from offlinemind.db.schema import SCHEMA_SQL

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite connections, schema initialization, and atomic transactions."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a thread-local SQLite connection with optimal pragmas."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=20.0,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            conn.row_factory = sqlite3.Row
            # Enable Foreign Keys & WAL mode for high concurrency and crash resilience
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 10000;")
            self._local.conn = conn
        return self._local.conn

    def init_db(self) -> None:
        """Initializes database schema and FTS5 virtual tables."""
        conn = self.get_connection()
        try:
            with conn:
                conn.executescript(SCHEMA_SQL)
            logger.info("Database initialized successfully at %s", self.db_path)
        except Exception as e:
            logger.error("Failed to initialize database schema: %s", e)
            raise

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager providing an atomic transaction with nested savepoint support."""
        conn = self.get_connection()
        if not hasattr(self._local, "tx_depth"):
            self._local.tx_depth = 0

        depth = self._local.tx_depth
        sp_name = f"sp_{depth}"

        try:
            if depth == 0:
                conn.execute("BEGIN IMMEDIATE;")
            else:
                conn.execute(f"SAVEPOINT {sp_name};")
            self._local.tx_depth += 1

            yield conn

            self._local.tx_depth -= 1
            if depth == 0:
                conn.commit()
            else:
                conn.execute(f"RELEASE {sp_name};")
        except Exception as e:
            self._local.tx_depth -= 1
            if depth == 0:
                try:
                    conn.rollback()
                except Exception:
                    pass
            else:
                try:
                    conn.execute(f"ROLLBACK TO {sp_name};")
                    conn.execute(f"RELEASE {sp_name};")
                except Exception:
                    pass
            logger.error("Transaction/Savepoint rolled back due to error: %s", e)
            raise

    def execute(self, sql: str, params: tuple | list | dict = ()) -> sqlite3.Cursor:
        """Executes a SQL query and returns the cursor."""
        conn = self.get_connection()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_seq: List[tuple | list | dict]) -> sqlite3.Cursor:
        """Executes many SQL statements."""
        conn = self.get_connection()
        return conn.executemany(sql, params_seq)

    def fetchone(self, sql: str, params: tuple | list | dict = ()) -> Optional[sqlite3.Row]:
        """Fetches a single row."""
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def fetchall(self, sql: str, params: tuple | list | dict = ()) -> List[sqlite3.Row]:
        """Fetches all rows."""
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def integrity_check(self) -> bool:
        """Runs SQLite integrity check to ensure database is not corrupted."""
        row = self.fetchone("PRAGMA integrity_check;")
        if row and row[0] == "ok":
            return True
        logger.warning("Database integrity check failed: %s", row[0] if row else "unknown")
        return False

    def close(self) -> None:
        """Closes the current thread's connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
