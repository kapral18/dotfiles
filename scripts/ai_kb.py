#!/usr/bin/env python3
"""Local markdown + SQLite FTS5 knowledgebase for agent runs.

Storage model is a structured capsule schema with provenance, scope,
domain tags, dense embedding, and curation metadata. The markdown
sidecars are canonical; a stale SQLite mirror is rebuilt from them
transactionally on init/read rather than silently emptied.

Each capsule lives both in `kb.sqlite3` (indexed) and as a markdown
sidecar file under `capsules/<id>.md` (human-grep-friendly).

Usage:
    ai_kb.py init
    ai_kb.py remember --title TITLE --body BODY [--kind KIND]
                      [--scope SCOPE] [--workspace PATH]
                      [--project PROJECT_ID] [--domain TAGS]
                      [--confidence FLOAT] [--verified-by RID]
                      [--supersedes ID] [--refs REF]
                      [--source SOURCE] [--tags TAGS]
                      [--no-embed]
    ai_kb.py search QUERY [--limit N]
                          [--scope SCOPE] [--kind KIND]
                          [--workspace PATH] [--domain TAG]
                          [--mode hybrid|bm25|vector]
                          [--json]
    ai_kb.py get ID [--json]
    ai_kb.py list [--limit N] [--json]
    ai_kb.py reembed [--limit N]
    ai_kb.py harvest [--session-id ID] [--topic TOPIC] [--worklog PATH] [--json]
    ai_kb.py doctor
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import agent_memory

# Embedder lives in a sibling module; import is local so this script
# works even when embed.py is missing or its runner is not installed
# (search degrades to BM25-only). Each method that needs the embedder
# imports lazily so a missing dep doesn't break read-only paths.

# --- Constants -------------------------------------------------------------

CAPSULE_KINDS = (
    "fact",
    "gotcha",
    "pattern",
    "anti_pattern",
    "recipe",
    "principle",
    "doc",
)
CAPSULE_SCOPES = ("workspace", "project", "domain", "universal")
SCHEMA_VERSION = 3  # bumped any time the table shape changes

# RRF constant used by hybrid retrieval; 60 is the canonical value from
# the original RRF paper and works well for top-K in [5, 50] without
# tuning per-corpus.
RRF_K = 60

# MMR diversification weight. 0.7 = strong relevance bias; lower values
# diversify more aggressively at the cost of relevance.
MMR_LAMBDA = 0.7

# Soft penalty applied to the RRF score for dormant capsules. `curate
# decay` raises a capsule's `decay_score` (0..1) on every pass in which
# the capsule has not been retrieved within DECAY_RECENT_DAYS; here that
# score is subtracted (scaled) from the RRF score so stale memory sinks
# without being filtered out. Retrieval resets `decay_score` to 0, so a
# capsule that keeps proving useful never sinks. Mirrors the magnitude of
# the same-workspace boost (+0.1) so a fully-decayed capsule (score 1.0)
# is penalized by the same amount a workspace match is rewarded.
DECAY_PENALTY_WEIGHT = 0.1

# A capsule retrieved within this many days is shielded from `curate
# decay`: decay measures dormancy (no retrievals), not mere age.
DECAY_RECENT_DAYS = 14

# Write-time near-duplicate refusal threshold: `remember` refuses a new
# capsule whose embedding cosine against an existing same-kind live
# capsule is at or above this value (mirrors the `curate` dedupe
# threshold) unless --force or --supersedes covers the collision.
DUPLICATE_COSINE_THRESHOLD = 0.95

# --- Worklog harvest -------------------------------------------------------
# `,ai-kb harvest` mines a hook worklog for durable-memory CANDIDATES; it
# never writes capsules (persistence stays agent-driven, see the ai-kb
# skill and hook README). The worklog path convention mirrors the agent
# hooks: /tmp/specs/<workspace-without-leading-slash>/<topic>.worklog.jsonl.
# Session/topic resolution is shared with `,agent-memory` so harvest cannot
# drift to a different bucket than the invoking agent session.
# First tokens too generic to be a durable "recipe" on their own.
HARVEST_NOISE_PROGRAMS = frozenset({"cd", "ls", "pwd", "echo", "cat", "clear", "which", "true", "false"})


# --- Helpers ---------------------------------------------------------------


def default_home() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return Path(os.environ.get("AI_KB_HOME", data_home / "ai-kb")).expanduser()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "note"


def make_id(title: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{stamp}-{slugify(title)}"


def quote_fts_term(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def to_fts_query(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9_./:-]+", query)
    if not terms:
        return quote_fts_term(query)
    return " OR ".join(quote_fts_term(term) for term in terms[:12])


def csv_join(values: list[str]) -> str:
    """Pack a list of tags/refs into the canonical comma-separated form
    used by the schema. Whitespace and empties are stripped, order is
    preserved, duplicates are removed."""
    seen: list[str] = []
    for v in values:
        s = (v or "").strip()
        if s and s not in seen:
            seen.append(s)
    return ",".join(seen)


def csv_split(value: str | None) -> list[str]:
    """Inverse of `csv_join`. Empty/None → []."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


# --- Capsule dataclass -----------------------------------------------------


@dataclass
class Capsule:
    """Canonical capsule record exposed to callers.

    `embedding` is intentionally NOT a field on this dataclass — it is
    a binary BLOB stored in the DB and only round-tripped through the
    embedder/retrieval code. Keeping it off the dataclass means
    `asdict(capsule)` is JSON-safe by default.
    """

    id: str
    kind: str
    title: str
    body: str
    source: str
    tags: str
    path: str
    scope: str
    workspace_path: str | None
    project_id: str | None
    domain_tags: str
    confidence: float
    verified_by: str | None
    supersedes: str | None
    superseded_by: str | None
    refs: str
    embedding_model: str | None
    embedding_dim: int
    decay_score: float
    created_at: str
    updated_at: str


# Fields persisted in the SQL schema in column order. Used to detect
# stale schemas and to project SELECT * row dicts down to Capsule
# arguments.
CAPSULE_COLUMNS: tuple[str, ...] = (
    "id",
    "kind",
    "title",
    "body",
    "source",
    "tags",
    "path",
    "scope",
    "workspace_path",
    "project_id",
    "domain_tags",
    "confidence",
    "verified_by",
    "supersedes",
    "superseded_by",
    "refs",
    "embedding",  # BLOB, not on Capsule dataclass
    "embedding_model",
    "embedding_dim",
    "decay_score",
    "retrieved_at",  # mutable SQLite-only retrieval state, not on sidecars
    "retrieval_count",
    "created_at",
    "updated_at",
)


def row_to_capsule(row: sqlite3.Row | dict) -> Capsule:
    """Project a `SELECT *` row dict down to the Capsule dataclass.

    Drops the `embedding` BLOB (kept inside the DB only). Used by every
    read path so callers receive a uniform shape.
    """
    d = dict(row)
    d.pop("embedding", None)
    # Mutable SQLite-only retrieval state; not part of the capsule shape.
    d.pop("retrieved_at", None)
    d.pop("retrieval_count", None)
    return Capsule(**d)


# --- Hit / search payload types --------------------------------------------


@dataclass
class Hit:
    """One retrieval result. Carries everything callers need to show
    or inject the capsule into a prompt: identity, scoring breakdown,
    structured metadata, body, and snippet for highlights."""

    id: str
    title: str
    body: str
    snippet: str
    source: str
    tags: str
    kind: str
    scope: str
    workspace_path: str | None
    domain_tags: str
    confidence: float
    bm25_rank: int | None  # 1-based rank in BM25 list, None if not in
    vector_rank: int | None  # 1-based rank in cosine list, None if not in
    bm25_score: float | None
    cosine_score: float | None
    rrf_score: float
    mmr_selected: bool


# --- Knowledge base --------------------------------------------------------


