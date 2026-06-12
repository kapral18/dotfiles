#!/usr/bin/env python3
"""Shared typed blackboard for in-flight multi-agent runs.

A run-scoped findings ledger sitting between `/tmp/specs` (ephemeral
free-text intent) and `,ai-kb` (durable cross-session knowledge).
Cooperating agents (Workflow fan-outs, Ralph roles, deep-research
runs) append typed entries with provenance and maintain an explicit
queue of open questions (signals), so intermediate findings are
queryable, auditable, and resumable instead of living only in each
agent's return value.

The mechanics are lifted from the validated core of
dl1683/irys-stateful-swarms: typed entries (observation, analysis,
calculation, strategy, gap, contradiction) with supports/contradicts/
supersedes links, signals with operational-gap blocking (`gate`), and
a survival check that final artifacts actually surface what the board
says must surface.

Usage:
    blackboard.py signal   --board B --content TEXT [--priority P] [--by W]
    blackboard.py add      --board B --type T --content TEXT
                           [--source-doc D] [--source-ref R] [--evidence Q]
                           [--confidence F] [--by W] [--addresses s1,s2]
                           [--supports e1,e2] [--contradicts e3]
                           [--supersedes e4] [--must-surface]
    blackboard.py waive    --board B --signal sN --reason TEXT
    blackboard.py state    --board B [--json]
    blackboard.py query    --board B [--type T] [--status S] [--signal sN]
                           [--grep PAT] [--limit N] [--json]
    blackboard.py gate     --board B [--json]
    blackboard.py survival --board B --report FILE [--json]
    blackboard.py boards   [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ENTRY_TYPES = ("observation", "analysis", "calculation", "strategy", "gap", "contradiction")
ENTRY_STATUSES = ("active", "disputed", "superseded")
SIGNAL_PRIORITIES = ("critical", "high", "medium", "low")
SIGNAL_STATUSES = ("open", "addressed", "waived")
BLOCKING_PRIORITIES = ("critical", "high")
SURVIVAL_TOKEN_THRESHOLD = 0.6

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    source_doc TEXT NOT NULL DEFAULT '',
    source_ref TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.5,
    created_by TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    must_surface INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS links (
    entry_id INTEGER NOT NULL,
    rel TEXT NOT NULL,
    target_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    waive_reason TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def default_home() -> Path:
    env = os.environ.get("BLACKBOARD_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".local" / "share" / "blackboard"


def board_path(board: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", board):
        raise SystemExit(f"error: invalid board name {board!r} (use [A-Za-z0-9._-])")
    return default_home() / f"{board}.sqlite3"


def connect(board: str) -> sqlite3.Connection:
    path = board_path(board)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_id(raw: str, prefix: str) -> int:
    raw = raw.strip()
    if raw.startswith(prefix):
        raw = raw[len(prefix) :]
    if not raw.isdigit():
        raise SystemExit(f"error: expected {prefix}<N> id, got {raw!r}")
    return int(raw)


def parse_id_list(raw: str, prefix: str) -> list[int]:
    return [parse_id(part, prefix) for part in raw.split(",") if part.strip()]


def entry_dict(row: sqlite3.Row, links: list[sqlite3.Row]) -> dict:
    rels: dict[str, list[str]] = {"supports": [], "contradicts": [], "supersedes": [], "addresses": []}
    for link in links:
        prefix = "s" if link["rel"] == "addresses" else "e"
        rels[link["rel"]].append(f"{prefix}{link['target_id']}")
    return {
        "id": f"e{row['id']}",
        "type": row["type"],
        "content": row["content"],
        "source_doc": row["source_doc"],
        "source_ref": row["source_ref"],
        "evidence": row["evidence"],
        "confidence": row["confidence"],
        "created_by": row["created_by"],
        "status": row["status"],
        "must_surface": bool(row["must_surface"]),
        "created_at": row["created_at"],
        **rels,
    }


def signal_dict(row: sqlite3.Row) -> dict:
    return {
        "id": f"s{row['id']}",
        "content": row["content"],
        "priority": row["priority"],
        "status": row["status"],
        "waive_reason": row["waive_reason"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def fetch_entries(conn: sqlite3.Connection, where: str = "", params: tuple = ()) -> list[dict]:
    rows = conn.execute(f"SELECT * FROM entries {where} ORDER BY id", params).fetchall()
    out = []
    for row in rows:
        links = conn.execute("SELECT rel, target_id FROM links WHERE entry_id = ?", (row["id"],)).fetchall()
        out.append(entry_dict(row, links))
    return out


def require_signal(conn: sqlite3.Connection, sid: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM signals WHERE id = ?", (sid,)).fetchone()
    if row is None:
        raise SystemExit(f"error: no signal s{sid}")
    return row


def require_entry(conn: sqlite3.Connection, eid: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (eid,)).fetchone()
    if row is None:
        raise SystemExit(f"error: no entry e{eid}")
    return row


# --- commands ---


def cmd_signal(args: argparse.Namespace) -> int:
    conn = connect(args.board)
    with conn:
        cur = conn.execute(
            "INSERT INTO signals (content, priority, created_by, created_at) VALUES (?, ?, ?, ?)",
            (args.content, args.priority, args.by, now_iso()),
        )
    print(f"s{cur.lastrowid}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    conn = connect(args.board)
    addresses = parse_id_list(args.addresses, "s") if args.addresses else []
    rel_targets = {
        "supports": parse_id_list(args.supports, "e") if args.supports else [],
        "contradicts": parse_id_list(args.contradicts, "e") if args.contradicts else [],
        "supersedes": parse_id_list(args.supersedes, "e") if args.supersedes else [],
    }
    with conn:
        for sid in addresses:
            require_signal(conn, sid)
        for targets in rel_targets.values():
            for eid in targets:
                require_entry(conn, eid)
        must_surface = 1 if (args.must_surface or args.type == "contradiction") else 0
        cur = conn.execute(
            "INSERT INTO entries (type, content, source_doc, source_ref, evidence, confidence,"
            " created_by, must_surface, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                args.type,
                args.content,
                args.source_doc,
                args.source_ref,
                args.evidence,
                args.confidence,
                args.by,
                must_surface,
                now_iso(),
            ),
        )
        eid = cur.lastrowid
        for rel, targets in rel_targets.items():
            for target in targets:
                conn.execute("INSERT INTO links (entry_id, rel, target_id) VALUES (?, ?, ?)", (eid, rel, target))
        for sid in addresses:
            conn.execute("INSERT INTO links (entry_id, rel, target_id) VALUES (?, 'addresses', ?)", (eid, sid))
            conn.execute("UPDATE signals SET status = 'addressed' WHERE id = ? AND status = 'open'", (sid,))
        for target in rel_targets["contradicts"]:
            conn.execute("UPDATE entries SET status = 'disputed' WHERE id = ? AND status = 'active'", (target,))
        for target in rel_targets["supersedes"]:
            conn.execute("UPDATE entries SET status = 'superseded' WHERE id = ?", (target,))
    print(f"e{eid}")
    return 0


def cmd_waive(args: argparse.Namespace) -> int:
    conn = connect(args.board)
    sid = parse_id(args.signal, "s")
    with conn:
        require_signal(conn, sid)
        conn.execute("UPDATE signals SET status = 'waived', waive_reason = ? WHERE id = ?", (args.reason, sid))
    print(f"s{sid} waived")
    return 0


def board_state(conn: sqlite3.Connection) -> dict:
    entry_counts: dict[str, int] = {}
    for row in conn.execute("SELECT type, COUNT(*) AS n FROM entries WHERE status = 'active' GROUP BY type"):
        entry_counts[row["type"]] = row["n"]
    status_counts: dict[str, int] = {}
    for row in conn.execute("SELECT status, COUNT(*) AS n FROM entries GROUP BY status"):
        status_counts[row["status"]] = row["n"]
    signal_counts: dict[str, dict[str, int]] = {}
    for row in conn.execute("SELECT priority, status, COUNT(*) AS n FROM signals GROUP BY priority, status"):
        signal_counts.setdefault(row["priority"], {})[row["status"]] = row["n"]
    open_blocking = [
        signal_dict(row)
        for row in conn.execute(
            "SELECT * FROM signals WHERE status = 'open' AND priority IN (?, ?) ORDER BY id",
            BLOCKING_PRIORITIES,
        )
    ]
    must = conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE must_surface = 1 AND status != 'superseded'"
    ).fetchone()["n"]
    return {
        "entries_by_type": entry_counts,
        "entries_by_status": status_counts,
        "signals": signal_counts,
        "open_blocking_signals": open_blocking,
        "must_surface_entries": must,
    }


def cmd_state(args: argparse.Namespace) -> int:
    conn = connect(args.board)
    state = board_state(conn)
    if args.json:
        print(json.dumps(state, indent=2))
        return 0
    print(f"board: {args.board}")
    print("entries (active): " + (json.dumps(state["entries_by_type"]) if state["entries_by_type"] else "none"))
    print("entries by status: " + json.dumps(state["entries_by_status"]))
    print("signals: " + json.dumps(state["signals"]))
    print(f"must-surface entries: {state['must_surface_entries']}")
    if state["open_blocking_signals"]:
        print("open blocking signals:")
        for sig in state["open_blocking_signals"]:
            print(f"  [{sig['id']}] [{sig['priority']}] {sig['content']}")
    else:
        print("open blocking signals: none")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    conn = connect(args.board)
    clauses, params = [], []
    if args.type:
        clauses.append("type = ?")
        params.append(args.type)
    if args.status:
        clauses.append("status = ?")
        params.append(args.status)
    if args.signal:
        sid = parse_id(args.signal, "s")
        clauses.append("id IN (SELECT entry_id FROM links WHERE rel = 'addresses' AND target_id = ?)")
        params.append(sid)
    if args.grep:
        clauses.append("(content LIKE ? OR evidence LIKE ? OR source_doc LIKE ?)")
        pat = f"%{args.grep}%"
        params.extend([pat, pat, pat])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    entries = fetch_entries(conn, where, tuple(params))
    if args.limit:
        entries = entries[-args.limit :]
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0
    for e in entries:
        marker = " [MUST-SURFACE]" if e["must_surface"] else ""
        src = f" ({e['source_doc'] or e['source_ref']})" if (e["source_doc"] or e["source_ref"]) else ""
        print(f"[{e['id']}] [{e['type']}/{e['status']}]{marker} {e['content']}{src}")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    conn = connect(args.board)
    state = board_state(conn)
    blocking = state["open_blocking_signals"]
    if args.json:
        print(json.dumps({"pass": not blocking, "open_blocking_signals": blocking}, indent=2))
    elif blocking:
        print("GATE FAILED: open critical/high signals must be addressed or waived before synthesis:")
        for sig in blocking:
            print(f"  [{sig['id']}] [{sig['priority']}] {sig['content']}")
    else:
        print("GATE PASSED: no open critical/high signals")
    return 1 if blocking else 0


def significant_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9.%$/-]*", text.lower())
    return {t for t in tokens if len(t) >= 4 or any(c.isdigit() for c in t)}


def item_survives(content: str, report_tokens: set[str]) -> bool:
    tokens = significant_tokens(content)
    if not tokens:
        return True
    found = sum(1 for t in tokens if t in report_tokens)
    return found / len(tokens) >= SURVIVAL_TOKEN_THRESHOLD


def cmd_survival(args: argparse.Namespace) -> int:
    conn = connect(args.board)
    report_file = Path(args.report)
    if not report_file.is_file():
        raise SystemExit(f"error: no report file {args.report}")
    report_tokens = significant_tokens(report_file.read_text(encoding="utf-8", errors="replace"))
    items = []
    for e in fetch_entries(conn, "WHERE must_surface = 1 AND status != 'superseded'"):
        items.append({"id": e["id"], "kind": "must-surface entry", "content": e["content"]})
    for row in conn.execute("SELECT * FROM signals WHERE status IN ('open', 'waived') ORDER BY id"):
        sig = signal_dict(row)
        items.append(
            {
                "id": sig["id"],
                "kind": f"{sig['status']} signal (must be disclosed)",
                "content": sig["content"],
            }
        )
    missing = [i for i in items if not item_survives(i["content"], report_tokens)]
    result = {
        "pass": not missing,
        "checked": len(items),
        "missing": missing,
        "note": "token-containment heuristic, not semantic verification: "
        f">={int(SURVIVAL_TOKEN_THRESHOLD * 100)}% of an item's significant tokens"
        " must appear in the report",
    }
    if args.json:
        print(json.dumps(result, indent=2))
    elif missing:
        print(f"SURVIVAL FAILED: {len(missing)}/{len(items)} items not detected in {args.report}:")
        for i in missing:
            print(f"  [{i['id']}] {i['kind']}: {i['content']}")
        print(f"note: {result['note']}")
    else:
        print(f"SURVIVAL PASSED: all {len(items)} must-surface items detected ({result['note']})")
    return 1 if missing else 0


def cmd_boards(args: argparse.Namespace) -> int:
    home = default_home()
    boards = sorted(p.stem for p in home.glob("*.sqlite3")) if home.is_dir() else []
    if args.json:
        print(json.dumps(boards))
    else:
        for b in boards:
            print(b)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def board_arg(p: argparse.ArgumentParser) -> None:
        p.add_argument("--board", required=True, help="board name (one per run/topic)")

    p = sub.add_parser("signal", help="open a question the run must answer")
    board_arg(p)
    p.add_argument("--content", required=True)
    p.add_argument("--priority", default="medium", choices=SIGNAL_PRIORITIES)
    p.add_argument("--by", default="", help="worker/agent label")
    p.set_defaults(func=cmd_signal)

    p = sub.add_parser("add", help="add a typed entry with provenance")
    board_arg(p)
    p.add_argument("--type", required=True, choices=ENTRY_TYPES)
    p.add_argument("--content", required=True)
    p.add_argument("--source-doc", default="", help="document/URL the finding came from")
    p.add_argument("--source-ref", default="", help="section, path:line, or anchor")
    p.add_argument("--evidence", default="", help="verbatim supporting quote")
    p.add_argument("--confidence", type=float, default=0.5)
    p.add_argument("--by", default="", help="worker/agent label")
    p.add_argument("--addresses", default="", help="signal ids this answers, e.g. s1,s2")
    p.add_argument("--supports", default="", help="entry ids this supports, e.g. e1,e2")
    p.add_argument("--contradicts", default="", help="entry ids this contradicts (they become disputed)")
    p.add_argument("--supersedes", default="", help="entry ids this supersedes")
    p.add_argument(
        "--must-surface",
        action="store_true",
        help="final artifact must include this (contradictions are always must-surface)",
    )
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("waive", help="explicitly waive a signal with a recorded reason")
    board_arg(p)
    p.add_argument("--signal", required=True, help="signal id, e.g. s3")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_waive)

    p = sub.add_parser("state", help="orchestrator view: counts and open blocking signals")
    board_arg(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_state)

    p = sub.add_parser("query", help="filter entries")
    board_arg(p)
    p.add_argument("--type", choices=ENTRY_TYPES)
    p.add_argument("--status", choices=ENTRY_STATUSES)
    p.add_argument("--signal", help="entries addressing this signal id")
    p.add_argument("--grep", help="substring match on content/evidence/source")
    p.add_argument("--limit", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("gate", help="exit 1 while critical/high signals are open (blocks synthesis)")
    board_arg(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("survival", help="check must-surface items appear in the final artifact")
    board_arg(p)
    p.add_argument("--report", required=True, help="path to the final artifact/report")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_survival)

    p = sub.add_parser("boards", help="list existing boards")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_boards)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
