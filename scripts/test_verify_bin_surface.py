#!/usr/bin/env python3
"""Tests for verify_bin_surface.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)


class TestVerifyBinSurface(unittest.TestCase):
    """WHEN validating comma-command discoverability."""

    def test_reports_missing_completion_docs_and_catalog(self):
        import verify_bin_surface

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/dot_config/fish/completions").mkdir(parents=True)
            (root / "docs/topics/workflow/custom-commands").mkdir(parents=True)
            (root / ".mermaids").mkdir(parents=True)

            (root / "home/exact_bin/executable_,missing").write_text("#!/bin/sh\n")
            (root / "docs/topics/workflow/custom-commands/index.md").write_text("| `,other` | Other |\n")
            (root / ".mermaids/07c-bin-commands.mmd").write_text('G[",other"]\n')

            failures = verify_bin_surface.check_bin_surface(root)

        assert any("missing Fish completion" in failure for failure in failures)
        assert any("missing docs token" in failure for failure in failures)
        assert any("missing catalog token" in failure for failure in failures)

    def test_accepts_template_command_with_matching_surface(self):
        import verify_bin_surface

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/dot_config/fish/completions").mkdir(parents=True)
            (root / "docs/topics/workflow/custom-commands").mkdir(parents=True)
            (root / ".mermaids").mkdir(parents=True)

            (root / "home/exact_bin/executable_,templated.tmpl").write_text("#!/bin/sh\n")
            (root / "home/dot_config/fish/completions/readonly_,templated.fish").write_text(
                "complete -c ,templated --no-files\n"
            )
            (root / "docs/topics/workflow/custom-commands/catalog.md").write_text("| `,templated` | Templated |\n")
            (root / ".mermaids/07c-bin-commands.mmd").write_text('G[",templated"]\n')

            failures = verify_bin_surface.check_bin_surface(root)

        assert failures == []

    def test_mermaid_matcher_requires_exact_command_token(self):
        import verify_bin_surface

        assert verify_bin_surface._mermaid_mentions_command('L[",w/main.sh"]\n', "w")
        assert not verify_bin_surface._mermaid_mentions_command('A[",copilot-cloudflare"]\n', "copilot")

    def test_accepts_command_library_with_matching_command(self):
        import verify_bin_surface

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/exact_lib/exact_,library").mkdir(parents=True)
            (root / "home/dot_config/fish/completions").mkdir(parents=True)
            (root / "docs/topics/workflow/custom-commands").mkdir(parents=True)
            (root / ".mermaids").mkdir(parents=True)

            (root / "home/exact_bin/executable_,library").write_text("#!/bin/sh\n")
            (root / "home/exact_lib/exact_,library/main.py").write_text("print('library')\n")
            (root / "home/dot_config/fish/completions/readonly_,library.fish").write_text(
                "complete -c ,library --no-files\n"
            )
            (root / "docs/topics/workflow/custom-commands/catalog.md").write_text("| `,library` | Library-backed |\n")
            (root / ".mermaids/07c-bin-commands.mmd").write_text('G[",library"]\n')

            failures = verify_bin_surface.check_bin_surface(root)

        assert failures == []

    def test_reports_orphaned_command_library(self):
        import verify_bin_surface

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/exact_lib/exact_,orphan").mkdir(parents=True)
            (root / "docs/topics/workflow/custom-commands").mkdir(parents=True)
            (root / ".mermaids").mkdir(parents=True)

            (root / "home/exact_lib/exact_,orphan/main.py").write_text("print('orphan')\n")
            (root / "docs/topics/workflow/custom-commands/index.md").write_text("No commands yet.\n")
            (root / ".mermaids/07c-bin-commands.mmd").write_text("No commands yet.\n")

            failures = verify_bin_surface.check_bin_surface(root)

        assert any(
            "command library" in failure and "has no matching command or explicit launcher reference" in failure
            for failure in failures
        )

    def test_accepts_shared_command_library_referenced_by_multiple_launchers(self):
        import verify_bin_surface

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/exact_lib/exact_,adapter").mkdir(parents=True)
            (root / "home/dot_config/fish/completions").mkdir(parents=True)
            (root / "docs/topics/workflow/custom-commands").mkdir(parents=True)
            (root / ".mermaids").mkdir(parents=True)

            (root / "home/exact_lib/exact_,adapter/main.py").write_text("print('adapter')\n")
            for name in ("one", "two"):
                (root / f"home/exact_bin/executable_,{name}").write_text(
                    '#!/bin/sh\nexec python3 "$HOME/lib/,adapter/main.py"\n'
                )
                (root / f"home/dot_config/fish/completions/readonly_,{name}.fish").write_text(
                    f"complete -c ,{name} --no-files\n"
                )
            (root / "docs/topics/workflow/custom-commands/catalog.md").write_text(
                "| `,one` | Adapter |\n| `,two` | Adapter |\n"
            )
            (root / ".mermaids/07c-bin-commands.mmd").write_text('G[",one · ,two"]\n')

            failures = verify_bin_surface.check_bin_surface(root)

        assert failures == []

    def test_reports_provider_variant_without_matching_docs_token(self):
        import verify_bin_surface

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/dot_config/fish/completions").mkdir(parents=True)
            (root / "docs/topics/workflow/custom-commands").mkdir(parents=True)
            (root / ".mermaids").mkdir(parents=True)

            (root / "home/exact_bin/executable_,copilot").write_text("#!/bin/sh\n")
            (root / "home/dot_config/fish/completions/readonly_,copilot.fish").write_text(
                "complete -c ,copilot --no-files\n"
            )
            (root / "docs/topics/workflow/custom-commands/catalog.md").write_text(
                "| `,copilot-cloudflare` | Variant |\n"
            )
            (root / ".mermaids/07c-bin-commands.mmd").write_text('A[",copilot"]\n')

            failures = verify_bin_surface.check_bin_surface(root)

        assert any("missing docs token" in failure for failure in failures)

    def test_reports_provider_variant_without_matching_catalog_token(self):
        import verify_bin_surface

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/dot_config/fish/completions").mkdir(parents=True)
            (root / "docs/topics/workflow/custom-commands").mkdir(parents=True)
            (root / ".mermaids").mkdir(parents=True)

            (root / "home/exact_bin/executable_,copilot").write_text("#!/bin/sh\n")
            (root / "home/dot_config/fish/completions/readonly_,copilot.fish").write_text(
                "complete -c ,copilot --no-files\n"
            )
            (root / "docs/topics/workflow/custom-commands/catalog.md").write_text("| `,copilot` | Base |\n")
            (root / ".mermaids/07c-bin-commands.mmd").write_text('A[",copilot-cloudflare"]\n')

            failures = verify_bin_surface.check_bin_surface(root)

        assert any("missing catalog token" in failure for failure in failures)

    def test_reports_empty_docs_directory(self):
        import verify_bin_surface

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/exact_bin").mkdir(parents=True)
            (root / "home/dot_config/fish/completions").mkdir(parents=True)
            (root / "docs/topics/workflow/custom-commands").mkdir(parents=True)
            (root / ".mermaids").mkdir(parents=True)

            (root / "home/exact_bin/executable_,emptydocs").write_text("#!/bin/sh\n")
            (root / "home/dot_config/fish/completions/readonly_,emptydocs.fish").write_text(
                "complete -c ,emptydocs --no-files\n"
            )
            (root / ".mermaids/07c-bin-commands.mmd").write_text('G[",emptydocs"]\n')

            failures = verify_bin_surface.check_bin_surface(root)

        assert any("docs file missing" in failure for failure in failures)


if __name__ == "__main__":
    unittest.main()
