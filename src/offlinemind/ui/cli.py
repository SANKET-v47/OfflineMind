"""Command-line interface (CLI) for OfflineMind."""

from __future__ import annotations
import sys
import argparse
from typing import Optional
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from offlinemind.config import DB_PATH, BACKUP_DIR, SEED_DATA_PATH
from offlinemind.db.connection import DatabaseManager
from offlinemind.db.backup import BackupManager
from offlinemind.core.knowledge_engine import KnowledgeEngine
from offlinemind.core.connectivity import ConnectivityMonitor
from offlinemind.llm.llm_client import LLMService
from offlinemind.sync.sync_engine import SyncEngine


def init_system():
    """Initializes system dependencies."""
    db = DatabaseManager(DB_PATH)
    bm = BackupManager(DB_PATH, BACKUP_DIR)
    ke = KnowledgeEngine(db)
    # Seed default knowledge if empty
    ke.seed_initial_data(SEED_DATA_PATH)
    monitor = ConnectivityMonitor()
    monitor.probe_now()
    llm = LLMService()
    sync = SyncEngine(db, ke, bm, monitor)
    return db, bm, ke, monitor, llm, sync


def cmd_status(args):
    _, bm, ke, monitor, llm, sync = init_system()
    online = monitor.is_online()
    sim = monitor.is_simulated_offline()
    ollama_ok = llm.is_ollama_available()
    fact_count = ke.count_facts()
    backups = bm.list_backups()
    sources = sync.list_trusted_sources(active_only=True)
    logs = sync.get_latest_sync_logs(1)

    print("\n" + "=" * 55)
    print("           OfflineMind System Status")
    print("=" * 55)
    net_str = "ONLINE" if online else ("OFFLINE (Simulated)" if sim else "OFFLINE")
    print(f"  Network Connectivity : [{net_str}]")
    print(f"  LLM Engine           : [{'Ollama (' + llm.model + ')' if ollama_ok else 'Extractive Fallback'}]")
    print(f"  Active Facts Stored  : {fact_count}")
    print(f"  Pre-Sync Snapshots   : {len(backups)}")
    print(f"  Trusted Sources      : {len(sources)}")
    if logs:
        l = logs[0]
        print(f"  Last Sync            : {l['start_time'][:19]} UTC ({l['status']})")
    print("=" * 55 + "\n")


def cmd_query(args):
    _, _, ke, _, llm, _ = init_system()
    query_text = args.query
    search_results = ke.search(query_text)
    history_entries = None
    if search_results:
        top_f = search_results[0].fact
        history_entries = ke.get_history(entity=top_f.entity, attribute=top_f.attribute)

    answer = llm.generate_answer(
        query=query_text,
        search_results=search_results,
        history_entries=history_entries,
        include_provenance=args.provenance,
    )

    print(f"\nQ: {query_text}\n")
    print(f"A: {answer.text}\n")
    if args.provenance:
        print(f"[Provenance: {answer.provenance}]")
        print(f"[Engine: {answer.model_used} | Confidence: {int(answer.confidence * 100)}%]\n")


def cmd_sync(args):
    _, _, _, monitor, _, sync = init_system()
    print("Starting synchronization with configured trusted sources...")
    if not monitor.is_online():
        print("Warning: Network is currently OFFLINE. Cannot perform sync.")
        return

    results = sync.sync_all()
    if not results:
        print("No active trusted sources configured. Use 'add-source' first.")
        return

    for res in results:
        print(f"\nSource: {res.source_url}")
        print(f"  Status   : {res.status}")
        print(f"  Checked  : {res.facts_checked}")
        print(f"  Updated  : {res.facts_updated}")
        print(f"  Added    : {res.facts_added}")
        print(f"  Conflicts: {res.conflicts_detected}")
        if res.error_message:
            print(f"  Errors   : {res.error_message}")


def cmd_history(args):
    _, _, ke, _, _, _ = init_system()
    records = ke.get_history(entity=args.entity, attribute=args.attribute)
    if not records:
        print("No audit history records found matching criteria.")
        return

    print(f"\nAudit History Trail ({len(records)} records):")
    print("-" * 75)
    for r in records:
        mutation = f"'{r.old_value}' -> '{r.new_value}'" if r.old_value else f"(Created) '{r.new_value}'"
        print(f"[{r.timestamp[:19]} UTC] v{r.version} | ({r.entity}, {r.attribute})")
        print(f"  Mutation: {mutation}")
        print(f"  Source  : {r.source} | Reason: {r.change_reason or 'N/A'}")
        print("-" * 75)


