#!/usr/bin/env python3
"""Tests immutable GH picker dispatch state in batch worktree completion."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import TMUX_PICKERS, modern_bash


class TestGhPickerDispatchState(unittest.TestCase):
    """WHEN background batch worktree updates picker cache/reload state."""

    def _write_executable(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o755)

    def _run_background_batch(
        self, script: Path, selection_file: Path, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [modern_bash(), str(script), str(selection_file), "--background"],
            capture_output=True,
            text=True,
            env=env,
        )

    def _setup_fixture(self, tmp_path: Path) -> dict[str, Path]:
        home = tmp_path / "home"
        cache_home = tmp_path / "cache"
        cache_dir = cache_home / "tmux"
        cache_dir.mkdir(parents=True)
        (home / "bin").mkdir(parents=True)

        patcher = home / ".config/tmux/scripts/pickers/github/lib/gh_patch_picker_cache.py"
        self._write_executable(
            patcher,
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import argparse
                import os

                parser = argparse.ArgumentParser()
                parser.add_argument("--cache-file", required=True)
                parser.add_argument("--kind", required=True)
                parser.add_argument("--repo", required=True)
                parser.add_argument("--num", required=True)
                parser.add_argument("--state", required=True)
                args = parser.parse_args()

                with open(os.environ["PATCH_LOG"], "a", encoding="utf-8") as fh:
                    fh.write(
                        f"{args.cache_file}\\t{args.kind}\\t{args.repo}\\t{args.num}\\t{args.state}\\n"
                    )
                """
            ),
        )

        self._write_executable(
            home / "bin/,gh-worktree",
            "#!/usr/bin/env bash\nexit 0\n",
        )

        self._write_executable(
            home / "bin/curl",
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                printf '%s\\n' "$*" >> "$CURL_LOG"
                exit 0
                """
            ),
        )

        selection_file = tmp_path / "selection.tsv"
        selection_file.write_text("PR 123\tpr\towner/repo\t123\thttps://example.test/pr/123\n")

        work_cache = cache_dir / "gh_picker_work.tsv"
        home_cache = cache_dir / "gh_picker_home.tsv"
        work_cache.write_text("work-cache\n")
        home_cache.write_text("home-cache\n")

        return {
            "home": home,
            "cache_home": cache_home,
            "cache_dir": cache_dir,
            "selection_file": selection_file,
            "work_cache": work_cache,
            "home_cache": home_cache,
            "patch_log": tmp_path / "patch.log",
            "curl_log": tmp_path / "curl.log",
        }

    def test_background_completion_targets_origin_dispatch_not_latest_global_picker(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            cache_dir = fixture["cache_dir"]
            (cache_dir / "gh_picker_mode").write_text("home")
            (cache_dir / "gh_picker_scope").write_text("focus")
            (cache_dir / "gh_picker_port").write_text("5151")

            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, fixture["selection_file"], env)
            assert result.returncode == 0, result.stderr

            patch_log = fixture["patch_log"].read_text()
            assert str(fixture["work_cache"]) in patch_log
            assert str(fixture["home_cache"]) not in patch_log

            curl_log = fixture["curl_log"].read_text()
            assert "127.0.0.1:4141" in curl_log
            assert "127.0.0.1:5151" not in curl_log
            assert "GH_PICKER_MODE=work" in curl_log
            assert "GH_PICKER_SCOPE=all" in curl_log
            assert "GH_PICKER_MODE=home" not in curl_log
            assert "GH_PICKER_SCOPE=focus" not in curl_log

    def test_single_picker_fallback_still_uses_shared_global_state_when_dispatch_missing(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            cache_dir = fixture["cache_dir"]
            (cache_dir / "gh_picker_mode").write_text("home")
            (cache_dir / "gh_picker_scope").write_text("focus")
            (cache_dir / "gh_picker_port").write_text("5151")

            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, fixture["selection_file"], env)
            assert result.returncode == 0, result.stderr

            patch_log = fixture["patch_log"].read_text()
            assert str(fixture["home_cache"]) in patch_log
            assert str(fixture["work_cache"]) not in patch_log

            curl_log = fixture["curl_log"].read_text()
            assert "127.0.0.1:5151" in curl_log
            assert "GH_PICKER_MODE=home" in curl_log
            assert "GH_PICKER_SCOPE=focus" in curl_log


if __name__ == "__main__":
    unittest.main()
