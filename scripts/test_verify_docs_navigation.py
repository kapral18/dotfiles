#!/usr/bin/env python3
"""Tests for verify_docs_navigation.py."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


class VerifyDocsNavigationTest(unittest.TestCase):
    """WHEN validating docs/reference navigation."""

    def _module(self):
        import verify_docs_navigation

        return verify_docs_navigation

    def _write_reference_docs(self, root: Path, rows: tuple[str, ...] | None = None) -> None:
        rows = self._module().EXPECTED_CATALOG_ROWS if rows is None else rows
        (root / "docs/reference").mkdir(parents=True)
        (root / "docs/topics/example").mkdir(parents=True)
        (root / "home").mkdir()
        (root / "scripts").mkdir()

        (root / "home/example").write_text("source\n", encoding="utf-8")
        (root / "scripts/example.py").write_text("print('ok')\n", encoding="utf-8")
        (root / "docs/topics/example/index.md").write_text("# Example\n", encoding="utf-8")

        (root / "docs/reference/reference-map.md").write_text(
            "\n".join(
                [
                    "# Reference map",
                    "[source](../../home/example)",
                    "[script](../../scripts/example.py)",
                    "[docs](../topics/example/index.md)",
                    "[anchor](#local)",
                    "[external](https://example.com)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (root / "docs/reference/implementation-coverage.md").write_text(
            "\n".join(
                [
                    "| Catalog | Docs |",
                    "| ------- | ---- |",
                    *[f"| `{row}` | [docs](../topics/example/index.md) |" for row in rows],
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_real_docs_navigation_matches_repo(self):
        """SHOULD pass for the committed reference docs."""
        m = self._module()

        failures = m.check_docs_navigation(REPO)

        assert failures == [], "stale docs navigation: " + "; ".join(failures)

    def test_reports_broken_relative_links(self):
        """SHOULD report a checked reference link whose target is missing."""
        m = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_reference_docs(root)
            (root / "docs/reference/reference-map.md").write_text("[missing](../../home/missing)\n", encoding="utf-8")

            failures = m.check_docs_navigation(root)

        assert any("broken link target ../../home/missing" in failure for failure in failures)

    def test_reports_missing_catalog_rows(self):
        """SHOULD report when implementation coverage omits a catalog row."""
        m = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_reference_docs(root, tuple(row for row in m.EXPECTED_CATALOG_ROWS if row != "07c"))

            failures = m.check_docs_navigation(root)

        assert any("missing catalog row `07c`" in failure for failure in failures)

    def test_reports_missing_reference_map_script(self):
        """SHOULD report when the scripts table names a missing script."""
        m = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_reference_docs(root)
            with (root / "docs/reference/reference-map.md").open("a", encoding="utf-8") as handle:
                handle.write(
                    "\n## Scripts (`scripts/`)\n\n| Script | Purpose |\n| ------ | ------- |\n| `missing.py` | Missing |\n"
                )

            failures = m.check_docs_navigation(root)

        assert any("missing scripts/missing.py" in failure for failure in failures)

    def test_main_passes_on_repo(self):
        """SHOULD exit 0 when run against the repo root."""
        m = self._module()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = m.main([str(REPO)])

        assert rc == 0


if __name__ == "__main__":
    unittest.main()
