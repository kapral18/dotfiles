#!/usr/bin/env python3
"""Tests for repository instruction and hook invariants."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
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


class TestUvToolsHook(unittest.TestCase):
    """WHEN reconciling uv tool package specs."""

    def test_reapplies_complex_specs_instead_of_key_only_skip(self):
        hook = (REPO / "home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl").read_text()

        assert "uv_spec_requires_reapply()" in hook
        assert '[[ "$spec" != "$key" ]]' in hook
        assert "install_args+=(--force)" in hook
        assert "reapplying declared spec" in hook


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


if __name__ == "__main__":
    unittest.main()
