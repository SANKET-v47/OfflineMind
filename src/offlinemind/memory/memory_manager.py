"""Structured 4-Tier Memory System (Short-Term, Long-Term, Episodic, Semantic)."""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class Message:
    """Single turn in a conversation."""

    def __init__(self, role: str, content: str, timestamp: Optional[str] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}


class MemoryManager:
    """Manages multi-tier local memory with explicit user controls."""

    def __init__(self, memory_dir: Path | str, max_short_term_turns: int = 10):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.conv_dir = self.memory_dir / "conversations"
        self.conv_dir.mkdir(parents=True, exist_ok=True)
        self.profile_file = self.memory_dir / "user_profile.json"

        self.max_short_term_turns = max_short_term_turns
        self.is_enabled = True
        self.short_term: List[Message] = []
        self._load_long_term()

    def _load_long_term(self) -> None:
        if self.profile_file.exists():
            try:
                with open(self.profile_file, "r", encoding="utf-8") as f:
                    self.long_term_facts: Dict[str, Any] = json.load(f)
            except Exception as e:
                logger.warning("Failed to load user profile memory: %s", e)
                self.long_term_facts = {}
        else:
            self.long_term_facts = {}

    def _save_long_term(self) -> None:
        with open(self.profile_file, "w", encoding="utf-8") as f:
            json.dump(self.long_term_facts, f, indent=2)

    # 1. Short-Term Memory
    def add_turn(self, role: str, content: str) -> None:
        if not self.is_enabled:
            return
        self.short_term.append(Message(role=role, content=content))
        # Keep within sliding window
        if len(self.short_term) > self.max_short_term_turns * 2:
            self.short_term = self.short_term[-self.max_short_term_turns * 2:]

    def get_conversation_context(self) -> List[Dict[str, str]]:
        if not self.is_enabled:
            return []
        return [m.to_dict() for m in self.short_term]

    def clear_short_term(self) -> None:
        self.short_term.clear()

    # 2. Long-Term Memory (User-approved facts)
    def remember_fact(self, key: str, value: Any) -> None:
        if not self.is_enabled:
            return
        self.long_term_facts[key.strip()] = value
        self._save_long_term()
        logger.info("Saved long-term fact: %s = %s", key, value)

    def forget_fact(self, key: str) -> bool:
        if key in self.long_term_facts:
            del self.long_term_facts[key]
            self._save_long_term()
            return True
        return False

    def get_all_facts(self) -> Dict[str, Any]:
        return dict(self.long_term_facts)

    # 3. Episodic Memory (Saved sessions)
    def save_session(self, title: str) -> str:
        session_id = f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        data = {
            "session_id": session_id,
            "title": title,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "messages": [m.to_dict() for m in self.short_term],
        }
        file_path = self.conv_dir / f"{session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return session_id

    def list_saved_sessions(self) -> List[Dict[str, Any]]:
        sessions = []
        for p in self.conv_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append({
                        "session_id": data.get("session_id", p.stem),
                        "title": data.get("title", "Untitled Session"),
                        "saved_at": data.get("saved_at", ""),
                        "turn_count": len(data.get("messages", [])),
                    })
            except Exception:
                pass
        sessions.sort(key=lambda s: s["saved_at"], reverse=True)
        return sessions

    # 4. User Controls: Export, Import, Wipe
    def export_memory(self, export_path: Path | str) -> None:
        dump = {
            "long_term_facts": self.long_term_facts,
            "sessions": [s for s in self.list_saved_sessions()],
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2)

    def import_memory(self, import_path: Path | str) -> None:
        with open(import_path, "r", encoding="utf-8") as f:
            dump = json.load(f)
        if "long_term_facts" in dump:
            self.long_term_facts.update(dump["long_term_facts"])
            self._save_long_term()

    def clear_all_memory(self) -> None:
        """Deletes all user memory completely."""
        self.short_term.clear()
        self.long_term_facts.clear()
        if self.profile_file.exists():
            self.profile_file.unlink()
        for p in self.conv_dir.glob("*.json"):
            p.unlink()
