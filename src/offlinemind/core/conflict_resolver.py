"""Conflict resolution module for incoming knowledge facts.
Determines whether to insert, update, reject, or quarantine facts into the review queue.
"""

from __future__ import annotations
from enum import Enum
from typing import Tuple, Optional
from datetime import datetime, timezone
from offlinemind.core.models import Fact


class ResolutionAction(str, Enum):
    INSERT_NEW = "INSERT_NEW"
    NO_CHANGE = "NO_CHANGE"
    UPDATE_WIN = "UPDATE_WIN"
    REJECT_INFERIOR = "REJECT_INFERIOR"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ConflictResolver:
    """Evaluates incoming facts against existing facts using priority, timestamps, and confidence."""

    @staticmethod
    def _parse_iso(timestamp_str: str) -> datetime:
        """Safely parses ISO timestamp strings normalized to UTC."""
        try:
            clean_str = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    @classmethod
    def resolve(
        cls,
        incoming: Fact,
        current: Optional[Fact],
    ) -> Tuple[ResolutionAction, str]:
        """Resolves conflict between an incoming fact and an existing fact.

        Returns:
            Tuple of (ResolutionAction, reason_string)
        """
        # Case 1: No existing fact exists for this entity & attribute
        if current is None:
            return ResolutionAction.INSERT_NEW, "Initial discovery of fact."

        # Case 2: Identical value already stored
        if incoming.value.strip().lower() == current.value.strip().lower():
            return ResolutionAction.NO_CHANGE, "Fact value unchanged."

        # Case 3: Priority comparison
        if incoming.source_priority > current.source_priority:
            return (
                ResolutionAction.UPDATE_WIN,
                f"Source priority ({incoming.source_priority} for '{incoming.source}') "
                f"exceeds current ({current.source_priority} for '{current.source}').",
            )

        if incoming.source_priority < current.source_priority:
            return (
                ResolutionAction.REJECT_INFERIOR,
                f"Incoming source priority ({incoming.source_priority}) is lower than "
                f"current ({current.source_priority}). Keeping current value.",
            )

        # Case 4: Equal priority -> Compare timestamps and confidence
        in_time = cls._parse_iso(incoming.updated_at)
        curr_time = cls._parse_iso(current.updated_at)

        # Confidence delta check
        conf_diff = incoming.confidence - current.confidence

        if in_time > curr_time:
            # Newer timestamp
            if conf_diff < -0.2:
                # Newer but noticeably lower confidence -> Quarantine for review
                return (
                    ResolutionAction.NEEDS_REVIEW,
                    f"Incoming fact is newer ({incoming.updated_at} vs {current.updated_at}) "
                    f"but confidence is significantly lower ({incoming.confidence:.2f} vs {current.confidence:.2f}).",
                )
            return (
                ResolutionAction.UPDATE_WIN,
                f"Newer timestamp from equal-priority source ({incoming.updated_at} > {current.updated_at}).",
            )

        elif in_time < curr_time:
            # Stale incoming fact
            return (
                ResolutionAction.REJECT_INFERIOR,
                f"Incoming fact timestamp is older ({incoming.updated_at} < {current.updated_at}).",
            )

        else:
            # Same timestamp, different values
            if incoming.confidence > current.confidence:
                return (
                    ResolutionAction.UPDATE_WIN,
                    f"Equal timestamp and priority, but higher confidence ({incoming.confidence:.2f} > {current.confidence:.2f}).",
                )
            elif incoming.confidence < current.confidence:
                return (
                    ResolutionAction.REJECT_INFERIOR,
                    f"Equal timestamp and priority, but lower confidence ({incoming.confidence:.2f} < {current.confidence:.2f}).",
                )
            else:
                return (
                    ResolutionAction.NEEDS_REVIEW,
                    "Conflicting values from equal-priority source with identical timestamps and confidence.",
                )
