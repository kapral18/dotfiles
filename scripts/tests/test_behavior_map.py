#!/usr/bin/env python3
"""Tests for the `,behavior-map` per-repo behavior map command."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMAND = REPO / "home" / "exact_lib" / "exact_,behavior-map" / "main.py"


def entry(entry_id: str, expect: str, *, anchor: str = "app.py::run", verified: bool = False) -> str:
    status = "status: verified\nverified_date: 2026-10-06" if verified else "status: unverified"
    return (
        f"---\nid: {entry_id}\n{status}\nanchors:\n  - {anchor}\nverify: python3 app.py\n---\n"
        f"Trigger: run the app.\nExpect: {expect}\n"
    )


class TestBehaviorMap(unittest.TestCase):
    """WHEN agents read and write a repo behavior map from several worktrees."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.store = base / "store"
        self.main = base / "proj"
        self.git("init", "-q", "-b", "main", str(self.main), cwd=base)
        (self.main / "app.py").write_text("def run():\n    return 1\n")
        self.git("add", "app.py")
        self.git("commit", "-q", "-m", "base")
        self.feature = base / "proj-feature"
        self.git("worktree", "add", "-q", "-b", "feature", str(self.feature))

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args: str, cwd: Path | None = None) -> str:
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
            cwd=cwd or self.main,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def bm(self, *args: str, stdin: str = "", cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "AGENT_BEHAVIOR_MAP_DIR": str(self.store), "GIT_CEILING_DIRECTORIES": self.tmp.name}
        return subprocess.run(
            [sys.executable, str(COMMAND), *args],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=cwd or self.main,
            env=env,
        )

    def ok(self, *args: str, stdin: str = "", cwd: Path | None = None) -> str:
        result = self.bm(*args, stdin=stdin, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result.stdout

    def show_entry(self, entry_id: str, cwd: Path | None = None) -> str:
        """Return `show <id>` output as printed; `save` drops the status line and keeps the header hash."""
        return self.ok("show", entry_id, cwd=cwd)

    def test_SHOULD_store_one_map_per_repo_shared_by_all_worktrees(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))

        self.assertTrue((self.store / "proj/base/app/run.md").is_file())
        self.assertIn("app/run", self.ok("show", "--ids", cwd=self.feature))

    def test_SHOULD_reject_entries_that_break_the_format(self):
        bad = entry("app/run", "x").replace("Expect: x\n", "Notes: free text\n")

        result = self.bm("save", "app/run", stdin=bad)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Expect:", result.stderr)
        self.assertIn("body line must start with", result.stderr)

    def test_SHOULD_refuse_a_write_when_the_entry_changed_since_it_was_read(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))
        first_read = self.show_entry("app/run")
        second_read = self.show_entry("app/run")

        self.ok("save", "app/run", stdin=first_read.replace("returns 1.", "returns one."))
        stale = self.bm("save", "app/run", stdin=second_read.replace("returns 1.", "returns uno."))
        blind = self.bm("save", "app/run", stdin=entry("app/run", "blind write."))

        self.assertEqual(stale.returncode, 1)
        self.assertIn("changed since you read it", stale.stderr)
        self.assertEqual(blind.returncode, 1)
        self.assertIn("keep the header line", blind.stderr)

    def test_SHOULD_keep_branch_changes_out_of_the_base_view(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))
        on_branch = self.show_entry("app/run", cwd=self.feature)

        self.ok("save", "app/run", stdin=on_branch.replace("returns 1.", "returns 2."), cwd=self.feature)

        self.assertIn("returns 1.", self.ok("show", "app/run"))
        branch_view = self.ok("show", "app/run", cwd=self.feature)
        self.assertIn("returns 2.", branch_view)
        self.assertIn("overlay", branch_view)

    def test_SHOULD_flag_drift_when_base_changes_after_the_branch_forked(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))
        self.ok(
            "save",
            "app/run",
            stdin=self.show_entry("app/run", cwd=self.feature).replace("returns 1.", "returns 2."),
            cwd=self.feature,
        )

        self.ok("save", "app/run", stdin=self.show_entry("app/run").replace("Trigger: run", "Trigger: start"))

        self.assertIn("drift", self.ok("show", cwd=self.feature))

    def test_SHOULD_promote_a_merged_branch_with_a_clean_three_way_merge(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))
        self.ok(
            "save",
            "app/run",
            stdin=self.show_entry("app/run", cwd=self.feature).replace("returns 1.", "returns 2."),
            cwd=self.feature,
        )
        self.ok("save", "app/new", stdin=entry("app/new", "is new."), cwd=self.feature)
        self.ok(
            "save", "app/run", stdin=self.show_entry("app/run").replace("verify: python3 app.py", "verify: make test")
        )
        (self.feature / "app.py").write_text("def run():\n    return 2\n")
        self.git("commit", "-q", "-am", "feature", cwd=self.feature)
        self.git("merge", "-q", "--no-edit", "feature")

        out = self.ok("promote", "feature", "--offline")

        merged = (self.store / "proj/base/app/run.md").read_text()
        self.assertIn("promoted 2 entries", out)
        self.assertIn("verify: make test", merged)
        self.assertIn("returns 2.", merged)
        self.assertTrue((self.store / "proj/base/app/new.md").is_file())
        self.assertEqual(list((self.store / "proj").glob("branches/*")), [])

    def test_SHOULD_hold_conflicts_until_resolved(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))
        self.ok(
            "save",
            "app/run",
            stdin=self.show_entry("app/run", cwd=self.feature).replace("returns 1.", "returns 2."),
            cwd=self.feature,
        )
        self.ok("save", "app/run", stdin=self.show_entry("app/run").replace("returns 1.", "returns 3."))

        result = self.bm("promote", "feature", "--force", "--offline")

        self.assertEqual(result.returncode, 1)
        self.assertIn("conflict app/run", result.stdout)
        self.assertIn("returns 3.", (self.store / "proj/base/app/run.md").read_text())
        self.assertIn("conflict", self.ok("show", cwd=self.feature))

        self.ok("resolve", "feature", "app/run", stdin=entry("app/run", "returns 2 or 3."))

        self.assertIn("returns 2 or 3.", (self.store / "proj/base/app/run.md").read_text())
        self.assertEqual(list((self.store / "proj").glob("branches/*")), [])

    def test_SHOULD_refuse_to_promote_an_unmerged_branch(self):
        self.ok("save", "app/new", stdin=entry("app/new", "is new."), cwd=self.feature)

        result = self.bm("promote", "feature", "--offline")

        self.assertEqual(result.returncode, 1)
        self.assertIn("not merged", result.stderr)

    def test_SHOULD_mark_a_branch_removal_without_touching_base(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))

        self.ok("remove", "app/run", cwd=self.feature)

        self.assertNotIn("app/run", self.ok("show", "--ids", cwd=self.feature))
        self.assertIn("app/run", self.ok("show", "--ids"))

    def test_SHOULD_promote_cleanly_when_both_sides_removed_the_entry(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))
        self.ok("remove", "app/run", cwd=self.feature)
        self.ok("remove", "app/run")

        out = self.ok("promote", "feature", "--force", "--offline")

        self.assertIn("promoted 1 entries", out)
        self.assertEqual(list((self.store / "proj").glob("branches/*")), [])

    def test_SHOULD_let_a_branch_recreate_an_entry_it_removed(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))
        on_branch = self.show_entry("app/run", cwd=self.feature)
        self.ok("remove", "app/run", cwd=self.feature)

        self.assertIn("No entries in this view.", self.ok("show", cwd=self.feature))
        self.ok("save", "app/run", stdin=on_branch.replace("returns 1.", "returns 4."), cwd=self.feature)

        self.assertIn("returns 4.", self.ok("show", "app/run", cwd=self.feature))

    def test_SHOULD_reject_names_that_collide_with_sidecar_files(self):
        result = self.bm("save", "app/x.base", stdin=entry("app/x.base", "x."))

        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid id", result.stderr)

    def test_SHOULD_flag_stale_and_broken_anchors(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1.", verified=True))
        self.ok("save", "app/gone", stdin=entry("app/gone", "x.", anchor="app.py::missing_symbol", verified=True))
        self.assertNotIn("stale", self.ok("show"))

        (self.main / "app.py").write_text("def run():\n    return 5\n")
        result = self.bm("check", "--offline")

        self.assertEqual(result.returncode, 1)
        self.assertIn("app/run: stale", result.stdout)
        self.assertIn("app/gone: broken, stale", result.stdout)

    def test_SHOULD_stay_fresh_across_a_commit_of_verified_uncommitted_code(self):
        (self.main / "src").mkdir()
        (self.main / "src/app.py").write_text("def run():\n    return 2\n")
        self.ok("save", "core/run", stdin=entry("core/run", "returns 2.", anchor="src/", verified=True))
        self.assertNotIn("stale", self.ok("show"))

        self.git("add", "src")
        self.git("commit", "-q", "-m", "add src")
        self.assertNotIn("stale", self.ok("show"))

        (self.main / "src/helper.py").write_text("x = 1\n")
        self.assertIn("stale", self.ok("show"))

    def test_SHOULD_list_entries_affected_by_the_branch_diff(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1."))
        (self.feature / "app.py").write_text("def run():\n    return 9\n")
        (self.feature / "other.py").write_text("x = 1\n")

        out = self.ok("affected", cwd=self.feature)

        self.assertIn("entry app/run: app.py", out)
        self.assertIn("unmapped: .", out)
        self.assertIn("2 files; 1 outside every mapped area", out)

    def test_SHOULD_send_a_change_deep_in_an_area_to_the_whole_area(self):
        (self.main / "src").mkdir()
        (self.main / "src/app.py").write_text("def run():\n    return 1\n")
        self.ok("save", "core/run", stdin=entry("core/run", "returns 1.", anchor="src/"))
        self.ok("save", "core/stop", stdin=entry("core/stop", "stops.", anchor="src/app.py::run"))

        out = self.ok("affected", "src/helper.py", "tools/new.py")

        self.assertIn("entry core/run: src/helper.py", out)
        self.assertIn("area core: 2 entries, check them with `show core`; changed src/helper.py", out)
        self.assertIn("unmapped: tools", out)
        self.assertIn("2 files; 1 outside every mapped area", out)

    def test_SHOULD_match_a_planned_directory_to_the_area_that_owns_it(self):
        (self.main / "src/sub").mkdir(parents=True)
        (self.main / "src/app.py").write_text("x = 1\n")
        self.ok("save", "core/run", stdin=entry("core/run", "runs.", anchor="src/"))

        owned = self.ok("affected", "src")
        unowned = self.ok("affected", "app.py")

        self.assertIn("area core", owned)
        self.assertIn("0 outside every mapped area", owned)
        self.assertIn("unmapped: .", unowned)

    def test_SHOULD_flag_a_directory_anchor_missing_its_slash_as_broken(self):
        (self.main / "src").mkdir()
        (self.main / "src/app.py").write_text("x = 1\n")
        self.ok("save", "core/run", stdin=entry("core/run", "runs.", anchor="src"))

        self.assertIn("broken", self.ok("show"))

    def test_SHOULD_reject_planned_paths_together_with_since(self):
        result = self.bm("affected", "app.py", "--since", "HEAD")

        self.assertEqual(result.returncode, 1)
        self.assertIn("not both", result.stderr)

    def test_SHOULD_not_drift_or_conflict_on_a_fingerprint_refresh_alone(self):
        self.ok("save", "app/run", stdin=entry("app/run", "returns 1.", verified=True))
        self.ok(
            "save",
            "app/run",
            stdin=self.show_entry("app/run", cwd=self.feature).replace("returns 1.", "returns 2."),
            cwd=self.feature,
        )
        (self.main / "app.py").write_text("def run():\n    return 3\n")
        self.ok("save", "app/run", stdin=self.show_entry("app/run"))

        self.assertNotIn("drift", self.ok("show", cwd=self.feature))
        out = self.ok("promote", "feature", "--force", "--offline")

        self.assertIn("promoted 1 entries", out)
        self.assertIn("returns 2.", (self.store / "proj/base/app/run.md").read_text())

    def test_SHOULD_not_claim_a_shared_directory_through_a_file_anchor(self):
        (self.main / "bin").mkdir()
        (self.main / "bin/tool").write_text("#!/bin/sh\n")
        self.ok("save", "tool/run", stdin=entry("tool/run", "runs.", anchor="bin/tool"))

        out = self.ok("affected", "bin/tool", "bin/other")

        self.assertIn("entry tool/run: bin/tool", out)
        self.assertNotIn("area tool", out)
        self.assertIn("unmapped: bin", out)

    def test_SHOULD_reject_a_symbol_on_a_directory_anchor(self):
        result = self.bm("save", "core/x", stdin=entry("core/x", "x.", anchor="src/::run"))

        self.assertEqual(result.returncode, 1)
        self.assertIn("directory anchor takes no symbol", result.stderr)

    def test_SHOULD_reject_planned_paths_outside_the_repo(self):
        result = self.bm("affected", "/etc/hosts")

        self.assertEqual(result.returncode, 1)
        self.assertIn("outside the repo", result.stderr)

    def test_SHOULD_refuse_writes_on_a_detached_head(self):
        self.git("checkout", "-q", "--detach", cwd=self.feature)

        result = self.bm("save", "app/run", stdin=entry("app/run", "x."), cwd=self.feature)

        self.assertEqual(result.returncode, 1)
        self.assertIn("detached HEAD", result.stderr)

    def test_SHOULD_point_to_init_when_the_repo_has_no_map(self):
        out = self.ok("show")

        self.assertIn("0 entries", out)
        self.assertIn("area init", out)


if __name__ == "__main__":
    unittest.main()
