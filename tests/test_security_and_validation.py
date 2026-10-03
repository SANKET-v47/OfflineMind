"""Security, sanitization, and resilience edge-case tests for OfflineMind."""

import tempfile
from pathlib import Path
import pytest
from offlinemind.db.connection import DatabaseManager
from offlinemind.core.knowledge_engine import KnowledgeEngine
from offlinemind.core.models import Fact
from offlinemind.sync.validator import sanitize_text, FactValidator


@pytest.fixture
def clean_ke():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sec_test.db"
        db = DatabaseManager(db_path)
        ke = KnowledgeEngine(db)
        yield ke, db
        db.close()


def test_sql_injection_resilience(clean_ke):
    ke, db = clean_ke
    # Attempt SQL injection in entity, attribute, value
    malicious_entity = "College'); DROP TABLE facts; --"
    malicious_value = "'; SELECT * FROM sqlite_master; --"

    fact = ke.add_fact(
        entity=malicious_entity,
        attribute="name",
        value=malicious_value,
        source="Untrusted",
    )
    assert fact.id is not None

    # Verify tables still intact
    tables = [r[0] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table';")]
    assert "facts" in tables

    # Retrieve and verify exact string stored safely
    retrieved = ke.get_fact(malicious_entity, "name")
    assert retrieved is not None
    assert retrieved.value == malicious_value


def test_control_character_and_null_byte_sanitization():
    raw_text = "Stanford\x00 University\x07\x08 of\x1b Science"
    sanitized = sanitize_text(raw_text)
    assert "\x00" not in sanitized
    assert "\x07" not in sanitized
    assert "\x08" not in sanitized
    assert "\x1b" not in sanitized
    assert "Stanford University of Science" == sanitized


def test_large_payload_truncation_or_rejection():
    # Fact exceeding maximum allowed attribute length
    giant_attr = "a" * 300
    _, err = FactValidator.validate_fact_dict({
        "entity": "College",
        "attribute": giant_attr,
        "value": "Test",
    })
    assert err is not None
    assert "exceeds maximum length" in err


def test_duplicate_fact_content_hash(clean_ke):
    ke, _ = clean_ke
    f1 = ke.add_fact("College", "city", "Palo Alto", "Catalog")
    # Query back
    f_stored = ke.get_fact("College", "city")
    assert f_stored.content_hash == f1.content_hash

    # Submitting identical incoming fact
    incoming_same = Fact(
        entity="College",
        attribute="city",
        value="Palo Alto",
        source="Catalog",
    )
    action, reason = ke.apply_incoming_fact(incoming_same)
    assert action.value == "NO_CHANGE"


def test_empty_database_query(clean_ke):
    ke, _ = clean_ke
    results = ke.search("What is my college?")
    assert len(results) == 0


def test_malformed_timestamp_resilience(clean_ke):
    ke, _ = clean_ke
    current = ke.add_fact("College", "code", "1234", "System", 50)

    # Incoming fact with invalid/corrupted timestamp format
    incoming = Fact(
        entity="College",
        attribute="code",
        value="5678",
        source="System",
        source_priority=50,
        updated_at="NOT_A_VALID_DATE_STRING",
    )
    # Conflict resolver should safely parse without throwing exceptions
    action, reason = ke.apply_incoming_fact(incoming)
    assert action is not None