class KnowledgeBase:
    """SQLite + FTS5 + dense-embedding capsule store.

    The capsule table holds structured metadata and the embedding BLOB.
    `capsule_fts` is a parallel FTS5 virtual table indexing
    `(title, body, tags, source, domain_tags)`; it is rebuilt from
    `capsules` whenever schema migration runs so the two never drift.

    Embeddings are stored as packed little-endian float32 BLOBs. Dim
    and model id are tracked per-row so the system can detect a model
    change and trigger a re-embed pass.
    """

    def __init__(self, home: Path | None = None, embedder=None) -> None:
        self.home = home or default_home()
        self.capsules_dir = self.home / "capsules"
        self.db_path = self.home / "kb.sqlite3"
        # Lazy import to keep this module importable even if embed.py
        # has issues. The embedder is constructed on first use unless
        # one is injected (tests inject stubs).
        self._embedder = embedder
        self._embedder_resolved = embedder is not None

    # --- schema ------------------------------------------------------------

    def init(self) -> None:
        """Ensure the schema exists and repair stale indexed state.

        We don't migrate capsule columns in place. When the `capsules`
        table shape drifts, we rebuild it from canonical sidecars and
        overlay recoverable mutable/derived SQLite state. When only the
        derived tables (`capsule_fts` / `kb_meta`) drift, we rebuild
        them from the current `capsules` rows without replacing the
        authoritative table.
        """
        self.capsules_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            state = self._schema_state(db)
            if state == "capsules_stale":
                capsules = self._load_sidecar_capsules()
                recovered = self._load_recoverable_capsule_state(db)
                rebuilt_rows = self._merge_rebuilt_rows(capsules, recovered)
                db.execute("BEGIN IMMEDIATE")
                self._drop_schema(db)
                self._create_schema(db)
                for row in rebuilt_rows:
                    self._insert_rebuilt_capsule(db, row)
                return
            if state == "derived_stale":
                db.execute("BEGIN IMMEDIATE")
                self._repair_derived_tables(db)
                return
            self._create_schema(db)

    def init_doc_ingest_table(self) -> None:
        """Idempotent table for tracking ingested documents.

        Stores the file path, sha256 of its content, when it was last
        ingested, and the list of capsule IDs created for that file so
        re-ingestion can replace stale chunks atomically. Created on
        first ingest call; init() doesn't pre-create it because most
        KBs never need it.
        """
        with self.connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS doc_ingests (
                    path TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    last_ingested_at TEXT NOT NULL,
                    capsule_ids TEXT NOT NULL
                )
                """
            )

    def _create_schema(self, db: sqlite3.Connection) -> None:
        self._create_capsules_table(db)
        self._create_derived_tables(db)
        self._create_capsule_indexes(db)

    @staticmethod
    def _create_capsules_table(db: sqlite3.Connection) -> None:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS capsules (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                source TEXT NOT NULL,
                tags TEXT NOT NULL,
                path TEXT NOT NULL,
                scope TEXT NOT NULL,
                workspace_path TEXT,
                project_id TEXT,
                domain_tags TEXT NOT NULL,
                confidence REAL NOT NULL,
                verified_by TEXT,
                supersedes TEXT,
                superseded_by TEXT,
                refs TEXT NOT NULL,
                embedding BLOB,
                embedding_model TEXT,
                embedding_dim INTEGER NOT NULL,
                decay_score REAL NOT NULL,
                retrieved_at TEXT,
                retrieval_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_derived_tables(db: sqlite3.Connection) -> None:
        db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS capsule_fts USING fts5(
                id UNINDEXED,
                title,
                body,
                tags,
                source,
                domain_tags
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS kb_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        db.execute(
            "INSERT OR REPLACE INTO kb_meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )

    @staticmethod
    def _create_capsule_indexes(db: sqlite3.Connection) -> None:
        db.execute("CREATE INDEX IF NOT EXISTS idx_capsules_kind ON capsules(kind)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_capsules_scope ON capsules(scope)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_capsules_workspace ON capsules(workspace_path)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_capsules_decay ON capsules(decay_score)")

    @staticmethod
    def _drop_schema(db: sqlite3.Connection) -> None:
        db.execute("DROP TABLE IF EXISTS capsule_fts")
        db.execute("DROP TABLE IF EXISTS capsules")
        db.execute("DROP TABLE IF EXISTS kb_meta")

    @staticmethod
    def _drop_derived_tables(db: sqlite3.Connection) -> None:
        db.execute("DROP TABLE IF EXISTS capsule_fts")
        db.execute("DROP TABLE IF EXISTS kb_meta")

    def _load_sidecar_capsules(self) -> list[Capsule]:
        capsules: list[Capsule] = []
        by_id: dict[str, Capsule] = {}
        for path in sorted(self.capsules_dir.glob("*.md")):
            capsule = self._parse_sidecar(path)
            if capsule.id in by_id:
                raise ValueError(f"duplicate capsule sidecar id {capsule.id!r} at {path}")
            by_id[capsule.id] = capsule
            capsules.append(capsule)
        capsules.sort(key=lambda c: (c.created_at, c.id))
        for capsule in capsules:
            if capsule.supersedes and capsule.supersedes in by_id:
                by_id[capsule.supersedes].superseded_by = capsule.id
        return capsules

    def _load_recoverable_capsule_state(self, db: sqlite3.Connection) -> dict[str, dict[str, object]]:
        cols = {r[1] for r in db.execute("PRAGMA table_info(capsules)").fetchall()}
        if "id" not in cols:
            return {}
        allowed = [
            "id",
            "supersedes",
            "superseded_by",
            "embedding",
            "embedding_model",
            "embedding_dim",
            "decay_score",
            "retrieved_at",
            "retrieval_count",
            "updated_at",
        ]
        select_cols = [col for col in allowed if col in cols]
        rows = db.execute(f"SELECT {','.join(select_cols)} FROM capsules").fetchall()
        recovered: dict[str, dict[str, object]] = {}
        for row in rows:
            state = {
                "supersedes": row["supersedes"] if "supersedes" in row.keys() and row["supersedes"] else None,
                "superseded_by": (
                    row["superseded_by"] if "superseded_by" in row.keys() and row["superseded_by"] else None
                ),
                "embedding": row["embedding"] if "embedding" in row.keys() else None,
                "embedding_model": (
                    row["embedding_model"] if "embedding_model" in row.keys() and row["embedding_model"] else None
                ),
                "embedding_dim": 0,
                "decay_score": 0.0,
                "updated_at": row["updated_at"] if "updated_at" in row.keys() and row["updated_at"] else None,
            }
            if "embedding_dim" in row.keys():
                try:
                    state["embedding_dim"] = max(0, int(row["embedding_dim"] or 0))
                except (TypeError, ValueError):
                    state["embedding_dim"] = 0
            if "decay_score" in row.keys():
                try:
                    state["decay_score"] = float(row["decay_score"] or 0.0)
                except (TypeError, ValueError):
                    state["decay_score"] = 0.0
            state["retrieved_at"] = (
                row["retrieved_at"] if "retrieved_at" in row.keys() and row["retrieved_at"] else None
            )
            state["retrieval_count"] = 0
            if "retrieval_count" in row.keys():
                try:
                    state["retrieval_count"] = max(0, int(row["retrieval_count"] or 0))
                except (TypeError, ValueError):
                    state["retrieval_count"] = 0
            if state["embedding"] is None:
                state["embedding_model"] = None
                state["embedding_dim"] = 0
            elif state["embedding_dim"] <= 0:
                try:
                    from embed import unpack_vector  # local import

                    state["embedding_dim"] = len(unpack_vector(state["embedding"]))
                except Exception:
                    state["embedding"] = None
                    state["embedding_model"] = None
                    state["embedding_dim"] = 0
            recovered[row["id"]] = state
        return recovered

    def _merge_rebuilt_rows(
        self, capsules: list[Capsule], recovered: dict[str, dict[str, object]]
    ) -> list[dict[str, object]]:
        sidecar_ids = {capsule.id for capsule in capsules}
        rows: list[dict[str, object]] = []
        by_id: dict[str, dict[str, object]] = {}
        for capsule in capsules:
            state = recovered.get(capsule.id, {})
            supersedes = capsule.supersedes
            if not supersedes:
                candidate = state.get("supersedes")
                if candidate in sidecar_ids:
                    supersedes = str(candidate)
            superseded_by = state.get("superseded_by")
            if superseded_by not in sidecar_ids:
                superseded_by = None
            row = {
                "id": capsule.id,
                "kind": capsule.kind,
                "title": capsule.title,
                "body": capsule.body,
                "source": capsule.source,
                "tags": capsule.tags,
                "path": capsule.path,
                "scope": capsule.scope,
                "workspace_path": capsule.workspace_path,
                "project_id": capsule.project_id,
                "domain_tags": capsule.domain_tags,
                "confidence": capsule.confidence,
                "verified_by": capsule.verified_by,
                "supersedes": supersedes,
                "superseded_by": superseded_by,
                "refs": capsule.refs,
                "embedding": state.get("embedding"),
                "embedding_model": state.get("embedding_model"),
                "embedding_dim": int(state.get("embedding_dim", 0) or 0),
                "decay_score": float(state.get("decay_score", capsule.decay_score) or 0.0),
                "retrieved_at": state.get("retrieved_at"),
                "retrieval_count": int(state.get("retrieval_count", 0) or 0),
                "created_at": capsule.created_at,
                "updated_at": str(state.get("updated_at") or capsule.updated_at),
            }
            rows.append(row)
            by_id[capsule.id] = row
        for row in rows:
            loser_id = row["supersedes"]
            if loser_id and loser_id in by_id:
                by_id[str(loser_id)]["superseded_by"] = row["id"]
        return rows

    def _parse_sidecar(self, path: Path) -> Capsule:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as err:
            raise ValueError(f"unable to read capsule sidecar {path}: {err}") from err
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError(f"malformed capsule sidecar {path}: missing opening frontmatter fence")
        frontmatter: dict[str, str] = {}
        body_start: int | None = None
        for idx, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                body_start = idx + 1
                break
            if not line.strip():
                continue
            if ":" not in line:
                raise ValueError(f"malformed capsule sidecar {path}: bad frontmatter line {line!r}")
            key, value = line.split(":", 1)
            key = key.strip()
            if not key:
                raise ValueError(f"malformed capsule sidecar {path}: empty frontmatter key")
            frontmatter[key] = value.strip()
        if body_start is None:
            raise ValueError(f"malformed capsule sidecar {path}: missing closing frontmatter fence")
        required = ("id", "title", "kind", "scope", "source", "confidence", "created_at")
        missing = [key for key in required if not frontmatter.get(key)]
        if missing:
            raise ValueError(f"malformed capsule sidecar {path}: missing {', '.join(missing)}")
        note_id = frontmatter["id"]
        if path.stem != note_id:
            raise ValueError(f"malformed capsule sidecar {path}: filename does not match id {note_id!r}")
        kind = frontmatter["kind"]
        scope = frontmatter["scope"]
        if kind not in CAPSULE_KINDS:
            raise ValueError(f"malformed capsule sidecar {path}: unknown kind {kind!r}")
        if scope not in CAPSULE_SCOPES:
            raise ValueError(f"malformed capsule sidecar {path}: unknown scope {scope!r}")
        try:
            confidence = float(frontmatter["confidence"])
        except ValueError as err:
            raise ValueError(
                f"malformed capsule sidecar {path}: invalid confidence {frontmatter['confidence']!r}"
            ) from err
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"malformed capsule sidecar {path}: confidence must be between 0 and 1")
        embedding_dim = 0
        if frontmatter.get("embedding_dim"):
            try:
                embedding_dim = int(frontmatter["embedding_dim"])
            except ValueError as err:
                raise ValueError(
                    f"malformed capsule sidecar {path}: invalid embedding_dim {frontmatter['embedding_dim']!r}"
                ) from err
            if embedding_dim < 0:
                raise ValueError(f"malformed capsule sidecar {path}: embedding_dim must be >= 0")
        decay_score = 0.0
        if frontmatter.get("decay_score"):
            try:
                decay_score = float(frontmatter["decay_score"])
            except ValueError as err:
                raise ValueError(
                    f"malformed capsule sidecar {path}: invalid decay_score {frontmatter['decay_score']!r}"
                ) from err
        body = self._strip_sidecar_heading(frontmatter["title"], "\n".join(lines[body_start:]))
        return Capsule(
            id=note_id,
            kind=kind,
            title=frontmatter["title"],
            body=body,
            source=frontmatter["source"],
            tags=frontmatter.get("tags", ""),
            path=str(path),
            scope=scope,
            workspace_path=frontmatter.get("workspace_path") or None,
            project_id=frontmatter.get("project_id") or None,
            domain_tags=frontmatter.get("domain_tags", ""),
            confidence=confidence,
            verified_by=frontmatter.get("verified_by") or None,
            supersedes=frontmatter.get("supersedes") or None,
            superseded_by=frontmatter.get("superseded_by") or None,
            refs=frontmatter.get("refs", ""),
            embedding_model=frontmatter.get("embedding_model") or None,
            embedding_dim=embedding_dim,
            decay_score=decay_score,
            created_at=frontmatter["created_at"],
            updated_at=frontmatter.get("updated_at") or frontmatter["created_at"],
        )

    @staticmethod
    def _strip_sidecar_heading(title: str, text: str) -> str:
        lines = text.lstrip("\n").splitlines()
        if lines:
            first = lines[0].lstrip()
            if first.startswith("# ") and first[2:].strip() == title:
                lines = lines[1:]
                while lines and not lines[0].strip():
                    lines = lines[1:]
        return "\n".join(lines).strip()

    def _insert_rebuilt_capsule(self, db: sqlite3.Connection, capsule: dict[str, object]) -> None:
        db.execute(
            """
            INSERT INTO capsules(
                id, kind, title, body, source, tags, path, scope,
                workspace_path, project_id, domain_tags, confidence,
                verified_by, supersedes, superseded_by, refs,
                embedding, embedding_model, embedding_dim,
                decay_score, retrieved_at, retrieval_count, created_at, updated_at
            )
            VALUES(
                :id, :kind, :title, :body, :source, :tags, :path, :scope,
                :workspace_path, :project_id, :domain_tags, :confidence,
                :verified_by, :supersedes, :superseded_by, :refs,
                :embedding, :embedding_model, :embedding_dim,
                :decay_score, :retrieved_at, :retrieval_count, :created_at, :updated_at
            )
            """,
            capsule,
        )
        db.execute(
            """
            INSERT INTO capsule_fts(id, title, body, tags, source, domain_tags)
            VALUES(:id, :title, :body, :tags, :source, :domain_tags)
            """,
            capsule,
        )

    def _repair_derived_tables(self, db: sqlite3.Connection) -> None:
        self._drop_derived_tables(db)
        self._create_derived_tables(db)
        self._create_capsule_indexes(db)
        rows = db.execute("SELECT id, title, body, tags, source, domain_tags FROM capsules").fetchall()
        for row in rows:
            db.execute(
                """
                INSERT INTO capsule_fts(id, title, body, tags, source, domain_tags)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (row["id"], row["title"], row["body"], row["tags"], row["source"], row["domain_tags"]),
            )

    def _schema_state(self, db: sqlite3.Connection) -> str:
        """Classify the current mirror state: missing, ok, capsules_stale, or derived_stale."""
        rows = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='capsules'").fetchall()
        if not rows:
            return "missing"
        cols = [r[1] for r in db.execute("PRAGMA table_info(capsules)").fetchall()]
        if tuple(cols) != CAPSULE_COLUMNS:
            return "capsules_stale"
        aux = {
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('capsule_fts', 'kb_meta')"
            ).fetchall()
        }
        if "capsule_fts" not in aux or "kb_meta" not in aux:
            return "derived_stale"
        return "derived_stale" if self._fts_mirror_diverges(db) else "ok"

    @staticmethod
    def _fts_mirror_diverges(db: sqlite3.Connection) -> bool:
        """True when `capsule_fts` no longer mirrors `capsules` on id, title,
        body, tags, source, or domain_tags.

        Two independent corruptions must both be caught, so we combine two
        checks:

        * a row-count mismatch — including an FTS row that duplicates an
          existing capsule (which double-counts in BM25). A set difference
          alone misses this because EXCEPT dedupes multiset duplicates.
        * a same-count in-place overwrite of a row's id or text (e.g.
          `capsule_fts` corrupted directly). A count comparison alone
          misses this because both tables still hold the same number of
          rows.

        We test the cheap count first (which also short-circuits the scan
        when it already diverges), then take a symmetric set difference
        (EXCEPT both ways) over the mirrored columns: any capsules row
        without an identical match in capsule_fts, or vice versa, means the
        mirror is stale. FTS5 stores column text verbatim (this is a plain,
        non-external-content table), so SELECT returns the exact original
        strings and EXCEPT can compare them like ordinary TEXT columns. The
        outer LIMIT 1 keeps this cheap by not materializing a full diff once
        any mismatch exists.
        """
        fts_count = db.execute("SELECT COUNT(*) FROM capsule_fts").fetchone()[0]
        cap_count = db.execute("SELECT COUNT(*) FROM capsules").fetchone()[0]
        if fts_count != cap_count:
            return True
        cols = "id, title, body, tags, source, domain_tags"
        # EXCEPT/UNION ALL are left-associative at the same precedence, so
        # each side must be its own parenthesized subquery: unparenthesized
        # `A EXCEPT B UNION ALL C EXCEPT D` parses as `((A EXCEPT B) UNION
        # ALL C) EXCEPT D`, not the symmetric-difference union intended here.
        row = db.execute(
            f"""
            SELECT 1 FROM (
                SELECT {cols} FROM capsules
                EXCEPT
                SELECT {cols} FROM capsule_fts
            )
            UNION ALL
            SELECT 1 FROM (
                SELECT {cols} FROM capsule_fts
                EXCEPT
                SELECT {cols} FROM capsules
            )
            LIMIT 1
            """
        ).fetchone()
        return row is not None

    def connect(self) -> sqlite3.Connection:
        self.home.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    # --- vec_runner subprocess --------------------------------------------

    def _vec_runner_path(self) -> Path:
        """Sibling vec_runner.py colocated with this module."""
        return Path(__file__).resolve().parent / "vec_runner.py"

    def _call_vec_runner(self, payload: dict, *, timeout: int = 60) -> dict:
        """Invoke `vec_runner.py` via `uv run --script` and parse its
        JSON output. Hard-fails (RuntimeError) on any failure mode —
        no silent fallback to BM25-only retrieval.

        Callers are expected to propagate the exception. The
        orchestrator's role-spawn path is allowed to surface this
        error to the human operator since vec_runner is a hard
        runtime requirement of the BIG-tier KB.

        Test escape hatch: setting `AI_KB_DISABLE_VEC=1` short-
        circuits to an empty result without spawning. Mirrors the
        `AI_KB_DISABLE_EMBED` pattern so unit tests can run
        without uv + the sqlite-vec wheel installed. Production
        never sets this var.
        """
        if os.environ.get("AI_KB_DISABLE_VEC") in ("1", "true", "yes"):
            mode = payload.get("mode")
            return {"hits": []} if mode == "knn" else {"pairs": []}
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("uv binary not found on PATH; vec_runner requires uv")
        runner = self._vec_runner_path()
        if not runner.is_file():
            raise RuntimeError(f"vec_runner missing at {runner}")
        cmd = [uv, "run", "--quiet", "--no-project", "--script", str(runner)]
        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as err:
            raise RuntimeError(f"vec_runner spawn failed: {err}") from err
        if proc.returncode != 0:
            raise RuntimeError(
                f"vec_runner exited {proc.returncode}: stderr={proc.stderr.strip()!r} stdout={proc.stdout.strip()!r}"
            )
        try:
            response = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as err:
            raise RuntimeError(f"vec_runner emitted unparseable stdout: {err} stdout={proc.stdout!r}") from err
        if "error" in response:
            raise RuntimeError(f"vec_runner error: {response['error']}")
        return response

    # --- embedder lookup ---------------------------------------------------

    def embedder(self):
        """Return the lazy-resolved Embedder, or None if unavailable.

        We resolve once per KB instance and cache the result; subsequent
        calls don't re-import or re-probe `uv`. Tests bypass this by
        passing an embedder into the constructor or by setting the
        `AI_KB_DISABLE_EMBED=1` env var (default in test fixtures
        so subprocess-based tests don't pay fastembed cold start each
        run; tests that need embedding round-trips clear it).
        """
        if self._embedder_resolved:
            return self._embedder
        if os.environ.get("AI_KB_DISABLE_EMBED") in ("1", "true", "yes"):
            self._embedder = None
            self._embedder_resolved = True
            return None
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import embed  # noqa: WPS433 — optional dep boundary

            self._embedder = embed.Embedder()
            if not self._embedder.is_available():
                self._embedder = None
        except Exception:
            self._embedder = None
        self._embedder_resolved = True
        return self._embedder

    # --- write paths -------------------------------------------------------

    def remember(
        self,
        title: str,
        body: str,
        *,
        kind: str = "fact",
        scope: str = "universal",
        source: str = "manual",
        tags: str = "",
        workspace_path: str | None = None,
        project_id: str | None = None,
        domain_tags: list[str] | str | None = None,
        confidence: float = 0.5,
        verified_by: str | None = None,
        supersedes: str | None = None,
        refs: list[str] | None = None,
        embed_now: bool = True,
        force: bool = False,
    ) -> Capsule:
        """Persist a new capsule with structured metadata and (optional)
        embedding. The kind, scope, and tags determine how downstream
        retrieval will filter and bias the result.

        Duplicate refusal: an exact (case-insensitive) title match against
        a live capsule, or a same-kind embedding cosine at or above
        `DUPLICATE_COSINE_THRESHOLD`, raises ``ValueError`` naming the
        existing capsule — pass ``supersedes`` for that capsule to update
        it, or ``force`` to store anyway.
        """
        if kind not in CAPSULE_KINDS:
            raise ValueError(f"unknown kind {kind!r}; expected one of {CAPSULE_KINDS}")
        if scope not in CAPSULE_SCOPES:
            raise ValueError(f"unknown scope {scope!r}; expected one of {CAPSULE_SCOPES}")
        confidence = float(max(0.0, min(1.0, confidence)))
        domain_csv = csv_join(domain_tags) if isinstance(domain_tags, list) else (domain_tags or "")
        refs_csv = csv_join(refs or [])

        self.init()
        note_id = make_id(title)
        now = utc_now()
        path = self.capsules_dir / f"{note_id}.md"
        body_clean = body.strip()

        embedding_blob: bytes | None = None
        embedding_model: str | None = None
        embedding_dim: int = 0
        embedding_vec: list[float] | None = None
        if embed_now:
            embedder = self.embedder()
            if embedder is not None:
                # We embed `title + "\n" + body` so capsules with a
                # short body still get a meaningful vector and titles
                # contribute to lexical-vs-semantic divergence handling.
                vec = embedder.embed_one(self._embed_text(title, body_clean))
                if vec:
                    from embed import pack_vector  # local import — see embedder()

                    embedding_blob = pack_vector(vec)
                    embedding_model = embedder.model
                    embedding_dim = len(vec)
                    embedding_vec = vec

        if not force:
            duplicate = self._find_duplicate(title, kind, embedding_vec, embedding_model, exempt_id=supersedes)
            if duplicate is not None:
                dup_id, dup_reason = duplicate
                raise ValueError(
                    f"duplicate capsule: {dup_reason} matches existing {dup_id!r}; "
                    f"pass supersedes={dup_id!r} to update it or force=True to store anyway"
                )

        front = (
            "---\n"
            f"id: {note_id}\n"
            f"title: {title}\n"
            f"kind: {kind}\n"
            f"scope: {scope}\n"
            f"source: {source}\n"
            f"tags: {tags}\n"
            f"workspace_path: {workspace_path or ''}\n"
            f"project_id: {project_id or ''}\n"
            f"domain_tags: {domain_csv}\n"
            f"confidence: {confidence}\n"
            f"verified_by: {verified_by or ''}\n"
            f"supersedes: {supersedes or ''}\n"
            f"refs: {refs_csv}\n"
            f"created_at: {now}\n"
            "---\n\n"
            f"# {title}\n\n"
            f"{body_clean}\n"
        )
        path.write_text(front)

        # If we set supersedes, also flip the parent's superseded_by
        # pointer so the link is bidirectional.
        if supersedes:
            with self.connect() as db:
                db.execute(
                    "UPDATE capsules SET superseded_by = ?, updated_at = ? WHERE id = ?",
                    (note_id, now, supersedes),
                )

        with self.connect() as db:
            db.execute(
                """
                INSERT INTO capsules(
                    id, kind, title, body, source, tags, path, scope,
                    workspace_path, project_id, domain_tags, confidence,
                    verified_by, supersedes, superseded_by, refs,
                    embedding, embedding_model, embedding_dim,
                    decay_score, retrieved_at, retrieval_count, created_at, updated_at
                )
                VALUES(
                    :id, :kind, :title, :body, :source, :tags, :path, :scope,
                    :workspace_path, :project_id, :domain_tags, :confidence,
                    :verified_by, :supersedes, NULL, :refs,
                    :embedding, :embedding_model, :embedding_dim,
                    0.0, NULL, 0, :created_at, :updated_at
                )
                """,
                {
                    "id": note_id,
                    "kind": kind,
                    "title": title,
                    "body": body_clean,
                    "source": source,
                    "tags": tags,
                    "path": str(path),
                    "scope": scope,
                    "workspace_path": workspace_path,
                    "project_id": project_id,
                    "domain_tags": domain_csv,
                    "confidence": confidence,
                    "verified_by": verified_by,
                    "supersedes": supersedes,
                    "refs": refs_csv,
                    "embedding": embedding_blob,
                    "embedding_model": embedding_model,
                    "embedding_dim": embedding_dim,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            db.execute(
                """
                INSERT INTO capsule_fts(id, title, body, tags, source, domain_tags)
                VALUES(:id, :title, :body, :tags, :source, :domain_tags)
                """,
                {
                    "id": note_id,
                    "title": title,
                    "body": body_clean,
                    "tags": tags,
                    "source": source,
                    "domain_tags": domain_csv,
                },
            )

        return Capsule(
            id=note_id,
            kind=kind,
            title=title,
            body=body_clean,
            source=source,
            tags=tags,
            path=str(path),
            scope=scope,
            workspace_path=workspace_path,
            project_id=project_id,
            domain_tags=domain_csv,
            confidence=confidence,
            verified_by=verified_by,
            supersedes=supersedes,
            superseded_by=None,
            refs=refs_csv,
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
            decay_score=0.0,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _embed_text(title: str, body: str) -> str:
        """The text we embed is title + body so capsules that are mostly
        title (e.g. doc-chunks with empty body fallback) still get a
        useful vector."""
        return f"{title}\n{body}".strip()

    def _find_duplicate(
        self,
        title: str,
        kind: str,
        embedding_vec: "list[float] | None",
        embedding_model: str | None,
        *,
        exempt_id: str | None = None,
    ) -> "tuple[str, str] | None":
        """Write-time duplicate probe over live (non-superseded) capsules.

        Returns ``(existing_id, reason)`` for an exact case-insensitive
        title collision (any kind) or a same-kind embedding cosine at or
        above `DUPLICATE_COSINE_THRESHOLD`; ``None`` when the capsule is
        novel. ``exempt_id`` skips the capsule an explicit ``supersedes``
        already covers. Fail-open on the vector lane: without a comparable
        embedding only the title check applies.
        """
        with self.connect() as db:
            row = db.execute(
                "SELECT id FROM capsules WHERE superseded_by IS NULL AND lower(title) = lower(?) LIMIT 1",
                (title,),
            ).fetchone()
            if row is not None and row["id"] != exempt_id:
                return str(row["id"]), "title"
            if not embedding_vec or not embedding_model:
                return None
            candidates = db.execute(
                """
                SELECT id, embedding FROM capsules
                WHERE superseded_by IS NULL
                  AND kind = ?
                  AND embedding IS NOT NULL
                  AND embedding_model = ?
                """,
                (kind, embedding_model),
            ).fetchall()
        from embed import cosine, unpack_vector  # local import — see embedder()

        for candidate in candidates:
            if candidate["id"] == exempt_id:
                continue
            try:
                existing_vec = unpack_vector(candidate["embedding"])
            except Exception:
                continue
            if cosine(embedding_vec, existing_vec) >= DUPLICATE_COSINE_THRESHOLD:
                return str(candidate["id"]), f"embedding cosine >= {DUPLICATE_COSINE_THRESHOLD}"
        return None

    def _record_retrieval(self, capsule_ids: "list[str]") -> None:
        """Mark returned capsules as live: stamp retrieval and clear decay.

        This is the usage signal `curate decay` keys off — a capsule
        retrieved within `DECAY_RECENT_DAYS` is shielded from decay, and a
        retrieval clears any decay it accumulated while dormant.
        `updated_at` is left untouched: it tracks content edits only.
        """
        if not capsule_ids:
            return
        now = utc_now()
        placeholders = ",".join("?" for _ in capsule_ids)
        with self.connect() as db:
            db.execute(
                f"""
                UPDATE capsules
                SET retrieved_at = ?,
                    retrieval_count = retrieval_count + 1,
                    decay_score = 0.0
                WHERE id IN ({placeholders})
                """,
                (now, *capsule_ids),
            )

    def reembed(self, *, limit: int | None = None) -> int:
        """Re-embed capsules whose embedding is missing or whose model
        differs from the current embedder. Returns the number updated.

        Used after a model swap or to backfill rows that were inserted
        when the embedder was unavailable. Returns 0 silently if no
        embedder is reachable now.
        """
        embedder = self.embedder()
        if embedder is None:
            return 0
        from embed import pack_vector  # local import

        self.init()
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT id, title, body, embedding_model
                FROM capsules
                WHERE embedding IS NULL
                   OR embedding_model IS NULL
                   OR embedding_model != ?
                ORDER BY created_at
                """,
                (embedder.model,),
            ).fetchall()

        if limit is not None:
            rows = rows[:limit]
        if not rows:
            return 0

        # Batch all texts in a single subprocess invocation; the runner
        # supports list input. This keeps backfill cheap even on KBs
        # with thousands of capsules.
        texts = [self._embed_text(r["title"], r["body"]) for r in rows]
        vectors = embedder.embed(texts)
        if not vectors or len(vectors) != len(rows):
            return 0
        now = utc_now()
        with self.connect() as db:
            for r, vec in zip(rows, vectors):
                if not vec:
                    continue
                db.execute(
                    """
                    UPDATE capsules
                    SET embedding = ?, embedding_model = ?, embedding_dim = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (pack_vector(vec), embedder.model, len(vec), now, r["id"]),
                )
        return len(rows)

    # --- doc ingestion -----------------------------------------------------

    def ingest_path(
        self,
        target: Path,
        *,
        scope: str = "universal",
        domain_tags: list[str] | None = None,
        workspace_path: str | None = None,
        max_bytes: int = 1_000_000,
    ) -> dict[str, object]:
        """Recursively ingest one path into the KB.

        Accepts a single .md file or a directory (walks `*.md` files).
        Each ingested file is chunked on `^#` and `^##` headings; each
        chunk becomes one `kind=doc` capsule. Returns a summary dict
        with counts of files seen, files ingested (changed since last
        run), files skipped (unchanged), and total capsules created.

        Idempotent on file content: if the file's sha256 matches the
        last recorded hash, the file is skipped and any existing
        capsules from that file are kept as-is. When the hash changes,
        the old capsules from that file are deleted and replaced.
        """
        self.init()
        self.init_doc_ingest_table()
        target = Path(target).expanduser().resolve()
        if not target.exists():
            raise FileNotFoundError(target)
        files: list[Path] = []
        if target.is_dir():
            files = sorted(p for p in target.rglob("*.md") if p.is_file())
        elif target.is_file() and target.suffix == ".md":
            files = [target]
        else:
            raise ValueError(f"unsupported ingest target: {target} (need .md file or dir)")

        domain_csv = csv_join(domain_tags or [])
        seen = 0
        ingested = 0
        skipped = 0
        capsule_count = 0
        for f in files:
            seen += 1
            try:
                size = f.stat().st_size
            except OSError:
                continue
            if size > max_bytes:
                continue
            text = f.read_text(errors="replace")
            sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

            with self.connect() as db:
                row = db.execute(
                    "SELECT sha256, capsule_ids FROM doc_ingests WHERE path = ?",
                    (str(f),),
                ).fetchone()
            if row and row["sha256"] == sha:
                skipped += 1
                continue

            # Replace stale chunks atomically. Existing capsules for
            # this file are removed first so retrieval doesn't return
            # outdated content alongside the new chunks.
            if row:
                old_ids = csv_split(row["capsule_ids"])
                for old_id in old_ids:
                    self.remove(old_id)

            chunks = self._chunk_markdown(text)
            new_ids: list[str] = []
            for chunk in chunks:
                title = chunk["title"][:120] or f.name
                body = chunk["body"].strip()
                if not body:
                    continue
                inferred = self._infer_domain_tags(f, domain_tags or [])
                capsule = self.remember(
                    title=title,
                    body=body,
                    kind="doc",
                    scope=scope,
                    source=f"file:{f}",
                    tags="kb-ingest,doc",
                    workspace_path=workspace_path,
                    domain_tags=inferred,
                    confidence=0.9,
                    # Ingest owns replacement through doc_ingests (stale
                    # chunks are removed above); re-chunked docs would
                    # otherwise trip the write-time duplicate probe.
                    force=True,
                )
                new_ids.append(capsule.id)
            capsule_count += len(new_ids)
            ingested += 1
            with self.connect() as db:
                db.execute(
                    """
                    INSERT INTO doc_ingests(path, sha256, last_ingested_at, capsule_ids)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        sha256 = excluded.sha256,
                        last_ingested_at = excluded.last_ingested_at,
                        capsule_ids = excluded.capsule_ids
                    """,
                    (str(f), sha, utc_now(), csv_join(new_ids)),
                )
        return {
            "files_seen": seen,
            "files_ingested": ingested,
            "files_skipped_unchanged": skipped,
            "capsules_stored": capsule_count,
        }

    @staticmethod
    def _chunk_markdown(text: str) -> list[dict[str, str]]:
        """Split a markdown document into capsule-sized chunks.

        Splits on lines that begin with `# ` or `## ` (H1 / H2). Each
        chunk uses the heading as its title and includes the heading
        line plus everything until the next H1/H2.

        Files without any H1/H2 produce one chunk titled with the
        first non-empty line (or "(untitled)" if the file is blank).
        Headings deeper than H2 are not split on — they're embedded
        inside the parent H1/H2 chunk to keep capsule count bounded.
        """
        lines = text.splitlines()
        chunks: list[dict[str, str]] = []
        cur_title: str | None = None
        cur_lines: list[str] = []

        def flush() -> None:
            nonlocal cur_title, cur_lines
            if cur_title is None and not cur_lines:
                return
            title = cur_title or _first_nonempty(cur_lines) or "(untitled)"
            chunks.append({"title": title, "body": "\n".join(cur_lines).strip()})
            cur_title = None
            cur_lines = []

        for line in lines:
            stripped = line.lstrip()
            is_h12 = stripped.startswith("# ") or stripped.startswith("## ") or stripped == "#" or stripped == "##"
            if is_h12:
                # Boundary: flush prior chunk, start a new one with
                # this heading as title and content.
                flush()
                cur_title = stripped.lstrip("#").strip()
                cur_lines = [line]
            else:
                cur_lines.append(line)
        flush()
        return chunks

    @staticmethod
    def _infer_domain_tags(path: Path, extra: list[str]) -> list[str]:
        """Auto-derive a small list of domain tags from a path.

        The tags surface in the FTS index and feed the `domain` filter
        so retrieval can target docs from a specific area without
        exact path matching. Uses the parent directory name(s) and the
        file stem with simple normalization.
        """
        candidates: list[str] = list(extra or [])
        parts = list(path.parts[-3:])  # e.g. ['skills', 'github', 'SKILL.md']
        for p in parts:
            if not p or p in (".", "/"):
                continue
            cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", p.lower()).strip("-")
            if cleaned and cleaned not in candidates and cleaned != "md":
                candidates.append(cleaned)
        return candidates[:6]

    # --- read paths --------------------------------------------------------

    def get(self, note_id: str) -> Capsule | None:
        self.init()
        with self.connect() as db:
            row = db.execute(
                f"SELECT {','.join(c for c in CAPSULE_COLUMNS if c != 'embedding')} FROM capsules WHERE id = ?",
                (note_id,),
            ).fetchone()
        return row_to_capsule(row) if row else None

    def remove(self, note_id: str) -> bool:
        self.init()
        capsule = self.get(note_id)
        if not capsule:
            return False
        with self.connect() as db:
            db.execute("DELETE FROM capsules WHERE id = ?", (note_id,))
            db.execute("DELETE FROM capsule_fts WHERE id = ?", (note_id,))
        try:
            Path(capsule.path).unlink()
        except FileNotFoundError:
            pass
        return True

    def list(self, limit: int = 50) -> list[Capsule]:
        self.init()
        cols = ",".join(c for c in CAPSULE_COLUMNS if c != "embedding")
        with self.connect() as db:
            rows = db.execute(
                f"SELECT {cols} FROM capsules ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [row_to_capsule(r) for r in rows]

    # --- retrieval ---------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 5,
        *,
        scope: str | list[str] | None = None,
        kind: str | list[str] | None = None,
        workspace: str | None = None,
        domain: str | list[str] | None = None,
        mode: str = "hybrid",
        workspace_gate: bool = False,
    ) -> list[dict[str, object]]:
        """Hybrid retrieval: BM25 + cosine + RRF + MMR.

        Modes:
          - "hybrid" (default): both lanes; merge with RRF; diversify
            with MMR. Best balance for most queries.
          - "bm25": lexical only. Useful for grep-style lookups.
          - "vector": cosine only. Useful for "find capsules that
            mean similar things" without needing keyword overlap.

        Filters (applied to candidate set BEFORE ranking) accept either
        a string or a list. `domain` matches if ANY of the given tags
        is present in the capsule's `domain_tags` CSV.

        `workspace` adds a soft +0.1 RRF score boost to capsules whose
        `workspace_path` exactly matches the supplied path; it does not
        filter — universal/domain capsules still surface.

        `workspace_gate=True` turns the workspace into a hard candidate
        filter: only capsules local to `workspace` or scoped
        `domain`/`universal` remain. This is the single owner of the
        cross-repo leakage gate that automatic injectors (session-start
        warm-start, per-turn recall) rely on; it requires `workspace`.

        A capsule's `decay_score` (raised by `curate decay` on dormant
        capsules) applies a soft RRF penalty of
        `DECAY_PENALTY_WEIGHT * decay_score`, so stale memory sinks in the
        ranking without being filtered out — a still-relevant decayed
        capsule can still surface.

        Every returned capsule is stamped as retrieved
        (`retrieved_at`/`retrieval_count`, decay cleared) so curation can
        distinguish dormant memory from memory that keeps earning recall.

        Returned dicts are JSON-friendly (no embedding BLOB) and include
        all `Hit` fields plus `body` and `snippet` for prompt injection.
        """
        self.init()
        if mode not in ("hybrid", "bm25", "vector"):
            raise ValueError(f"unknown search mode {mode!r}")
        if workspace_gate and not workspace:
            raise ValueError("workspace_gate requires a workspace path")

        scopes = _normalize_filter(scope)
        kinds = _normalize_filter(kind)
        domains = _normalize_filter(domain)

        # Pre-filter the candidate set. We over-fetch (4*limit) so RRF
        # has room to mix the two lanes; final cut is `limit`.
        candidate_pool = max(limit * 4, 20)

        bm25_hits: list[tuple[str, float, str]] = []
        if mode in ("hybrid", "bm25"):
            bm25_hits = self._bm25_search(query, candidate_pool, scopes, kinds, domains)

        vector_hits: list[tuple[str, float]] = []
        if mode in ("hybrid", "vector"):
            vector_hits = self._vector_search(query, candidate_pool, scopes, kinds, domains)

        # Build a unified candidate map keyed by capsule id.
        candidate_ids: list[str] = []
        seen: set[str] = set()
        for hid, _, _ in bm25_hits:
            if hid not in seen:
                seen.add(hid)
                candidate_ids.append(hid)
        for hid, _ in vector_hits:
            if hid not in seen:
                seen.add(hid)
                candidate_ids.append(hid)
        if not candidate_ids:
            return []

        rows = self._fetch_rows(candidate_ids)
        # Stable order: rows in insertion order from candidate_ids.
        ordered_rows = [rows[h] for h in candidate_ids if h in rows]
        if workspace_gate:
            ordered_rows = [
                row
                for row in ordered_rows
                if row["workspace_path"] == workspace or row["scope"] in ("domain", "universal")
            ]
            if not ordered_rows:
                return []

        bm25_rank = {hid: i + 1 for i, (hid, _, _) in enumerate(bm25_hits)}
        bm25_score = {hid: s for hid, s, _ in bm25_hits}
        snippets = {hid: snip for hid, _, snip in bm25_hits}
        vec_rank = {hid: i + 1 for i, (hid, _) in enumerate(vector_hits)}
        vec_score = {hid: s for hid, s in vector_hits}

        hits: list[Hit] = []
        for row in ordered_rows:
            r_bm = bm25_rank.get(row["id"])
            r_vec = vec_rank.get(row["id"])
            rrf = 0.0
            if r_bm is not None:
                rrf += 1.0 / (RRF_K + r_bm)
            if r_vec is not None:
                rrf += 1.0 / (RRF_K + r_vec)
            if workspace and row["workspace_path"] == workspace:
                rrf += 0.1  # soft boost; same-workspace capsules win ties
            decay = row["decay_score"] if "decay_score" in row.keys() else 0.0
            if decay:
                rrf -= DECAY_PENALTY_WEIGHT * float(decay)  # soft penalty; dormant capsules sink
            hits.append(
                Hit(
                    id=row["id"],
                    title=row["title"],
                    body=row["body"],
                    snippet=snippets.get(row["id"], row["body"][:200]),
                    source=row["source"],
                    tags=row["tags"],
                    kind=row["kind"],
                    scope=row["scope"],
                    workspace_path=row["workspace_path"],
                    domain_tags=row["domain_tags"],
                    confidence=row["confidence"],
                    bm25_rank=r_bm,
                    vector_rank=r_vec,
                    bm25_score=bm25_score.get(row["id"]),
                    cosine_score=vec_score.get(row["id"]),
                    rrf_score=rrf,
                    mmr_selected=False,
                )
            )

        hits.sort(key=lambda h: h.rrf_score, reverse=True)

        # MMR diversification: for hybrid mode, walk the ranked list and
        # penalize hits that are too close to already-selected ones in
        # vector space. For BM25-only / vector-only modes we skip MMR
        # (those modes are explicit "I want pure-X" requests).
        if mode == "hybrid":
            hits = self._apply_mmr(hits, limit)
        else:
            for h in hits[:limit]:
                h.mmr_selected = True
            hits = hits[:limit]

        self._record_retrieval([h.id for h in hits])
        return [asdict(h) for h in hits]

    # --- retrieval internals ----------------------------------------------

    def _bm25_search(
        self,
        query: str,
        n: int,
        scopes: list[str],
        kinds: list[str],
        domains: list[str],
    ) -> list[tuple[str, float, str]]:
        """Return [(id, score, snippet), ...] sorted best→worst.

        Filters (scope/kind/domain) join to the `capsules` table because
        they live there, not in FTS. We over-fetch and then trim to `n`.
        """
        fts_query = to_fts_query(query)
        sql_filters, params = self._build_filter_clause(scopes, kinds, domains)
        sql = f"""
            SELECT
                f.id AS id,
                snippet(capsule_fts, 1, '[', ']', '...', 16) AS snippet,
                bm25(capsule_fts) AS score
            FROM capsule_fts AS f
            JOIN capsules AS c ON c.id = f.id
            WHERE capsule_fts MATCH ?
              {sql_filters}
            ORDER BY score
            LIMIT ?
        """
        with self.connect() as db:
            try:
                rows = db.execute(sql, (fts_query, *params, n)).fetchall()
            except sqlite3.OperationalError:
                # FTS query rejected (e.g. all stopwords). Fall back to
                # a LIKE scan so we still return *something* lexical.
                like = f"%{query.lower()}%"
                like_filters, like_params = self._build_filter_clause(scopes, kinds, domains, alias="c")
                rows = db.execute(
                    f"""
                    SELECT id, body AS snippet, 0.0 AS score
                    FROM capsules AS c
                    WHERE (LOWER(title) LIKE ? OR LOWER(body) LIKE ?
                           OR LOWER(tags) LIKE ? OR LOWER(domain_tags) LIKE ?)
                      {like_filters}
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (like, like, like, like, *like_params, n),
                ).fetchall()
        return [(r["id"], float(r["score"]), str(r["snippet"])) for r in rows]

    def _vector_search(
        self,
        query: str,
        n: int,
        scopes: list[str],
        kinds: list[str],
        domains: list[str],
    ) -> list[tuple[str, float]]:
        """Return [(id, cosine), ...] sorted best→worst.

        Delegates to `vec_runner.py` (a uv-managed subprocess that
        loads sqlite-vec). The runner manages its own `vec_index`
        virtual table — lazily created and synced from
        `capsules.embedding` BLOBs on every call — so this method
        only has to spawn the process and parse JSON.

        Returns [] when no embedder is available (cannot embed the
        query) or the KB has no embedded capsules. Hard-fails
        (RuntimeError) if vec_runner itself is unreachable or errors;
        no silent fallback to BM25-only retrieval.
        """
        embedder = self.embedder()
        if embedder is None:
            return []
        qvec = embedder.embed_one(query)
        if not qvec:
            return []
        response = self._call_vec_runner(
            {
                "mode": "knn",
                "db_path": str(self.db_path),
                "query_vector": [float(x) for x in qvec],
                "k": max(n * 2, 20),
                "limit": n,
                "filters": {"scopes": scopes, "kinds": kinds, "domains": domains},
            }
        )
        return [(h["id"], float(h["cosine"])) for h in response.get("hits", [])]

    def _build_filter_clause(
        self,
        scopes: list[str],
        kinds: list[str],
        domains: list[str],
        alias: str = "c",
    ) -> tuple[str, list]:
        """Compose the WHERE-tail used by both BM25 and vector paths.

        Returns a SQL fragment starting with `AND` (or empty string)
        and the parameter list to bind. Domains are checked with LIKE
        against the CSV column because we don't normalize them into a
        join table for now (small N, low value).

        Superseded capsules are always filtered out — they represent
        stale knowledge that has been replaced by a newer/better
        capsule via curation. Callers that explicitly want them (e.g.
        diagnostics tools) bypass `search()` and read the table
        directly.
        """
        parts: list[str] = [f"{alias}.superseded_by IS NULL"]
        params: list = []
        if scopes:
            placeholders = ",".join("?" * len(scopes))
            parts.append(f"{alias}.scope IN ({placeholders})")
            params.extend(scopes)
        if kinds:
            placeholders = ",".join("?" * len(kinds))
            parts.append(f"{alias}.kind IN ({placeholders})")
            params.extend(kinds)
        if domains:
            sub = []
            for d in domains:
                sub.append(f"{alias}.domain_tags LIKE ?")
                params.append(f"%{d}%")
            parts.append("(" + " OR ".join(sub) + ")")
        return " AND " + " AND ".join(parts), params

    def _fetch_rows(self, ids: list[str]) -> dict[str, sqlite3.Row]:
        """Bulk-fetch rows by id, preserving columns we need to score
        and present. Returns {id: row}."""
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        cols = ",".join(c for c in CAPSULE_COLUMNS if c != "embedding")
        with self.connect() as db:
            rows = db.execute(
                f"SELECT {cols} FROM capsules WHERE id IN ({placeholders})",
                tuple(ids),
            ).fetchall()
        return {r["id"]: r for r in rows}

    def _apply_mmr(self, hits: list[Hit], k: int) -> list[Hit]:
        """Maximal Marginal Relevance diversification.

        Iteratively pick the hit that maximizes
            λ * relevance(h) - (1-λ) * max_cosine(h, already_selected)
        until we have k hits. Relevance is the precomputed RRF score.

        We need vectors to compute pairwise cosine; if the embedder is
        unavailable the function degenerates to a top-k by RRF score.
        """
        if not hits or k <= 0:
            return []
        try:
            from embed import cosine, unpack_vector
        except Exception:
            for h in hits[:k]:
                h.mmr_selected = True
            return hits[:k]

        # Bulk-fetch embeddings for the candidate set.
        ids = [h.id for h in hits]
        placeholders = ",".join("?" * len(ids))
        with self.connect() as db:
            rows = db.execute(
                f"SELECT id, embedding FROM capsules WHERE id IN ({placeholders})",
                tuple(ids),
            ).fetchall()
        vectors: dict[str, list[float]] = {}
        for r in rows:
            v = unpack_vector(r["embedding"])
            if v:
                vectors[r["id"]] = v

        if not vectors:
            for h in hits[:k]:
                h.mmr_selected = True
            return hits[:k]

        selected: list[Hit] = []
        candidates = list(hits)

        # Seed with the top-RRF hit.
        candidates.sort(key=lambda h: h.rrf_score, reverse=True)
        first = candidates.pop(0)
        first.mmr_selected = True
        selected.append(first)

        while candidates and len(selected) < k:
            best: Hit | None = None
            best_score = -1e9
            for cand in candidates:
                cand_vec = vectors.get(cand.id)
                if cand_vec is None:
                    sim_max = 0.0
                else:
                    sim_max = max(
                        (cosine(cand_vec, vectors.get(s.id, [])) for s in selected),
                        default=0.0,
                    )
                mmr = MMR_LAMBDA * cand.rrf_score - (1 - MMR_LAMBDA) * sim_max
                if mmr > best_score:
                    best_score = mmr
                    best = cand
            if best is None:
                break
            best.mmr_selected = True
            selected.append(best)
            candidates.remove(best)
        return selected

    # --- curation ----------------------------------------------------------

    def curate(
        self,
        *,
        dedupe: bool = True,
        decay: bool = True,
        contradiction_scan: bool = True,
        dedupe_cosine_threshold: float = 0.95,
        contradiction_cosine_threshold: float = 0.85,
        decay_step: float = 0.1,
        decay_max: float = 1.0,
    ) -> dict[str, object]:
        """Run a one-shot curation pass over the KB.

        Operations (each independently flag-able):

        - dedupe: pair-wise cosine on stored embeddings; for each pair
          above `dedupe_cosine_threshold` with the same `kind`, mark
          the older / lower-confidence capsule as `superseded_by` the
          winner. The loser stays in the DB so retrieval history
          remains intact; downstream consumers (search) can choose to
          filter superseded rows.

        - decay: every capsule not retrieved in this pass has its
          `decay_score` increased by `decay_step`, capped at
          `decay_max`. Search bias against high-decay rows can be
          implemented in a future pass.

        - contradiction_scan: surface candidate pairs where a
          `kind=gotcha` and a `kind=fact` capsule have very similar
          embeddings (cosine > `contradiction_cosine_threshold`) —
          these often indicate the gotcha refines or contradicts the
          fact. Returns the candidate pairs in the summary so a human
          (or the reflector role) can adjudicate; we do not auto-link.

        Returns a summary dict with counts and the contradiction
        candidate list.
        """
        self.init()

        # Snapshot capsule metadata once. We no longer load embedding
        # BLOBs — the pairwise similarity work runs in vec_runner over
        # its own vec_index. We just need the metadata for dedupe
        # winner selection and for distinguishing dedupe pairs from
        # contradiction pairs by kind.
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT id, title, body, kind, scope, confidence,
                       supersedes, superseded_by, decay_score, created_at
                FROM capsules
                WHERE embedding IS NOT NULL
                """
            ).fetchall()
        meta: dict[str, dict] = {
            r["id"]: {
                "id": r["id"],
                "title": r["title"],
                "body": r["body"],
                "kind": r["kind"],
                "confidence": r["confidence"],
                "decay_score": r["decay_score"],
                "created_at": r["created_at"],
                "superseded_by": r["superseded_by"],
            }
            for r in rows
        }

        dedupes_applied = 0
        contradictions: list[dict[str, object]] = []
        if meta and (dedupe or contradiction_scan):
            # Use the lower of the two thresholds so the runner emits
            # everything we might need; we partition into dedupe vs
            # contradiction in Python by kind.
            lo_threshold = min(
                dedupe_cosine_threshold if dedupe else 1.0,
                contradiction_cosine_threshold if contradiction_scan else 1.0,
            )
            response = self._call_vec_runner(
                {
                    "mode": "pairs",
                    "db_path": str(self.db_path),
                    "k": 10,
                    "threshold": lo_threshold,
                }
            )
            for pair in response.get("pairs", []):
                a_id, b_id = pair["a_id"], pair["b_id"]
                a, b = meta.get(a_id), meta.get(b_id)
                if a is None or b is None:
                    continue
                if a["superseded_by"] or b["superseded_by"]:
                    continue
                sim = float(pair["cosine"])
                if dedupe and a["kind"] == b["kind"] and sim >= dedupe_cosine_threshold:
                    # Pick the loser deterministically. Higher
                    # confidence wins; ties go to the more recent
                    # capsule. Body length is a final tiebreak so a
                    # one-line stub doesn't outrank a fully-written
                    # version of the same lesson.
                    keeper, loser = self._dedupe_winner(a, b)
                    self._mark_superseded(loser["id"], keeper["id"])
                    loser["superseded_by"] = keeper["id"]
                    dedupes_applied += 1
                elif (
                    contradiction_scan
                    and {a["kind"], b["kind"]} == {"fact", "gotcha"}
                    and sim >= contradiction_cosine_threshold
                ):
                    contradictions.append(
                        {
                            "a_id": a["id"],
                            "b_id": b["id"],
                            "a_kind": a["kind"],
                            "b_kind": b["kind"],
                            "cosine": round(sim, 4),
                        }
                    )

        decayed = 0
        if decay:
            now = utc_now()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=DECAY_RECENT_DAYS)).replace(microsecond=0).isoformat()
            with self.connect() as db:
                # Decay is dormancy, not age: only capsules with no
                # retrieval inside DECAY_RECENT_DAYS accumulate decay.
                # A single UPDATE keeps the operation cheap regardless
                # of KB size; ISO-8601 UTC strings compare lexically.
                cur = db.execute(
                    """
                    UPDATE capsules
                    SET decay_score = MIN(?, decay_score + ?),
                        updated_at = ?
                    WHERE superseded_by IS NULL
                      AND (retrieved_at IS NULL OR retrieved_at < ?)
                    """,
                    (decay_max, decay_step, now, cutoff),
                )
                decayed = cur.rowcount or 0

        return {
            "duplicates": dedupes_applied,
            "decayed": decayed,
            "contradictions": contradictions[:20],
            "candidates_examined": len(meta),
        }

    @staticmethod
    def _dedupe_winner(a: dict, b: dict) -> tuple[dict, dict]:
        """Pick (keeper, loser) for a near-duplicate pair.

        Order of precedence: higher confidence; more recent
        created_at; longer body. The decision is fully deterministic
        so re-running curate produces the same outcome.
        """
        if a["confidence"] != b["confidence"]:
            return (a, b) if a["confidence"] > b["confidence"] else (b, a)
        if a["created_at"] != b["created_at"]:
            return (a, b) if a["created_at"] > b["created_at"] else (b, a)
        if len(a["body"]) != len(b["body"]):
            return (a, b) if len(a["body"]) > len(b["body"]) else (b, a)
        # Last-resort tie-break: lexical id order so the choice is
        # stable across runs even when nothing else differentiates.
        return (a, b) if a["id"] < b["id"] else (b, a)

    def _mark_superseded(self, loser_id: str, keeper_id: str) -> None:
        """Wire `loser → keeper` in both directions: the loser's
        `superseded_by` points at the keeper, and the keeper's
        `supersedes` is set if not already (chain-aware: if keeper
        already supersedes another capsule, leave that link intact).
        """
        now = utc_now()
        with self.connect() as db:
            db.execute(
                "UPDATE capsules SET superseded_by = ?, updated_at = ? WHERE id = ?",
                (keeper_id, now, loser_id),
            )
            row = db.execute("SELECT supersedes FROM capsules WHERE id = ?", (keeper_id,)).fetchone()
            if row and not row["supersedes"]:
                db.execute(
                    "UPDATE capsules SET supersedes = ?, updated_at = ? WHERE id = ?",
                    (loser_id, now, keeper_id),
                )

    # --- doctor ------------------------------------------------------------

    def doctor(self) -> list[str]:
        self.init()
        checks: list[str] = []
        checks.append(f"home={self.home}")
        checks.append(f"db={self.db_path}")
        checks.append(f"schema_version={SCHEMA_VERSION}")
        with self.connect() as db:
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_probe USING fts5(value)")
            db.execute("DROP TABLE _fts_probe")
            total = db.execute("SELECT COUNT(*) FROM capsules").fetchone()[0]
            with_embed = db.execute("SELECT COUNT(*) FROM capsules WHERE embedding IS NOT NULL").fetchone()[0]
        checks.append("sqlite_fts5=ok")
        checks.append(f"capsules={total}")
        checks.append(f"capsules_with_embedding={with_embed}")
        embedder = self.embedder()
        if embedder is None:
            checks.append("embedder=unavailable (BM25-only retrieval)")
        else:
            checks.append(f"embedder=available model={embedder.model}")
        runner = self._vec_runner_path()
        if not runner.is_file():
            checks.append(f"vec_runner=missing at {runner}")
        elif shutil.which("uv") is None:
            checks.append("vec_runner=present but uv not found on PATH")
        elif os.environ.get("AI_KB_DISABLE_VEC") in ("1", "true", "yes"):
            checks.append("vec_runner=disabled via AI_KB_DISABLE_VEC")
        else:
            try:
                self._call_vec_runner(
                    {
                        "mode": "knn",
                        "db_path": str(self.db_path),
                        "query_vector": [],
                        "k": 1,
                        "limit": 1,
                        "filters": {},
                    },
                    timeout=15,
                )
                checks.append(f"vec_runner=ok at {runner}")
            except RuntimeError as err:
                checks.append(f"vec_runner=error: {err}")
        return checks


