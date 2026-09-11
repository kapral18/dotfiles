#!/usr/bin/env python3
"""Focused tests for install pnpm pkgs."""

from __future__ import annotations

import pty
import unittest
from unittest.mock import patch

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


FAKE_PNPM = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

state_path = Path(os.environ["FAKE_PNPM_STATE"])
state = json.loads(state_path.read_text(encoding="utf-8"))
state["pnpm_home"] = os.environ["PNPM_HOME"]
args = sys.argv[1:]
state.setdefault("calls", []).append(" ".join(args))
state.setdefault("exotic_settings", []).append(os.environ.get("PNPM_CONFIG_BLOCK_EXOTIC_SUBDEPS"))
if args == ["root", "-g"]:
    state_path.write_text(json.dumps(state), encoding="utf-8")
    if state.get("root_behavior") == "fail":
        print("global root unavailable", file=sys.stderr)
        sys.exit(72)
    print(state["global_workspace"])
    sys.exit(0)

if len(args) >= 3 and args[0] == "-C" and args[2:5] == ["config", "get", "--location=project"]:
    state["config_get_calls"] = state.get("config_get_calls", 0) + 1
    state_path.write_text(json.dumps(state), encoding="utf-8")
    if state.get("config_get_behavior") == "fail":
        print("allowBuilds unavailable", file=sys.stderr)
        sys.exit(72)
    if state.get("config_get_behavior") == "malformed":
        print("not json")
        sys.exit(0)
    print(json.dumps(state.get("allow_builds")))
    sys.exit(0)

if len(args) >= 3 and args[0] == "-C" and args[2:5] == ["config", "set", "--location=project"]:
    state["config_set_calls"] = state.get("config_set_calls", 0) + 1
    if state.get("config_set_behavior") == "fail":
        state_path.write_text(json.dumps(state), encoding="utf-8")
        print("allowBuilds write rejected", file=sys.stderr)
        sys.exit(72)
    state["allow_builds"] = json.loads(args[-1])
    state_path.write_text(json.dumps(state), encoding="utf-8")
    sys.exit(0)

if args == ["ls", "-g", "--json", "--depth", "0"]:
    state["list_calls"] = state.get("list_calls", 0) + 1
    behavior = state.get("list_behaviors", {}).get(str(state["list_calls"]))
    state_path.write_text(json.dumps(state), encoding="utf-8")
    if behavior == "fail":
        print("listing unavailable", file=sys.stderr)
        sys.exit(73)
    if behavior == "malformed":
        print("not json")
        sys.exit(0)
    dependencies = {
        name: {"from": name, **metadata}
        for name, metadata in state["installed"].items()
    }
    print(json.dumps([{ "dependencies": dependencies }]))
    sys.exit(0)

if "--yes" not in args:
    print("expected noninteractive flag", file=sys.stderr)
    sys.exit(1)
if sys.stdin.isatty() and not sys.stdout.isatty():
    print("IO error: not a terminal", file=sys.stderr)
    sys.exit(1)
args.remove("--yes")
action = " ".join(args)
with Path(os.environ["FAKE_PNPM_LOG"]).open("a", encoding="utf-8") as log:
    print(action, file=log)
effect = state.get("effects", {}).get(action)
if effect:
    state["installed"][effect["package"]]["path"] = effect["path"]
state_path.write_text(json.dumps(state), encoding="utf-8")
failure = state.get("failures", {}).get(action)
if failure:
    print("operation output before failure")
    print(failure, file=sys.stderr)
    sys.exit(71)
