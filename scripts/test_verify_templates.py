#!/usr/bin/env python3
"""Tests for verify_templates.py."""

from __future__ import annotations

import contextlib
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _test_support  # noqa: F401  (puts scripts/ on sys.path)


class TestVerifyTemplates(unittest.TestCase):
    """WHEN verifying chezmoi templates render before apply."""

    def test_find_templates_excludes_non_tmpl_and_chezmoi_config(self):
        import verify_templates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.tmpl").write_text("x")
            (root / "b.txt").write_text("x")
            (root / ".chezmoi.toml.tmpl").write_text("x")
            (root / "sub").mkdir()
            (root / "sub" / "c.tmpl").write_text("x")

            found = verify_templates.find_templates(root)
            rels = [p.relative_to(root).as_posix() for p in found]
            assert rels == ["a.tmpl", "sub/c.tmpl"]

    def test_render_template_accepts_valid_and_flags_broken(self):
        if shutil.which("chezmoi") is None:
            raise unittest.SkipTest("chezmoi is required to render templates")
        import verify_templates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "good.tmpl"
            good.write_text("os = {{ .chezmoi.os }}\n")
            bad = root / "bad.tmpl"
            bad.write_text("{{ if true }}never closed\n")

            ok, _ = verify_templates.render_template(good)
            assert ok

            ok, message = verify_templates.render_template(bad)
            assert not ok
            assert "template" in message.lower()

    def test_exact_lib_single_include_projection_must_be_byte_identical(self):
        import verify_templates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "home"
            template = source_dir / "exact_lib" / "exact_,tool" / "readonly_main.py.tmpl"
            included = root / "scripts" / "main.py"
            template.parent.mkdir(parents=True)
            included.parent.mkdir(parents=True)
            included.write_bytes(b"print('ok')\n")
            template.write_text('{{ include "../scripts/main.py" }}\n')

            message = verify_templates.exact_projection_error(
                template,
                source_dir,
                included.read_bytes() + b"\n",
            )

        assert message is not None
        assert "byte-identical" in message

    def test_render_pins_chezmoi_to_the_supplied_source_checkout(self):
        import verify_templates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "home"
            source_dir.mkdir()
            (root / ".chezmoiroot").write_text("home\n")
            template = source_dir / "value.tmpl"
            template.write_text("value")
            completed = subprocess.CompletedProcess([], 0, stdout=b"value", stderr=b"")
            with patch.object(verify_templates.subprocess, "run", return_value=completed) as run:
                ok, _ = verify_templates.render_template(template, source_dir)

        assert ok
        assert run.call_args.args[0] == ["chezmoi", "--source", str(root.resolve()), "execute-template"]

    def test_render_keeps_a_standalone_source_directory_scoped(self):
        import verify_templates

        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "source"
            source_dir.mkdir()
            template = source_dir / "value.tmpl"
            template.write_text("value")
            completed = subprocess.CompletedProcess([], 0, stdout=b"value", stderr=b"")
            with patch.object(verify_templates.subprocess, "run", return_value=completed) as run:
                ok, _ = verify_templates.render_template(template, source_dir)

        assert ok
        assert run.call_args.args[0] == ["chezmoi", "--source", str(source_dir.resolve()), "execute-template"]

    def test_main_returns_nonzero_when_a_template_is_broken(self):
        if shutil.which("chezmoi") is None:
            raise unittest.SkipTest("chezmoi is required to render templates")
        import verify_templates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.tmpl").write_text("{{ .chezmoi.os }}\n")
            (root / "bad.tmpl").write_text("{{ end }}\n")

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = verify_templates.main([str(root)])
            assert rc == 1

    def test_main_passes_on_only_valid_templates(self):
        if shutil.which("chezmoi") is None:
            raise unittest.SkipTest("chezmoi is required to render templates")
        import verify_templates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.tmpl").write_text("{{ .chezmoi.os }}\n")

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = verify_templates.main([str(root)])
            assert rc == 0


if __name__ == "__main__":
    unittest.main()