def _normalize_filter(value) -> list[str]:
    """Normalize a string|list|None filter argument into a clean list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(v).strip() for v in value if str(v).strip()]


def _first_nonempty(lines: list[str]) -> str:
    for line in lines:
        s = line.strip()
        if s:
            return s
    return ""


# --- CLI -------------------------------------------------------------------


def resolve_topic(workspace: Path, explicit: str | None, session_id: str | None = None) -> str:
    """Resolve the same explicit/session/branch topic that `,agent-memory` uses."""
    spec_dir = agent_memory.spec_dir_for(workspace)
    return agent_memory.resolve_selected_topic(spec_dir, workspace, explicit, session_id)


def worklog_path(workspace: Path, topic: str) -> Path:
    return agent_memory.spec_dir_for(workspace) / f"{topic}.worklog.jsonl"


def read_worklog(path: Path) -> list[dict]:
    """Parse a worklog JSONL file into dict entries, skipping malformed lines."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    entries: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _entry_command(entry: dict) -> str:
    return str(entry.get("command") or "").strip()


def _entry_failed(entry: dict) -> bool:
    if entry.get("error"):
        return True
    if str(entry.get("status") or "").lower() in {"error", "failed", "failure"}:
        return True
    return str(entry.get("event") or "") == "postToolUseFailure"


