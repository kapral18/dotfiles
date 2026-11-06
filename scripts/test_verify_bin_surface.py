#!/usr/bin/env python3
"""Tests for verify_bin_surface.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401
import verify_bin_surface


class TestVerifyBinSurface(unittest.TestCase):
    def test_reports_missing_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/exact_bin/executable_,missing").write_text("#!/bin/sh\n")

            failures = verify_bin_surface.check_bin_surface(root)

        assert len(failures) == 1
        assert ",missing: missing Fish completion" in failures[0]

    def test_accepts_template_command_with_matching_library_without_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/exact_lib/exact_,library").mkdir(parents=True)
            (root / "home/dot_config/fish/completions").mkdir(parents=True)
            (root / "home/exact_bin/executable_,library.tmpl").write_text("#!/bin/sh\n")
            (root / "home/exact_lib/exact_,library/main.py").write_text("print('library')\n")
            (root / "home/dot_config/fish/completions/readonly_,library.fish").write_text(
                "complete -c ,library --no-files\n"
            )

            failures = verify_bin_surface.check_bin_surface(root)

        assert failures == []

    def test_reports_orphaned_command_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/exact_lib/exact_,orphan").mkdir(parents=True)
            (root / "home/exact_lib/exact_,orphan/main.py").write_text("print('orphan')\n")

            failures = verify_bin_surface.check_bin_surface(root)

        assert len(failures) == 1
        assert ",orphan: command library" in failures[0]
        assert "has no matching command or explicit launcher reference" in failures[0]

    def test_accepts_shared_command_library_referenced_by_multiple_launchers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/exact_lib/exact_,adapter").mkdir(parents=True)
            (root / "home/dot_config/fish/completions").mkdir(parents=True)
            (root / "home/exact_lib/exact_,adapter/main.py").write_text("print('adapter')\n")
            for name in ("one", "two"):
                (root / f"home/exact_bin/executable_,{name}").write_text(
                    '#!/bin/sh\nexec python3 "$HOME/lib/,adapter/main.py"\n'
                )
                (root / f"home/dot_config/fish/completions/readonly_,{name}.fish").write_text(
                    f"complete -c ,{name} --no-files\n"
                )

            failures = verify_bin_surface.check_bin_surface(root)

        assert failures == []


if __name__ == "__main__":
    unittest.main()