"""


class TestInstallPnpmPkgs(unittest.TestCase):
    """WHEN syncing global pnpm packages with optional version pins."""

    def _fixture(
        self,
        tmp: str,
        desired: str,
        installed: dict[str, str],
        *,
        list_behaviors: dict[str, str] | None = None,
        failures: dict[str, str] | None = None,
        effects: dict[str, dict[str, str]] | None = None,
        allow_builds: dict[str, object] | None = None,
        root_behavior: str | None = None,
        config_get_behavior: str | None = None,
    ):
        home = Path(tmp) / "home"
        home.mkdir()
        (home / ".default-pnpm-pkgs").write_text(desired, encoding="utf-8")
        bindir = Path(tmp) / "bin"
        bindir.mkdir()
        global_dir = Path(tmp) / "pnpm-global" / "v11"
        state = {
            "installed": {},
            "list_behaviors": list_behaviors or {},
            "failures": failures or {},
            "effects": effects or {},
            "allow_builds": allow_builds,
            "global_workspace": str(global_dir),
            "root_behavior": root_behavior,
            "config_get_behavior": config_get_behavior,
        }
        for name, version in installed.items():
            package_path = global_dir / f"hash-{name.replace('/', '+')}" / "node_modules" / name
            state["installed"][name] = {"version": version, "path": str(package_path)}
        state_path = Path(tmp) / "pnpm-state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        log = Path(tmp) / "pnpm.log"
        pnpm = bindir / "pnpm"
        pnpm.write_text(FAKE_PNPM.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1), encoding="utf-8")
        pnpm.chmod(0o755)
        return home, bindir, log, state_path

    def _run(
        self,
        home: Path,
        bindir: Path,
        log: Path,
        state: Path,
        *,
        path: str | None = None,
        pnpm_home: str | None = None,
        stdin: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(REPO / "home/exact_bin/executable_,install-pnpm-pkgs")],
            capture_output=True,
            stdin=stdin,
            text=True,
            env={
                **os.environ,
                "HOME": str(home),
                "PNPM_HOME": str(home / ".local/share/pnpm") if pnpm_home is None else pnpm_home,
                "PATH": path or f"{bindir}:{os.environ['PATH']}",
                "FAKE_PNPM_LOG": str(log),
                "FAKE_PNPM_STATE": str(state),
            },
        )

    @staticmethod
    def _actions(log: Path) -> list[str]:
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    @staticmethod
    def _link(home: Path, name: str) -> Path:
        return home / ".local/share/pnpm-global-links/node_modules" / name

    def _seed_link(self, home: Path, name: str, target: str) -> None:
        link = self._link(home, name)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)

    def _state_path(self, state: Path, name: str) -> str:
        return json.loads(state.read_text(encoding="utf-8"))["installed"][name]["path"]

    def test_SHOULD_repin_pinned_packages_and_upgrade_only_unpinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(
                tmp,
                "pinned@1.2.3\n@org/scoped@2.0.0\nunpinned\n",
                {"pinned": "1.0.0", "@org/scoped": "2.0.0", "unpinned": "0.9.0"},
            )
            result = self._run(home, bindir, log, state, path=str(bindir))
            actions = self._actions(log)
            recorded = json.loads(state.read_text())
            list_calls = recorded["list_calls"]
            scoped_link_exists = self._link(home, "@org/scoped").is_symlink()

        assert result.returncode == 0, result.stderr
        assert "add -g pinned@1.2.3" in actions
        assert not any("add -g @org/scoped" in action for action in actions)
        assert "update -g --latest unpinned" in actions
        assert not any(action.startswith("update -g --latest pinned") for action in actions)
        assert not any(action.startswith("update -g --latest @org/scoped") for action in actions)
        assert scoped_link_exists
        assert list_calls == 2
        assert recorded["allow_builds"] == {"pinned": True, "@org/scoped": True, "unpinned": True}

    def test_SHOULD_approve_all_desired_top_level_packages_before_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            default_entries = [
                line.strip()
                for line in (REPO / "home/readonly_dot_default-pnpm-pkgs").read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            desired = "\n".join([*default_entries, "@scope/pinned@1.2.3"]) + "\n"
            desired_names = []
            for entry in [*default_entries, "@scope/pinned@1.2.3"]:
                name, marker, _pin = entry.rpartition("@")
                desired_names.append(name if marker and name else entry)
            unrelated = {
                "@google/genai": True,
                "esbuild": False,
                "onnxruntime-node": "placeholder",
                "protobufjs": True,
                "sharp": False,
            }
            installed = {name: "1.2.3" if name == "@scope/pinned" else "1.0.0" for name in desired_names}
            home, bindir, log, state = self._fixture(tmp, desired, installed, allow_builds=unrelated)
            result = self._run(home, bindir, log, state)
            recorded = json.loads(state.read_text(encoding="utf-8"))
            actions = self._actions(log)

        assert result.returncode == 0, result.stderr
        assert recorded["allow_builds"] == {**unrelated, **{name: True for name in desired_names}}
        assert recorded["config_set_calls"] == 1
        assert recorded["calls"][:3] == [
            "root -g",
            f"-C {recorded['global_workspace']} config get --location=project --json allowBuilds",
            f"-C {recorded['global_workspace']} config set --location=project --json allowBuilds "
            f"{json.dumps(recorded['allow_builds'])}",
        ]
        assert any(action.startswith("update -g --latest") for action in actions)

    def test_SHOULD_not_rewrite_build_approvals_when_all_desired_packages_are_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            desired = "plain\n@scope/pinned@1.2.3\n"
            approvals = {"plain": True, "@scope/pinned": True, "unrelated": False}
            home, bindir, log, state = self._fixture(
                tmp,
                desired,
                {"plain": "1.0.0", "@scope/pinned": "1.2.3"},
                allow_builds=approvals,
            )
            result = self._run(home, bindir, log, state)
            recorded = json.loads(state.read_text(encoding="utf-8"))

        assert result.returncode == 0, result.stderr
        assert recorded["allow_builds"] == approvals
        assert recorded.get("config_set_calls", 0) == 0

    def test_SHOULD_stop_before_package_mutation_when_build_approvals_are_unreadable(self):
        for behavior in ("fail", "malformed"):
            with self.subTest(behavior=behavior), tempfile.TemporaryDirectory() as tmp:
                home, bindir, log, state = self._fixture(tmp, "plain\n", {}, config_get_behavior=behavior)
                result = self._run(home, bindir, log, state)
                recorded = json.loads(state.read_text(encoding="utf-8"))

                assert result.returncode == 1
                assert self._actions(log) == []
                assert "ls -g --json --depth 0" not in recorded["calls"]

    def test_SHOULD_install_missing_with_pin_and_remove_undesired(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(tmp, "new-pkg@3.1.0\nfresh\n", {"stray": "1.0.0"})
            result = self._run(home, bindir, log, state)
            actions = self._actions(log)

        assert result.returncode == 0, result.stderr
        assert "add -g new-pkg@3.1.0" in actions
        assert "add -g fresh@latest" in actions
        assert "remove -g stray" in actions

    def test_SHOULD_sync_without_prompt_when_invoked_with_terminal_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(tmp, "current\n", {"current": "1.0.0"})
            master, terminal = pty.openpty()
            try:
                assert os.isatty(terminal)
                result = self._run(home, bindir, log, state, stdin=terminal)
            finally:
                os.close(terminal)
                os.close(master)
            assert result.returncode == 0, result.stderr
            assert self._actions(log) == ["update -g --latest current"]
            assert self._link(home, "current").is_symlink()

    def test_SHOULD_allow_exotic_subdeps_only_for_desired_adds_and_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(
                tmp,
                "fresh\n@org/pinned@2.0.0\ncurrent\n",
                {"@org/pinned": "1.0.0", "current": "1.0.0", "stray": "1.0.0"},
            )
            with patch.dict(os.environ, {"PNPM_CONFIG_BLOCK_EXOTIC_SUBDEPS": "true"}):
                result = self._run(home, bindir, log, state)
                assert os.environ["PNPM_CONFIG_BLOCK_EXOTIC_SUBDEPS"] == "true"
            recorded = json.loads(state.read_text())

        assert result.returncode == 0, result.stderr
        allowed = {
            "add -g fresh@latest --yes",
            "add -g @org/pinned@2.0.0 --yes",
            "update -g --latest fresh --yes",
            "update -g --latest current --yes",
        }
        assert allowed.issubset(recorded["calls"])
        assert "remove -g stray --yes" in recorded["calls"]
        assert len(recorded["calls"]) == len(recorded["exotic_settings"])
        for call, setting in zip(recorded["calls"], recorded["exotic_settings"]):
            assert setting == ("false" if call in allowed else "true"), (call, setting)

    def test_SHOULD_fail_without_pnpm_on_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(tmp, "fresh\n", {})
            (bindir / "pnpm").unlink()
            result = self._run(home, bindir, log, state, path=str(bindir))

        assert result.returncode == 1
        assert "pnpm not found on PATH" in result.stderr

    def test_SHOULD_refresh_moved_links_after_failed_update_and_stop_later_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(
                tmp,
                "moved\nfails\nafter\n@org/scoped@2.0.0\n",
                {"moved": "1.0.0", "fails": "1.0.0", "after": "1.0.0", "@org/scoped": "2.0.0"},
            )
            moved_new = str(Path(tmp) / "new-moved-path")
            self._seed_link(home, "moved", str(Path(tmp) / "old-moved-path"))
            self._seed_link(home, "@org/scoped", str(Path(tmp) / "old-scoped-path"))
            current = json.loads(state.read_text(encoding="utf-8"))
            current["effects"] = {"update -g --latest moved": {"package": "moved", "path": moved_new}}
            current["failures"] = {"update -g --latest fails": "update exploded"}
            state.write_text(json.dumps(current), encoding="utf-8")
            result = self._run(home, bindir, log, state)
            actions = self._actions(log)
            moved_link = self._link(home, "moved")
            scoped_link = self._link(home, "@org/scoped")
            moved_target_after_failure = os.readlink(moved_link)
            scoped_link_exists = scoped_link.is_symlink()

        assert result.returncode == 1
        assert "update exploded" in result.stderr
        assert "operation output before failure" in result.stderr
        assert "All pnpm packages synced successfully" not in result.stdout
        assert moved_target_after_failure == moved_new
        assert scoped_link_exists
        assert "update -g --latest after" not in actions

    def test_SHOULD_leave_old_links_when_initial_listing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(
                tmp, "current\n", {"current": "1.0.0"}, list_behaviors={"1": "fail"}
            )
            old_target = str(Path(tmp) / "old-current-path")
            self._seed_link(home, "current", old_target)
            result = self._run(home, bindir, log, state)
            link_target_after_failure = os.readlink(self._link(home, "current"))
            actions = self._actions(log)

        assert result.returncode == 1
        assert "listing unavailable" in result.stderr
        assert link_target_after_failure == old_target
        assert actions == []

    def test_SHOULD_leave_old_links_when_final_listing_fails_or_is_malformed(self):
        for behavior in ("fail", "malformed"):
            with self.subTest(behavior=behavior), tempfile.TemporaryDirectory() as tmp:
                home, bindir, log, state = self._fixture(
                    tmp,
                    "current\n",
                    {"current": "1.0.0"},
                    list_behaviors={"2": behavior},
                )
                old_target = str(Path(tmp) / "old-current-path")
                self._seed_link(home, "current", old_target)
                result = self._run(home, bindir, log, state)

                assert result.returncode == 1
                assert os.readlink(self._link(home, "current")) == old_target
                assert "update -g --latest current" in self._actions(log)

    def test_SHOULD_refresh_links_after_failed_add_or_remove(self):
        cases = (
            ("new\nexisting\n", {"existing": "1.0.0"}, "add -g new@latest"),
            ("keep\n", {"keep": "1.0.0", "stray": "1.0.0"}, "remove -g stray"),
        )
        for desired, installed, failure_action in cases:
            with self.subTest(failure_action=failure_action), tempfile.TemporaryDirectory() as tmp:
                home, bindir, log, state = self._fixture(tmp, desired, installed)
                moved_target = str(Path(tmp) / "moved-existing-path")
                self._seed_link(home, next(iter(installed)), str(Path(tmp) / "old-existing-path"))
                current = json.loads(state.read_text(encoding="utf-8"))
                current["effects"] = {failure_action: {"package": next(iter(installed)), "path": moved_target}}
                current["failures"] = {failure_action: "mutation exploded"}
                state.write_text(json.dumps(current), encoding="utf-8")
                result = self._run(home, bindir, log, state)

                assert result.returncode == 1
                assert "mutation exploded" in result.stderr
                assert os.readlink(self._link(home, next(iter(installed)))) == moved_target

    def test_SHOULD_remove_stale_links_when_inventory_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(tmp, "# no packages\n\n", {})
            self._seed_link(home, "stale", str(Path(tmp) / "old-path"))
            result = self._run(home, bindir, log, state)
            assert result.returncode == 0, result.stderr
            assert list((home / ".local/share/pnpm-global-links/node_modules").iterdir()) == []
            assert self._actions(log) == []

    def test_SHOULD_report_both_mutation_and_refresh_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(
                tmp,
                "current\n",
                {"current": "1.0.0"},
                list_behaviors={"2": "fail"},
                failures={"update -g --latest current": "upgrade rejected"},
            )
            old_target = str(Path(tmp) / "old-current-path")
            self._seed_link(home, "current", old_target)
            result = self._run(home, bindir, log, state)
            assert result.returncode == 1
            assert "upgrade rejected" in result.stderr
            assert "listing unavailable" in result.stderr
            assert os.readlink(self._link(home, "current")) == old_target

    def test_SHOULD_use_default_when_pnpm_home_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(tmp, "", {})
            result = self._run(home, bindir, log, state, pnpm_home="")
            assert result.returncode == 0, result.stderr
            assert json.loads(state.read_text())["pnpm_home"] == str(home / ".local/share/pnpm")

    def test_SHOULD_report_original_failure_when_link_directory_creation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(
                tmp,
                "current\n",
                {"current": "1.0.0"},
                failures={"update -g --latest current": "upgrade rejected"},
            )
            parent = home / ".local/share/pnpm-global-links"
            parent.parent.mkdir(parents=True)
            parent.write_text("existing file")
            result = self._run(home, bindir, log, state)
            assert result.returncode == 1
            assert "upgrade rejected" in result.stderr
            assert "could not replace stable pnpm links" in result.stderr
            assert parent.read_text() == "existing file"

    def test_SHOULD_replace_symlink_root_without_removing_its_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log, state = self._fixture(tmp, "", {})
            old = Path(tmp) / "external-links"
            old.mkdir()
            (old / "sentinel").write_text("keep")
            root = home / ".local/share/pnpm-global-links/node_modules"
            root.parent.mkdir(parents=True)
            root.symlink_to(old)
            result = self._run(home, bindir, log, state)
            assert result.returncode == 0, result.stderr
            assert not root.is_symlink()
            assert list(root.iterdir()) == []
            assert (old / "sentinel").read_text() == "keep"


if __name__ == "__main__":
    unittest.main()
