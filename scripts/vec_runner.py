#!/usr/bin/env -S uv run --quiet --no-project --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "sqlite-vec>=0.1,<1.0",
# ]
# ///
"""Vector retrieval runner — isolated subprocess that loads the
sqlite-vec extension and serves KNN / pairs queries against a Ralph
KB SQLite database.

Why a subprocess: the orchestrator process (`scripts/ralph.py`) is
launched via `/usr/bin/env python3`, which on macOS resolves to
Apple's Xcode python whose stdlib `sqlite3` module is built without
`enable_load_extension`. Loading vec0 in-process is therefore not
possible without either swapping the interpreter (extra install
burden) or pulling sqlite-vec into the orchestrator's import graph
(violates the stdlib-only constraint).

Mirrors `scripts/embed_runner.py` for fastembed: PEP 723 inline-script
metadata declares the dep, `uv run --script` resolves a Python with
extension loading enabled, and the orchestrator only knows how to
spawn a subprocess and parse JSON.

This runner manages its own `vec_index` table — a vec0 virtual table
mirroring `capsules.id` and `capsules.embedding` — synchronizing
deltas from the canonical `capsules` table on every call. The
orchestrator process never sees `vec_index`; that table is purely an
implementation detail of this runner.

Protocol (request/response over stdio, single round-trip per spawn):

    KNN search:
        stdin  -> {
            "mode": "knn",
            "db_path": "/abs/path/to/kb.sqlite3",
            "query_vector": [f32, f32, ...],
            "k": 20,
            "limit": 5,
            "filters": {
                "scopes":  [...],
                "kinds":   [...],
                "domains": [...]
            }
        }
        stdout -> {"hits": [{"id": "...", "cosine": 0.91}, ...]}

    Pairwise (curate dedupe / contradiction shortlist):
        stdin  -> {
            "mode": "pairs",
            "db_path": "/abs/path/to/kb.sqlite3",
            "k": 10,
            "threshold": 0.85
        }
        stdout -> {"pairs": [{"a_id": "...", "b_id": "...", "cosine": 0.92}, ...]}

    Failure (any mode): {"error": "<message>"}; exit code 1.

The runner never mutates the `capsules` table. It only reads from
it and writes to its own `vec_index` table. Concurrent callers are
serialized by SQLite's WAL locking.
"""

from __future__ import annotations

import json
import re
import sqlite3
import struct
import sys
from typing import Any


def _print_error_and_exit(message: str) -> None:
    print(json.dumps({"error": message}))
    sys.exit(1)


