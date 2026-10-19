#!/usr/bin/env python3
"""Tests for repository instruction and hook invariants."""

from __future__ import annotations

import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO

SCRIPTS = REPO / "scripts"
LOCAL_SCRIPT_RE = re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]+\.(?:py|sh))(?![A-Za-z0-9_.-])")
HOOK_SCRIPT_REF_RE = re.compile(r"\.\./scripts/([A-Za-z0-9_.-]+\.(?:py|sh))")
HASH_EXPRESSION_RE = re.compile(r"(?:sha256sum|shasum\s+-a\s+256)")


def _local_transform_dependencies(path: Path) -> set[Path]:
    if not path.is_file():
        raise AssertionError(f"missing local transform: {path}")
    if path.suffix == ".sh":
        return {
            SCRIPTS / name for name in LOCAL_SCRIPT_RE.findall(path.read_text(encoding="utf-8")) if name != path.name
        }

    modules = {candidate.stem: candidate for candidate in SCRIPTS.glob("*.py")}
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    dependencies: set[Path] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module.split(".", 1)[0])
        dependencies.update(modules[name] for name in names if name in modules)
    return dependencies


def _transform_closure(paths: set[Path]) -> set[Path]:
    pending = list(paths)
    result: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in result:
            continue
        if not path.is_file():
            raise AssertionError(f"missing local transform: {path}")
        result.add(path)
        pending.extend(_local_transform_dependencies(path) - result)
    return result


class TestUvToolReconciliation(unittest.TestCase):
    @unittest.skipUnless(shutil.which("chezmoi"), "chezmoi is not installed")
    def test_installed_complex_specs_are_reapplied_but_bare_names_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "readonly_dot_python-version").write_text("3.13\n")
            specs = ["ruff", "black==25.1.0", "git+https://example.invalid/tools/lexy.git"]
            (source / "readonly_dot_default-uv-tools.tmpl").write_text("\n".join(specs) + "\n")
            config = root / "chezmoi.toml"
            config.touch()
            bindir = root / "bin"
            bindir.mkdir()
            chezmoi = bindir / "chezmoi"
            chezmoi.write_text(
                "#!/bin/sh\nexec "
                + shlex.join([shutil.which("chezmoi"), "--config", str(config), "--source", str(source)])
                + ' "$@"\n'
            )
            chezmoi.chmod(0o755)
            calls = root / "uv-calls"
            uv = bindir / "uv"
            uv.write_text(
                f"#!{sys.executable}\nimport json, os, sys\n"
                "if sys.argv[1:] == ['tool', 'list']:\n"
                "    print('ruff v1\\nblack v1\\nlexy v1')\n"
                "else:\n"
                "    with open(os.environ['UV_CALLS'], 'a') as log:\n"
                "        log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                "    sys.exit(0 if sys.argv[1:3] == ['tool', 'install'] else 3)\n"
            )
            uv.chmod(0o755)
            env = {"HOME": str(root), "PATH": f"{bindir}:{os.defpath}", "TMPDIR": str(root), "UV_CALLS": str(calls)}
            template = REPO / "home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl"
            rendered = subprocess.run(
                [str(chezmoi), "execute-template"],
                input=template.read_text(),
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            result = subprocess.run(
                ["/bin/bash"],
                input=rendered.stdout,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            actual = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
            self.assertEqual(actual, [["tool", "install", "--force", spec] for spec in specs[1:]])


class TestOnchangeHookHashClosure(unittest.TestCase):
    """WHEN hash-gated hooks call registry-backed helper scripts."""

    def test_SHOULD_hash_every_direct_and_transitive_local_transform(self):
        hooks = sorted((REPO / "home/.chezmoiscripts").glob("run_onchange_after_07-*.sh.tmpl"))
        self.assertTrue(hooks)
        failures: dict[str, list[str]] = {}
        for hook in hooks:
            lines = hook.read_text(encoding="utf-8").splitlines()
            direct = {
                SCRIPTS / name
                for line in lines
                if not HASH_EXPRESSION_RE.search(line)
                for name in HOOK_SCRIPT_REF_RE.findall(line)
            }
            required = {path.name for path in _transform_closure(direct)}
            hashed = {
                name for line in lines if HASH_EXPRESSION_RE.search(line) for name in HOOK_SCRIPT_REF_RE.findall(line)
            }
            missing = sorted(required - hashed)
            if missing:
                failures[hook.name] = missing
        self.assertEqual(failures, {})

    def test_SHOULD_keep_the_llama_sync_helper_in_the_hash_gate(self):
        hook = (REPO / "home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl").read_text()
        helper_hash_lines = [line for line in hook.splitlines() if "sync_llama_cpp_models.py" in line]
        self.assertTrue(any(HASH_EXPRESSION_RE.search(line) for line in helper_hash_lines))


class TestHookOrder(unittest.TestCase):
    """WHEN chezmoi runs after-hooks in target-name order and stops at a failed one."""

    def test_SHOULD_run_the_docker_dependent_redtab_hook_last(self):
        # It fails while Docker Desktop is stopped; any hook after it would be skipped.
        hooks = (REPO / "home/.chezmoiscripts").glob("run_*after_*")
        target_names = sorted(path.name.split("after_", 1)[1] for path in hooks)

        self.assertEqual(target_names[-1], "09-install-redtab.sh.tmpl")


class TestMachineLocalShellExtras(unittest.TestCase):
    """WHEN shell profiles need a git-unmanaged extra source."""

    TAILS = (
        (
            REPO / "home/readonly_dot_profile.tmpl",
            ["[ -f ~/.profile.local ] && source ~/.profile.local"],
        ),
        (
            REPO / "home/readonly_dot_bashrc.tmpl",
            ["[ -f ~/.bashrc.local ] && source ~/.bashrc.local"],
        ),
        (
            REPO / "home/readonly_dot_zshrc.tmpl",
            ["[ -f ~/.zshrc.local ] && source ~/.zshrc.local"],
        ),
        (
            REPO / "home/dot_config/fish/readonly_config.fish.tmpl",
            [
                "if test -f $HOME/.config/fish/config.local.fish",
                "    source $HOME/.config/fish/config.local.fish",
                "end",
            ],
        ),
    )

    def test_SHOULD_source_optional_local_override_as_last_code(self):
        for path, tail in self.TAILS:
            with self.subTest(path=path.name):
                code = [
                    line
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                ]
                self.assertEqual(code[-len(tail) :], tail)

    def test_SHOULD_keep_local_override_files_out_of_source(self):
        forbidden = (
            REPO / "home/dot_profile.local",
            REPO / "home/dot_bashrc.local",
            REPO / "home/dot_zshrc.local",
            REPO / "home/dot_config/fish/config.local.fish",
            REPO / "home/dot_config/fish/readonly_config.local.fish",
        )
        present = [str(path.relative_to(REPO)) for path in forbidden if path.exists()]
        self.assertEqual(present, [])


class TestPrivateRedditSubscriptions(unittest.TestCase):
    """WHEN the personal redtab subscription list stays machine-local in a public repo."""

    def test_SHOULD_keep_the_list_out_of_source_under_any_attribute_prefix(self):
        copies = [str(path.relative_to(REPO)) for path in (REPO / "home/dot_config/redtab").glob("*subscriptions*")]

        self.assertEqual(copies, [])


if __name__ == "__main__":
    unittest.main()