def _program(command: str) -> str:
    if not command:
        return ""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if not tokens:
        return ""
    return os.path.basename(tokens[0])


def _error_signature(entry: dict) -> str:
    """First line of the entry's real error message, digit-normalized so
    `line 42` and `line 88` collapse to one signature. Only the `error`
    field is used (worklog_recorder sets it solely from `error_message`); a
    bare nonzero exit with no error text is not a durable signal. Empty when
    there is no error message."""
    text = str(entry.get("error") or "")
    first = ""
    for line in text.splitlines():
        if line.strip():
            first = line.strip()
            break
    if not first:
        return ""
    norm = re.sub(r"\d+", "<n>", first)
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm[:120]


def _normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip())


def _evidence(entry: dict) -> dict:
    ev: dict = {}
    if entry.get("ts"):
        ev["ts"] = entry["ts"]
    for key in ("event", "tool_name", "command", "status"):
        value = entry.get(key)
        if value:
            ev[key] = value
    if entry.get("error"):
        ev["error"] = str(entry["error"])[:200]
    return ev


# Structured `,agent-memory note` kinds share the capsule taxonomy, so a
# harvested note keeps its kind verbatim. `question` is intentionally not
# harvestable: open questions are task-scoped spec context, not durable
# memory candidates; `doc` is ingestion-only and cannot be noted.
HARVESTABLE_NOTE_KINDS = frozenset(CAPSULE_KINDS) - {"doc"}


