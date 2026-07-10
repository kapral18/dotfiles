#!/usr/bin/env python3
"""Tests for verify_mermaids.py."""

from __future__ import annotations

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


class VerifyMermaidsTest(unittest.TestCase):
    """WHEN validating the .mermaids/ navigation map's file-census claims."""

    def _module(self):
        import verify_mermaids

        return verify_mermaids

    def test_real_census_matches_repo(self):
        """SHOULD pass for the committed map (counts and prose anchors current)."""
        m = self._module()
        failures = m.check_claims(REPO)
        assert failures == [], "stale .mermaids census: " + "; ".join(failures)

    def test_count_drift_is_detected(self):
        """SHOULD report a mismatch when a claimed count diverges from git."""
        m = self._module()
        bogus = [m.Claim("bogus", ["home/exact_bin/*"], 999999, [])]
        failures = m.check_claims(REPO, bogus)
        assert any("claimed 999999" in f for f in failures)

    def test_effective_census_counts_unstaged_adds_and_removes(self):
        """SHOULD validate file-count changes before the rename is staged."""
        m = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / "kept.txt").write_text("kept\n", encoding="utf-8")
            (repo / "removed.txt").write_text("removed\n", encoding="utf-8")
            subprocess.run(["git", "add", "kept.txt", "removed.txt"], cwd=repo, check=True)
            (repo / "removed.txt").unlink()
            (repo / "added.txt").write_text("added\n", encoding="utf-8")

            assert m._git_ls_files(repo, None) == 2
            assert m._git_ls_files(repo, ["*.txt"]) == 2

    def test_total_claim_covers_readme_and_overview_anchors(self):
        """SHOULD lock the total effective-file anchors in README and overview."""
        m = self._module()
        total_claim = next(claim for claim in m.CENSUS if claim.globs is None)

        assert ("README.md", f"{total_claim.claimed} files in the effective git file set") in total_claim.anchors
        assert ("00-overview.mmd", f"{total_claim.claimed} files in the effective git file set") in total_claim.anchors
        assert ("00-overview.mmd", f"file census ({total_claim.claimed} total)") in total_claim.anchors

    def test_neovim_local_plugin_claims_are_split_and_independent(self):
        """SHOULD keep the loader and source dirs as separate 14-file claims."""
        m = self._module()
        local_claim = next(claim for claim in m.CENSUS if claim.name.endswith("exact_plugins_local/"))
        src_claim = next(claim for claim in m.CENSUS if claim.name.endswith("exact_plugins_local_src/"))

        assert local_claim.claimed == 14
        assert src_claim.claimed == 14
        assert ("07b-neovim.mmd", "exact_plugins_local/ (loaders, 14 each)") in local_claim.anchors
        assert ("07b-neovim.mmd", "exact_plugins_local_src/ (implementations, 14 each)") in src_claim.anchors
        assert ("README.md", "local plugins (14 each)") in local_claim.anchors
        assert ("README.md", "local plugins (14 each)") in src_claim.anchors

        local_failures = m.check_claims(
            REPO,
            [
                m.Claim(local_claim.name, local_claim.globs, local_claim.claimed + 1, local_claim.anchors),
                src_claim,
            ],
        )
        src_failures = m.check_claims(
            REPO,
            [
                local_claim,
                m.Claim(src_claim.name, src_claim.globs, src_claim.claimed + 1, src_claim.anchors),
            ],
        )
        assert any(local_claim.name in failure for failure in local_failures)
        assert any(src_claim.name in failure for failure in src_failures)

    def test_fish_census_is_enforced_in_overview(self):
        """SHOULD keep the Fish subtree count in the enforced census table."""
        m = self._module()
        fish_claim = next(claim for claim in m.CENSUS if claim.globs == ["home/dot_config/fish/*"])

        assert ("00-overview.mmd", f"fish {fish_claim.claimed}") in fish_claim.anchors

    def test_missing_anchor_is_detected(self):
        """SHOULD report when the claimed count is absent from the diagram prose."""
        m = self._module()
        bogus = [m.Claim("bogus", None, m._git_ls_files(REPO, None), [("README.md", "NO_SUCH_ANCHOR_xyz")])]
        failures = m.check_claims(REPO, bogus)
        assert any("anchor not found" in f for f in failures)

    def test_main_passes_on_repo(self):
        """SHOULD exit 0 when run against the repo root."""
        m = self._module()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = m.main([str(REPO)])
        assert rc == 0


if __name__ == "__main__":
    unittest.main()