def _serialize_f32(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _connect(db_path: str) -> sqlite3.Connection:
    """Open the KB DB with vec0 loaded.

    We deliberately do NOT touch any user-facing PRAGMAs (journal_mode,
    busy_timeout) — those are owned by `ai_kb.py::connect`. We only set
    a busy timeout so we don't crash if the orchestrator is mid-write.
    """
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA busy_timeout=5000")
    try:
        import sqlite_vec
    except ImportError as err:
        _print_error_and_exit(f"sqlite_vec wheel not installed: {err}")
    try:
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
    except sqlite3.OperationalError as err:
        _print_error_and_exit(f"failed to load vec0: {err}")
    except AttributeError:
        _print_error_and_exit(
            "this Python's sqlite3 module lacks enable_load_extension; "
            "uv's bundled Python should have it — check your uv install"
        )
    return db


def _existing_vec_dim(db: sqlite3.Connection) -> int | None:
    """Return the embedding dim of the existing vec_index, or None.

    We parse the dim from the table's `sql` rather than introspecting
    schema because vec0 doesn't expose dim through PRAGMA. The table
    DDL contains `embedding float[NNN]`.
    """
    row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='vec_index'").fetchone()
    if not row or not row[0]:
        return None
    match = re.search(r"float\[(\d+)\]", row[0])
    return int(match.group(1)) if match else None


def _capsules_dim(db: sqlite3.Connection) -> int | None:
    """Sample one capsules row to learn the canonical embedding dim.

    Returns None if no embedded capsules exist yet.
    """
    row = db.execute(
        "SELECT embedding_dim FROM capsules WHERE embedding IS NOT NULL AND embedding_dim > 0 LIMIT 1"
    ).fetchone()
    return int(row[0]) if row else None


def _ensure_vec_index(db: sqlite3.Connection) -> int | None:
    """Lazily create vec_index and sync with `capsules`. Returns the
    embedding dim used by the index, or None if no embeddings exist
    in the KB yet (caller should treat that as an empty result set).

    Resilience: if a model swap changed the dim, we drop and rebuild
    the index. This is rare and the rebuild cost is bounded by the
    KB size.
    """
    cap_dim = _capsules_dim(db)
    if cap_dim is None:
        return None

    existing_dim = _existing_vec_dim(db)
    if existing_dim is not None and existing_dim != cap_dim:
        db.execute("DROP TABLE vec_index")
        existing_dim = None

    if existing_dim is None:
        db.execute(
            f"""
            CREATE VIRTUAL TABLE vec_index USING vec0(
                id TEXT PRIMARY KEY,
                embedding float[{cap_dim}] distance_metric=cosine
            )
            """
        )

    db.execute(
        """
        DELETE FROM vec_index
        WHERE id NOT IN (
            SELECT id FROM capsules WHERE embedding IS NOT NULL AND embedding_dim > 0
        )
        """
    )
    new_rows = db.execute(
        """
        SELECT c.id, c.embedding
        FROM capsules c
        LEFT JOIN vec_index v ON v.id = c.id
        WHERE c.embedding IS NOT NULL
          AND c.embedding_dim = ?
          AND v.id IS NULL
        """,
        (cap_dim,),
    ).fetchall()
    if new_rows:
        db.executemany(
            "INSERT INTO vec_index(id, embedding) VALUES (?, ?)",
            [(r[0], r[1]) for r in new_rows],
        )
    db.commit()
    return cap_dim


def _build_filter_clause(filters: dict[str, Any]) -> tuple[str, list]:
    """Compose a SQL fragment + params for filtering capsules.

    Mirrors `ai_kb.py::_build_filter_clause` but operates on the
    `capsules c` alias inside the JOIN.
    """
    parts: list[str] = ["c.superseded_by IS NULL"]
    params: list = []
    scopes = filters.get("scopes") or []
    kinds = filters.get("kinds") or []
    domains = filters.get("domains") or []
    if scopes:
        parts.append(f"c.scope IN ({','.join('?' * len(scopes))})")
        params.extend(scopes)
    if kinds:
        parts.append(f"c.kind IN ({','.join('?' * len(kinds))})")
        params.extend(kinds)
    if domains:
        sub = " OR ".join("c.domain_tags LIKE ?" for _ in domains)
        parts.append(f"({sub})")
        params.extend(f"%{d}%" for d in domains)
    return " AND ".join(parts), params


def _knn(db: sqlite3.Connection, req: dict[str, Any]) -> dict[str, Any]:
    qvec = req.get("query_vector") or []
    if not isinstance(qvec, list) or not all(isinstance(x, (int, float)) for x in qvec):
        _print_error_and_exit("'query_vector' must be a list of floats")
    if not qvec:
        return {"hits": []}
    k = int(req.get("k", 20))
    limit = int(req.get("limit", 5))
    filters = req.get("filters") or {}

    dim = _ensure_vec_index(db)
    if dim is None:
        return {"hits": []}
    if len(qvec) != dim:
        _print_error_and_exit(f"query_vector dim {len(qvec)} != index dim {dim}; re-embed required")

    where, params = _build_filter_clause(filters)
    sql = f"""
        WITH knn AS (
            SELECT id, distance
            FROM vec_index
            WHERE embedding MATCH ? AND k = ?
            ORDER BY distance
        )
        SELECT knn.id, knn.distance
        FROM knn
        JOIN capsules c ON c.id = knn.id
        WHERE {where}
        ORDER BY knn.distance
        LIMIT ?
    """
    rows = db.execute(
        sql,
        (_serialize_f32([float(x) for x in qvec]), k, *params, limit),
    ).fetchall()
    hits = [{"id": r[0], "cosine": max(0.0, 1.0 - float(r[1]))} for r in rows]
    return {"hits": hits}


def _pairs(db: sqlite3.Connection, req: dict[str, Any]) -> dict[str, Any]:
    """Find pairs of capsules whose cosine similarity meets a threshold.

    Strategy: for each capsule with an embedding, run a KNN with k+1
    (over-fetch by one to account for the capsule matching itself),
    keep the canonical-ordered pair (a_id < b_id) once, drop pairs
    below threshold. O(N · k · log N), much better than the previous
    O(N²).
    """
    k = int(req.get("k", 10))
    threshold = float(req.get("threshold", 0.85))
    threshold = max(0.0, min(1.0, threshold))

    dim = _ensure_vec_index(db)
    if dim is None:
        return {"pairs": []}

    seen: set[tuple[str, str]] = set()
    pairs: list[dict[str, Any]] = []
    rows = db.execute("SELECT id, embedding FROM vec_index").fetchall()
    for src_id, src_blob in rows:
        for nb_id, nb_dist in db.execute(
            """
            SELECT id, distance FROM vec_index
            WHERE embedding MATCH ? AND k = ?
            ORDER BY distance
            """,
            (src_blob, k + 1),
        ).fetchall():
            if nb_id == src_id:
                continue
            cosine_sim = max(0.0, 1.0 - float(nb_dist))
            if cosine_sim < threshold:
                continue
            a_id, b_id = sorted((src_id, nb_id))
            if (a_id, b_id) in seen:
                continue
            seen.add((a_id, b_id))
            pairs.append({"a_id": a_id, "b_id": b_id, "cosine": cosine_sim})
    pairs.sort(key=lambda p: p["cosine"], reverse=True)
    return {"pairs": pairs}


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        _print_error_and_exit("empty stdin; expected one JSON object")

    try:
        req = json.loads(raw)
    except json.JSONDecodeError as err:
        _print_error_and_exit(f"stdin not valid JSON: {err}")

    if not isinstance(req, dict):
        _print_error_and_exit("request must be a JSON object")

    mode = req.get("mode")
    db_path = req.get("db_path")
    if not isinstance(db_path, str) or not db_path:
        _print_error_and_exit("'db_path' must be a non-empty string")

    db = _connect(db_path)
    try:
        if mode == "knn":
            result = _knn(db, req)
        elif mode == "pairs":
            result = _pairs(db, req)
        else:
            _print_error_and_exit(f"unknown mode {mode!r}; expected 'knn' or 'pairs'")
            return  # unreachable, satisfies linters
        print(json.dumps(result))
    except sqlite3.Error as err:
        _print_error_and_exit(f"sqlite error: {err}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
