#!/usr/bin/env python3
"""Tests for verify_agent_file_sizes.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


class VerifyAgentFileSizesTest(unittest.TestCase):
    """WHEN gating agent reference markdown against the harness view limit."""

    def _module(self):
        import verify_agent_file_sizes

        return verify_agent_file_sizes

    def test_real_agent_tree_passes(self):
        """SHOULD pass for the committed skill/hook tree (no oversized references)."""
        m = self._module()
        offenders = m.oversized_files(REPO)
        assert offenders == [], "oversized agent references: " + "; ".join(
            f"{path} ({size}B)" for path, size in offenders
        )

    def test_oversized_reference_is_reported(self):
        """SHOULD flag a reference markdown file at or over 20480 bytes."""
        m = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ref_dir = repo / m.AGENT_TREE / "exact_skills" / "exact_k-x" / "exact_references"
            ref_dir.mkdir(parents=True)
            (ref_dir / "readonly_big.md").write_text("x" * m.MAX_BYTES, encoding="utf-8")
            (ref_dir / "readonly_small.md").write_text("x" * (m.MAX_BYTES - 1), encoding="utf-8")
            offenders = m.oversized_files(repo)
        assert [(str(path), size) for path, size in offenders] == [
            (
                str(Path(m.AGENT_TREE) / "exact_skills" / "exact_k-x" / "exact_references" / "readonly_big.md"),
                m.MAX_BYTES,
            )
        ]

    def test_skill_md_is_exempt(self):
        """SHOULD ignore SKILL.md files: harness skill loaders deliver them, not the view tool."""
        m = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            skill_dir = repo / m.AGENT_TREE / "exact_skills" / "exact_k-x"
            skill_dir.mkdir(parents=True)
            (skill_dir / "readonly_SKILL.md").write_text("x" * (m.MAX_BYTES * 2), encoding="utf-8")
            (skill_dir / "SKILL.md").write_text("x" * (m.MAX_BYTES * 2), encoding="utf-8")
            assert m.oversized_files(repo) == []

    def test_main_reports_offenders_and_exit_code(self):
        """SHOULD exit non-zero and name the file when the bound is crossed."""
        import contextlib
        import io

        m = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ref_dir = repo / m.AGENT_TREE
            ref_dir.mkdir(parents=True)
            (ref_dir / "readonly_big.md").write_text("x" * m.MAX_BYTES, encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = m.main(["verify_agent_file_sizes.py", str(repo)])
        assert code == 1
        assert "readonly_big.md" in err.getvalue()