def detect_candidates(entries: list[dict], *, min_repeats: int = 2) -> list[dict]:
    """Deterministic worklog detectors returning durable-memory candidates.

    Four lenses over the worklog: (0) a structured `,agent-memory note`
    (`structured_note`) — deliberate capture, so a single occurrence is a
    candidate and `min_repeats` does not apply; (1) a failing command later
    followed by a clean run of the same program (`failure_to_fix`); (2) an
    error signature seen `min_repeats`+ times (`recurring_error`); and (3) a
    clean command run `min_repeats`+ times (`repeated_command`). No capsule
    is written; each candidate is a suggestion the caller must verify before
    remembering.
    """
    candidates: list[dict] = []

    # 0. structured notes recorded via `,agent-memory note`. These are the
    # idea/decision capture surface: unlike command lenses they carry intent,
    # so one deliberate note is enough. Identical (kind, text) notes collapse.
    seen_notes: set[tuple[str, str]] = set()
    for entry in entries:
        if entry.get("event") != "note":
            continue
        note_kind = str(entry.get("note_kind") or "")
        text = str(entry.get("text") or "").strip()
        if note_kind not in HARVESTABLE_NOTE_KINDS or not text:
            continue
        note_key = (note_kind, text)
        if note_key in seen_notes:
            continue
        seen_notes.add(note_key)
        refs = str(entry.get("refs") or "")
        body = text
        if refs:
            body += f" Refs: {refs}."
        body += " Recorded deliberately via `,agent-memory note`; verify before remembering."
        evidence = _evidence(entry)
        evidence["note_kind"] = note_kind
        candidates.append(
            {
                "detector": "structured_note",
                "kind": note_kind,
                "title": f"{note_kind}: {text}"[:120],
                "body": body,
                "count": 1,
                "evidence": [evidence],
                "note_kind": note_kind,
            }
        )

    # 1. failure -> later clean run of the same program. Anchor on a real
    # error message (not a bare nonzero exit) and skip noise programs, so a
    # compound investigation command that merely exits nonzero is not a lead.
    seen_fix: set[tuple[str, str]] = set()
    for i, entry in enumerate(entries):
        if not entry.get("error"):
            continue
        command = _entry_command(entry)
        prog = _program(command)
        if not prog or prog in HARVEST_NOISE_PROGRAMS:
            continue
        sig = _error_signature(entry)
        if not sig:
            continue
        fix = None
        for later in entries[i + 1 :]:
            if _program(_entry_command(later)) == prog and not _entry_failed(later):
                fix = later
                break
        if fix is None:
            continue
        key = (prog, sig)
        if key in seen_fix:
            continue
        seen_fix.add(key)
        candidates.append(
            {
                "detector": "failure_to_fix",
                "kind": "gotcha",
                "title": f"{prog} failure: {sig}"[:120],
                "body": (
                    f"`{command}` failed with: {sig}. A later `{_entry_command(fix)}` ran clean. "
                    "Verify the root cause and the fix before trusting this."
                ),
                "count": 1,
                "evidence": [_evidence(entry), _evidence(fix)],
                "signature": sig,
                "program": prog,
            }
        )

    fixed_sigs = {c["signature"] for c in candidates if "signature" in c}

    # 2. recurring error signature (real error messages only).
    err_groups: dict[str, list[dict]] = {}
    for entry in entries:
        if not entry.get("error"):
            continue
        sig = _error_signature(entry)
        if not sig or sig in fixed_sigs:
            continue
        err_groups.setdefault(sig, []).append(entry)
    for sig, group in err_groups.items():
        if len(group) < min_repeats:
            continue
        candidates.append(
            {
                "detector": "recurring_error",
                "kind": "gotcha",
                "title": f"Recurring error: {sig}"[:120],
                "body": (
                    f"Seen {len(group)}x in this topic's worklog: {sig}. "
                    "Capture the root cause and the durable fix as a gotcha."
                ),
                "count": len(group),
                "evidence": [_evidence(e) for e in group[:3]],
                "signature": sig,
                "program": "",
            }
        )

    # 3. repeated clean command.
    cmd_groups: dict[str, list[dict]] = {}
    for entry in entries:
        if _entry_failed(entry):
            continue
        command = _entry_command(entry)
        if not command:
            continue
        if _program(command) in HARVEST_NOISE_PROGRAMS:
            continue
        # Multiline / very long compound one-liners are ad-hoc investigation
        # scaffolding, not durable recipes.
        if "\n" in command:
            continue
        norm = _normalize_command(command)
        if len(norm) < 4 or len(norm) > 200:
            continue
        cmd_groups.setdefault(norm, []).append(entry)
    for norm, group in cmd_groups.items():
        if len(group) < min_repeats:
            continue
        candidates.append(
            {
                "detector": "repeated_command",
                "kind": "recipe",
                "title": f"Frequent command: {norm}"[:120],
                "body": (
                    f"`{norm}` ran {len(group)}x cleanly in this topic. "
                    "If it is a reusable procedure, capture it as a recipe."
                ),
                "count": len(group),
                "evidence": [_evidence(e) for e in group[:3]],
                "signature": norm,
                "program": _program(norm),
            }
        )

    priority = {"failure_to_fix": 0, "recurring_error": 1, "repeated_command": 2}
    candidates.sort(key=lambda c: (priority.get(c["detector"], 9), -c["count"]))
    return candidates


