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
                    "Ralph memory",
                    "--body",
                    "Ralph stores durable learnings across sessions.",
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
            assert capsule["title"] == "Ralph memory"

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
    DBs are dropped on first init, not migrated.
    """

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
            # Now init should detect the stale shape and wipe.
            kb.init()
            with kb.connect() as db:
                cols = [r[1] for r in db.execute("PRAGMA table_info(capsules)").fetchall()]
                count = db.execute("SELECT COUNT(*) FROM capsules").fetchone()[0]
            assert tuple(cols) == ai_kb.CAPSULE_COLUMNS
            assert count == 0, "stale rows must be dropped — no compat path"

    def test_remember_persists_full_metadata(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RALPH_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                c = kb.remember(
                    title="kb test",
                    body="full payload",
                    kind="gotcha",
                    scope="project",
                    workspace_path="/ws",
                    project_id="proj-1",
                    domain_tags=["python", "ralph"],
                    confidence=0.8,
                    verified_by="go-rid-1",
                )
                assert c.kind == "gotcha"
                assert c.scope == "project"
                assert c.workspace_path == "/ws"
                assert c.project_id == "proj-1"
                assert c.domain_tags == "python,ralph"
                assert c.confidence == 0.8
                assert c.verified_by == "go-rid-1"
                # No embedder under disable flag → embedding fields blank.
                assert c.embedding_dim == 0
                assert c.embedding_model is None
                # Round-trip via get().
                got = kb.get(c.id)
                assert got is not None
                assert got.kind == "gotcha"
                assert got.domain_tags == "python,ralph"
            finally:
                os.environ.pop("RALPH_KB_DISABLE_EMBED", None)

    def test_remember_rejects_unknown_kind_or_scope(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RALPH_KB_DISABLE_EMBED"] = "1"
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
                os.environ.pop("RALPH_KB_DISABLE_EMBED", None)

    def test_supersedes_links_bidirectionally(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RALPH_KB_DISABLE_EMBED"] = "1"
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
                os.environ.pop("RALPH_KB_DISABLE_EMBED", None)


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
            saved = os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                c = kb.remember(
                    title="Ralph manifest layout",
                    body="Ralph state under runs/*/manifest.json with kind values.",
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
                    os.environ["RALPH_KB_DISABLE_EMBED"] = saved


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
        self.saved_disable = os.environ.pop("RALPH_KB_DISABLE_EMBED", None)

    def tearDown(self):
        if self.saved_disable is not None:
            os.environ["RALPH_KB_DISABLE_EMBED"] = self.saved_disable

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
            # cap_b: high semantic relevance to a Ralph-flavored query,
            # but no shared tokens with the query.
            kb.remember(
                title="Run state on disk",
                body="Each Ralph execution stores its progress under its own directory.",
                kind="fact",
            )

            hits = kb.search("ralph manifest layout", limit=3, mode="hybrid")
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
                    body=f"Lesson number {i} about Ralph orchestration.",
                    kind="fact",
                )
            hits = kb.search("ralph orchestration", limit=2, mode="hybrid")
            assert len(hits) == 2
            for h in hits:
                assert h["mmr_selected"] is True, h


class TestKnowledgeBaseCurate(unittest.TestCase):
    """Phase 7: curation pass — dedupe, decay, contradiction-scan.

    Dedupe + contradiction tests need embeddings (cosine math); decay
    test runs without an embedder so the fast suite stays fast.
    """

    def test_decay_runs_even_without_embeddings(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RALPH_KB_DISABLE_EMBED"] = "1"
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
                os.environ.pop("RALPH_KB_DISABLE_EMBED", None)

    def test_dedupe_marks_near_duplicates_as_superseded(self):
        import embed

        if not embed.Embedder().is_available():
            self.skipTest("fastembed runner not available")

        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
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
                    os.environ["RALPH_KB_DISABLE_EMBED"] = saved

    def test_contradiction_scan_returns_candidate_pairs(self):
        import embed

        if not embed.Embedder().is_available():
            self.skipTest("fastembed runner not available")

        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
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
                    os.environ["RALPH_KB_DISABLE_EMBED"] = saved


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
            saved = os.environ.get("RALPH_KB_DISABLE_VEC")
            os.environ["RALPH_KB_DISABLE_VEC"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                knn = kb._call_vec_runner({"mode": "knn", "db_path": str(kb.db_path)})
                pairs = kb._call_vec_runner({"mode": "pairs", "db_path": str(kb.db_path)})
                assert knn == {"hits": []}, knn
                assert pairs == {"pairs": []}, pairs
            finally:
                if saved is None:
                    os.environ.pop("RALPH_KB_DISABLE_VEC", None)
                else:
                    os.environ["RALPH_KB_DISABLE_VEC"] = saved

    def test_call_vec_runner_raises_when_runner_missing(self):
        """If the colocated `vec_runner.py` is absent, hard-fail with
        a clear RuntimeError rather than silently degrading."""
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("RALPH_KB_DISABLE_VEC", None)
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
                    os.environ["RALPH_KB_DISABLE_VEC"] = saved

    def test_doctor_reports_vec_runner_status(self):
        """`,ai-kb doctor` must surface vec_runner state so operators
        can debug a broken install. Verifies the line is present in
        either the disabled / missing / ok variant — exact wording is
        a contract the doctor command exposes to humans."""
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.get("RALPH_KB_DISABLE_VEC")
            os.environ["RALPH_KB_DISABLE_VEC"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                lines = kb.doctor()
                vec_lines = [l for l in lines if l.startswith("vec_runner=")]
                assert len(vec_lines) == 1, lines
                assert "disabled via RALPH_KB_DISABLE_VEC" in vec_lines[0], vec_lines
            finally:
                if saved is None:
                    os.environ.pop("RALPH_KB_DISABLE_VEC", None)
                else:
                    os.environ["RALPH_KB_DISABLE_VEC"] = saved


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
            env = {**os.environ, "AI_KB_HOME": str(tmp_path / "kb"), "RALPH_KB_DISABLE_EMBED": "1"}
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


class TestKnowledgeBaseDocIngestion(unittest.TestCase):
    """Phase 5: bulk-ingest existing markdown documentation into the
    KB as `kind=doc` capsules. Idempotent on file content so re-runs
    don't pile up duplicates; chunked on H1/H2 headings so retrieval
    can return individually-relevant sections.
    """

    def setUp(self):
        self.saved_disable = os.environ.get("RALPH_KB_DISABLE_EMBED")
        os.environ["RALPH_KB_DISABLE_EMBED"] = "1"

    def tearDown(self):
        if self.saved_disable is None:
            os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
        else:
            os.environ["RALPH_KB_DISABLE_EMBED"] = self.saved_disable

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
    bracketed match-highlight) but not the full `body`. Ralph's
    `_fetch_learnings` indexed `h["body"]` and got `None`, so role
    prompts saw only the capsule title (a meta-string like
    `Ralph learning go-…-executor-1`) instead of the actual lesson.
    """

    def test_search_includes_body_field_in_results(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            kb.init()
            kb.remember(
                title="t1",
                body="Ralph state layout uses runs/*/manifest.json with kind=='go' filter.",
                source="ralph:test",
                tags="ralph,test",
            )
            hits = kb.search("Ralph manifest layout", limit=5)
            assert len(hits) == 1, hits
            row = hits[0]
            assert "body" in row, f"search row must include body: keys={sorted(row.keys())}"
            assert "manifest.json" in (row["body"] or ""), row["body"]
            # snippet should still be present for CLI / UI consumers
            assert "snippet" in row, "search row must still include snippet for highlights"

    def test_fetch_learnings_injects_body_text_not_title(self):
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_home = tmp_path / "state"
            kb_home = tmp_path / "kb"
            state_home.mkdir()
            kb_home.mkdir()
            runner = ralph.RalphRunner(state_home=state_home, kb_home=kb_home)
            runner.init()
            runner.kb.remember(
                title="Ralph learning go-foo-executor-1",
                body="Concrete fact: spec target_artifact must be an absolute path.",
                source="ralph:go-foo-executor-1",
                tags="ralph,session-learning",
            )
            text, hits = runner._fetch_learnings("spec target_artifact path", top_k=5)
            assert "Concrete fact" in text, f"role prompts must inject capsule body, not title:\n{text!r}"
            assert "Ralph learning go-foo-executor-1" not in text, (
                f"title (meta-string) must not be the injected content:\n{text!r}"
            )
            # The hits payload mirrors the ranked search results — caller-side
            # consumers (TUI retrieval_log, future curator) read it directly.
            assert len(hits) == 1, hits
            assert hits[0]["title"].startswith("Ralph learning"), hits[0]


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
