"""LLM client integrating Ollama with high-accuracy rule-based extractive fallback."""

from __future__ import annotations
import json
import logging
from typing import List, Optional
import requests

from offlinemind.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SEC
from offlinemind.core.models import Answer, Fact, FactHistoryEntry, SearchResult

logger = logging.getLogger(__name__)


class LLMService:
    """Provides grounded question answering via Ollama or extractive retrieval fallback."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout: float = OLLAMA_TIMEOUT_SEC,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _is_server_reachable(self) -> bool:
        """Fast socket probe to check if Ollama port is open."""
        import socket
        from urllib.parse import urlparse
        try:
            parsed = urlparse(self.base_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 11434
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except Exception:
            return False

    def is_ollama_available(self) -> bool:
        """Checks if local Ollama daemon is reachable and model is present."""
        if not self._is_server_reachable():
            return False

        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=1.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                if models:
                    model_base = self.model.split(":")[0]
                    # If specified model is present, keep it; otherwise use the first locally available model
                    if not any(model_base in m for m in models):
                        self.model = models[0]
                    return True
        except Exception:
            pass
        return False

    def generate_answer(
        self,
        query: str,
        search_results: List[SearchResult],
        history_entries: Optional[List[FactHistoryEntry]] = None,
        include_provenance: bool = True,
    ) -> Answer:
        """Generates an answer grounded in verified facts, or via local neural LLM."""
        facts_used = [r.fact for r in search_results if r.score >= 0.5]
        if not facts_used and search_results:
            facts_used = [search_results[0].fact]

        # 1. If local neural LLM (Ollama) is available, use it
        if self.is_ollama_available():
            try:
                answer = self._call_ollama(query, facts_used, history_entries, include_provenance)
                if answer:
                    return answer
            except Exception as e:
                logger.warning("Ollama inference failed, falling back to extractive QA: %s", e)

        # 2. If no facts matched and no LLM is running
        if not facts_used:
            return Answer(
                text=(
                    "I do not have verified knowledge about that in my local offline knowledge base.\n\n"
                    "💡 *To chat with me freely like ChatGPT on any topic offline, start a local neural model (like Ollama: `ollama run phi3:mini` or `llama3.2`).*"
                ),
                facts_used=[],
                provenance="No matching local records found. Start Ollama for open-domain chat.",
                model_used="retrieval-fallback",
                confidence=0.0,
            )

        # 3. Deterministic, accurate retrieval-augmented extractive QA
        return self._generate_extractive_answer(query, facts_used[0], history_entries, include_provenance)

    def _call_ollama(
        self,
        query: str,
        facts: List[Fact],
        history_entries: Optional[List[FactHistoryEntry]],
        include_provenance: bool,
    ) -> Optional[Answer]:
        """Calls local Ollama instance with grounded context or general conversational prompt."""
        if facts:
            context_lines = []
            for f in facts:
                context_lines.append(f"- Entity: {f.entity}, {f.attribute}: {f.value} (Source: {f.source}, Updated: {f.updated_at}, Version: {f.version})")

            history_lines = []
            if history_entries:
                for h in history_entries[:3]:
                    if h.old_value:
                        history_lines.append(f"- Previously was '{h.old_value}', updated to '{h.new_value}' on {h.timestamp} from {h.source} (Reason: {h.change_reason})")

            prompt = (
                "You are OfflineMind, a trustworthy offline-first AI assistant. "
                "Answer the user's question using the provided verified facts below. "
                "If the fact has a recorded historical change, mention what it was previously, when it was updated, and the source.\n\n"
                f"VERIFIED FACTS:\n{chr(10).join(context_lines)}\n\n"
            )
            if history_lines:
                prompt += f"UPDATE HISTORY:\n{chr(10).join(history_lines)}\n\n"
            prompt += f"QUESTION: {query}\n\nANSWER (concise and factual):"
            prov_text = self._build_provenance_str(facts[0])
            conf = facts[0].confidence
        else:
            prompt = (
                "You are OfflineMind, a helpful and intelligent offline AI assistant running locally on the user's device. "
                "Answer the user's question clearly, informatively, and accurately in real time.\n\n"
                f"QUESTION: {query}\n\n"
                "ANSWER:"
            )
            prov_text = f"Local Neural LLM ({self.model}) | Completely Offline"
            conf = 0.9

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3 if facts else 0.7, "top_p": 0.9},
        }

        resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
        if resp.status_code == 200:
            raw_text = resp.json().get("response", "").strip()
            return Answer(
                text=raw_text,
                facts_used=facts,
                provenance=prov_text,
                model_used=f"ollama:{self.model}",
                confidence=conf,
            )
        return None

    def _generate_extractive_answer(
        self,
        query: str,
        fact: Fact,
        history_entries: Optional[List[FactHistoryEntry]],
        include_provenance: bool,
    ) -> Answer:
        """Deterministic, grammatically clean answer generation without LLM overhead."""
        q_lower = query.lower()

        # Format natural text based on attribute and entity
        if fact.attribute.lower() in ("name", "title"):
            if fact.entity.lower() in ("user", "self", "person"):
                main_text = f"Your name is **{fact.value}**."
            elif fact.entity.lower() in ("college", "university", "school", "institution"):
                main_text = f"Your college name is **{fact.value}**."
            else:
                main_text = f"The {fact.attribute} of {fact.entity} is **{fact.value}**."
        elif fact.attribute.lower() in ("capital", "capital_city"):
            main_text = f"The capital of {fact.entity} is **{fact.value}**."
        elif fact.attribute.lower() in ("location", "city", "address"):
            main_text = f"The {fact.attribute} of {fact.entity} is **{fact.value}**."
        elif fact.attribute.lower() in ("major", "degree"):
            main_text = f"Your {fact.attribute} is **{fact.value}**."
        elif fact.attribute.lower() in ("founded", "year", "established"):
            main_text = f"{fact.entity} was founded in **{fact.value}**."
        else:
            main_text = f"{fact.entity} {fact.attribute.replace('_', ' ')}: **{fact.value}**."

        # Check for history / update explanation
        history_note = None
        if history_entries:
            # Filter mutations where value actually changed
            mutations = [h for h in history_entries if h.old_value is not None]
            if mutations:
                latest_m = mutations[0]
                history_note = (
                    f"Notice: This fact was updated from '{latest_m.old_value}' "
                    f"to '{latest_m.new_value}' on {latest_m.timestamp[:10]} "
                    f"from source '{latest_m.source}'."
                )
                if latest_m.change_reason:
                    history_note += f" (Reason: {latest_m.change_reason})"

        full_answer_text = main_text
        if history_note:
            full_answer_text += f"\n\n> ℹ️ {history_note}"

        prov_str = self._build_provenance_str(fact)
        if include_provenance and "provenance" in q_lower:
            full_answer_text += f"\n\n**Provenance:** {prov_str}"

        return Answer(
            text=full_answer_text,
            facts_used=[fact],
            provenance=prov_str,
            model_used="retrieval-extractive",
            confidence=fact.confidence,
            history_note=history_note,
        )

    @staticmethod
    def _build_provenance_str(fact: Fact) -> str:
        """Formats verifiable provenance string."""
        return (
            f"Source: {fact.source} (Priority: {fact.source_priority}) | "
            f"Last Updated: {fact.updated_at[:19]} UTC | "
            f"Version: v{fact.version} | "
            f"Confidence: {int(fact.confidence * 100)}%"
        )
