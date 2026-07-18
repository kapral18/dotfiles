#!/usr/bin/env python3
"""Tests for ai_kb.py knowledge-base behavior."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import SCRIPTS


class TestAiKb(unittest.TestCase):
    """WHEN remembering and searching durable agent knowledge."""

    def test_remember_search_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "--home",
                    tmp,
                    "remember",
                    "--title",
                    "Agent memory",
                    "--body",
                    "The KB stores durable learnings across sessions.",
                    "--source",
                    "test",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
            )
            assert result.returncode == 0, result.stderr
            capsule = json.loads(result.stdout)
            assert capsule["title"] == "Agent memory"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "--home",
                    tmp,
                    "search",
                    "durable learnings",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
            )
            assert result.returncode == 0, result.stderr
            rows = json.loads(result.stdout)
            assert rows[0]["id"] == capsule["id"]


class TestKnowledgeBaseSchemaV2(unittest.TestCase):
    """Phase 1 of the BIG redesign: structured capsule schema with kind,
    scope, domain tags, confidence, verified_by, supersedes, embedding
    BLOB and the rest. Schema changes are breaking by policy — old
    DBs are rebuilt from canonical sidecars, not migrated in place.
    """

    @staticmethod
    def _fake_embedder():
        class FakeEmbedder:
            model = "test/fake-embedder"

            @staticmethod
            def embed_one(text: str) -> list[float]:
                seed = sum((idx + 1) * ord(ch) for idx, ch in enumerate(text))
                return [
                    ((seed % 97) + 1) / 100.0,
                    (((seed // 97) % 97) + 1) / 100.0,
                    (((seed // (97 * 97)) % 97) + 1) / 100.0,
                ]

            def embed(self, texts: list[str]) -> list[list[float]]:
                return [self.embed_one(text) for text in texts]

        return FakeEmbedder()

    def _seed_curated_state(self, kb):
        old = kb.remember(
            title="Canonical old fact",
            body="shared-needle canonical-old",
            source="tests:old",
            project_id="proj-curation",
        )
        keeper = kb.remember(
            title="Canonical keeper fact",
            body="shared-needle canonical-keeper",
            source="tests:keeper",
            project_id="proj-curation",
            supersedes=old.id,
        )
        loser = kb.remember(
            title="Curated loser fact",
            body="shared-needle curated-loser",
            source="tests:loser",
            project_id="proj-curation",
        )
        kb._mark_superseded(loser.id, keeper.id)
        with kb.connect() as db:
            db.execute(
                "UPDATE capsules SET decay_score = ?, updated_at = ? WHERE id = ?",
                (0.6, "2026-07-10T12:34:56+00:00", keeper.id),
            )
        return old, keeper, loser

    def _capsule_state(self, kb, *ids: str) -> dict[str, dict]:
        placeholders = ",".join("?" * len(ids))
        with kb.connect() as db:
            rows = db.execute(
                f"""
                SELECT id, supersedes, superseded_by, decay_score,
                       retrieved_at, retrieval_count,
                       created_at, updated_at,
                       hex(embedding) AS embedding_hex,
                       embedding_model, embedding_dim
                FROM capsules
                WHERE id IN ({placeholders})
                ORDER BY id
                """,
                ids,
            ).fetchall()
        return {
            row["id"]: {
                "supersedes": row["supersedes"],
                "superseded_by": row["superseded_by"],
                "decay_score": row["decay_score"],
                "retrieved_at": row["retrieved_at"],
                "retrieval_count": row["retrieval_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "embedding_hex": row["embedding_hex"],
                "embedding_model": row["embedding_model"],
                "embedding_dim": row["embedding_dim"],
            }
            for row in rows
        }

    def _force_capsules_schema_mismatch(self, kb):
        with kb.connect() as db:
            db.execute("DROP TABLE IF EXISTS capsule_fts")
            db.execute("DROP TABLE IF EXISTS kb_meta")
            db.execute("ALTER TABLE capsules RENAME TO capsules_backup")
            db.execute(
                """
                CREATE TABLE capsules (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    path TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    workspace_path TEXT,
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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                INSERT INTO capsules(
                    id, kind, title, body, source, tags, path, scope,
                    workspace_path, domain_tags, confidence, verified_by,
                    supersedes, superseded_by, refs, embedding,
                    embedding_model, embedding_dim, decay_score,
                    created_at, updated_at
                )
                SELECT
                    id, kind, title, body, source, tags, path, scope,
                    workspace_path, domain_tags, confidence, verified_by,
                    supersedes, superseded_by, refs, embedding,
                    embedding_model, embedding_dim, decay_score,
                    created_at, updated_at
                FROM capsules_backup
                """
            )
            db.execute("DROP TABLE capsules_backup")

    def test_init_creates_full_schema(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            kb.init()
            with kb.connect() as db:
                cols = [r[1] for r in db.execute("PRAGMA table_info(capsules)").fetchall()]
            assert tuple(cols) == ai_kb.CAPSULE_COLUMNS, (
                f"schema mismatch:\n got: {cols}\nwant: {list(ai_kb.CAPSULE_COLUMNS)}"
            )

    def test_init_drops_stale_table_when_columns_dont_match(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            # Fake a stale schema: minimal old shape with fewer columns.
            with kb.connect() as db:
                db.execute(
                    """
                    CREATE TABLE capsules (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        body TEXT
                    )
                    """
                )
                db.execute("INSERT INTO capsules(id,title,body) VALUES('x','t','b')")
            # Now init should detect the stale shape and rebuild. With no
            # sidecars present, the rebuilt mirror is empty.
            kb.init()
            with kb.connect() as db:
                cols = [r[1] for r in db.execute("PRAGMA table_info(capsules)").fetchall()]
                count = db.execute("SELECT COUNT(*) FROM capsules").fetchone()[0]
            assert tuple(cols) == ai_kb.CAPSULE_COLUMNS
            assert count == 0, "stale rows must be dropped — no compat path"

    def test_read_paths_rebuild_stale_schema_from_sidecars_without_losing_metadata(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved_disable = os.environ.get("AI_KB_DISABLE_EMBED")
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                old = kb.remember(
                    title="Old rebuild fact",
                    body="Old body survives the mirror rebuild.",
                    kind="gotcha",
                    scope="project",
                    source="tests:old",
                    tags="ops,rebuild",
                    workspace_path="/ws/rebuild",
                    project_id="proj-rebuild",
                    domain_tags=["ai-kb", "rebuild"],
                    confidence=0.9,
                    verified_by="rid-123",
                    refs=["docs/rebuild.md:10", "https://example.test/rebuild"],
                    embed_now=False,
                )
                new = kb.remember(
                    title="New rebuild fact",
                    body="schema-heal-needle proves search still works after stale schema repair.",
                    kind="pattern",
                    scope="project",
                    source="tests:new",
                    tags="ops,rebuild",
                    workspace_path="/ws/rebuild",
                    project_id="proj-rebuild",
                    domain_tags=["ai-kb", "rebuild"],
                    confidence=0.8,
                    verified_by="rid-456",
                    supersedes=old.id,
                    refs=["docs/rebuild.md:42"],
                    embed_now=False,
                )
                with kb.connect() as db:
                    db.execute("DROP TABLE IF EXISTS capsule_fts")
                    db.execute("DROP TABLE IF EXISTS kb_meta")
                    db.execute("DROP TABLE IF EXISTS capsules")
                    db.execute(
                        """
                        CREATE TABLE capsules (
                            id TEXT PRIMARY KEY,
                            title TEXT,
                            body TEXT
                        )
                        """
                    )
                    db.execute("INSERT INTO capsules(id,title,body) VALUES('bogus','bogus','bogus')")

                listed = kb.list(limit=10)
                assert sorted(c.id for c in listed) == sorted([old.id, new.id]), listed
                rebuilt_old = kb.get(old.id)
                rebuilt_new = kb.get(new.id)
                assert rebuilt_old is not None
                assert rebuilt_new is not None
                assert rebuilt_old.source == "tests:old"
                assert rebuilt_old.tags == "ops,rebuild"
                assert rebuilt_old.scope == "project"
                assert rebuilt_old.workspace_path == "/ws/rebuild"
                assert rebuilt_old.project_id == "proj-rebuild"
                assert rebuilt_old.domain_tags == "ai-kb,rebuild"
                assert rebuilt_old.confidence == 0.9
                assert rebuilt_old.verified_by == "rid-123"
                assert rebuilt_old.refs == "docs/rebuild.md:10,https://example.test/rebuild"
                assert rebuilt_old.superseded_by == new.id
                assert rebuilt_new.supersedes == old.id

                hits = kb.search("schema-heal-needle", limit=5, mode="bm25")
                assert [hit["id"] for hit in hits] == [new.id], hits
                assert hits[0]["body"] == new.body

                doctor = kb.doctor()
                assert "capsules=2" in doctor, doctor
                with kb.connect() as db:
                    cols = [r[1] for r in db.execute("PRAGMA table_info(capsules)").fetchall()]
                assert tuple(cols) == ai_kb.CAPSULE_COLUMNS
            finally:
                if saved_disable is None:
                    os.environ.pop("AI_KB_DISABLE_EMBED", None)
                else:
                    os.environ["AI_KB_DISABLE_EMBED"] = saved_disable

    def test_stale_schema_rebuild_preserves_curated_sqlite_only_state(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved_disable = os.environ.get("AI_KB_DISABLE_EMBED")
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp), embedder=self._fake_embedder())
                old, keeper, loser = self._seed_curated_state(kb)
                state_before = self._capsule_state(kb, old.id, keeper.id, loser.id)
                assert state_before[keeper.id]["supersedes"] == old.id
                assert state_before[loser.id]["superseded_by"] == keeper.id
                assert abs(state_before[keeper.id]["decay_score"] - 0.6) < 1e-6
                assert state_before[keeper.id]["updated_at"] == "2026-07-10T12:34:56+00:00"
                assert state_before[keeper.id]["embedding_model"] == "test/fake-embedder"
                assert state_before[keeper.id]["embedding_dim"] == 3
                hits_before = kb.search("shared-needle", limit=10, mode="bm25")
                assert loser.id not in [hit["id"] for hit in hits_before], hits_before

                # The search stamps retrieval on the returned capsules and
                # clears their decay. The simulated stale schema predates the
                # retrieval columns, so the rebuild preserves the cleared
                # decay but cannot recover retrieval state (a real v2->v3
                # migration starts every capsule as never-retrieved).
                expected = {cid: dict(state) for cid, state in state_before.items()}
                for hit in hits_before:
                    hid = hit["id"]
                    if hid in expected:
                        expected[hid]["decay_score"] = 0.0
                retrieved_state = self._capsule_state(kb, old.id, keeper.id, loser.id)
                for hit in hits_before:
                    if hit["id"] in retrieved_state:
                        assert retrieved_state[hit["id"]]["retrieved_at"] is not None

                self._force_capsules_schema_mismatch(kb)

                rebuilt = kb.list(limit=10)
                assert sorted(c.id for c in rebuilt) == sorted([old.id, keeper.id, loser.id]), rebuilt
                state_after = self._capsule_state(kb, old.id, keeper.id, loser.id)
                assert state_after == expected, (expected, state_after)

                hits_after = kb.search("shared-needle", limit=10, mode="bm25")
                hit_ids = [hit["id"] for hit in hits_after]
                assert keeper.id in hit_ids, hit_ids
                assert loser.id not in hit_ids, hit_ids
            finally:
                if saved_disable is None:
                    os.environ.pop("AI_KB_DISABLE_EMBED", None)
                else:
                    os.environ["AI_KB_DISABLE_EMBED"] = saved_disable

    def test_stale_schema_rebuild_fails_closed_on_malformed_sidecar(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved_disable = os.environ.get("AI_KB_DISABLE_EMBED")
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                good = kb.remember(
                    title="Good sidecar",
                    body="This sidecar remains intact when another sidecar is malformed.",
                    source="tests:good",
                    embed_now=False,
                )
                (kb.capsules_dir / "broken.md").write_text(
                    "---\n"
                    "id: broken\n"
                    "kind: fact\n"
                    "scope: project\n"
                    "source: tests:broken\n"
                    "confidence: 0.5\n"
                    "created_at: 2026-07-10T00:00:00+00:00\n"
                    "---\n\n"
                    "# broken\n\n"
                    "missing title frontmatter should fail closed\n"
                )
                with kb.connect() as db:
                    db.execute("DROP TABLE IF EXISTS capsule_fts")
                    db.execute("DROP TABLE IF EXISTS kb_meta")
                    db.execute("DROP TABLE IF EXISTS capsules")
                    db.execute(
                        """
                        CREATE TABLE capsules (
                            id TEXT PRIMARY KEY,
                            title TEXT,
                            body TEXT
                        )
                        """
                    )
                    db.execute("INSERT INTO capsules(id,title,body) VALUES('bogus','bogus','bogus')")

                with self.assertRaisesRegex(ValueError, "broken.md"):
                    kb.list(limit=10)

                with kb.connect() as db:
                    cols = [r[1] for r in db.execute("PRAGMA table_info(capsules)").fetchall()]
                    count = db.execute("SELECT COUNT(*) FROM capsules").fetchone()[0]
                assert cols == ["id", "title", "body"], cols
                assert count == 1, count
                assert (kb.capsules_dir / f"{good.id}.md").exists()
            finally:
                if saved_disable is None:
                    os.environ.pop("AI_KB_DISABLE_EMBED", None)
                else:
                    os.environ["AI_KB_DISABLE_EMBED"] = saved_disable

    def test_aux_table_repair_preserves_current_capsules_table_and_state(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved_disable = os.environ.get("AI_KB_DISABLE_EMBED")
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp), embedder=self._fake_embedder())
                old, keeper, loser = self._seed_curated_state(kb)
                state_before = self._capsule_state(kb, old.id, keeper.id, loser.id)
                with kb.connect() as db:
                    rootpage_before = db.execute(
                        "SELECT rootpage FROM sqlite_master WHERE type = 'table' AND name = 'capsules'"
                    ).fetchone()[0]
                    db.execute("DROP TABLE IF EXISTS capsule_fts")
                    db.execute("DROP TABLE IF EXISTS kb_meta")

                hits = kb.search("shared-needle", limit=10, mode="bm25")
                hit_ids = [hit["id"] for hit in hits]
                assert keeper.id in hit_ids, hit_ids
                assert loser.id not in hit_ids, hit_ids

                with kb.connect() as db:
                    rootpage_after = db.execute(
                        "SELECT rootpage FROM sqlite_master WHERE type = 'table' AND name = 'capsules'"
                    ).fetchone()[0]
                    fts_count = db.execute("SELECT COUNT(*) FROM capsule_fts").fetchone()[0]
                state_after = self._capsule_state(kb, old.id, keeper.id, loser.id)
                assert rootpage_after == rootpage_before, (rootpage_before, rootpage_after)
                assert fts_count == 3, fts_count
                # Aux repair must not touch capsule rows beyond the search's
                # own retrieval stamp (decay cleared, retrieval counted).
                expected = {cid: dict(state) for cid, state in state_before.items()}
                for hid in hit_ids:
                    if hid in expected:
                        expected[hid]["decay_score"] = 0.0
                        expected[hid]["retrieval_count"] = state_before[hid]["retrieval_count"] + 1
                        assert state_after[hid]["retrieved_at"] is not None
                        expected[hid]["retrieved_at"] = state_after[hid]["retrieved_at"]
                assert state_after == expected, (expected, state_after)
            finally:
                if saved_disable is None:
                    os.environ.pop("AI_KB_DISABLE_EMBED", None)
                else:
                    os.environ["AI_KB_DISABLE_EMBED"] = saved_disable

    def test_schema_state_detects_same_count_fts_content_drift(self):
        """A corrupted capsule_fts row (same id, same row count, wrong text)
        must be classified derived_stale, not 'ok'. A count-only comparison
        trusts this mirror because both tables still have one row each; the
        fix compares mirrored column content, not just row counts."""
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            cap = kb.remember(
                title="Canonical title",
                body="Canonical body text",
                source="tests:drift",
                tags="a,b",
                domain_tags=["d1"],
                embed_now=False,
            )
            with kb.connect() as db:
                db.execute(
                    "UPDATE capsule_fts SET title=?, body=? WHERE id=?",
                    ("WRONG TITLE", "WRONG BODY", cap.id),
                )
            with kb.connect() as db:
                assert kb._schema_state(db) == "derived_stale"

            good_hits = kb.search("Canonical", limit=5, mode="bm25")
            assert [h["id"] for h in good_hits] == [cap.id], good_hits
            assert good_hits[0]["body"] == "Canonical body text", good_hits

            bad_hits = kb.search("WRONG", limit=5, mode="bm25")
            assert bad_hits == [], bad_hits

            with kb.connect() as db:
                assert kb._schema_state(db) == "ok"

    def test_schema_state_detects_fts_id_mismatch_same_count(self):
        """A capsule_fts row whose id no longer matches any capsules row
        (but the row counts are still equal) must also be derived_stale."""
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            cap = kb.remember(
                title="Only capsule",
                body="Only capsule body",
                source="tests:idmismatch",
                embed_now=False,
            )
            with kb.connect() as db:
                db.execute(
                    "UPDATE capsule_fts SET id=? WHERE id=?",
                    ("bogus-id-not-a-real-capsule", cap.id),
                )
            with kb.connect() as db:
                assert kb._schema_state(db) == "derived_stale"

            hits = kb.search("Only capsule", limit=5, mode="bm25")
            assert [h["id"] for h in hits] == [cap.id], hits

            with kb.connect() as db:
                assert kb._schema_state(db) == "ok"

    def test_schema_state_detects_duplicate_fts_row(self):
        """An extra capsule_fts row that duplicates an existing capsule's
        content (fts_count > capsule_count, but every distinct row still
        matches) must be classified derived_stale. A symmetric set
        difference alone misses this because EXCEPT dedupes the duplicate;
        the count comparison catches it so the double-counted BM25 hit is
        repaired."""
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            cap = kb.remember(
                title="Dup capsule",
                body="Dup capsule body",
                source="tests:dup",
                tags="a",
                embed_now=False,
            )
            with kb.connect() as db:
                db.execute(
                    """
                    INSERT INTO capsule_fts(id, title, body, tags, source, domain_tags)
                    SELECT id, title, body, tags, source, domain_tags FROM capsule_fts
                    """
                )
                fts_count = db.execute("SELECT COUNT(*) FROM capsule_fts").fetchone()[0]
                cap_count = db.execute("SELECT COUNT(*) FROM capsules").fetchone()[0]
                assert fts_count == 2 and cap_count == 1, (fts_count, cap_count)
            with kb.connect() as db:
                assert kb._schema_state(db) == "derived_stale"

            hits = kb.search("Dup capsule", limit=5, mode="bm25")
            assert [h["id"] for h in hits] == [cap.id], hits

            with kb.connect() as db:
                assert kb._schema_state(db) == "ok"
                assert db.execute("SELECT COUNT(*) FROM capsule_fts").fetchone()[0] == 1

    def test_remember_persists_full_metadata(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                c = kb.remember(
                    title="kb test",
                    body="full payload",
                    kind="gotcha",
                    scope="project",
                    workspace_path="/ws",
                    project_id="proj-1",
                    domain_tags=["python", "memory"],
                    confidence=0.8,
                    verified_by="go-rid-1",
                )
                assert c.kind == "gotcha"
                assert c.scope == "project"
                assert c.workspace_path == "/ws"
                assert c.project_id == "proj-1"
                assert c.domain_tags == "python,memory"
                assert c.confidence == 0.8
                assert c.verified_by == "go-rid-1"
                # No embedder under disable flag → embedding fields blank.
                assert c.embedding_dim == 0
                assert c.embedding_model is None
                # Round-trip via get().
                got = kb.get(c.id)
                assert got is not None
                assert got.kind == "gotcha"
                assert got.domain_tags == "python,memory"
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)

    def test_remember_rejects_unknown_kind_or_scope(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                try:
                    kb.remember("t", "b", kind="bogus")
                except ValueError as err:
                    assert "kind" in str(err)
                else:
                    raise AssertionError("expected ValueError for unknown kind")
                try:
                    kb.remember("t", "b", scope="bogus")
                except ValueError as err:
                    assert "scope" in str(err)
                else:
                    raise AssertionError("expected ValueError for unknown scope")
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)

    def test_supersedes_links_bidirectionally(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                old = kb.remember(title="v1", body="old fact")
                new = kb.remember(title="v2", body="new fact", supersedes=old.id)
                refreshed_old = kb.get(old.id)
                assert refreshed_old is not None
                assert refreshed_old.superseded_by == new.id, (
                    f"superseded_by must be set bidirectionally: got {refreshed_old.superseded_by!r}"
                )
                assert new.supersedes == old.id
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)


class TestKnowledgeBaseEmbeddingRoundtrip(unittest.TestCase):
    """End-to-end embedding test: actually shells out to the fastembed
    runner. Slow (~1s cold start) — only runs when the runner is
    available; otherwise skipped so CI without `uv` doesn't fail.
    """

    def setUp(self):
        import embed

        e = embed.Embedder()
        if not e.is_available():
            self.skipTest("fastembed runner not available (uv missing or runner script missing)")
        self.embedder = e

    def test_remember_stores_embedding_when_runner_available(self):
        import ai_kb
        from embed import cosine, unpack_vector

        with tempfile.TemporaryDirectory() as tmp:
            # Ensure the disable flag is OFF for this test.
            saved = os.environ.pop("AI_KB_DISABLE_EMBED", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                c = kb.remember(
                    title="Legion manifest layout",
                    body="Legion state under legions/*/manifest.json with kind values.",
                )
                assert c.embedding_dim == 384, c.embedding_dim
                assert c.embedding_model == "BAAI/bge-small-en-v1.5"
                # Verify the stored embedding round-trips and self-cosine == 1.
                with kb.connect() as db:
                    row = db.execute("SELECT embedding FROM capsules WHERE id = ?", (c.id,)).fetchone()
                vec = unpack_vector(row["embedding"])
                assert len(vec) == 384
                assert abs(cosine(vec, vec) - 1.0) < 1e-5
            finally:
                if saved is not None:
                    os.environ["AI_KB_DISABLE_EMBED"] = saved


class TestKnowledgeBaseHybridRetrieval(unittest.TestCase):
    """Phase 2: hybrid (BM25 + cosine + RRF + MMR) retrieval with
    structured filters. The canonical regression is the
    "semantic-without-lexical-overlap" case — a query whose tokens do
    not appear in the capsule body but whose meaning is similar must
    surface the capsule via the vector lane.
    """

    def setUp(self):
        import embed

        if not embed.Embedder().is_available():
            self.skipTest("fastembed runner not available")
        # Embedding tests need the embedder ON.
        self.saved_disable = os.environ.pop("AI_KB_DISABLE_EMBED", None)

    def tearDown(self):
        if self.saved_disable is not None:
            os.environ["AI_KB_DISABLE_EMBED"] = self.saved_disable

    def test_vector_mode_finds_semantic_match_without_keyword_overlap(self):
        """Capsule says 'feline' / query asks 'cat'. BM25 misses, vector hits."""
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            kb.remember(
                title="Animal taxonomy",
                body="The domestic feline is a small carnivorous mammal.",
                kind="fact",
                scope="universal",
            )
            # BM25-only query that has no token overlap with the body.
            bm25 = kb.search("cat pet", limit=3, mode="bm25")
            assert bm25 == [], (
                f"BM25-only must miss across token boundaries; got {len(bm25)} hit(s):\n{[h['title'] for h in bm25]}"
            )
            # Vector mode bridges the lexical gap.
            vec = kb.search("cat pet", limit=3, mode="vector")
            assert len(vec) == 1, f"vector lane must surface the semantically-related capsule; got {vec}"
            assert vec[0]["title"] == "Animal taxonomy"
            assert vec[0]["cosine_score"] is not None

    def test_hybrid_mode_combines_lanes_via_rrf(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            # cap_a: high BM25 (exact token), low semantic relevance
            kb.remember(
                title="Manifest format",
                body="A manifest file describes packaging metadata.",
                kind="fact",
            )
            # cap_b: high semantic relevance to an orchestrator-flavored query,
            # but no shared tokens with the query.
            kb.remember(
                title="Run state on disk",
                body="Each legion stores its progress under its own directory.",
                kind="fact",
            )

            hits = kb.search("legion manifest layout", limit=3, mode="hybrid")
            assert len(hits) == 2
            ids = [h["id"] for h in hits]
            # Both capsules must appear in the fused result.
            assert any("Manifest format" == h["title"] for h in hits), hits
            assert any("Run state on disk" == h["title"] for h in hits), hits
            # Each hit should have a non-zero RRF score.
            for h in hits:
                assert h["rrf_score"] > 0.0, h

    def test_filters_scope_kind_and_domain_pre_rank(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            kb.remember(
                title="Workspace gotcha",
                body="trailing slash matters in workspace paths.",
                kind="gotcha",
                scope="workspace",
                workspace_path="/ws/a",
                domain_tags=["python", "paths"],
            )
            kb.remember(
                title="Universal principle",
                body="trailing slash matters in workspace paths everywhere.",
                kind="principle",
                scope="universal",
                domain_tags=["python", "paths"],
            )

            # Filter by kind=gotcha → only one hit.
            only_gotchas = kb.search("trailing slash", limit=5, kind="gotcha")
            assert len(only_gotchas) == 1
            assert only_gotchas[0]["kind"] == "gotcha"

            # Filter by scope=universal → only the other.
            universals = kb.search("trailing slash", limit=5, scope="universal")
            assert len(universals) == 1
            assert universals[0]["scope"] == "universal"

            # Domain filter ANDs across calls but ORs across given values
            # (any-tag-match within a single call). Both have python so
            # both should match.
            both = kb.search("trailing slash", limit=5, domain="python")
            assert len(both) == 2

    def test_workspace_path_gives_soft_rrf_boost(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            in_ws = kb.remember(
                title="Workspace-A note",
                body="Specific note about repo layout.",
                kind="fact",
                workspace_path="/ws/a",
            )
            out_ws = kb.remember(
                title="Workspace-B note",
                body="Specific note about repo layout.",
                kind="fact",
                workspace_path="/ws/b",
            )
            hits = kb.search("repo layout", limit=2, workspace="/ws/a")
            assert len(hits) == 2
            # The matching-workspace capsule must rank first courtesy of
            # the +0.1 RRF boost, even when the bodies are identical.
            assert hits[0]["id"] == in_ws.id, [h["title"] for h in hits]
            assert hits[1]["id"] == out_ws.id

    def test_decayed_capsule_sinks_but_still_surfaces(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            fresh = kb.remember(
                title="Fresh note",
                body="Specific note about repo layout.",
                kind="fact",
            )
            stale = kb.remember(
                title="Stale note",
                body="Specific note about repo layout.",
                kind="fact",
            )
            # Drive the stale capsule's decay_score to the cap so the soft
            # penalty is at its strongest.
            with kb.connect() as db:
                db.execute("UPDATE capsules SET decay_score = 1.0 WHERE id = ?", (stale.id,))

            hits = kb.search("repo layout", limit=2)
            ids = [h["id"] for h in hits]
            # Penalized, not filtered: the decayed capsule still surfaces.
            assert set(ids) == {fresh.id, stale.id}, ids
            # But it sinks below the otherwise-identical fresh capsule.
            assert ids[0] == fresh.id, ids
            ranked = {h["id"]: h["rrf_score"] for h in hits}
            assert ranked[fresh.id] > ranked[stale.id], ranked

    def test_hybrid_mode_marks_mmr_selected(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            for i in range(3):
                kb.remember(
                    title=f"capsule {i}",
                    body=f"Lesson number {i} about legion orchestration.",
                    kind="fact",
                    # These near-identical bodies intentionally exercise MMR;
                    # bypass the write-time duplicate probe.
                    force=True,
                )
            hits = kb.search("legion orchestration", limit=2, mode="hybrid")
            assert len(hits) == 2
            for h in hits:
                assert h["mmr_selected"] is True, h


class TestKnowledgeBaseWriteDedupe(unittest.TestCase):
    """Write-time duplicate refusal in remember()."""

    def test_remember_refuses_exact_title_collision_without_force(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                first = kb.remember(title="Postgres locks explained", body="Original body.")
                with self.assertRaisesRegex(ValueError, first.id):
                    kb.remember(title="postgres locks EXPLAINED", body="Different body.")
                forced = kb.remember(title="Postgres locks explained", body="Different body.", force=True)
                assert forced.id != first.id
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)

    def test_remember_refuses_near_duplicate_embedding_without_force(self):
        import embed

        if not embed.Embedder().is_available():
            self.skipTest("fastembed runner not available")

        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("AI_KB_DISABLE_EMBED", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                first = kb.remember(
                    title="JWT must be validated",
                    body="Always validate JWT signature before reading claims.",
                    kind="gotcha",
                )
                with self.assertRaisesRegex(ValueError, first.id):
                    kb.remember(
                        title="Validate JWT signatures",
                        body="Always validate the JWT signature before using any claims.",
                        kind="gotcha",
                    )
                # An explicit supersedes for the colliding capsule is the
                # sanctioned update path and must not be refused.
                replacement = kb.remember(
                    title="Validate JWT signatures",
                    body="Always validate the JWT signature before using any claims.",
                    kind="gotcha",
                    supersedes=first.id,
                )
                assert kb.get(first.id).superseded_by == replacement.id
            finally:
                if saved is not None:
                    os.environ["AI_KB_DISABLE_EMBED"] = saved

    def test_superseded_capsules_do_not_block_new_titles(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                first = kb.remember(title="Old truth", body="v1")
                second = kb.remember(title="New truth", body="v2", supersedes=first.id)
                assert second.supersedes == first.id
                # first is retired; reusing its title is legitimate.
                third = kb.remember(title="Old truth", body="v3")
                assert third.id != first.id
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)


class TestKnowledgeBaseWorkspaceGate(unittest.TestCase):
    """The hard cross-repo leakage gate owned by search()."""

    def _seed(self, kb):
        local = kb.remember(
            title="Local workspace note",
            body="build pipeline quirk",
            scope="project",
            workspace_path="/ws/here",
        )
        foreign = kb.remember(
            title="Foreign workspace note",
            body="build pipeline quirk elsewhere",
            scope="project",
            workspace_path="/ws/other",
            force=True,
        )
        universal = kb.remember(
            title="Universal build note",
            body="build pipeline quirk everywhere",
            scope="universal",
            force=True,
        )
        return local, foreign, universal

    def test_gate_keeps_local_and_cross_project_scopes_only(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                local, foreign, universal = self._seed(kb)
                open_ids = {
                    h["id"] for h in kb.search("build pipeline quirk", limit=10, mode="bm25", workspace="/ws/here")
                }
                assert foreign.id in open_ids, open_ids
                gated = kb.search(
                    "build pipeline quirk",
                    limit=10,
                    mode="bm25",
                    workspace="/ws/here",
                    workspace_gate=True,
                )
                gated_ids = {h["id"] for h in gated}
                assert gated_ids == {local.id, universal.id}, gated_ids
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)

    def test_gate_requires_workspace(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                with self.assertRaisesRegex(ValueError, "workspace_gate"):
                    kb.search("anything", workspace_gate=True)
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)


class TestKnowledgeBaseRetrievalTracking(unittest.TestCase):
    """search() stamps retrieval; curate decay only touches dormant capsules."""

    def test_search_stamps_retrieval_and_clears_decay(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                hit = kb.remember(title="Retrieved note", body="alpha needle body")
                miss = kb.remember(title="Dormant note", body="unrelated content entirely", force=True)
                with kb.connect() as db:
                    db.execute("UPDATE capsules SET decay_score = 0.5")
                rows = kb.search("alpha needle", limit=5, mode="bm25")
                assert [r["id"] for r in rows] == [hit.id], rows
                with kb.connect() as db:
                    got = {
                        r["id"]: r
                        for r in db.execute(
                            "SELECT id, retrieved_at, retrieval_count, decay_score FROM capsules"
                        ).fetchall()
                    }
                assert got[hit.id]["retrieval_count"] == 1
                assert got[hit.id]["retrieved_at"] is not None
                assert got[hit.id]["decay_score"] == 0.0
                assert got[miss.id]["retrieval_count"] == 0
                assert got[miss.id]["retrieved_at"] is None
                assert abs(got[miss.id]["decay_score"] - 0.5) < 1e-6
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)

    def test_curate_decay_shields_recently_retrieved_capsules(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                live = kb.remember(title="Live note", body="alpha needle body")
                dormant = kb.remember(title="Dormant note", body="unrelated content entirely", force=True)
                kb.search("alpha needle", limit=5, mode="bm25")
                summary = kb.curate(decay=True, dedupe=False, contradiction_scan=False, decay_step=0.2)
                assert summary["decayed"] == 1, summary
                with kb.connect() as db:
                    scores = {
                        r["id"]: r["decay_score"] for r in db.execute("SELECT id, decay_score FROM capsules").fetchall()
                    }
                assert scores[live.id] == 0.0, scores
                assert abs(scores[dormant.id] - 0.2) < 1e-6, scores
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)


class TestKnowledgeBaseCurate(unittest.TestCase):
    """Phase 7: curation pass — dedupe, decay, contradiction-scan.

    Dedupe + contradiction tests need embeddings (cosine math); decay
    test runs without an embedder so the fast suite stays fast.
    """

    def test_decay_runs_even_without_embeddings(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AI_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                kb.remember(title="a", body="A body")
                kb.remember(title="b", body="B body")
                # No-embed path: dedupe/contradiction skip (no candidate
                # vectors) but decay still runs because it operates on
                # the SQL row set, not embeddings. This is the contract
                # we want — tools should keep curating even when the
                # embedder is unavailable.
                summary = kb.curate(decay=True, dedupe=True, contradiction_scan=True, decay_step=0.2)
                assert summary["duplicates"] == 0, summary
                assert summary["contradictions"] == [], summary
                assert summary["candidates_examined"] == 0, summary
                assert summary["decayed"] == 2, summary
                # Verify the decay column actually moved on disk.
                with kb.connect() as db:
                    rows = db.execute("SELECT decay_score FROM capsules ORDER BY title").fetchall()
                scores = sorted(r["decay_score"] for r in rows)
                assert all(abs(s - 0.2) < 1e-6 for s in scores), scores

                # Run again: decay accumulates, capped at decay_max.
                kb.curate(decay=True, dedupe=False, contradiction_scan=False, decay_step=0.5)
                with kb.connect() as db:
                    rows = db.execute("SELECT decay_score FROM capsules").fetchall()
                # 0.2 + 0.5 = 0.7
                assert all(abs(r["decay_score"] - 0.7) < 1e-6 for r in rows), [r["decay_score"] for r in rows]
            finally:
                os.environ.pop("AI_KB_DISABLE_EMBED", None)

    def test_dedupe_marks_near_duplicates_as_superseded(self):
        import embed

        if not embed.Embedder().is_available():
            self.skipTest("fastembed runner not available")

        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("AI_KB_DISABLE_EMBED", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                # Two near-duplicates of the same gotcha. Same kind,
                # near-identical content → cosine should clear 0.95.
                older = kb.remember(
                    title="JWT must be validated",
                    body="Always validate JWT signature before reading claims.",
                    kind="gotcha",
                    confidence=0.5,
                )
                # A short delay ensures the newer capsule has a later
                # `created_at` so the deterministic tiebreak prefers it
                # when confidences match.
                time.sleep(0.01)
                newer = kb.remember(
                    title="Validate JWT signatures",
                    body="Always validate the JWT signature before using any claims.",
                    kind="gotcha",
                    confidence=0.7,
                    # The near-duplicate is the fixture under test: curate
                    # dedupe must retire it, so bypass the write-time probe.
                    force=True,
                )
                kb.remember(
                    title="Unrelated note",
                    body="A completely unrelated capsule about monorepos and yarn workspaces.",
                    kind="fact",
                )
                summary = kb.curate(
                    dedupe=True,
                    decay=True,
                    contradiction_scan=False,
                )
                assert summary["duplicates"] >= 1, summary
                # Higher confidence wins → older becomes the loser.
                refreshed_older = kb.get(older.id)
                refreshed_newer = kb.get(newer.id)
                assert refreshed_older is not None and refreshed_newer is not None
                assert refreshed_older.superseded_by == newer.id, (
                    f"older capsule must be marked superseded by newer; got {refreshed_older.superseded_by!r}"
                )
                assert refreshed_newer.supersedes == older.id, (
                    f"newer capsule must point at older via `supersedes`; got {refreshed_newer.supersedes!r}"
                )

                # Search must filter superseded rows out by default.
                hits = kb.search("validate JWT", limit=5, mode="bm25", kind="gotcha")
                ids = [h["id"] for h in hits]
                assert refreshed_newer.id in ids, ids
                assert refreshed_older.id not in ids, "search must hide superseded capsules"
            finally:
                if saved is not None:
                    os.environ["AI_KB_DISABLE_EMBED"] = saved

    def test_contradiction_scan_returns_candidate_pairs(self):
        import embed

        if not embed.Embedder().is_available():
            self.skipTest("fastembed runner not available")

        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("AI_KB_DISABLE_EMBED", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                kb.remember(
                    title="Token expiry fact",
                    body="JWT tokens expire after 60 minutes by default.",
                    kind="fact",
                )
                kb.remember(
                    title="Token expiry gotcha",
                    body="JWT tokens expire after 60 minutes; double-check via the iat claim.",
                    kind="gotcha",
                )
                summary = kb.curate(
                    dedupe=False,
                    decay=False,
                    contradiction_scan=True,
                    contradiction_cosine_threshold=0.7,
                )
                contradictions = summary["contradictions"]
                assert len(contradictions) >= 1, summary
                pair = contradictions[0]
                assert pair["a_kind"] in ("fact", "gotcha")
                assert pair["b_kind"] in ("fact", "gotcha")
                assert pair["a_kind"] != pair["b_kind"]
            finally:
                if saved is not None:
                    os.environ["AI_KB_DISABLE_EMBED"] = saved


class TestKnowledgeBaseVecRunner(unittest.TestCase):
    """Stream 2: vector lane is now driven by `vec_runner.py` over a
    `uv run --script` subprocess loading sqlite-vec. These tests pin
    the orchestrator-side plumbing — `_call_vec_runner` short-circuits
    on the env disable flag, raises loudly when the runner cannot be
    spawned, and forwards the runner's JSON payload unchanged.
    """

    def test_call_vec_runner_short_circuits_when_disabled(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.get("AI_KB_DISABLE_VEC")
            os.environ["AI_KB_DISABLE_VEC"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                knn = kb._call_vec_runner({"mode": "knn", "db_path": str(kb.db_path)})
                pairs = kb._call_vec_runner({"mode": "pairs", "db_path": str(kb.db_path)})
                assert knn == {"hits": []}, knn
                assert pairs == {"pairs": []}, pairs
            finally:
                if saved is None:
                    os.environ.pop("AI_KB_DISABLE_VEC", None)
                else:
                    os.environ["AI_KB_DISABLE_VEC"] = saved

    def test_call_vec_runner_raises_when_runner_missing(self):
        """If the colocated `vec_runner.py` is absent, hard-fail with
        a clear RuntimeError rather than silently degrading."""
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("AI_KB_DISABLE_VEC", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                # Monkey-patch the runner path to a non-existent file.
                original = kb._vec_runner_path
                kb._vec_runner_path = lambda: Path(tmp) / "nope.py"
                try:
                    raised = False
                    try:
                        kb._call_vec_runner({"mode": "knn", "db_path": str(kb.db_path)})
                    except RuntimeError as err:
                        assert "vec_runner missing" in str(err), err
                        raised = True
                    assert raised, "expected RuntimeError when vec_runner.py is absent"
                finally:
                    kb._vec_runner_path = original
            finally:
                if saved is not None:
                    os.environ["AI_KB_DISABLE_VEC"] = saved

    def test_doctor_reports_vec_runner_status(self):
        """`,ai-kb doctor` must surface vec_runner state so operators
        can debug a broken install. Verifies the line is present in
        either the disabled / missing / ok variant — exact wording is
        a contract the doctor command exposes to humans."""
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.get("AI_KB_DISABLE_VEC")
            os.environ["AI_KB_DISABLE_VEC"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                lines = kb.doctor()
                vec_lines = [l for l in lines if l.startswith("vec_runner=")]
                assert len(vec_lines) == 1, lines
                assert "disabled via AI_KB_DISABLE_VEC" in vec_lines[0], vec_lines
            finally:
                if saved is None:
                    os.environ.pop("AI_KB_DISABLE_VEC", None)
                else:
                    os.environ["AI_KB_DISABLE_VEC"] = saved


class TestKnowledgeBaseAsToolCLI(unittest.TestCase):
    """Phase 6: roles invoke the KB as a tool via the `,ai-kb search`
    subcommand. The shape of the CLI output (JSON array of hits with
    body/title/kind/scope/score) is part of the contract roles depend
    on; pin the schema so a careless refactor doesn't break agents
    that rely on it.
    """

    def test_search_cli_returns_json_array_with_expected_keys(self):
        """Run `python3 ai_kb.py search ... --json` against a fresh
        KB. The output must be a JSON array; each hit must carry the
        keys roles parse downstream."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {**os.environ, "AI_KB_HOME": str(tmp_path / "kb"), "AI_KB_DISABLE_EMBED": "1"}
            seed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "remember",
                    "--title",
                    "Tool probe",
                    "--body",
                    "An executor sometimes forgets to wire exports.",
                    "--kind",
                    "gotcha",
                    "--scope",
                    "project",
                    "--workspace",
                    "/ws/probe",
                    "--no-embed",
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert seed.returncode == 0, seed.stderr
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "search",
                    "executor wire exports",
                    "--limit",
                    "3",
                    "--mode",
                    "bm25",
                    "--kind",
                    "gotcha",
                    "--json",
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert run.returncode == 0, run.stderr
            payload = json.loads(run.stdout)
            assert isinstance(payload, list), type(payload)
            assert len(payload) >= 1, payload
            row = payload[0]
            for key in (
                "id",
                "title",
                "body",
                "snippet",
                "kind",
                "scope",
                "domain_tags",
                "confidence",
                "rrf_score",
                "bm25_rank",
                "vector_rank",
            ):
                assert key in row, f"missing key {key!r}; got keys {sorted(row.keys())}"
            assert row["kind"] == "gotcha"
            assert "wire exports" in row["body"]

    def test_search_cli_reads_automatic_queries_from_bounded_stdin(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "kb"
            kb = ai_kb.KnowledgeBase(home)
            kb.remember(
                "Private hook query",
                "Automatic recall keeps sensitive queries off process argv.",
                kind="gotcha",
                scope="project",
                workspace_path="/ws/private",
                embed_now=False,
            )
            query = "sensitive automatic recall argv"
            command = [
                sys.executable,
                str(SCRIPTS / "ai_kb.py"),
                "--home",
                str(home),
                "search",
                "--query-stdin",
                "--mode",
                "bm25",
                "--json",
            ]
            run = subprocess.run(
                command,
                input=query,
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert run.returncode == 0, run.stderr
            assert query not in command
            assert json.loads(run.stdout)[0]["title"] == "Private hook query"

            oversized = subprocess.run(
                command,
                input="x" * 4097,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert oversized.returncode == 2
            assert "exceeds 4096 characters" in oversized.stderr


class TestKnowledgeBaseDocIngestion(unittest.TestCase):
    """Phase 5: bulk-ingest existing markdown documentation into the
    KB as `kind=doc` capsules. Idempotent on file content so re-runs
    don't pile up duplicates; chunked on H1/H2 headings so retrieval
    can return individually-relevant sections.
    """

    def setUp(self):
        self.saved_disable = os.environ.get("AI_KB_DISABLE_EMBED")
        os.environ["AI_KB_DISABLE_EMBED"] = "1"

    def tearDown(self):
        if self.saved_disable is None:
            os.environ.pop("AI_KB_DISABLE_EMBED", None)
        else:
            os.environ["AI_KB_DISABLE_EMBED"] = self.saved_disable

    def test_ingest_file_chunks_on_h1_h2_headings(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            doc = tmp_path / "agents.md"
            doc.write_text(
                "# Agents\n\nIntro paragraph.\n\n"
                "## Skills\n\nSkill list goes here.\n\n"
                "### Sub-section under Skills\n\nshould stay inside Skills chunk\n\n"
                "## Tools\n\nTool list goes here.\n"
            )
            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")
            summary = kb.ingest_path(doc)
            assert summary["files_seen"] == 1
            assert summary["files_ingested"] == 1
            assert summary["files_skipped_unchanged"] == 0
            assert summary["capsules_stored"] == 3, summary

            # Verify titles match the headings.
            titles = sorted(c.title for c in kb.list(limit=10))
            assert titles == ["Agents", "Skills", "Tools"], titles

            # H3 stayed inside its parent chunk.
            skills = next(c for c in kb.list(limit=10) if c.title == "Skills")
            assert "Sub-section under Skills" in skills.body
            assert skills.kind == "doc", skills.kind
            assert "kb-ingest" in skills.tags

    def test_ingest_idempotent_on_unchanged_file(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            doc = tmp_path / "x.md"
            doc.write_text("# Title\n\nbody\n")
            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")

            first = kb.ingest_path(doc)
            assert first["files_ingested"] == 1
            ids_after_first = sorted(c.id for c in kb.list(limit=10))

            second = kb.ingest_path(doc)
            assert second["files_seen"] == 1
            assert second["files_ingested"] == 0
            assert second["files_skipped_unchanged"] == 1
            assert second["capsules_stored"] == 0
            ids_after_second = sorted(c.id for c in kb.list(limit=10))
            assert ids_after_first == ids_after_second, (
                f"capsule ids must be unchanged on idempotent re-ingest:\n"
                f"first: {ids_after_first}\nsecond: {ids_after_second}"
            )

    def test_ingest_replaces_chunks_when_file_changes(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            doc = tmp_path / "x.md"
            doc.write_text("# Old\n\nold body\n")
            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")

            kb.ingest_path(doc)
            assert [c.title for c in kb.list(limit=10)] == ["Old"]

            doc.write_text("# New A\n\na body\n\n## New B\n\nb body\n")
            summary = kb.ingest_path(doc)
            assert summary["files_ingested"] == 1
            assert summary["capsules_stored"] == 2

            titles = sorted(c.title for c in kb.list(limit=10))
            assert titles == ["New A", "New B"], titles

    def test_ingest_directory_walks_md_files(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "skills" / "foo").mkdir(parents=True)
            (tmp_path / "skills" / "foo" / "SKILL.md").write_text("# Foo skill\n\nfoo body\n")
            (tmp_path / "skills" / "bar").mkdir(parents=True)
            (tmp_path / "skills" / "bar" / "SKILL.md").write_text("# Bar skill\n\nbar body\n")
            (tmp_path / "skills" / "README.txt").write_text("not md, must skip")

            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")
            summary = kb.ingest_path(tmp_path / "skills")
            assert summary["files_seen"] == 2, summary
            assert summary["capsules_stored"] == 2, summary

            titles = sorted(c.title for c in kb.list(limit=10))
            assert titles == ["Bar skill", "Foo skill"], titles

            # Domain tag inference should pick up skill name from
            # parent dir.
            foo = next(c for c in kb.list(limit=10) if c.title == "Foo skill")
            assert "foo" in (foo.domain_tags or "").split(","), foo.domain_tags

    def test_ingest_rejects_non_markdown_target(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            f = tmp_path / "x.txt"
            f.write_text("not markdown")
            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")
            try:
                kb.ingest_path(f)
            except ValueError as err:
                assert "unsupported" in str(err)
            else:
                raise AssertionError("expected ValueError on non-markdown target")


class TestKnowledgeBaseSearchReturnsBody(unittest.TestCase):
    """Pin the regression where the FTS5 path returned `snippet` (the
    bracketed match-highlight) but not the full `body`. Recall
    consumers index `h["body"]`; when it was missing they injected only
    the capsule title (a meta-string) instead of the actual lesson.
    """

    def test_search_includes_body_field_in_results(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            kb.init()
            kb.remember(
                title="t1",
                body="Legion state layout uses legions/*/manifest.json with a stage filter.",
                source="palantir:test",
                tags="palantir,test",
            )
            hits = kb.search("Legion manifest layout", limit=5)
            assert len(hits) == 1, hits
            row = hits[0]
            assert "body" in row, f"search row must include body: keys={sorted(row.keys())}"
            assert "manifest.json" in (row["body"] or ""), row["body"]
            # snippet should still be present for CLI / UI consumers
            assert "snippet" in row, "search row must still include snippet for highlights"


class TestAiKbRememberSupersedes(unittest.TestCase):
    """WHEN `,ai-kb remember` is called with --supersedes / --refs."""

    AIKB = SCRIPTS / "ai_kb.py"

    def _remember(self, data_home: str, *args: str) -> dict:
        """Run remember in an isolated KB (no embedder) and return the capsule JSON."""
        result = subprocess.run(
            [sys.executable, str(self.AIKB), "remember", "--no-embed", "--json", *args],
            capture_output=True,
            text=True,
            env={**os.environ, "XDG_DATA_HOME": data_home},
        )
        if result.returncode != 0:
            raise AssertionError(f"remember failed:\n{result.stderr}")
        return json.loads(result.stdout)

    def test_supersedes_links_both_directions_and_retires_old_capsule(self):
        """SHOULD set superseded_by on the old capsule and supersedes on the new one, and drop the old from search."""
        with tempfile.TemporaryDirectory() as tmp:
            old = self._remember(
                tmp,
                "--title",
                "Old fact about X",
                "--body",
                "X uses approach foo",
                "--kind",
                "fact",
                "--scope",
                "project",
            )
            new = self._remember(
                tmp,
                "--title",
                "Corrected fact about X",
                "--body",
                "X actually uses approach bar, verified at lib.py:10",
                "--kind",
                "fact",
                "--scope",
                "project",
                "--supersedes",
                old["id"],
                "--confidence",
                "0.9",
            )

            get_old = subprocess.run(
                [sys.executable, str(self.AIKB), "get", old["id"], "--json"],
                capture_output=True,
                text=True,
                env={**os.environ, "XDG_DATA_HOME": tmp},
            )
            old_capsule = json.loads(get_old.stdout)

            assert old_capsule["superseded_by"] == new["id"]  # old points forward to replacement
            assert new["supersedes"] == old["id"]  # new points back to what it retired

            search = subprocess.run(
                [sys.executable, str(self.AIKB), "search", "fact about X", "--mode", "bm25", "--json"],
                capture_output=True,
                text=True,
                env={**os.environ, "XDG_DATA_HOME": tmp},
            )
            hit_ids = [r["id"] for r in json.loads(search.stdout or "[]")]
            assert new["id"] in hit_ids  # replacement surfaces
            assert old["id"] not in hit_ids  # superseded capsule excluded from results

    def test_supersedes_unknown_id_errors_without_writing(self):
        """SHOULD exit non-zero and not create a capsule when the supersede target is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.AIKB),
                    "remember",
                    "--no-embed",
                    "--title",
                    "Z",
                    "--body",
                    "z",
                    "--supersedes",
                    "does-not-exist-id",
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "XDG_DATA_HOME": tmp},
            )
            assert result.returncode == 1
            assert "not found" in result.stderr

            listed = subprocess.run(
                [sys.executable, str(self.AIKB), "list", "--json"],
                capture_output=True,
                text=True,
                env={**os.environ, "XDG_DATA_HOME": tmp},
            )
            assert json.loads(listed.stdout or "[]") == []  # nothing was written

    def test_refs_are_stored_as_csv(self):
        """SHOULD persist repeated --refs as a CSV refs field on the capsule."""
        with tempfile.TemporaryDirectory() as tmp:
            cap = self._remember(
                tmp, "--title", "With refs", "--body", "b", "--refs", "lib.py:10", "--refs", "https://example/doc"
            )
            assert cap["refs"] == "lib.py:10,https://example/doc"


class TestWorklogHarvest(unittest.TestCase):
    """WHEN mining a hook worklog for durable-memory candidates (read-only)."""

    @staticmethod
    def _entry(**kwargs):
        base = {"ts": "2026-07-05T00:00:00Z", "event": "postToolUse", "tool_name": "Shell"}
        base.update(kwargs)
        return base

    def test_detect_failure_to_fix(self):
        import ai_kb

        entries = [
            self._entry(command="pytest test_foo.py", status="error", error="FAILED test_foo AssertionError line 42"),
            self._entry(command="pytest test_foo.py", status="success"),
        ]
        cands = ai_kb.detect_candidates(entries)
        f2f = [c for c in cands if c["detector"] == "failure_to_fix"]
        assert len(f2f) == 1, cands
        assert f2f[0]["kind"] == "gotcha"
        assert f2f[0]["program"] == "pytest"
        # digit-normalized signature so line numbers collapse
        assert "line <n>" in f2f[0]["signature"]

    def test_detect_structured_notes_keep_the_capsule_kind_verbatim(self):
        """A single deliberate `,agent-memory note` is a candidate; kinds share the capsule taxonomy and min_repeats never applies."""
        import ai_kb

        entries = [
            self._entry(
                event="note", note_kind="principle", text="keep /tmp/specs primary", refs="scripts/spec_mirror.py"
            ),
            self._entry(event="note", note_kind="gotcha", text="hooks must fail open"),
            self._entry(event="note", note_kind="fact", text="codex spawns hooks without a shell"),
            self._entry(event="note", note_kind="pattern", text="mirror named topics to XDG state"),
            self._entry(event="note", note_kind="anti_pattern", text="do not move the spec root wholesale"),
            self._entry(event="note", note_kind="recipe", text="chezmoi execute-template < x.tmpl verifies rendering"),
        ]
        cands = ai_kb.detect_candidates(entries, min_repeats=99)
        notes = {c["note_kind"]: c for c in cands if c["detector"] == "structured_note"}
        assert set(notes) == {"principle", "gotcha", "fact", "pattern", "anti_pattern", "recipe"}, cands
        for kind, candidate in notes.items():
            assert candidate["kind"] == kind, candidate
        assert notes["principle"]["title"].startswith("principle: keep /tmp/specs primary")
        assert "Refs: scripts/spec_mirror.py." in notes["principle"]["body"]
        assert notes["principle"]["count"] == 1

    def test_decision_notes_harvest_as_fact_candidates(self):
        """A `decision` note is deliberate capture too, but its capsule candidate kind is `fact`."""
        import ai_kb

        entries = [
            self._entry(
                event="note", note_kind="decision", text="ship the bridge behind the seam", refs="mcp_servers.yaml"
            ),
        ]
        cands = [c for c in ai_kb.detect_candidates(entries, min_repeats=99) if c["detector"] == "structured_note"]
        assert len(cands) == 1, cands
        assert cands[0]["note_kind"] == "decision"
        assert cands[0]["kind"] == "fact"
        assert cands[0]["title"].startswith("decision: ship the bridge behind the seam")

    def test_question_notes_and_duplicates_are_not_candidates(self):
        import ai_kb

        entries = [
            self._entry(event="note", note_kind="question", text="should sessions mirror too?"),
            self._entry(event="note", note_kind="fact", text="same text"),
            self._entry(event="note", note_kind="fact", text="same text"),
            self._entry(event="note", note_kind="doc", text="ingestion-only kind ignored"),
            self._entry(event="note", note_kind="bogus-kind", text="ignored"),
            self._entry(event="note", note_kind="fact", text=""),
        ]
        cands = [c for c in ai_kb.detect_candidates(entries) if c["detector"] == "structured_note"]
        assert len(cands) == 1, cands
        assert cands[0]["title"].startswith("fact: same text"), cands

    def test_failure_without_later_fix_yields_no_f2f(self):
        import ai_kb

        entries = [self._entry(command="npm run build", error="error TS2307: missing module")]
        cands = ai_kb.detect_candidates(entries)
        assert [c for c in cands if c["detector"] == "failure_to_fix"] == []

    def test_nonzero_exit_without_error_message_is_not_a_failure(self):
        import ai_kb

        # A compound investigation command that merely exits nonzero (status
        # error, banner text in output, no error_message) then a clean rerun
        # must NOT produce a failure_to_fix candidate.
        entries = [
            self._entry(command="rg needle | head", status="error", output="===== banner ====="),
            self._entry(command="rg needle | head", status="success"),
        ]
        cands = ai_kb.detect_candidates(entries)
        assert [c for c in cands if c["detector"] == "failure_to_fix"] == [], cands

    def test_repeated_long_and_multiline_commands_excluded(self):
        import ai_kb

        long_cmd = 'p=~/x; echo "===="; ' + "ls -1 dir; " * 30  # >200 chars
        multiline = "cd /repo\necho hi\nsed -n '1,5p' file"
        entries = [
            self._entry(command=long_cmd, status="success"),
            self._entry(command=long_cmd, status="success"),
            self._entry(command=multiline, status="success"),
            self._entry(command=multiline, status="success"),
        ]
        cands = ai_kb.detect_candidates(entries, min_repeats=2)
        assert [c for c in cands if c["detector"] == "repeated_command"] == [], cands

    def test_detect_recurring_error(self):
        import ai_kb

        entries = [
            self._entry(command="curl x", error="Timeout after 30s"),
            self._entry(command="curl y", error="Timeout after 45s"),
        ]
        cands = ai_kb.detect_candidates(entries, min_repeats=2)
        rec = [c for c in cands if c["detector"] == "recurring_error"]
        assert len(rec) == 1, cands
        assert rec[0]["count"] == 2
        assert rec[0]["kind"] == "gotcha"
        assert rec[0]["signature"] == "Timeout after <n>s"

    def test_fixed_signature_not_double_reported_as_recurring(self):
        import ai_kb

        # Same error signature appears twice AND is later fixed: it must be a
        # single failure_to_fix, not also a recurring_error (fixed_sigs guard).
        entries = [
            self._entry(command="pytest a.py", error="FAILED AssertionError line 42"),
            self._entry(command="pytest b.py", error="FAILED AssertionError line 88"),
            self._entry(command="pytest a.py", status="success"),
        ]
        cands = ai_kb.detect_candidates(entries, min_repeats=2)
        detectors = [c["detector"] for c in cands]
        assert detectors.count("failure_to_fix") == 1, cands
        assert "recurring_error" not in detectors, cands

    def test_detect_repeated_command_and_noise_excluded(self):
        import ai_kb

        entries = [
            self._entry(command="make check", status="success"),
            self._entry(command="make check", status="success"),
            self._entry(command="ls", status="success"),
            self._entry(command="ls", status="success"),
        ]
        cands = ai_kb.detect_candidates(entries, min_repeats=2)
        rep = [c for c in cands if c["detector"] == "repeated_command"]
        assert len(rep) == 1, cands
        assert rep[0]["signature"] == "make check"
        assert rep[0]["count"] == 2
        assert rep[0]["kind"] == "recipe"

    def test_min_repeats_threshold(self):
        import ai_kb

        entries = [
            self._entry(command="make check", status="success"),
            self._entry(command="make check", status="success"),
        ]
        assert ai_kb.detect_candidates(entries, min_repeats=3) == []

    def test_read_worklog_skips_malformed(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            wl = Path(tmp) / "current.worklog.jsonl"
            wl.write_text(
                '{"ts":"t","command":"make check","status":"success"}\n'
                "not json\n"
                "\n"
                '{"ts":"t2","command":"make check","status":"success"}\n',
                encoding="utf-8",
            )
            entries = ai_kb.read_worklog(wl)
            assert len(entries) == 2
            cands = ai_kb.detect_candidates(entries, min_repeats=2)
            assert any(c["detector"] == "repeated_command" for c in cands)

    def test_suppress_known_flags_existing_capsule(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            known = kb.remember(
                title="pytest test_foo AssertionError",
                body="FAILED test_foo AssertionError line fixed by updating the fixture",
                kind="gotcha",
                scope="workspace",
                workspace_path="/ws",
                source="test",
                embed_now=False,
            )
            entries = [
                self._entry(command="pytest test_foo.py", error="FAILED test_foo AssertionError line 42"),
                self._entry(command="pytest test_foo.py", status="success"),
                self._entry(command="make check", status="success"),
                self._entry(command="make check", status="success"),
            ]
            cands = ai_kb.detect_candidates(entries, min_repeats=2)
            ai_kb.suppress_known(kb, cands, Path("/ws"))
            by_detector = {c["detector"]: c for c in cands}
            assert by_detector["failure_to_fix"]["known"] is True
            assert by_detector["failure_to_fix"]["known_id"] == known.id
            # unrelated recipe stays unknown
            assert by_detector["repeated_command"]["known"] is False

    def test_harvest_cli_json_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb_home = Path(tmp) / "kb"
            wl = Path(tmp) / "current.worklog.jsonl"
            wl.write_text(
                '{"ts":"t1","command":"make check","status":"success"}\n'
                '{"ts":"t2","command":"make check","status":"success"}\n',
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "--home",
                    str(kb_home),
                    "harvest",
                    "--worklog",
                    str(wl),
                    "--workspace",
                    "/ws",
                    "--session-id",
                    "../",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
            )
            assert result.returncode == 0, result.stderr
            payload = json.loads(result.stdout)
            assert payload["topic"] == "current"
            assert payload["entries"] == 2
            assert any(c["detector"] == "repeated_command" for c in payload["candidates"])
            # harvest never writes capsules
            listed = subprocess.run(
                [sys.executable, str(SCRIPTS / "ai_kb.py"), "--home", str(kb_home), "list", "--json"],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
            )
            assert json.loads(listed.stdout or "[]") == []

    def test_harvest_cli_resolves_session_bound_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=workspace, check=True)

            spec_root = root / "specs"
            spec_dir = spec_root / str(workspace.resolve()).lstrip(os.sep)
            spec_dir.mkdir(parents=True)
            (spec_dir / ".session-topic-session-a.txt").write_text("alpha\n")
            (spec_dir / "alpha.worklog.jsonl").write_text(
                '{"ts":"t1","command":"make check","status":"success"}\n'
                '{"ts":"t2","command":"make check","status":"success"}\n',
                encoding="utf-8",
            )
            (spec_dir / "current.worklog.jsonl").write_text(
                '{"ts":"stale","command":"false","status":"failure"}\n',
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["AGENT_MEMORY_SPEC_ROOT"] = str(spec_root)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "--home",
                    str(root / "kb"),
                    "harvest",
                    "--workspace",
                    str(workspace),
                    "--session-id",
                    "session-a",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )

            assert result.returncode == 0, result.stderr
            payload = json.loads(result.stdout)
            assert payload["topic"] == "alpha"
            assert payload["worklog"].endswith("/alpha.worklog.jsonl")
            assert payload["entries"] == 2


if __name__ == "__main__":
    unittest.main()
