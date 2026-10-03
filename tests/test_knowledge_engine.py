"""Unit tests for the KnowledgeEngine module."""

import tempfile
from pathlib import Path
import pytest
from offlinemind.db.connection import DatabaseManager
from offlinemind.core.knowledge_engine import KnowledgeEngine
from offlinemind.core.models import Fact
from offlinemind.core.conflict_resolver import ResolutionAction


@pytest.fixture
def ke_instance():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "ke_test.db"
        db = DatabaseManager(db_path)
        ke = KnowledgeEngine(db)
        yield ke
        db.close()


def test_add_and_get_fact(ke_instance):
    fact = ke_instance.add_fact(
        entity="College",
        attribute="name",
        value="Springfield Technical College",
        source="Handbook 2024",
        source_priority=50,
    )
    assert fact.id is not None
    assert fact.version == 1

    retrieved = ke_instance.get_fact("College", "name")
    assert retrieved is not None
    assert retrieved.value == "Springfield Technical College"
    assert retrieved.source == "Handbook 2024"


def test_update_fact_creates_history(ke_instance):
    fact = ke_instance.add_fact(
        entity="College",
        attribute="name",
        value="Old College",
        source="Catalog 2020",
        source_priority=50,
    )

    updated = ke_instance.update_fact(
        fact_id=fact.id,
        new_value="New College",
        source="Official Gazette 2026",
        source_priority=80,
        reason="Official rebranding",
    )
    assert updated.version == 2
    assert updated.value == "New College"

    # Check history
    history = ke_instance.get_history(entity="College", attribute="name")
    assert len(history) == 2  # initial creation + 1 update
    # Latest history entry should show old value
    latest_mutation = history[0]
    assert latest_mutation.old_value == "Old College"
    assert latest_mutation.new_value == "New College"
    assert latest_mutation.change_reason == "Official rebranding"


def test_search_exact_and_fts(ke_instance):
    ke_instance.add_fact(
        entity="University",
        attribute="chancellor",
        value="Dr. Elizabeth Warren",
        source="Directory",
    )
    ke_instance.add_fact(
        entity="Library",
        attribute="hours",
        value="Open 24/7 during finals",
        source="Notice",
    )

    # Search for chancellor
    results = ke_instance.search("Who is the chancellor?")
    assert len(results) > 0
    assert results[0].fact.entity == "University"
    assert results[0].fact.attribute == "chancellor"

    # Search for library hours
    results_lib = ke_instance.search("Tell me about library hours during finals")
    assert len(results_lib) > 0
    assert results_lib[0].fact.entity == "Library"


def test_apply_incoming_fact_scenarios(ke_instance):
    # Add initial fact
    ke_instance.add_fact(
        entity="Course",
        attribute="prerequisite",
        value="CS101",
        source="Catalog",
        source_priority=40,
    )

    # 1. Higher priority updates fact
    incoming_higher = Fact(
        entity="Course",
        attribute="prerequisite",
        value="CS102",
        source="Department Head",
        source_priority=90,
    )
    action, _ = ke_instance.apply_incoming_fact(incoming_higher)
    assert action == ResolutionAction.UPDATE_WIN

    curr = ke_instance.get_fact("Course", "prerequisite")
    assert curr.value == "CS102"
    assert curr.version == 2

    # 2. Conflicting update with equal priority & equal timestamp enters review queue
    incoming_conflict = Fact(
        entity="Course",
        attribute="prerequisite",
        value="CS103",
        source="Department Head",
        source_priority=90,
        updated_at=curr.updated_at,  # identical timestamp
    )
    action2, _ = ke_instance.apply_incoming_fact(incoming_conflict)
    assert action2 == ResolutionAction.NEEDS_REVIEW

    # Check review queue
    pending = ke_instance.get_review_queue()
    assert len(pending) == 1
    assert pending[0].incoming_value == "CS103"

    # Resolve review item
    resolved = ke_instance.resolve_review(pending[0].id, accept_incoming=True, notes="Approved by dean")
    assert resolved is True

    curr_after_review = ke_instance.get_fact("Course", "prerequisite")
    assert curr_after_review.value == "CS103"
    assert curr_after_review.version == 3