_HARVEST_STOPWORDS = frozenset(
    {"the", "and", "for", "with", "from", "this", "that", "was", "are", "not", "ran", "cannot"}
)
# Fraction of a candidate's distinctive tokens that a capsule must share to
# count as "already remembered". Above a fragile BM25 score threshold, token
# overlap is stable across queries.
HARVEST_SUPPRESS_OVERLAP = 0.6


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for tok in re.findall(r"[a-zA-Z0-9_./-]+", text.lower()):
        tok = tok.strip("-./")
        if len(tok) >= 3 and tok not in _HARVEST_STOPWORDS:
            out.add(tok)
    return out


def _distinctive_tokens(signature: str) -> list[str]:
    """Longest, most specific tokens of a signature — the ones a real capsule
    about the same thing would also contain (error codes, symbols, filenames)."""
    toks = [t for t in _tokens(signature) if any(ch.isalpha() for ch in t)]
    toks.sort(key=len, reverse=True)
    return toks[:6]


def suppress_known(kb: "KnowledgeBase", candidates: list[dict], workspace: Path | None) -> list[dict]:
    """Annotate candidates already covered by a capsule (`known`/`known_id`).

    Uses the BM25 lane (no embedder dependency), then a token-overlap test
    rather than a fragile score threshold: a capsule is a match when it shares
    at least `HARVEST_SUPPRESS_OVERLAP` of the candidate's distinctive tokens.
    Never drops entries — the CLI/JSON caller decides how to present known ones.
    """
    ws = str(workspace) if workspace else None
    for candidate in candidates:
        candidate["known"] = False
        candidate["known_id"] = None
        sig = " ".join((candidate.get("signature") or "").split())
        query = (sig or candidate.get("title") or "")[:200]
        distinctive = _distinctive_tokens(sig or candidate.get("title") or "")
        if not query or not distinctive:
            continue
        try:
            hits = kb.search(query, limit=3, workspace=ws, mode="bm25")
        except Exception:
            hits = []
        for hit in hits:
            hit_toks = _tokens(str(hit.get("title") or "") + " " + str(hit.get("body") or ""))
            overlap = sum(1 for t in distinctive if t in hit_toks) / len(distinctive)
            if overlap >= HARVEST_SUPPRESS_OVERLAP:
                candidate["known"] = True
                candidate["known_id"] = str(hit.get("id") or "")
                break
    return candidates


