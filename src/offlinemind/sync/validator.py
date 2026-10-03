"""Data validation, input sanitization, and security rules for sync payloads."""

from __future__ import annotations
import re
from urllib.parse import urlparse
from typing import Dict, Any, Tuple, Optional, List
from offlinemind.core.models import Fact, get_current_iso_time
from offlinemind.config import ALLOW_INSECURE_HTTP


def sanitize_text(text: Any) -> str:
    """Sanitizes text by stripping null bytes and control characters."""
    if text is None:
        return ""
    val = str(text)
    # Remove null bytes and non-printable control characters (except newline and tab)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", val)
    return sanitized.strip()


def validate_sync_url(url: str, allow_insecure_http: bool = ALLOW_INSECURE_HTTP) -> bool:
    """Validates remote source URL according to HTTPS-only security rules.
    
    HTTP is permitted only for localhost / 127.0.0.1 if allow_insecure_http is True.
    """
    try:
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return False

        if parsed.scheme == "https":
            return True

        if parsed.scheme == "http":
            host = parsed.hostname or ""
            is_loopback = host in ("127.0.0.1", "localhost", "::1")
            return allow_insecure_http and is_loopback

        return False
    except Exception:
        return False


class FactValidator:
    """Validates incoming fact dictionaries and constructs verified Fact instances."""

    @classmethod
    def validate_fact_dict(
        cls,
        data: Dict[str, Any],
        fallback_source: str = "Remote Sync",
        fallback_priority: int = 50,
        default_timestamp: Optional[str] = None,
    ) -> Tuple[Optional[Fact], Optional[str]]:
        """Validates a single raw fact dictionary.

        Returns:
            Tuple of (Fact or None, error_message or None)
        """
        if not isinstance(data, dict):
            return None, "Fact payload item must be a JSON object."

        raw_entity = data.get("entity")
        raw_attr = data.get("attribute")
        raw_val = data.get("value")

        if not raw_entity or not str(raw_entity).strip():
            return None, "Field 'entity' cannot be empty."
        if not raw_attr or not str(raw_attr).strip():
            return None, "Field 'attribute' cannot be empty."
        if raw_val is None or str(raw_val).strip() == "":
            return None, "Field 'value' cannot be empty."

        entity = sanitize_text(raw_entity)
        attribute = sanitize_text(raw_attr)
        value = sanitize_text(raw_val)

        if len(entity) > 255:
            return None, "Field 'entity' exceeds maximum length of 255 characters."
        if len(attribute) > 255:
            return None, "Field 'attribute' exceeds maximum length of 255 characters."
        if len(value) > 10000:
            return None, "Field 'value' exceeds maximum length of 10000 characters."

        # Confidence
        confidence_val = data.get("confidence", 1.0)
        try:
            confidence = float(confidence_val)
            if not (0.0 <= confidence <= 1.0):
                return None, f"Confidence must be between 0.0 and 1.0, got {confidence}."
        except (ValueError, TypeError):
            return None, f"Invalid confidence value: {confidence_val}."

        # Priority
        priority_val = data.get("source_priority", fallback_priority)
        try:
            priority = int(priority_val)
            if not (1 <= priority <= 100):
                priority = min(100, max(1, priority))
        except (ValueError, TypeError):
            priority = fallback_priority

        source = sanitize_text(data.get("source", fallback_source)) or fallback_source
        category = sanitize_text(data.get("category", "general")) or "general"
        updated_at = data.get("updated_at") or default_timestamp or get_current_iso_time()

        fact = Fact(
            entity=entity,
            attribute=attribute,
            value=value,
            source=source,
            source_priority=priority,
            category=category,
            confidence=confidence,
            updated_at=updated_at,
        )
        return fact, None

    @classmethod
    def validate_feed_payload(
        cls,
        payload: Any,
        fallback_source: str,
        fallback_priority: int = 50,
    ) -> Tuple[List[Fact], List[str]]:
        """Validates an entire feed payload (dict containing 'facts' list or raw list).

        Returns:
            Tuple of (valid_facts_list, error_messages_list)
        """
        valid_facts: List[Fact] = []
        errors: List[str] = []

        if not payload:
            return [], ["Feed payload is empty."]

        raw_facts = []
        feed_source = fallback_source
        feed_timestamp = None

        if isinstance(payload, dict):
            feed_source = sanitize_text(payload.get("source_name", fallback_source)) or fallback_source
            feed_timestamp = payload.get("timestamp")
            if "facts" in payload and isinstance(payload["facts"], list):
                raw_facts = payload["facts"]
            else:
                return [], ["Payload missing 'facts' list."]
        elif isinstance(payload, list):
            raw_facts = payload
        else:
            return [], ["Invalid payload format. Expected JSON object with 'facts' list or array."]

        for idx, item in enumerate(raw_facts):
            fact, err = cls.validate_fact_dict(
                item,
                fallback_source=feed_source,
                fallback_priority=fallback_priority,
                default_timestamp=feed_timestamp,
            )
            if err:
                errors.append(f"Fact #{idx}: {err}")
            elif fact:
                valid_facts.append(fact)

        return valid_facts, errors