def cmd_review(args):
    _, _, ke, _, _, _ = init_system()
    items = ke.get_review_queue(status="PENDING")
    if not items:
        print("No pending conflict items in review queue.")
        return

    print(f"\nPending Conflicts Requiring Review ({len(items)} items):\n")
    for item in items:
        print(f"ID #{item.id}: ({item.entity}, {item.attribute})")
        print(f"  Current Value : '{item.current_value}' from '{item.current_source}'")
        print(f"  Incoming Value: '{item.incoming_value}' from '{item.incoming_source}'")
        print(f"  Reason        : {item.conflict_reason}")
        print(f"  Created At    : {item.created_at}")

        if args.interactive:
            choice = input("  Resolve? (a = accept incoming, r = reject incoming, s = skip): ").strip().lower()
            if choice == "a":
                ke.resolve_review(item.id, accept_incoming=True, notes="Approved in CLI review")
                print("  -> Accepted incoming fact.")
            elif choice == "r":
                ke.resolve_review(item.id, accept_incoming=False, notes="Rejected in CLI review")
                print("  -> Rejected incoming fact.")
        print("-" * 55)


def cmd_add_fact(args):
    _, _, ke, _, _, _ = init_system()
    fact = ke.add_fact(
        entity=args.entity,
        attribute=args.attribute,
        value=args.value,
        source=args.source or "Manual Entry",
        source_priority=args.priority,
        category=args.category or "general",
    )
    print(f"Added fact ID {fact.id}: ({fact.entity}, {fact.attribute}) = '{fact.value}'")


def interactive_repl():
    """Runs a friendly interactive shell."""
    _, _, ke, monitor, llm, sync = init_system()
    print("\n" + "=" * 60)
    print("       Welcome to OfflineMind Interactive Shell")
    print("   Type your questions or commands (:status, :sync, :quit)")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("OfflineMind> ").strip()
            if not user_input:
                continue
            if user_input in (":quit", ":exit", "quit", "exit"):
                print("Goodbye!")
                break
            elif user_input == ":status":
                cmd_status(None)
            elif user_input == ":sync":
                cmd_sync(None)
            elif user_input == ":history":
                cmd_history(argparse.Namespace(entity=None, attribute=None))
            else:
                search_res = ke.search(user_input)
                hist = None
                if search_res:
                    f = search_res[0].fact
                    hist = ke.get_history(entity=f.entity, attribute=f.attribute)
                ans = llm.generate_answer(user_input, search_res, hist, include_provenance=True)
                print(f"\n{ans.text}\n")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting OfflineMind.")
            break


def main():
    parser = argparse.ArgumentParser(description="OfflineMind: Offline-First AI Assistant")
    subparsers = parser.add_subparsers(dest="command")

    # query
    p_query = subparsers.add_parser("query", help="Ask a question")
    p_query.add_argument("query", help="Question string")
    p_query.add_argument("--provenance", action="store_true", help="Include provenance details")

    # status
    subparsers.add_parser("status", help="Show system status")

    # sync
    subparsers.add_parser("sync", help="Sync knowledge from trusted sources")

    # history
    p_hist = subparsers.add_parser("history", help="Show audit version history")
    p_hist.add_argument("--entity", default=None, help="Filter by entity")
    p_hist.add_argument("--attribute", default=None, help="Filter by attribute")

    # review
    p_rev = subparsers.add_parser("review", help="Inspect and resolve conflicts")
    p_rev.add_argument("--interactive", action="store_true", help="Interactively resolve conflicts")

    # add-fact
    p_add = subparsers.add_parser("add-fact", help="Add a new fact manually")
    p_add.add_argument("entity")
    p_add.add_argument("attribute")
    p_add.add_argument("value")
    p_add.add_argument("--source", default="Manual Entry")
    p_add.add_argument("--priority", type=int, default=70)
    p_add.add_argument("--category", default="general")

    args = parser.parse_args()
    if not args.command:
        interactive_repl()
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "query":
        cmd_query(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "history":
        cmd_history(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "add-fact":
        cmd_add_fact(args)


if __name__ == "__main__":
    main()
