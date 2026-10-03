"""Unit tests for the ConflictResolver logic."""

import pytest
from offlinemind.core.models import Fact
from offlinemind.core.conflict_resolver import ConflictResolver, ResolutionAction


def test_insert_new_when_no_current_fact():
    incoming = Fact(entity="College", attribute="mascot", value="Wildcat", source="Official")
    action, reason = ConflictResolver.resolve(incoming, None)
    assert action == ResolutionAction.INSERT_NEW


def test_no_change_when_values_match():
    current = Fact(entity="College", attribute="name", value="Springfield Tech", source="Old Source")
    incoming = Fact(entity="College", attribute="name", value="Springfield Tech", source="New Source")
    action, reason = ConflictResolver.resolve(incoming, current)
    assert action == ResolutionAction.NO_CHANGE


def test_priority_wins():
    current = Fact(
        entity="College", attribute="name", value="Old College",
        source="Student Blog", source_priority=30
    )
    incoming = Fact(
        entity="College", attribute="name", value="New College",
        source="Official Registrar", source_priority=90
    )
    action, reason = ConflictResolver.resolve(incoming, current)
    assert action == ResolutionAction.UPDATE_WIN
    assert "exceeds current" in reason


def test_inferior_priority_rejected():
    current = Fact(
        entity="College", attribute="name", value="Official College",
        source="Official Registrar", source_priority=90
    )
    incoming = Fact(
        entity="College", attribute="name", value="Fake College",
        source="Random Forum", source_priority=20
    )
    action, reason = ConflictResolver.resolve(incoming, current)
    assert action == ResolutionAction.REJECT_INFERIOR


def test_equal_priority_newest_timestamp_wins():
    current = Fact(
        entity="College", attribute="dean", value="Dr. Smith",
        source="Directory", source_priority=50, updated_at="2026-01-01T10:00:00"
    )
    incoming = Fact(
        entity="College", attribute="dean", value="Dr. Roberts",
        source="Directory", source_priority=50, updated_at="2026-02-01T10:00:00"
    )
    action, reason = ConflictResolver.resolve(incoming, current)
    assert action == ResolutionAction.UPDATE_WIN


def test_equal_priority_older_timestamp_rejected():
    current = Fact(
        entity="College", attribute="dean", value="Dr. Roberts",
        source="Directory", source_priority=50, updated_at="2026-02-01T10:00:00"
    )
    incoming = Fact(
        entity="College", attribute="dean", value="Dr. Smith",
        source="Directory", source_priority=50, updated_at="2026-01-01T10:00:00"
    )
    action, reason = ConflictResolver.resolve(incoming, current)
    assert action == ResolutionAction.REJECT_INFERIOR


def test_lower_confidence_quarantined_to_review():
    current = Fact(
        entity="College", attribute="president", value="Alice Cooper",
        source="SourceA", source_priority=50, confidence=1.0, updated_at="2026-01-01T10:00:00"
    )
    # Incoming is newer, but confidence drops significantly to 0.4
    incoming = Fact(
        entity="College", attribute="president", value="Bob Marley",
        source="SourceA", source_priority=50, confidence=0.4, updated_at="2026-02-01T10:00:00"
    )
    action, reason = ConflictResolver.resolve(incoming, current)
    assert action == ResolutionAction.NEEDS_REVIEW
