"""Unit tests for the Database and Backup managers."""

import tempfile
import sqlite3
from pathlib import Path
import pytest
from offlinemind.db.connection import DatabaseManager
from offlinemind.db.backup import BackupManager


@pytest.fixture
def temp_db_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_db_initialization_and_schema(temp_db_dir):
    db_file = temp_db_dir / "test.db"
    db = DatabaseManager(db_file)
    assert db_file.exists()
    assert db.integrity_check() is True

    # Verify tables exist
    tables = [r[0] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table';")]
    assert "facts" in tables
    assert "fact_history" in tables
    assert "review_queue" in tables
    assert "sync_logs" in tables
    assert "trusted_sources" in tables
    assert "facts_fts" in tables
    db.close()


def test_db_transaction_and_rollback(temp_db_dir):
    db_file = temp_db_dir / "test_tx.db"
    db = DatabaseManager(db_file)

    # Successful transaction
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO facts (id, entity, attribute, value, source, created_at, updated_at)
               VALUES ('f1', 'College', 'name', 'Stanford University', 'Official', '2026-01-01', '2026-01-01');"""
        )

    row = db.fetchone("SELECT value FROM facts WHERE id='f1'")
    assert row is not None
    assert row["value"] == "Stanford University"

    # Failed transaction rolls back
    with pytest.raises(ValueError):
        with db.transaction() as conn:
            conn.execute(
                """INSERT INTO facts (id, entity, attribute, value, source, created_at, updated_at)
                   VALUES ('f2', 'College', 'motto', 'Die Luft der Freiheit weht', 'Official', '2026-01-01', '2026-01-01');"""
            )
            raise ValueError("Forced error mid-transaction")

    # f2 must not exist
    row2 = db.fetchone("SELECT * FROM facts WHERE id='f2'")
    assert row2 is None
    db.close()


def test_fts5_triggers_and_search(temp_db_dir):
    db_file = temp_db_dir / "test_fts.db"
    db = DatabaseManager(db_file)

    # Insert a fact
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO facts (id, entity, attribute, value, category, source, created_at, updated_at)
               VALUES ('fact_10', 'University of Oxford', 'founded', '1096', 'education', 'Registrar', '2026-01-01', '2026-01-01');"""
        )

    # Search in FTS5
    results = db.fetchall(
        "SELECT entity, attribute, value FROM facts_fts WHERE facts_fts MATCH 'Oxford OR 1096';"
    )
    assert len(results) == 1
    assert results[0]["entity"] == "University of Oxford"

    # Update fact and verify FTS sync
    with db.transaction() as conn:
        conn.execute(
            "UPDATE facts SET value = 'Circa 1096' WHERE id = 'fact_10';"
        )

    results_updated = db.fetchall(
        "SELECT value FROM facts_fts WHERE facts_fts MATCH 'Circa';"
    )
    assert len(results_updated) == 1
    assert results_updated[0]["value"] == "Circa 1096"
    db.close()


def test_backup_and_restore(temp_db_dir):
    db_file = temp_db_dir / "main.db"
    backup_dir = temp_db_dir / "backups"
    db = DatabaseManager(db_file)

    # Seed data
    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO facts (id, entity, attribute, value, source, created_at, updated_at)
               VALUES ('f_snap', 'Host', 'OS', 'Windows 11', 'SystemInfo', '2026-01-01', '2026-01-01');"""
        )

    # Create backup
    backup_mgr = BackupManager(db_file, backup_dir, max_backups=2)
    b1 = backup_mgr.create_backup("test")
    assert b1.exists()
    assert len(backup_mgr.list_backups()) == 1

    # Modify main db
    with db.transaction() as conn:
        conn.execute("UPDATE facts SET value = 'Ubuntu 24.04' WHERE id = 'f_snap';")

    row_modified = db.fetchone("SELECT value FROM facts WHERE id = 'f_snap'")
    assert row_modified["value"] == "Ubuntu 24.04"
    db.close()

    # Restore from backup
    assert backup_mgr.restore_backup(b1) is True

    # Re-open db and check value was restored to Windows 11
    db_restored = DatabaseManager(db_file)
    row_restored = db_restored.fetchone("SELECT value FROM facts WHERE id = 'f_snap'")
    assert row_restored["value"] == "Windows 11"
    db_restored.close()


def test_nested_transaction_savepoints(temp_db_dir):
    db_file = temp_db_dir / "nested_tx.db"
    db = DatabaseManager(db_file)

    with db.transaction() as conn:
        conn.execute(
            """INSERT INTO facts (id, entity, attribute, value, source, created_at, updated_at)
               VALUES ('parent', 'Tree', 'root', 'Oak', 'Botany', '2026-01-01', '2026-01-01');"""
        )
        # Inner transaction that fails
        try:
            with db.transaction() as inner_conn:
                inner_conn.execute(
                    """INSERT INTO facts (id, entity, attribute, value, source, created_at, updated_at)
                       VALUES ('child_fail', 'Leaf', 'color', 'Red', 'Botany', '2026-01-01', '2026-01-01');"""
                )
                raise RuntimeError("Inner failure")
        except RuntimeError:
            pass

        # Another inner transaction that succeeds
        with db.transaction() as inner_conn2:
            inner_conn2.execute(
                """INSERT INTO facts (id, entity, attribute, value, source, created_at, updated_at)
                   VALUES ('child_ok', 'Leaf', 'color', 'Green', 'Botany', '2026-01-01', '2026-01-01');"""
            )

    # parent and child_ok must exist, child_fail must NOT exist
    assert db.fetchone("SELECT * FROM facts WHERE id = 'parent'") is not None
    assert db.fetchone("SELECT * FROM facts WHERE id = 'child_ok'") is not None
    assert db.fetchone("SELECT * FROM facts WHERE id = 'child_fail'") is None
    db.close()

