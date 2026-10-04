"""Central Assistant Orchestrator coordinating Router, Local LLM, Memory, RAG, Web Search, and Tools."""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Iterator, List, Optional, Dict, Any

from offlinemind.config import DATA_DIR
from offlinemind.llm.model_manager import ModelManager
from offlinemind.web.internet_manager import InternetManager, InternetState
from offlinemind.web.search import WebSearchProvider, DuckDuckGoSearchProvider, SearchResultItem
from offlinemind.web.router import QueryRouter, RouteIntent
from offlinemind.rag.vector_store import LocalVectorStore
from offlinemind.memory.memory_manager import MemoryManager
from offlinemind.tools.manager import ToolManager
from offlinemind.core.knowledge_engine import KnowledgeEngine

logger = logging.getLogger(__name__)


class AssistantOrchestrator:
    """End-to-end intelligence engine uniting offline-first local reasoning with on-demand web search."""

    def __init__(
        self,
        model_manager: Optional[ModelManager] = None,
        internet_manager: Optional[InternetManager] = None,
        search_provider: Optional[WebSearchProvider] = None,
        vector_store: Optional[LocalVectorStore] = None,
        memory_manager: Optional[MemoryManager] = None,
        tool_manager: Optional[ToolManager] = None,
        knowledge_engine: Optional[KnowledgeEngine] = None,
        web_search_enabled: bool = True,
    ):
        self.model_mgr = model_manager or ModelManager()
        self.net_mgr = internet_manager or InternetManager()
        self.net_mgr.start()
        self.search_prov = search_provider or DuckDuckGoSearchProvider()
        self.vector_store = vector_store or LocalVectorStore(DATA_DIR / "vector_db.db")
        self.memory_mgr = memory_manager or MemoryManager(DATA_DIR / "memory")
        self.tool_mgr = tool_manager or ToolManager()
        self.ke = knowledge_engine
        self.web_search_enabled = web_search_enabled

    def process_query_stream(
        self,
        query: str,
        permit_web: bool = True,
        attached_doc_path: Optional[str] = None,
    ) -> Iterator[str]:
        """Orchestrates query analysis, retrieval/tools, and yields token stream in real time."""
        clean_q = query.strip()
        if not clean_q:
            return

        # 1. Short-term memory turn registration
        self.memory_mgr.add_turn("user", clean_q)

        # 2. Check for explicit memory commands (e.g. "Remember that my car is a Honda Civic")
        if clean_q.lower().startswith("remember that ") or clean_q.lower().startswith("remember: "):
            content = clean_q.split(" ", 2)[-1]
            key = f"note_{len(self.memory_mgr.get_all_facts()) + 1}"
            self.memory_mgr.remember_fact(key, content)
            reply = f"[Memory Saved] I have committed this to my local long-term memory: '{content}'"
            self.memory_mgr.add_turn("assistant", reply)
            yield reply
            return

        # 3. Intent & Routing Analysis
        intent, reason = QueryRouter.route(clean_q, has_attached_docs=bool(attached_doc_path))
        logger.info("Routed query '%s' to intent: %s (%s)", clean_q, intent.value, reason)

        # 4. Handle Tools (e.g. Calculator, System Diagnostics)
        if intent == RouteIntent.TOOL_REQUIRED:
            if any(term in clean_q.lower() for term in ["system info", "disk space", "specs"]):
                res = self.tool_mgr.execute("system_info", {})
                if res.success:
                    reply = (
                        f"**System Diagnostics (Offline):**\n"
                        f"- OS: {res.output['os']} {res.output['os_release']} ({res.output['architecture']})\n"
                        f"- Disk Storage: {res.output['disk_free_gb']} GB free out of {res.output['disk_total_gb']} GB ({res.output['disk_used_percent']}% used)\n"
                        f"- Python Runtime: {res.output['python_version']}"
                    )
                else:
                    reply = f"Tool Error: {res.error}"
                self.memory_mgr.add_turn("assistant", reply)
                yield reply
                return
            elif any(c in clean_q for c in ["+", "*", "/", "sqrt", "sin", "cos"]):
                # Extract math expression
                import re
                expr = re.sub(r"[^\d+\-*/().\s\w]", "", clean_q.replace("calculate", "").replace("what is", "").strip())
                res = self.tool_mgr.execute("calculator", {"expression": expr})
                if res.success:
                    reply = f"**Calculation Result:** `{expr}` = **{res.output}**"
                    self.memory_mgr.add_turn("assistant", reply)
                    yield reply
                    return

        # 5. Handle Document RAG
        rag_context = ""
        rag_citations: List[str] = []
        if intent == RouteIntent.LOCAL_DOCUMENT_REQUIRED or attached_doc_path:
            rag_results = self.vector_store.search(clean_q, top_k=2)
            if rag_results:
                rag_context = "\n\n".join([f"[Doc: {r.doc_name}]: {r.text}" for r in rag_results])
                rag_citations = [f"{r.doc_name} (Relevance: {round(r.score, 2)})" for r in rag_results]

        # 6. Handle Web Search
        web_context = ""
        web_citations: List[SearchResultItem] = []
        if intent == RouteIntent.WEB_REQUIRED and self.web_search_enabled and permit_web:
            if not self.net_mgr.is_online():
                # Strictly adhere to Rule 20: Do NOT hallucinate current info if offline
                offline_warning = (
                    "[Offline Mode Notice]: You asked for current information, but your device is currently offline "
                    "or internet access is disabled. I cannot verify today's information without an active connection.\n\n"
                    "Here is what I can tell you from my offline knowledge and reasoning:\n\n"
                )
                yield offline_warning
            else:
                logger.info("Executing real-time web search for query: %s", clean_q)
                results = self.search_prov.search(clean_q, max_results=3)
                if results:
                    web_citations = results
                    web_context = "\n\n".join([f"Source [{i+1}] ({r.title} - {r.url}):\n{r.snippet}" for i, r in enumerate(results)])

        # 7. Check verified local facts from KnowledgeEngine (if configured)
        verified_facts_str = ""
        if self.ke:
            fact_results = self.ke.search(clean_q, limit=2)
            if fact_results:
                facts_list = [f"- {r.fact.entity} {r.fact.attribute}: {r.fact.value}" for r in fact_results if r.score >= 0.6]
                if facts_list:
                    verified_facts_str = "\n".join(facts_list)

        # 8. Build Prompt for Local LLM (ChatGPT / Claude / Gemini Persona & Direct Style)
        system_prompt = (
            "You are OfflineMind, a highly intelligent, direct, and concise personal AI assistant (like ChatGPT, Claude, and Gemini).\n\n"
            "Communication Rules:\n"
            "1. Be direct, clear, and focused on the key facts. Answer the user's question directly in the very first sentence.\n"
            "2. Give short, high-value, and important answers. Avoid rambling, repeating the question, or unnecessary filler words.\n"
            "3. Use clean formatting: bullet points for lists, bolding for key terms, and short paragraphs.\n"
            "4. Only provide long explanations if the user explicitly asks to 'explain in detail', 'write code', 'write an essay', or elaborate.\n"
            "5. If document context or web search results are provided below, synthesize only the most relevant facts directly.\n"
            "6. Never pretend to have real-time information if offline."
        )

        user_prompt_sections = []
        if verified_facts_str:
            user_prompt_sections.append(f"VERIFIED LOCAL KNOWLEDGE:\n{verified_facts_str}")
        if rag_context:
            user_prompt_sections.append(f"LOCAL DOCUMENT CONTEXT:\n{rag_context}")
        if web_context:
            user_prompt_sections.append(f"REAL-TIME WEB SEARCH RESULTS:\n{web_context}")

        long_term_mem = self.memory_mgr.get_all_facts()
        if long_term_mem:
            user_prompt_sections.append(f"USER PROFILE FACTS:\n{json.dumps(long_term_mem)}")

        recent_turns = self.memory_mgr.get_conversation_context(limit=4)
        if len(recent_turns) > 1:
            history_lines = [
                f"{t.get('role', 'user').capitalize()}: {t.get('content', '')}"
                if isinstance(t, dict) else f"{t.role.capitalize()}: {t.content}"
                for t in recent_turns[:-1]
            ]
            if history_lines:
                user_prompt_sections.append("RECENT CONVERSATION:\n" + "\n".join(history_lines))

        user_prompt_sections.append(f"QUESTION: {clean_q}\n\nANSWER (Concise & Direct):")
        final_prompt = "\n\n".join(user_prompt_sections)

        # 9. Stream from Local LLM Provider
        full_response_text = ""
        if self.model_mgr.active_provider.is_available():
            try:
                for token in self.model_mgr.active_provider.stream_generate(
                    prompt=final_prompt,
                    system_prompt=system_prompt,
                    temperature=0.3 if (web_context or rag_context or verified_facts_str) else 0.45,
                    num_predict=450,
                    repeat_penalty=1.15,
                ):
                    full_response_text += token
                    yield token
            except Exception as e:
                logger.warning("Local LLM stream interrupted: %s", e)
                fallback = f"\n[Model connection error: {e}]"
                yield fallback
                full_response_text += fallback
        else:
            # Fallback when no local model daemon is active
            fallback = (
                "[Notice]: Local model daemon is currently not running.\n"
                "Please run `ollama run llama3.2:1b` in PowerShell to activate the local neural model."
            )
            yield fallback
            full_response_text = fallback

        # 10. Append Citations & Provenance Footnotes
        footnotes = []
        if web_citations:
            sources_txt = "\n".join([f"- [{i+1}] [{c.title}]({c.url})" for i, c in enumerate(web_citations)])
            footnotes.append(f"\n\n**Web Sources:**\n{sources_txt}")
        if rag_citations:
            docs_txt = ", ".join(rag_citations)
            footnotes.append(f"\n\n**Document Context:** {docs_txt}")

        for fn in footnotes:
            yield fn
            full_response_text += fn

        # Record assistant answer in short-term memory
        self.memory_mgr.add_turn("assistant", full_response_text)
