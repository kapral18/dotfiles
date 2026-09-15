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


PI_RUNTIME = REPO / "home/exact_lib/exact_,doctor/readonly_pi_runtime.py"


def _pi_store(root: Path, store: str, peers: tuple[str, ...]) -> Path:
    """pnpm global-store layout: <store>/node_modules/@earendil-works/pi-coding-agent -> ../.pnpm/<key>/node_modules/..."""
    pnpm_dir = (
        root / "pnpm/global/v11" / store / "node_modules/.pnpm/@earendil-works+pi-coding-agent@0.85.1/node_modules"
    )
    for pkg in peers:
        (pnpm_dir / pkg).mkdir(parents=True)
        (pnpm_dir / pkg / "package.json").write_text('{"name": "%s"}' % pkg, encoding="utf-8")
    host = pnpm_dir / "@earendil-works/pi-coding-agent"
    (host / "dist/bundle").mkdir(parents=True, exist_ok=True)
    (host / "dist/bundle/cli.js").write_text("", encoding="utf-8")
    top = root / "pnpm/global/v11" / store / "node_modules/@earendil-works"
    top.mkdir(parents=True)
    (top / "pi-coding-agent").symlink_to(host)
    return top / "pi-coding-agent/dist/bundle/cli.js"


def _pi_shim(root: Path, target: Path) -> Path:
    shim = root / "bin/pi"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(f'#!/bin/sh\nexec node "{target}" "$@"\n# cmd-shim-target={target}\n', encoding="utf-8")
    shim.chmod(0o755)
    return shim


class TestPiRuntimeProbe(unittest.TestCase):
    PEERS = (
        "@earendil-works/pi-coding-agent",
        "@earendil-works/pi-agent-core",
        "@earendil-works/pi-tui",
        "@earendil-works/pi-ai",
        "typebox",
        "@earendil-works/chord",
    )

    def _probe(self, shim: Path) -> dict:
        result = subprocess.run(
            ["python3", str(PI_RUNTIME), "--shim", str(shim)], capture_output=True, text=True, check=True
        )
        return json.loads(result.stdout)

    def test_live_store_with_every_peer_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cli = _pi_store(root, "2454-18d50b07e3fd3cc8-0", self.PEERS)
            report = self._probe(_pi_shim(root, cli))
            self.assertEqual(report["status"], "pass", report)
            self.assertIn("2454-18d50b0", report["detail"])

    def test_removed_store_warns_with_reinstall_hint(self) -> None:
        """The audited failure: `pnpm add -g` pruned the store the shim (and a live Pi) still named."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cli = _pi_store(root, "a3ab-18d5073542a15678-0", self.PEERS)
            shim = _pi_shim(root, cli)
            shutil.rmtree(root / "pnpm/global/v11/a3ab-18d5073542a15678-0")
            report = self._probe(shim)
            self.assertEqual(report["status"], "warn", report)
            self.assertIn("removed install", report["detail"])
            self.assertIn("pnpm add -g @earendil-works/pi-coding-agent", report["hint"])

    def test_missing_peer_names_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cli = _pi_store(root, "2454-18d50b07e3fd3cc8-0", tuple(p for p in self.PEERS if p != "typebox"))
            report = self._probe(_pi_shim(root, cli))
            self.assertEqual(report["status"], "warn", report)
            self.assertIn("typebox", report["detail"])

    def test_peer_directory_with_foreign_manifest_name_is_missing(self) -> None:
        """Mirrors the runner: a directory named like the peer but whose manifest names another package does not resolve."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cli = _pi_store(root, "2454-18d50b07e3fd3cc8-0", self.PEERS)
            pnpm_dir = (
                root
                / "pnpm/global/v11/2454-18d50b07e3fd3cc8-0/node_modules/.pnpm/@earendil-works+pi-coding-agent@0.85.1/node_modules"
            )
            (pnpm_dir / "typebox/package.json").write_text('{"name": "not-typebox"}', encoding="utf-8")
            report = self._probe(_pi_shim(root, cli))
            self.assertEqual(report["status"], "warn", report)
            self.assertIn("typebox", report["detail"])

    def test_absent_shim_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = self._probe(Path(tmp) / "nope")
            self.assertEqual(report["status"], "skip", report)

    def test_doctor_surfaces_the_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            (home / "lib" / ",doctor").mkdir(parents=True)
            shutil.copy(PI_RUNTIME, home / "lib/,doctor/pi_runtime.py")
            cli = _pi_store(root, "a3ab-18d5073542a15678-0", self.PEERS)
            shim = _pi_shim(home, cli)
            shutil.rmtree(root / "pnpm/global/v11/a3ab-18d5073542a15678-0")
            result = _run_doctor(
                home, "--quiet", env_extra={"PATH": os.pathsep.join((str(shim.parent), os.environ["PATH"]))}
            )
            self.assertIn("Pi runtime: pi shim targets a removed install", result.stdout)


if __name__ == "__main__":
    unittest.main()
