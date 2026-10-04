"""Native graphical user interface for OfflineMind using Tkinter."""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from pathlib import Path
from typing import Optional

from offlinemind.config import DB_PATH, BACKUP_DIR, SEED_DATA_PATH, DATA_DIR
from offlinemind.db.connection import DatabaseManager
from offlinemind.db.backup import BackupManager
from offlinemind.core.knowledge_engine import KnowledgeEngine
from offlinemind.core.connectivity import ConnectivityMonitor
from offlinemind.llm.llm_client import LLMService
from offlinemind.sync.sync_engine import SyncEngine
from offlinemind.core.orchestrator import AssistantOrchestrator


class OfflineMindGUI(tk.Tk):
    """Main Application Window for OfflineMind."""

    def __init__(self):
        super().__init__()
        self.title("OfflineMind - Personal AI Assistant (Offline-First)")
        self.geometry("980x740")
        self.minsize(800, 600)

        # Initialize Backend Components
        self.db = DatabaseManager(DB_PATH)
        self.bm = BackupManager(DB_PATH, BACKUP_DIR)
        self.ke = KnowledgeEngine(self.db)
        self.ke.seed_initial_data(SEED_DATA_PATH)
        self.monitor = ConnectivityMonitor()
        self.monitor.start()
        self.llm = LLMService()
        self.sync_engine = SyncEngine(self.db, self.ke, self.bm, self.monitor)

        # Unified Orchestrator (RAG, Web Search, Memory, Tools, Local LLM)
        self.orchestrator = AssistantOrchestrator(
            model_manager=self.llm.model_mgr,
            knowledge_engine=self.ke,
            web_search_enabled=True,
        )

        # Seed default trusted source if database has none configured
        if not self.sync_engine.list_trusted_sources(active_only=False):
            from offlinemind.config import MOCK_SERVER_URL
            self.sync_engine.add_trusted_source(
                name="Official University Registrar",
                url=f"{MOCK_SERVER_URL}/api/trusted_feed",
                priority=85,
            )

        self.include_prov_var = tk.BooleanVar(value=True)
        self.web_enabled_var = tk.BooleanVar(value=True)
        self._stop_stream_event = threading.Event()

        self._configure_styles()
        self._build_ui()
        self._start_status_poller()

        # Welcome message in chat
        self._append_assistant_message(
            "Hello! I am **OfflineMind**, your private, offline-first personal AI assistant.\n\n"
            "• I run locally on your computer with complete privacy.\n"
            "• I can chat, write code, analyze local documents, run calculations, and remember facts.\n"
            "• When online and permitted, I can search the web for real-time information with citations.\n"
            "• You can toggle Web Search, manage local memory, or index documents using the toolbar above.",
            provenance="Local Neural Engine & Embedded Knowledge Base | Status: Ready",
        )

    def _configure_styles(self):
        """Configures modern colors and TTK theme."""
        self.configure(bg="#181825")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background="#181825")
        style.configure("Card.TFrame", background="#1e1e2e", relief="flat")
        style.configure("Header.TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 13, "bold"))
        style.configure("Status.TLabel", background="#1e1e2e", foreground="#a6adc8", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=5)

    def _build_ui(self):
        # 1. Top Header Card
        header_card = ttk.Frame(self, style="Card.TFrame", padding=12)
        header_card.pack(fill="x", padx=14, pady=10)

        # Left Title
        title_box = ttk.Frame(header_card, style="Card.TFrame")
        title_box.pack(side="left")
        ttk.Label(title_box, text="🧠 OfflineMind", style="Header.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Private Offline-First Personal AI Assistant with Real-Time Web Intelligence", style="Status.TLabel").pack(anchor="w")

        # Right Status Pills
        status_box = ttk.Frame(header_card, style="Card.TFrame")
        status_box.pack(side="right")

        self.net_badge = tk.Label(
            status_box, text="● CHECKING", bg="#45475a", fg="#cdd6f4",
            font=("Segoe UI", 9, "bold"), padx=10, pady=4, relief="flat"
        )
        self.net_badge.pack(side="left", padx=4)

        self.engine_badge = tk.Label(
            status_box, text="⚡ LLM", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 9, "bold"), padx=10, pady=4, relief="flat"
        )
        self.engine_badge.pack(side="left", padx=4)

        self.web_badge = tk.Label(
            status_box, text="🌐 Web: ON", bg="#89b4fa", fg="#11111b",
            font=("Segoe UI", 9, "bold"), padx=10, pady=4, relief="flat"
        )
        self.web_badge.pack(side="left", padx=4)

        self.docs_badge = tk.Label(
            status_box, text="📄 0 Docs", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 9, "bold"), padx=10, pady=4, relief="flat"
        )
        self.docs_badge.pack(side="left", padx=4)

        # 2. Controls Toolbar
        toolbar = ttk.Frame(self, style="TFrame")
        toolbar.pack(fill="x", padx=14, pady=(0, 10))

        btn_new_chat = tk.Button(
            toolbar, text="🗑️ New Chat", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 9), command=self._on_new_chat_clicked, relief="flat", padx=10, pady=4
        )
        btn_new_chat.pack(side="left", padx=(0, 6))

        self.btn_web_toggle = tk.Button(
            toolbar, text="🌐 Web: Enabled", bg="#89b4fa", fg="#11111b",
            font=("Segoe UI", 9, "bold"), command=self._on_toggle_web_clicked, relief="flat", padx=10, pady=4
        )
        self.btn_web_toggle.pack(side="left", padx=6)

        btn_memory = tk.Button(
            toolbar, text="🧠 Memory", bg="#cba6f7", fg="#11111b",
            font=("Segoe UI", 9, "bold"), command=self._show_memory_window, relief="flat", padx=10, pady=4
        )
        btn_memory.pack(side="left", padx=6)

        btn_docs = tk.Button(
            toolbar, text="📄 Documents (RAG)", bg="#f9e2af", fg="#11111b",
            font=("Segoe UI", 9, "bold"), command=self._show_documents_window, relief="flat", padx=10, pady=4
        )
        btn_docs.pack(side="left", padx=6)

        self.btn_toggle_offline = tk.Button(
            toolbar, text="🔒 Force Offline", bg="#45475a", fg="#cdd6f4",
            font=("Segoe UI", 9), command=self._on_toggle_offline_clicked, relief="flat", padx=10, pady=4
        )
        self.btn_toggle_offline.pack(side="left", padx=6)

        btn_sync = tk.Button(
            toolbar, text="🔄 Sync Sources", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 9), command=self._on_sync_clicked, relief="flat", padx=10, pady=4
        )
        btn_sync.pack(side="left", padx=6)

        btn_history = tk.Button(
            toolbar, text="📜 History", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 9), command=self._show_history_window, relief="flat", padx=10, pady=4
        )
        btn_history.pack(side="left", padx=6)

        # 3. Main Chat History
        chat_frame = ttk.Frame(self, style="TFrame")
        chat_frame.pack(fill="both", expand=True, padx=14, pady=0)

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, wrap="word", bg="#1e1e2e", fg="#cdd6f4",
            font=("Segoe UI", 10), insertbackground="#cdd6f4",
            padx=14, pady=14, relief="flat"
        )
        self.chat_display.pack(fill="both", expand=True)
        self.chat_display.config(state="disabled")

        # Chat tag styles
        self.chat_display.tag_config("user_header", foreground="#89b4fa", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("user_body", foreground="#cdd6f4", font=("Segoe UI", 10))
        self.chat_display.tag_config("ai_header", foreground="#a6e3a1", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("ai_body", foreground="#cdd6f4", font=("Segoe UI", 10))
        self.chat_display.tag_config("provenance", foreground="#9399b2", font=("Segoe UI", 8, "italic"))
        self.chat_display.tag_config("history_alert", foreground="#fab387", font=("Segoe UI", 9, "bold"))

        # 4. Input Area Card
        input_card = ttk.Frame(self, style="Card.TFrame", padding=10)
        input_card.pack(fill="x", padx=14, pady=12)

        self.entry_query = tk.Entry(
            input_card, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
            font=("Segoe UI", 11), relief="flat"
        )
        self.entry_query.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self.entry_query.bind("<Return>", lambda e: self._on_send_clicked())
        self.entry_query.focus_set()

        self.btn_stop = tk.Button(
            input_card, text="⏹ Stop", bg="#45475a", fg="#cdd6f4",
            font=("Segoe UI", 9), command=self._on_stop_clicked, relief="flat", padx=10, pady=4, state="disabled"
        )
        self.btn_stop.pack(side="left", padx=(0, 8))

        btn_send = tk.Button(
            input_card, text="Send ➔", bg="#89b4fa", fg="#11111b",
            font=("Segoe UI", 10, "bold"), activebackground="#b4befe",
            command=self._on_send_clicked, relief="flat", padx=16, pady=4
        )
        btn_send.pack(side="right")

    def _start_status_poller(self):
        """Starts periodic refresh of network badges."""
        def poll():
            while True:
                time.sleep(1.5)
                try:
                    self.after(0, self._update_status_badges)
                except Exception:
                    break

        t = threading.Thread(target=poll, daemon=True)
        t.start()

    def _update_status_badges(self):
        """Refreshes status badges on UI thread."""
        is_online = self.monitor.is_online()
        is_sim = self.monitor.is_simulated_offline()

        if is_online:
            self.net_badge.config(text="● ONLINE", bg="#10b981", fg="#ffffff")
        elif is_sim:
            self.net_badge.config(text="● SIM OFFLINE", bg="#ef4444", fg="#ffffff")
        else:
            self.net_badge.config(text="● OFFLINE", bg="#ef4444", fg="#ffffff")

        # Update button text
        if is_sim:
            self.btn_toggle_offline.config(text="🌐 Disable Simulated Offline", bg="#f38ba8", fg="#11111b")
        else:
            self.btn_toggle_offline.config(text="🌐 Force Simulated Offline", bg="#45475a", fg="#cdd6f4")

        # LLM badge
        if self.llm.is_ollama_available():
            self.engine_badge.config(text="⚡ Ollama", bg="#89b4fa", fg="#11111b")
        else:
            self.engine_badge.config(text="🔍 Local Extractive", bg="#313244", fg="#a6adc8")

        # Web Search badge
        if self.web_enabled_var.get() and is_online:
            self.web_badge.config(text="🌐 Web: ACTIVE", bg="#a6e3a1", fg="#11111b")
        elif self.web_enabled_var.get() and not is_online:
            self.web_badge.config(text="🌐 Web: OFFLINE", bg="#45475a", fg="#fab387")
        else:
            self.web_badge.config(text="🌐 Web: DISABLED", bg="#313244", fg="#6c7086")

        # Document count badge
        doc_count = len(self.orchestrator.vector_store.list_documents())
        self.docs_badge.config(text=f"📄 {doc_count} Docs")

    def _on_toggle_web_clicked(self):
        curr = self.web_enabled_var.get()
        self.web_enabled_var.set(not curr)
        self.orchestrator.web_search_enabled = not curr
        if not curr:
            self.btn_web_toggle.config(text="🌐 Web: Enabled", bg="#89b4fa", fg="#11111b")
        else:
            self.btn_web_toggle.config(text="🌐 Web: Disabled", bg="#45475a", fg="#cdd6f4")
        self._update_status_badges()

    def _on_new_chat_clicked(self):
        self.orchestrator.memory_mgr.clear_short_term()
        self.chat_display.config(state="normal")
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state="disabled")
        self._append_assistant_message(
            "New conversation started. Memory buffer cleared. How can I help you?",
            provenance="New Session",
        )

    def _on_stop_clicked(self):
        self._stop_stream_event.set()
        self.btn_stop.config(state="disabled")

    def _on_toggle_offline_clicked(self):
        curr_sim = self.monitor.is_simulated_offline()
        self.monitor.set_simulated_offline(not curr_sim)
        self.orchestrator.net_mgr.set_force_offline(not curr_sim)
        self._update_status_badges()

    def _on_sync_clicked(self):
        """Runs synchronization in a background thread."""
        if not self.monitor.is_online():
            messagebox.showwarning(
                "Offline",
                "Cannot synchronize: Network is currently offline.\n"
                "If simulated offline is enabled, toggle it to online first."
            )
            return

        def run_sync():
            results = self.sync_engine.sync_all()
            if not results:
                self.after(0, lambda: messagebox.showwarning(
                    "No Sources Configured",
                    "No trusted sources found in database.\nUse '📥 Import JSON' or register a feed URL."
                ))
                return
            total_up = sum(r.facts_updated for r in results)
            total_add = sum(r.facts_added for r in results)
            failed = [r for r in results if r.status == "FAILED"]
            if failed:
                err_details = "\n".join(f"• {r.source_url}:\n  {r.error_message}" for r in failed)
                status_summary = (
                    f"Sync Finished with Warnings:\n"
                    f"• Facts Updated: {total_up}\n"
                    f"• Facts Added: {total_add}\n"
                    f"• Sources Synced: {len(results) - len(failed)}/{len(results)}\n\n"
                    f"Failed Source(s):\n{err_details}\n\n"
                    f"Tip: If testing locally, ensure the mock server is running:\n  python run_mock_server.py"
                )
                self.after(0, lambda: messagebox.showwarning("Sync Warning", status_summary))
            else:
                status_summary = (
                    f"Sync Completed Successfully!\n"
                    f"• Facts Updated: {total_up}\n"
                    f"• Facts Added: {total_add}\n"
                    f"• Sources Synced: {len(results)}"
                )
                self.after(0, lambda: messagebox.showinfo("Sync Success", status_summary))
            self.after(0, self._update_status_badges)

        threading.Thread(target=run_sync, daemon=True).start()

    def _on_send_clicked(self):
        query = self.entry_query.get().strip()
        if not query:
            return

        self.entry_query.delete(0, tk.END)
        self._append_user_message(query)
        self.btn_stop.config(state="normal")
        self._stop_stream_event.clear()

        def process_query():
            self.after(0, self._prepare_assistant_bubble)
            try:
                for chunk in self.orchestrator.process_query_stream(
                    query=query,
                    permit_web=self.web_enabled_var.get(),
                ):
                    if self._stop_stream_event.is_set():
                        self.after(0, lambda: self._append_stream_chunk("\n[⏹ Generation stopped by user.]"))
                        break
                    self.after(0, lambda c=chunk: self._append_stream_chunk(c))
            except Exception as e:
                self.after(0, lambda err=e: self._append_stream_chunk(f"\n[Error: {err}]"))

            self.after(0, lambda: self._finish_assistant_stream(None))
            self.after(0, lambda: self.btn_stop.config(state="disabled"))

        threading.Thread(target=process_query, daemon=True).start()

    def _append_user_message(self, text: str):
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, f"\nYou\n", "user_header")
        self.chat_display.insert(tk.END, f"{text}\n", "user_body")
        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")

    def _prepare_assistant_bubble(self):
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, f"\nOfflineMind\n", "ai_header")
        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")

    def _append_stream_chunk(self, chunk: str):
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, chunk, "ai_body")
        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")

    def _finish_assistant_stream(self, provenance: Optional[str] = None):
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, "\n")
        if provenance:
            self.chat_display.insert(tk.END, f"[{provenance}]\n", "provenance")
        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")

    def _append_assistant_message(self, text: str, provenance: Optional[str] = None, history_note: Optional[str] = None):
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, f"\nOfflineMind\n", "ai_header")
        self.chat_display.insert(tk.END, f"{text}\n", "ai_body")
        if provenance:
            self.chat_display.insert(tk.END, f"[{provenance}]\n", "provenance")
        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")

    def _show_history_window(self):
        """Displays audit history in a clean modal dialog."""
        records = self.ke.get_history()
        win = tk.Toplevel(self)
        win.title("Audit Version History")
        win.geometry("750x450")
        win.configure(bg="#181825")

        tree_frame = ttk.Frame(win, padding=10)
        tree_frame.pack(fill="both", expand=True)

        cols = ("Time", "Version", "Entity", "Attribute", "Old Value", "New Value", "Source")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        tree.column("Time", width=140)
        tree.column("Old Value", width=120)
        tree.column("New Value", width=120)

        for r in records:
            tree.insert("", "end", values=(
                r.timestamp[:19], f"v{r.version}", r.entity, r.attribute,
                r.old_value or "(Initial)", r.new_value, r.source
            ))

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _show_review_window(self):
        """Displays pending conflict items for manual review."""
        items = self.ke.get_review_queue(status="PENDING")
        win = tk.Toplevel(self)
        win.title("Conflict Review Queue")
        win.geometry("700x400")
        win.configure(bg="#181825")

        if not items:
            lbl = tk.Label(win, text="✓ No pending conflicts in review queue.", bg="#181825", fg="#a6e3a1", font=("Segoe UI", 12))
            lbl.pack(pady=50)
            return

        lbl = tk.Label(win, text=f"Pending Conflicts ({len(items)} items)", bg="#181825", fg="#cdd6f4", font=("Segoe UI", 11, "bold"))
        lbl.pack(anchor="w", padx=14, pady=8)

        cols = ("ID", "Entity", "Attribute", "Current", "Incoming", "Reason")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for col in cols:
            tree.heading(col, text=col)
        tree.pack(fill="both", expand=True, padx=14, pady=8)

        for it in items:
            tree.insert("", "end", values=(it.id, it.entity, it.attribute, it.current_value, it.incoming_value, it.conflict_reason))

    def _show_add_fact_window(self):
        """Displays a dialog allowing the user to add or update facts manually."""
        win = tk.Toplevel(self)
        win.title("➕ Add Verified Fact")
        win.geometry("460x420")
        win.configure(bg="#181825")
        win.resizable(False, False)

        tk.Label(win, text="Add New Knowledge Fact", bg="#181825", fg="#89b4fa", font=("Segoe UI", 12, "bold")).pack(pady=(16, 12))

        form_frame = tk.Frame(win, bg="#181825")
        form_frame.pack(fill="x", padx=24)

        fields = [
            ("Entity (e.g. User, India, College):", "entity_entry"),
            ("Attribute (e.g. name, capital, location):", "attr_entry"),
            ("Value (e.g. Sanket, New Delhi):", "val_entry"),
            ("Source (e.g. User Profile, Manual Entry):", "source_entry"),
            ("Category (e.g. personal, geography, education):", "cat_entry"),
        ]

        entries = {}
        for label_text, key in fields:
            lbl = tk.Label(form_frame, text=label_text, bg="#181825", fg="#cdd6f4", font=("Segoe UI", 9), anchor="w")
            lbl.pack(fill="x", pady=(4, 1))
            ent = tk.Entry(form_frame, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4", relief="flat", font=("Segoe UI", 10))
            ent.pack(fill="x", ipady=3)
            entries[key] = ent

        entries["source_entry"].insert(0, "User Manual Entry")
        entries["cat_entry"].insert(0, "general")

        def save_fact():
            entity = entries["entity_entry"].get().strip()
            attr = entries["attr_entry"].get().strip()
            val = entries["val_entry"].get().strip()
            source = entries["source_entry"].get().strip() or "User Manual Entry"
            cat = entries["cat_entry"].get().strip() or "general"

            if not entity or not attr or not val:
                messagebox.showerror("Validation Error", "Entity, Attribute, and Value are all required.", parent=win)
                return

            incoming = Fact(
                entity=entity,
                attribute=attr,
                value=val,
                source=source,
                source_priority=80,
                category=cat,
                confidence=1.0,
            )
            action, reason = self.ke.apply_incoming_fact(incoming)
            self._update_status_badges()
            self._append_assistant_message(
                f"✅ Fact saved: **{entity}**'s {attr} is **{val}**.\n(Action: {action.value} | {reason})",
                provenance=f"Source: {source} | Category: {cat}"
            )
            messagebox.showinfo("Fact Saved", f"Successfully saved:\n{entity} -> {attr} = {val}", parent=win)
            win.destroy()

        btn_save = tk.Button(
            win, text="💾 Save to Local Knowledge Base", bg="#a6e3a1", fg="#11111b",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=6, command=save_fact
        )
        btn_save.pack(pady=16)

    def _show_import_window(self):
        """Displays dialog to import facts from JSON file or seed knowledge."""
        win = tk.Toplevel(self)
        win.title("📥 Import Knowledge Feed")
        win.geometry("500x320")
        win.configure(bg="#181825")
        win.resizable(False, False)

        tk.Label(win, text="Import Knowledge Facts", bg="#181825", fg="#f9e2af", font=("Segoe UI", 12, "bold")).pack(pady=(16, 8))
        tk.Label(win, text="Load verified facts from a JSON file into your offline database.", bg="#181825", fg="#a6adc8", font=("Segoe UI", 9)).pack(pady=(0, 16))

        def load_seed():
            seed_file = Path("data/seed_knowledge.json")
            if not seed_file.exists():
                messagebox.showerror("Error", f"Seed file not found at {seed_file.resolve()}", parent=win)
                return
            count = self._import_json_path(seed_file)
            messagebox.showinfo("Success", f"Successfully loaded {count} facts from seed_knowledge.json!", parent=win)
            win.destroy()

        def browse_file():
            from tkinter import filedialog
            file_path = filedialog.askopenfilename(
                parent=win,
                title="Select Knowledge JSON File",
                filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
            )
            if file_path:
                count = self._import_json_path(Path(file_path))
                messagebox.showinfo("Success", f"Successfully imported {count} facts from {Path(file_path).name}!", parent=win)
                win.destroy()

        btn_seed = tk.Button(
            win, text="📦 Reload Seed Knowledge (seed_knowledge.json)", bg="#89b4fa", fg="#11111b",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=8, command=load_seed
        )
        btn_seed.pack(fill="x", padx=30, pady=8)

        btn_browse = tk.Button(
            win, text="📂 Browse & Import Custom JSON File...", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 10), relief="flat", padx=14, pady=8, command=browse_file
        )
        btn_browse.pack(fill="x", padx=30, pady=8)

    def _import_json_path(self, path: Path) -> int:
        """Parses JSON file and applies facts through knowledge engine."""
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        facts_list = data if isinstance(data, list) else data.get("facts", [])
        count = 0
        for item in facts_list:
            fact = Fact(
                entity=item["entity"],
                attribute=item["attribute"],
                value=item["value"],
                source=item.get("source", "JSON Import"),
                source_priority=item.get("source_priority", 60),
                category=item.get("category", "general"),
                confidence=item.get("confidence", 1.0),
            )
            self.ke.apply_incoming_fact(fact)
            count += 1
        self._update_status_badges()
        self._append_assistant_message(
            f"📥 Imported **{count}** facts from `{path.name}`.",
            provenance="Local Database Refreshed"
        )
        return count

    def _show_memory_window(self):
        """Displays memory viewer and editor for long-term user facts."""
        win = tk.Toplevel(self)
        win.title("🧠 Local Long-Term Memory")
        win.geometry("680x440")
        win.configure(bg="#181825")

        tk.Label(win, text="Local User Memory", bg="#181825", fg="#cba6f7", font=("Segoe UI", 12, "bold")).pack(pady=(12, 4))
        tk.Label(win, text="Facts stored locally on your device to personalize offline conversation.", bg="#181825", fg="#a6adc8", font=("Segoe UI", 9)).pack(pady=(0, 10))

        tree_frame = ttk.Frame(win, padding=10)
        tree_frame.pack(fill="both", expand=True)

        cols = ("Memory Key", "Stored Value")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        tree.heading("Memory Key", text="Memory Key")
        tree.heading("Stored Value", text="Stored Value")
        tree.column("Memory Key", width=180)
        tree.column("Stored Value", width=420)

        facts = self.orchestrator.memory_mgr.get_all_facts()
        for k, v in facts.items():
            tree.insert("", "end", values=(k, str(v)))

        tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        btn_box = tk.Frame(win, bg="#181825")
        btn_box.pack(fill="x", padx=14, pady=10)

        def forget_selected():
            sel = tree.selection()
            if not sel:
                return
            item = tree.item(sel[0])
            key = item["values"][0]
            self.orchestrator.memory_mgr.forget_fact(key)
            tree.delete(sel[0])
            messagebox.showinfo("Memory Deleted", f"Removed '{key}' from memory.", parent=win)

        def export_mem():
            from tkinter import filedialog
            f_path = filedialog.asksaveasfilename(
                parent=win,
                title="Export Memory JSON",
                defaultextension=".json",
                filetypes=[("JSON Files", "*.json")]
            )
            if f_path:
                self.orchestrator.memory_mgr.export_memory(Path(f_path))
                messagebox.showinfo("Success", f"Memory exported to {Path(f_path).name}", parent=win)

        tk.Button(btn_box, text="🗑️ Forget Selected", bg="#f38ba8", fg="#11111b", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, command=forget_selected).pack(side="left", padx=4)
        tk.Button(btn_box, text="📤 Export Memory", bg="#89b4fa", fg="#11111b", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, command=export_mem).pack(side="left", padx=4)

    def _show_documents_window(self):
        """Displays local RAG document repository manager."""
        win = tk.Toplevel(self)
        win.title("📄 Local Document Repository (RAG)")
        win.geometry("740x450")
        win.configure(bg="#181825")

        tk.Label(win, text="Local Document Knowledge Base", bg="#181825", fg="#f9e2af", font=("Segoe UI", 12, "bold")).pack(pady=(12, 4))
        tk.Label(win, text="Ingest local PDFs, Word docs, code, and text files for offline semantic search.", bg="#181825", fg="#a6adc8", font=("Segoe UI", 9)).pack(pady=(0, 10))

        tree_frame = ttk.Frame(win, padding=10)
        tree_frame.pack(fill="both", expand=True)

        cols = ("Doc ID", "File Name", "Type", "Chunks", "Chars")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Doc ID", width=120)
        tree.column("File Name", width=260)
        tree.column("Type", width=70)
        tree.column("Chunks", width=70)
        tree.column("Chars", width=80)

        def refresh_doc_list():
            for item in tree.get_children():
                tree.delete(item)
            docs = self.orchestrator.vector_store.list_documents()
            for d in docs:
                tree.insert("", "end", values=(d["doc_id"][:12], d["name"], d.get("extension", ""), d.get("chunk_count", 0), d.get("char_count", 0)))
            self._update_status_badges()

        refresh_doc_list()

        tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        btn_box = tk.Frame(win, bg="#181825")
        btn_box.pack(fill="x", padx=14, pady=10)

        def add_document():
            from tkinter import filedialog
            f_path = filedialog.askopenfilename(
                parent=win,
                title="Select Document for Offline RAG",
                filetypes=[
                    ("All Supported Files", "*.pdf;*.txt;*.docx;*.md;*.py;*.json;*.csv"),
                    ("PDF Documents", "*.pdf"),
                    ("Text & Markdown", "*.txt;*.md"),
                    ("Word Documents", "*.docx"),
                    ("Code Files", "*.py;*.json;*.csv;*.sql"),
                    ("All Files", "*.*")
                ]
            )
            if f_path:
                try:
                    doc_id = self.orchestrator.vector_store.add_document(Path(f_path))
                    refresh_doc_list()
                    messagebox.showinfo("Success", f"Ingested '{Path(f_path).name}' into local vector knowledge base!", parent=win)
                except Exception as e:
                    messagebox.showerror("Ingestion Error", f"Failed to ingest document: {e}", parent=win)

        def delete_document():
            sel = tree.selection()
            if not sel:
                return
            item = tree.item(sel[0])
            doc_id_prefix = item["values"][0]
            # Match full doc id
            for d in self.orchestrator.vector_store.list_documents():
                if d["doc_id"].startswith(doc_id_prefix):
                    self.orchestrator.vector_store.delete_document(d["doc_id"])
                    break
            refresh_doc_list()
            messagebox.showinfo("Deleted", "Document removed from local vector store.", parent=win)

        tk.Button(btn_box, text="➕ Ingest Document...", bg="#a6e3a1", fg="#11111b", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4, command=add_document).pack(side="left", padx=4)
        tk.Button(btn_box, text="🗑️ Delete Document", bg="#f38ba8", fg="#11111b", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, command=delete_document).pack(side="left", padx=4)


def main():
    print("\n" + "=" * 65, flush=True)
    print("        OfflineMind - Modern Offline Desktop AI Assistant", flush=True)
    print("=" * 65, flush=True)
    print("  [*] Initializing local models, vector DB, and GUI...", flush=True)
    app = OfflineMindGUI()
    # Ensure window is raised to foreground on Windows desktop
    try:
        app.lift()
        app.attributes("-topmost", True)
        app.after_idle(app.attributes, "-topmost", False)
        app.focus_force()
    except Exception:
        pass

    print("  [+] GUI window is now active on your desktop.", flush=True)
    print("  [*] Close the application window or press Ctrl+C to exit.", flush=True)
    print("=" * 65 + "\n", flush=True)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[*] Exiting OfflineMind.", flush=True)
    finally:
        print("[*] OfflineMind GUI closed cleanly.", flush=True)


if __name__ == "__main__":
    main()
