#!/usr/bin/env python3
"""Behavioral tests for the `,doctor` command."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import generated_artifact_ledger
from _test_support import REPO

DOCTOR = REPO / "home/exact_lib/exact_,doctor/main.sh"


def _run_doctor(home: Path, *args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HOME": str(home), "XDG_STATE_HOME": str(home / ".local/state")}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(DOCTOR), *args],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
    )


def _make_source(root: Path) -> Path:
    """Hermetic CHEZMOI_SOURCE_DIR with a working manifest helper at ../scripts."""
    src = root / "src"
    (src / ".chezmoiscripts").mkdir(parents=True)
    helper_dir = root / "scripts"
    helper_dir.mkdir(exist_ok=True)
    shutil.copy(REPO / "scripts/managed_config_manifest.py", helper_dir / "managed_config_manifest.py")
    return src


def _write_manifest(home: Path, rows: list[tuple[str, str]]) -> Path:
    state = home / ".local/state/chezmoi"
    state.mkdir(parents=True, exist_ok=True)
    manifest = state / "managed_configs.tsv"
    manifest.write_text(
        "".join(f"{target}\t{checksum}\t2026-09-14T00:00:00Z\n" for target, checksum in rows),
        encoding="utf-8",
    )
    return manifest


def _install_ai_py(home: Path) -> None:
    lib = home / "lib" / ",doctor"
    lib.mkdir(parents=True)
    shutil.copy(REPO / "scripts/generated_artifact_ledger.py", lib / "ai.py")


def _write_ledger(home: Path, artifact: dict) -> None:
    state = home / ".local/state/chezmoi"
    state.mkdir(parents=True, exist_ok=True)
    (state / "generated_artifacts.v1.json").write_text(
        json.dumps({"schema_version": 1, "artifacts": {artifact["artifact_id"]: artifact}}),
        encoding="utf-8",
    )


def _ledger_artifact(target: str, ownership: dict, expected: str, producer: str = "07-fake") -> dict:
    return {
        "artifact_id": "fake-mcp",
        "producer": producer,
        "profile": "work",
        "target": target,
        "inputs": [],
        "input_hashes": {},
        "transforms": [],
        "transform_hashes": {},
        "references": [],
        "ownership": ownership,
        "expected_semantic_hash": expected,
        "consumer": {"id": "fake", "command": ["fake"]},
        "live_probe": {"kind": "command", "argv": ["fake", "--version"]},
        "recorded_at": "2026-09-14T00:00:00Z",
    }


class TestDoctor(unittest.TestCase):
    def test_missing_antigravity_configs_are_reported_when_agy_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bindir = home / "bin"
            bindir.mkdir()
            agy = bindir / "agy"
            agy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            agy.chmod(0o755)

            result = subprocess.run(
                ["bash", str(DOCTOR), "--quiet"],
                cwd=home,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": os.pathsep.join((str(bindir), os.environ["PATH"])),
                    "XDG_STATE_HOME": str(home / ".local/state"),
                },
                capture_output=True,
                text=True,
            )

            self.assertIn("Antigravity hooks missing", result.stdout)
            self.assertIn("Antigravity MCP missing", result.stdout)

    def test_stale_missing_entry_is_retired_silently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            src = _make_source(root)
            target = str(home / "no-longer-generated.json")
            manifest = _write_manifest(home, [(target, "0" * 64)])

            result = _run_doctor(home, "--quiet", env_extra={"CHEZMOI_SOURCE_DIR": str(src)})

            self.assertNotIn("was managed", result.stdout)
            self.assertNotIn("no-longer-generated", result.stdout)
            self.assertNotIn(target, manifest.read_text(encoding="utf-8"))

    def test_removed_upstream_entry_is_retired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            src = _make_source(root)
            (src / ".chezmoiremove").write_text(".local/bin/old-tool\n", encoding="utf-8")
            target = str(home / ".local/bin/old-tool")
            manifest = _write_manifest(home, [(target, "0" * 64)])

            result = _run_doctor(home, "--quiet", env_extra={"CHEZMOI_SOURCE_DIR": str(src)})

            self.assertNotIn("was managed", result.stdout)
            self.assertNotIn(target, manifest.read_text(encoding="utf-8"))

    def test_missing_produced_entry_warns_with_rerun_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            src = _make_source(root)
            (src / ".chezmoiscripts" / "run_onchange_after_07-fake.sh").write_text(
                '#!/bin/sh\necho "$HOME/.fake-tool/settings.json"\n', encoding="utf-8"
            )
            target = str(home / ".fake-tool/settings.json")
            _write_manifest(home, [(target, "0" * 64)])

            result = _run_doctor(home, "--quiet", env_extra={"CHEZMOI_SOURCE_DIR": str(src)})

            self.assertIn("missing (was managed)", result.stdout)
            self.assertIn("~/.fake-tool/settings.json", result.stdout)
            self.assertIn(
                'chezmoi state delete --bucket=entryState --key="$HOME/.chezmoiscripts/07-fake.sh"',
                result.stdout,
            )

    def test_app_owned_drift_stays_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            src = _make_source(root)
            _install_ai_py(home)
            ownership = {"adapter": "json-selectors", "selectors": ["mcpServers"]}
            recorded = json.dumps({"mcpServers": {"a": {"url": "https://a.invalid"}}}).encode()
            live = json.dumps({"mcpServers": {"a": {"url": "https://a.invalid"}}, "appState": {"n": 1}}).encode()
            target = home / ".claude.json"
            target.write_bytes(live)
            expected = generated_artifact_ledger.semantic_hash(recorded, ownership)
            _write_ledger(home, _ledger_artifact(str(target), ownership, expected))
            _write_manifest(home, [(str(target), hashlib.sha256(recorded).hexdigest())])

            result = _run_doctor(home, "--quiet", env_extra={"CHEZMOI_SOURCE_DIR": str(src)})
            self.assertNotIn("drifted", result.stdout)

            verbose = _run_doctor(home, "--verbose", env_extra={"CHEZMOI_SOURCE_DIR": str(src)})
            self.assertIn("managed keys intact", verbose.stdout)

    def test_owned_drift_warns_with_rerun_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            src = _make_source(root)
            _install_ai_py(home)
            (src / ".chezmoiscripts" / "run_onchange_after_07-fake.sh").write_text(
                "#!/bin/sh\necho fake\n", encoding="utf-8"
            )
            ownership = {"adapter": "json-selectors", "selectors": ["mcpServers"]}
            recorded = json.dumps({"mcpServers": {"a": {"url": "https://a.invalid"}}}).encode()
            live = json.dumps({"mcpServers": {"a": {"url": "https://b.invalid"}}}).encode()
            target = home / ".claude.json"
            target.write_bytes(live)
            expected = generated_artifact_ledger.semantic_hash(recorded, ownership)
            _write_ledger(home, _ledger_artifact(str(target), ownership, expected))
            _write_manifest(home, [(str(target), hashlib.sha256(recorded).hexdigest())])

            result = _run_doctor(home, "--quiet", env_extra={"CHEZMOI_SOURCE_DIR": str(src)})

            self.assertIn("changed outside chezmoi", result.stdout)
            self.assertIn("differ from policy", result.stdout)
            self.assertIn("~/.claude.json", result.stdout)
            self.assertIn(
                'chezmoi state delete --bucket=entryState --key="$HOME/.chezmoiscripts/07-fake.sh"',
                result.stdout,
            )

    def test_whole_file_drift_without_artifact_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            src = _make_source(root)
            target = home / "plain-managed.json"
            target.write_text('{"v": 2}', encoding="utf-8")
            stale = hashlib.sha256(b'{"v": 1}').hexdigest()
            _write_manifest(home, [(str(target), stale)])

            result = _run_doctor(home, "--quiet", env_extra={"CHEZMOI_SOURCE_DIR": str(src)})

            self.assertIn("has drifted from managed state", result.stdout)
            self.assertIn("~/plain-managed.json", result.stdout)

    def test_rerun_hint_targets_entry_state_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            src = _make_source(root)
            (src / ".chezmoiscripts" / "run_onchange_after_07-fake.sh.tmpl").write_text(
                '#!/bin/sh\necho "$HOME/.fake-tool/settings.json"\n', encoding="utf-8"
            )
            (src / ".chezmoiscripts" / "run_onchange_after_07-second.fish.tmpl").write_text(
                '#!/usr/bin/env fish\necho "$HOME/.second/settings.json"\n', encoding="utf-8"
            )
            _write_manifest(
                home,
                [
                    (str(home / ".fake-tool/settings.json"), "0" * 64),
                    (str(home / ".second/settings.json"), "0" * 64),
                ],
            )

            result = _run_doctor(home, "--quiet", env_extra={"CHEZMOI_SOURCE_DIR": str(src)})

            self.assertIn(
                'chezmoi state delete --bucket=entryState --key="$HOME/.chezmoiscripts/07-fake.sh"',
                result.stdout,
            )
            self.assertIn(
                'chezmoi state delete --bucket=entryState --key="$HOME/.chezmoiscripts/07-second.fish"',
                result.stdout,
            )


if __name__ == "__main__":
    unittest.main()