def _remember_line(candidate: dict, workspace: Path | None) -> str:
    args = [
        ",ai-kb",
        "remember",
        "--title",
        shlex.quote(candidate["title"]),
        "--kind",
        candidate["kind"],
        "--scope",
        "workspace",
    ]
    if workspace:
        args += ["--workspace", shlex.quote(str(workspace))]
    args += [
        "--source",
        shlex.quote(f"worklog:{candidate['detector']}"),
        "--confidence",
        "0.5",
        "--body",
        shlex.quote(candidate["body"]),
    ]
    return " ".join(args)


def print_capsule(capsule: Capsule, as_json: bool) -> None:
    if as_json:
        print(json.dumps(asdict(capsule), indent=2))
        return
    print(f"{capsule.id}\t{capsule.kind}/{capsule.scope}\t{capsule.title}\t{capsule.source}\t{capsule.path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local agent knowledgebase")
    parser.add_argument("--home", type=Path, help="Override AI_KB_HOME")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    remember = sub.add_parser("remember")
    remember.add_argument("--title", required=True)
    remember.add_argument("--body", required=True)
    remember.add_argument("--kind", default="fact", choices=CAPSULE_KINDS)
    remember.add_argument("--scope", default="universal", choices=CAPSULE_SCOPES)
    remember.add_argument("--source", default="manual")
    remember.add_argument("--tags", default="")
    remember.add_argument("--workspace", default=None, dest="workspace_path")
    remember.add_argument("--project", default=None, dest="project_id")
    remember.add_argument(
        "--domain",
        default=None,
        action="append",
        dest="domain_tags",
        help="Domain tag (repeat for multiple)",
    )
    remember.add_argument("--confidence", type=float, default=0.5)
    remember.add_argument("--verified-by", default=None)
    remember.add_argument(
        "--supersedes",
        default=None,
        help="ID of an existing capsule this one replaces (links both directions)",
    )
    remember.add_argument(
        "--refs",
        default=None,
        action="append",
        help="Related capsule ID or external reference (repeat for multiple)",
    )
    remember.add_argument("--no-embed", action="store_true")
    remember.add_argument(
        "--force",
        action="store_true",
        help="Store even when an existing capsule collides on title or near-duplicate embedding",
    )
    remember.add_argument("--json", action="store_true")

    search = sub.add_parser("search")
    search.add_argument("query", nargs="?")
    search.add_argument(
        "--query-stdin",
        action="store_true",
        help="Read the query from stdin so automatic callers do not expose it in process argv",
    )
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--scope", default=None, action="append")
    search.add_argument("--kind", default=None, action="append")
    search.add_argument("--workspace", default=None)
    search.add_argument(
        "--workspace-gate",
        action="store_true",
        help="Hard-filter to capsules local to --workspace or scoped domain/universal (requires --workspace)",
    )
    search.add_argument("--domain", default=None, action="append")
    search.add_argument("--mode", default="hybrid", choices=("hybrid", "bm25", "vector"))
    search.add_argument("--json", action="store_true")

    get = sub.add_parser("get")
    get.add_argument("id")
    get.add_argument("--json", action="store_true")

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--limit", type=int, default=50)
    list_cmd.add_argument("--json", action="store_true")

    reembed = sub.add_parser("reembed")
    reembed.add_argument("--limit", type=int, default=None)

    curate = sub.add_parser("curate", help="One-shot KB curation pass: dedupe, decay, contradiction-scan")
    curate.add_argument("--no-dedupe", action="store_true")
    curate.add_argument("--no-decay", action="store_true")
    curate.add_argument("--no-contradictions", action="store_true")
    curate.add_argument("--dedupe-threshold", type=float, default=0.95)
    curate.add_argument("--contradiction-threshold", type=float, default=0.85)
    curate.add_argument("--decay-step", type=float, default=0.1)
    curate.add_argument("--json", action="store_true")

    ingest = sub.add_parser("ingest", help="Ingest a markdown file or directory of .md files")
    ingest.add_argument("target", type=Path)
    ingest.add_argument("--scope", default="universal", choices=CAPSULE_SCOPES)
    ingest.add_argument("--workspace", default=None)
    ingest.add_argument(
        "--domain",
        default=None,
        action="append",
        dest="domain_tags",
        help="Domain tag (repeat for multiple); inferred tags are added on top",
    )
    ingest.add_argument("--max-bytes", type=int, default=1_000_000)
    ingest.add_argument("--json", action="store_true")

    harvest = sub.add_parser(
        "harvest",
        help="Surface durable-memory candidates from a topic worklog (read-only; never writes capsules)",
    )
    harvest.add_argument("--workspace", default=None, help="Workspace path (default: cwd)")
    harvest.add_argument("--topic", default=None, help="Explicit topic name (overrides --session-id)")
    harvest.add_argument("--session-id", default=None, help="Resolve the invoking session's bound topic")
    harvest.add_argument(
        "--worklog",
        default=None,
        help="Explicit worklog path (overrides --workspace/--topic/--session-id)",
    )
    harvest.add_argument("--min-repeats", type=int, default=2, dest="min_repeats")
    harvest.add_argument("--limit", type=int, default=20)
    harvest.add_argument("--json", action="store_true")

    sub.add_parser("doctor")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    kb = KnowledgeBase(args.home)

    if args.cmd == "init":
        kb.init()
        print(kb.home)
        return 0
    if args.cmd == "remember":
        if args.supersedes is not None and kb.get(args.supersedes) is None:
            print(f"error: --supersedes target {args.supersedes!r} not found", file=sys.stderr)
            return 1
        if not 0.0 <= args.confidence <= 1.0:
            print(
                f"warning: confidence {args.confidence} is outside [0, 1] and will be clamped",
                file=sys.stderr,
            )
        degraded = [
            label
            for label, missing in (
                ("--source left at the 'manual' default", args.source == "manual"),
                ("no --domain tag", not args.domain_tags),
            )
            if missing
        ]
        if degraded:
            print(f"warning: degraded capsule metadata: {'; '.join(degraded)}", file=sys.stderr)
        try:
            capsule = kb.remember(
                args.title,
                args.body,
                kind=args.kind,
                scope=args.scope,
                source=args.source,
                tags=args.tags,
                workspace_path=args.workspace_path,
                project_id=args.project_id,
                domain_tags=args.domain_tags or [],
                confidence=args.confidence,
                verified_by=args.verified_by,
                supersedes=args.supersedes,
                refs=args.refs or [],
                embed_now=not args.no_embed,
                force=args.force,
            )
        except ValueError as err:
            print(f"error: {err}", file=sys.stderr)
            return 1
        print_capsule(capsule, args.json)
        return 0
    if args.cmd == "search":
        if args.query_stdin and args.query is not None:
            parser.error("search accepts either a positional query or --query-stdin, not both")
        if args.query_stdin:
            query = sys.stdin.read(4097)
            if len(query) > 4096:
                parser.error("stdin search query exceeds 4096 characters")
            query = query.strip()
        else:
            query = args.query or ""
        if not query:
            parser.error("search requires a positional query or --query-stdin")
        if args.workspace_gate and not args.workspace:
            parser.error("--workspace-gate requires --workspace")
        rows = kb.search(
            query,
            args.limit,
            scope=args.scope,
            kind=args.kind,
            workspace=args.workspace,
            domain=args.domain,
            mode=args.mode,
            workspace_gate=args.workspace_gate,
        )
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for row in rows:
                print(
                    f"{row['id']}\t{row['kind']}/{row['scope']}\t"
                    f"{row['title']}\trrf={row['rrf_score']:.4f}\t{row['snippet']}"
                )
        return 0
    if args.cmd == "get":
        capsule = kb.get(args.id)
        if not capsule:
            print(f"not found: {args.id}", file=sys.stderr)
            return 1
        print_capsule(capsule, args.json)
        return 0
    if args.cmd == "list":
        capsules = kb.list(args.limit)
        if args.json:
            print(json.dumps([asdict(c) for c in capsules], indent=2))
        else:
            for c in capsules:
                print_capsule(c, False)
        return 0
    if args.cmd == "reembed":
        n = kb.reembed(limit=args.limit)
        print(f"reembedded {n} capsule(s)")
        return 0
    if args.cmd == "curate":
        summary = kb.curate(
            dedupe=not args.no_dedupe,
            decay=not args.no_decay,
            contradiction_scan=not args.no_contradictions,
            dedupe_cosine_threshold=args.dedupe_threshold,
            contradiction_cosine_threshold=args.contradiction_threshold,
            decay_step=args.decay_step,
        )
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(
                f"duplicates_marked={summary.get('duplicates', 0)} "
                f"decayed={summary.get('decayed', 0)} "
                f"contradictions={len(summary.get('contradictions', []))} "
                f"candidates_examined={summary.get('candidates_examined', 0)}"
            )
            for c in summary.get("contradictions", []):
                print(f"  ! pair {c['a_id']} ({c['a_kind']}) <-> {c['b_id']} ({c['b_kind']}) cosine={c['cosine']}")
        return 0
    if args.cmd == "ingest":
        summary = kb.ingest_path(
            args.target,
            scope=args.scope,
            workspace_path=args.workspace,
            domain_tags=args.domain_tags,
            max_bytes=args.max_bytes,
        )
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(
                f"files_seen={summary['files_seen']} "
                f"files_ingested={summary['files_ingested']} "
                f"files_skipped_unchanged={summary['files_skipped_unchanged']} "
                f"capsules_stored={summary['capsules_stored']}"
            )
        return 0
    if args.cmd == "harvest":
        workspace = Path(args.workspace or Path.cwd()).expanduser().resolve()
        import worklog_queue

        if args.worklog:
            worklog = Path(args.worklog).expanduser()
            suffix = ".worklog.jsonl"
            topic = worklog.name[: -len(suffix)] if worklog.name.endswith(suffix) else worklog.name
        else:
            topic = resolve_topic(workspace, args.topic, args.session_id)
            worklog = worklog_path(workspace, topic)
        try:
            flush_result = worklog_queue.flush_spec_dir(worklog.parent)
        except (OSError, ValueError, worklog_queue.QueueError) as err:
            print(f"harvest worklog flush failed: {err}", file=sys.stderr)
            return 2
        if flush_result.errors or flush_result.pending:
            print(
                f"harvest worklog flush incomplete: pending={flush_result.pending} errors={flush_result.errors}",
                file=sys.stderr,
            )
            return 2
        entries = read_worklog(worklog)
        candidates = detect_candidates(entries, min_repeats=args.min_repeats)
        suppress_known(kb, candidates, workspace)
        shown = [c for c in candidates if not c["known"]][: args.limit]
        suppressed = sum(1 for c in candidates if c["known"])
        if args.json:
            print(
                json.dumps(
                    {
                        "workspace": str(workspace),
                        "session_id": None if args.worklog else args.session_id,
                        "topic": topic,
                        "worklog": str(worklog),
                        "worklog_exists": worklog.exists(),
                        "entries": len(entries),
                        "suppressed_known": suppressed,
                        "candidates": candidates,
                    },
                    indent=2,
                )
            )
            return 0
        if not worklog.exists():
            print(f"no worklog at {worklog}", file=sys.stderr)
            return 0
        suffix = f", {suppressed} already in KB" if suppressed else ""
        if not shown:
            print(f"harvest: {len(entries)} worklog entries, no new durable candidates{suffix}")
            return 0
        print(f"harvest: {len(shown)} candidate(s) from {len(entries)} worklog entries (topic {topic}){suffix}")
        for candidate in shown:
            print()
            print(f"[{candidate['detector']}] {candidate['title']}  (x{candidate['count']}, kind={candidate['kind']})")
            for ev in candidate["evidence"]:
                bits = [ev.get("ts") or ""]
                if ev.get("command"):
                    bits.append(f"$ {ev['command']}")
                if ev.get("error"):
                    bits.append(f"! {ev['error']}")
                line = "  ".join(b for b in bits if b)
                if line:
                    print(f"  {line}")
            print("  verify, then:")
            print(f"    {_remember_line(candidate, workspace)}")
        return 0
    if args.cmd == "doctor":
        for check in kb.doctor():
            print(check)
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
