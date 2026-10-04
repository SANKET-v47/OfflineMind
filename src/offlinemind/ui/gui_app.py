"""Native graphical user interface for OfflineMind using Tkinter."""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from pathlib import Path
from typing import Optional

from offlinemind.config import DB_PATH, BACKUP_DIR, SEED_DATA_PATH
from offlinemind.db.connection import DatabaseManager
from offlinemind.db.backup import BackupManager
from offlinemind.core.knowledge_engine import KnowledgeEngine
from offlinemind.core.connectivity import ConnectivityMonitor
from offlinemind.llm.llm_client import LLMService
from offlinemind.sync.sync_engine import SyncEngine


class OfflineMindGUI(tk.Tk):
    """Main Application Window for OfflineMind."""

    def __init__(self):
        super().__init__()
        self.title("OfflineMind - Offline-First AI Assistant")
        self.geometry("900x700")
        self.minsize(750, 550)

        # Initialize Backend Components
        self.db = DatabaseManager(DB_PATH)
        self.bm = BackupManager(DB_PATH, BACKUP_DIR)
        self.ke = KnowledgeEngine(self.db)
        self.ke.seed_initial_data(SEED_DATA_PATH)
        self.monitor = ConnectivityMonitor()
        self.monitor.start()
        self.llm = LLMService()
        self.sync_engine = SyncEngine(self.db, self.ke, self.bm, self.monitor)

        # Seed default trusted source if database has none configured
        if not self.sync_engine.list_trusted_sources(active_only=False):
            from offlinemind.config import MOCK_SERVER_URL
            self.sync_engine.add_trusted_source(
                name="Official University Registrar",
                url=f"{MOCK_SERVER_URL}/api/trusted_feed",
                priority=85,
            )

        self.include_prov_var = tk.BooleanVar(value=True)

        self._configure_styles()
        self._build_ui()
        self._start_status_poller()

        # Welcome message in chat
        self._append_assistant_message(
            "Hello! I am **OfflineMind**, your local, offline-first AI assistant.\n\n"
            "• Ask me questions about your college, major, courses, or stored facts.\n"
            "• I function completely offline without internet.\n"
            "• When connectivity is restored, I can safely synchronize updates from trusted sources.",
            provenance="Embedded Knowledge Base | Status: Ready",
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
        ttk.Label(title_box, text="Offline-First Self-Updating Knowledge Engine", style="Status.TLabel").pack(anchor="w")

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

        self.facts_badge = tk.Label(
            status_box, text="📚 0 Facts", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 9, "bold"), padx=10, pady=4, relief="flat"
        )
        self.facts_badge.pack(side="left", padx=4)

        # 2. Controls Toolbar
        toolbar = ttk.Frame(self, style="TFrame")
        toolbar.pack(fill="x", padx=14, pady=(0, 10))

        btn_sync = tk.Button(
            toolbar, text="🔄 Sync Now", bg="#89b4fa", fg="#11111b",
            font=("Segoe UI", 9, "bold"), activebackground="#b4befe",
            command=self._on_sync_clicked, relief="flat", padx=12, pady=4
        )
        btn_sync.pack(side="left", padx=(0, 6))

        self.btn_toggle_offline = tk.Button(
            toolbar, text="🌐 Force Simulated Offline", bg="#45475a", fg="#cdd6f4",
            font=("Segoe UI", 9), activebackground="#585b70",
            command=self._on_toggle_offline_clicked, relief="flat", padx=10, pady=4
        )
        self.btn_toggle_offline.pack(side="left", padx=6)

        btn_history = tk.Button(
            toolbar, text="📜 Version History", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 9), command=self._show_history_window,
            relief="flat", padx=10, pady=4
        )
        btn_history.pack(side="left", padx=6)

        btn_review = tk.Button(
            toolbar, text="⚖️ Review Queue", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 9), command=self._show_review_window,
            relief="flat", padx=10, pady=4
        )
        btn_review.pack(side="left", padx=6)

        btn_add = tk.Button(
            toolbar, text="➕ Add Fact", bg="#a6e3a1", fg="#11111b",
            font=("Segoe UI", 9, "bold"), activebackground="#94e2d5",
            command=self._show_add_fact_window, relief="flat", padx=10, pady=4
        )
        btn_add.pack(side="left", padx=6)

        btn_import = tk.Button(
            toolbar, text="📥 Import JSON", bg="#f9e2af", fg="#11111b",
            font=("Segoe UI", 9, "bold"), activebackground="#f5e0dc",
            command=self._show_import_window, relief="flat", padx=10, pady=4
        )
        btn_import.pack(side="left", padx=6)

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

        chk_prov = tk.Checkbutton(
            input_card, text="Provenance", variable=self.include_prov_var,
            bg="#1e1e2e", fg="#a6adc8", selectcolor="#313244",
            activebackground="#1e1e2e", activeforeground="#cdd6f4",
            font=("Segoe UI", 9)
        )
        chk_prov.pack(side="left", padx=(0, 8))

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

        # Facts count
        count = self.ke.count_facts()
        self.facts_badge.config(text=f"📚 {count} Facts")

    def _on_toggle_offline_clicked(self):
        curr_sim = self.monitor.is_simulated_offline()
        self.monitor.set_simulated_offline(not curr_sim)
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

        # Process answer in background
        include_prov = self.include_prov_var.get()

        def process_query():
            search_res = self.ke.search(query)
            hist = None
            if search_res:
                top_f = search_res[0].fact
                hist = self.ke.get_history(entity=top_f.entity, attribute=top_f.attribute)

            self.after(0, self._prepare_assistant_bubble)

            try:
                for chunk in self.llm.stream_answer(
                    query=query,
                    search_results=search_res,
                    history_entries=hist,
                    include_provenance=include_prov,
                ):
                    self.after(0, lambda c=chunk: self._append_stream_chunk(c))
            except Exception as e:
                self.after(0, lambda err=e: self._append_stream_chunk(f"\n[Error: {err}]"))

            if search_res and include_prov:
                prov_str = f"Source: {search_res[0].fact.source} | Version: v{search_res[0].fact.version}"
                self.after(0, lambda: self._finish_assistant_stream(prov_str))
            else:
                self.after(0, lambda: self._finish_assistant_stream(None))

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


def main():
    app = OfflineMindGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
