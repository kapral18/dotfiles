#!/usr/bin/env python3
"""Focused tests for install yarn pkgs."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestInstallYarnPkgs(unittest.TestCase):
    """WHEN syncing global yarn packages with optional version pins."""

    def _fixture(self, tmp: str, desired: str, installed: dict[str, str]):
        home = Path(tmp) / "home"
        home.mkdir()
        (home / ".default-yarn-pkgs").write_text(desired, encoding="utf-8")
        bindir = Path(tmp) / "bin"
        bindir.mkdir()
        global_dir = Path(tmp) / "yarn-global"
        (global_dir / "node_modules").mkdir(parents=True)
        (global_dir / "package.json").write_text(json.dumps({"dependencies": dict.fromkeys(installed, "*")}))
        for name, version in installed.items():
            pkg_dir = global_dir / "node_modules" / name
            pkg_dir.mkdir(parents=True, exist_ok=True)
            (pkg_dir / "package.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        log = Path(tmp) / "yarn.log"
        yarn = bindir / "yarn"
        yarn.write_text(
            f'#!/usr/bin/env bash\nif [[ "$1 $2" == "global dir" ]]; then\n  echo "{global_dir}"\n  exit 0\nfi\n'
            f'echo "$*" >> "{log}"\nexit 0\n',
            encoding="utf-8",
        )
        yarn.chmod(0o755)
        return home, bindir, log

    def _run(self, home: Path, bindir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [modern_bash(), str(REPO / "home/exact_bin/executable_,install-yarn-pkgs")],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home), "PATH": f"{bindir}:{os.environ['PATH']}"},
        )

    def test_SHOULD_repin_pinned_packages_and_upgrade_only_unpinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log = self._fixture(
                tmp,
                "pinned@1.2.3\n@org/scoped@2.0.0\nunpinned\n",
                {"pinned": "1.0.0", "@org/scoped": "2.0.0", "unpinned": "0.9.0"},
            )
            result = self._run(home, bindir)
            actions = log.read_text(encoding="utf-8").splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        # Wrong-version pin is re-installed at the exact pin; matching pin is left alone.
        assert "global add pinned@1.2.3" in actions
        assert not any("add @org/scoped" in action for action in actions)
        # Pinned packages are never upgraded; the unpinned one is.
        assert "global upgrade unpinned --latest" in actions
        assert not any(action.startswith("global upgrade pinned") for action in actions)
        assert not any(action.startswith("global upgrade @org/scoped") for action in actions)

    def test_SHOULD_install_missing_with_pin_and_remove_undesired(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log = self._fixture(tmp, "new-pkg@3.1.0\nfresh\n", {"stray": "1.0.0"})
            result = self._run(home, bindir)
            actions = log.read_text(encoding="utf-8").splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        assert "global add new-pkg@3.1.0" in actions
        assert "global add fresh@latest" in actions
        assert "global remove stray" in actions


if __name__ == "__main__":
    unittest.main()
