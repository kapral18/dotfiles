#!/usr/bin/env python3
"""Regression tests for scoped pre-commit formatting and binary-safe probes."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO, modern_bash


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    check: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            env={**os.environ, **(env or {})},
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(f"command timed out after {timeout}s: {' '.join(args)}") from exc
    if check and result.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result


def install_legacy_bash_path(bin_dir: Path, *, brew_prefix: Path | None) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    write_executable(
        bin_dir / "bash",
        """
        #!/bin/sh
        exec /bin/bash "$@"
        """,
    )
    if brew_prefix is None:
        brew_stub = bin_dir / "brew"
        if brew_stub.exists() or brew_stub.is_symlink():
            brew_stub.unlink()
        return

    fallback_bin = brew_prefix / "bin"
    fallback_bin.mkdir(parents=True, exist_ok=True)
    link = fallback_bin / "bash"
    if not link.exists():
        link.symlink_to(modern_bash())
    write_executable(
        bin_dir / "brew",
        f"""
        #!/bin/sh
        if [ "$1" = "--prefix" ] && [ "${{2:-}}" = "bash" ]; then
          printf '%s\\n' {str(brew_prefix)!r}
          exit 0
        fi
        exit 1
        """,
    )


class PreCommitFixture:
    """Disposable repo for exercising the real hook in isolation."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(dir=REPO, prefix=".tmp-pre-commit-")
        self.root = Path(self._tmp.name)
        self.log_path = self.root / "hook.log"
        self.bin_dir = self.root / "test-bin"

    def cleanup(self) -> None:
        self._tmp.cleanup()

    def init_repo(self) -> None:
        run(["git", "init", "-q", "-b", "main"], cwd=self.root)
        run(["git", "config", "user.name", "Test User"], cwd=self.root)
        run(["git", "config", "user.email", "test@example.com"], cwd=self.root)
        run(["git", "config", "commit.gpgsign", "false"], cwd=self.root)
        (self.root / ".githooks").mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / ".githooks/pre-commit", self.root / ".githooks/pre-commit")

    def hook_env(self, *, include_brew: bool = True) -> dict[str, str]:
        install_legacy_bash_path(
            self.bin_dir,
            brew_prefix=self.root / "fake-brew" if include_brew else None,
        )
        return {
            "PATH": f"{self.bin_dir}{os.pathsep}{os.defpath}",
            "HOOK_LOG": str(self.log_path),
            "GIT_PAGER": "cat",
            "TERM": "dumb",
        }

    def install_scoped_formatter_stubs(self) -> None:
        write_executable(
            self.root / "bin/fmt",
            """
            #!/usr/bin/env python3
            import os
            import sys
            from pathlib import Path

            log = Path(os.environ["HOOK_LOG"])
            with log.open("a", encoding="utf-8") as handle:
                handle.write("bin/fmt " + " ".join(sys.argv[1:]) + "\\n")

            staged = Path.cwd() / "staged.txt"
            args = sys.argv[1:]
            if args == ["--check", "staged.txt"]:
                raise SystemExit(0 if staged.read_text(encoding="utf-8") == "formatted\\n" else 1)
            if args == ["staged.txt"]:
                staged.write_text("formatted\\n", encoding="utf-8")
                raise SystemExit(0)
            raise SystemExit(f"unexpected fmt args: {args!r}")
            """,
        )
        write_executable(
            self.bin_dir / "make",
            """
            #!/usr/bin/env python3
            import os
            import sys
            from pathlib import Path

            log = Path(os.environ["HOOK_LOG"])
            with log.open("a", encoding="utf-8") as handle:
                handle.write("make " + " ".join(sys.argv[1:]) + "\\n")

            repo = Path.cwd()
            staged = repo / "staged.txt"
            dirty = repo / "dirty.txt"
            args = sys.argv[1:]
            if args == ["-s", "check"]:
                raise SystemExit(0 if staged.read_text(encoding="utf-8") == "formatted\\n" else 1)
            if args == ["-s", "fmt"]:
                staged.write_text("formatted\\n", encoding="utf-8")
                dirty.write_bytes(b"MUTATED BY GLOBAL FMT\\n")
                raise SystemExit(0)
            raise SystemExit(f"unexpected make args: {args!r}")
            """,
        )

    def read_log(self) -> list[str]:
        if not self.log_path.exists():
            return []
        return [line for line in self.log_path.read_text(encoding="utf-8").splitlines() if line]


class TestPreCommitHook(unittest.TestCase):
    """WHEN the repo pre-commit hook formats staged files."""

    def setUp(self) -> None:
        self.fixture = PreCommitFixture()
        self.addCleanup(self.fixture.cleanup)
        self.fixture.init_repo()
        self.fixture.install_scoped_formatter_stubs()
        self.env = self.fixture.hook_env()

    def _prepare_dirty_repo(self) -> tuple[Path, bytes]:
        root = self.fixture.root
        staged = root / "staged.txt"
        dirty = root / "dirty.txt"
        staged.write_text("formatted\n", encoding="utf-8")
        dirty.write_bytes(b"dirty baseline\n")
        run(["git", "add", "staged.txt", "dirty.txt"], cwd=root)
        run(["git", "commit", "-q", "-m", "init"], cwd=root)

        staged.write_text("needs formatting\n", encoding="utf-8")
        run(["git", "add", "staged.txt"], cwd=root)

        dirty_bytes = b"leave these bytes alone\n"
        dirty.write_bytes(dirty_bytes)
        return dirty, dirty_bytes

    def _run_hook(
        self,
        *,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        hook = self.fixture.root / ".githooks/pre-commit"
        return run([str(hook)], cwd=self.fixture.root, env=env or self.env, check=False, timeout=timeout)

    def test_WHEN_path_bash_is_legacy_and_brew_is_missing_SHOULD_exit_promptly_with_error(self):
        """SHOULD fail fast instead of recursively execing /bin/bash."""
        result = self._run_hook(env=self.fixture.hook_env(include_brew=False), timeout=2)

        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == "error: bash 4+ required (mapfile)\n"
        assert self.fixture.read_log() == []

    def test_WHEN_a_staged_file_needs_repair_SHOULD_scope_bin_fmt_before_make_check(self):
        """SHOULD repair only the staged path, then run the full repo check once."""
        self._prepare_dirty_repo()

        result = self._run_hook()

        assert result.returncode == 0, result.stderr
        assert self.fixture.read_log() == [
            "bin/fmt --check staged.txt",
            "bin/fmt staged.txt",
            "make -s check",
        ]
        staged_index = run(["git", "show", ":staged.txt"], cwd=self.fixture.root).stdout
        assert staged_index == "formatted\n"

    def test_WHEN_scoped_repair_runs_SHOULD_preserve_unrelated_dirty_file_bytes(self):
        """SHOULD leave an unrelated unstaged file byte-identical."""
        dirty, original_bytes = self._prepare_dirty_repo()

        result = self._run_hook()

        assert result.returncode == 0, result.stderr
        assert dirty.read_bytes() == original_bytes

    def test_WHEN_a_staged_file_has_unstaged_edits_SHOULD_refuse_partial_staging(self):
        """SHOULD abort before formatting so partial staging stays intact."""
        root = self.fixture.root
        partial = root / "partial.txt"
        partial.write_text(
            "\n".join(
                [
                    "line 1",
                    "line 2",
                    "line 3",
                    "line 4",
                    "line 5",
                    "line 6",
                    "line 7",
                    "line 8",
                    "line 9",
                    "line 10",
                    "line 11",
                    "line 12",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        run(["git", "add", "partial.txt"], cwd=root)
        run(["git", "commit", "-q", "-m", "base"], cwd=root)

        partial.write_text(
            "\n".join(
                [
                    "line 1 staged",
                    "line 2",
                    "line 3",
                    "line 4",
                    "line 5",
                    "line 6",
                    "line 7",
                    "line 8",
                    "line 9",
                    "line 10",
                    "line 11",
                    "line 12 unstaged",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        run(
            ["git", "add", "-p", "partial.txt"],
            cwd=root,
            env=self.env,
            input_text="y\nn\n",
        )

        result = self._run_hook()

        assert result.returncode == 1
        assert "refusing to auto-format with unstaged changes in: partial.txt" in result.stderr
        assert self.fixture.read_log() == []

    def test_WHEN_global_commit_signing_is_enabled_SHOULD_disable_it_in_fixture_repo(self):
        """SHOULD keep fixture commits local-only even when HOME forces signing."""
        signing_home = tempfile.TemporaryDirectory(dir=REPO, prefix=".tmp-signing-home-")
        self.addCleanup(signing_home.cleanup)
        home = Path(signing_home.name)
        (home / ".gitconfig").write_text(
            textwrap.dedent(
                """
                [commit]
                    gpgsign = true
                [gpg]
                    program = /no/such/gpg
                """
            ).lstrip("\n"),
            encoding="utf-8",
        )
        env = {**self.env, "HOME": str(home)}
        signed = self.fixture.root / "signed.txt"
        signed.write_text("ok\n", encoding="utf-8")

        local_sign = run(["git", "config", "--local", "--get", "commit.gpgsign"], cwd=self.fixture.root).stdout.strip()
        run(["git", "add", "signed.txt"], cwd=self.fixture.root, env=env)
        run(["git", "commit", "-q", "-m", "signed"], cwd=self.fixture.root, env=env)

        assert local_sign == "false"


class TestBinFmtClassification(unittest.TestCase):
    """WHEN bin/fmt classifies extensionless files."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(dir=REPO, prefix=".tmp-bin-fmt-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "bin").mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / "bin/fmt", self.root / "bin/fmt")
        self.log_path = self.root / "fmt.log"
        self.bin_dir = self.root / "test-bin"
        self.env = {
            "PATH": f"{self.bin_dir}{os.pathsep}{os.defpath}",
            "FMT_LOG": str(self.log_path),
            "TMPDIR": str(self.root),
        }

    def _write_formatter_stubs(self) -> None:
        write_executable(
            self.bin_dir / "shfmt",
            """
            #!/usr/bin/env python3
            import os
            import sys
            from pathlib import Path

            with Path(os.environ["FMT_LOG"]).open("a", encoding="utf-8") as handle:
                handle.write("shfmt " + " ".join(sys.argv[1:]) + "\\n")
            raise SystemExit(0)
            """,
        )
        write_executable(
            self.bin_dir / "ruff",
            """
            #!/usr/bin/env python3
            import os
            import sys
            from pathlib import Path

            with Path(os.environ["FMT_LOG"]).open("a", encoding="utf-8") as handle:
                handle.write("ruff " + " ".join(sys.argv[1:]) + "\\n")
            raise SystemExit(0)
            """,
        )

    def test_WHEN_extensionless_files_include_binary_and_shebang_text_SHOULD_probe_safely(self):
        """SHOULD detect shell/Python shebangs without null-byte warnings."""
        self._write_formatter_stubs()
        shell_script = self.root / "shell-tool"
        python_script = self.root / "python-tool"
        binary_file = self.root / "jpeg-probe"
        shell_script.write_text("#!/usr/bin/env bash\nprintf ok\n", encoding="utf-8")
        python_script.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
        binary_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x02binary\x00payload")

        sh_result = run(
            [
                modern_bash(),
                str(self.root / "bin/fmt"),
                "--check",
                "--type",
                "sh",
                "shell-tool",
                "jpeg-probe",
            ],
            cwd=self.root,
            env=self.env,
            check=False,
        )
        py_result = run(
            [
                modern_bash(),
                str(self.root / "bin/fmt"),
                "--check",
                "--type",
                "py",
                "python-tool",
                "jpeg-probe",
            ],
            cwd=self.root,
            env=self.env,
            check=False,
        )

        assert sh_result.returncode == 0, sh_result.stderr
        assert py_result.returncode == 0, py_result.stderr
        assert "ignored null byte" not in sh_result.stderr
        assert "ignored null byte" not in py_result.stderr
        log_lines = self.log_path.read_text(encoding="utf-8").splitlines()
        assert log_lines == [
            "shfmt -d shell-tool",
            "ruff check --select I --diff python-tool",
            "ruff format --check python-tool",
        ]

    def test_WHEN_path_bash_is_legacy_and_brew_is_missing_SHOULD_exit_promptly_with_error(self):
        """SHOULD fail fast instead of recursively execing /bin/bash."""
        install_legacy_bash_path(self.bin_dir, brew_prefix=None)

        result = run(
            [str(self.root / "bin/fmt"), "--check", "--type", "sh"],
            cwd=self.root,
            env=self.env,
            check=False,
            timeout=2,
        )

        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == "error: bash 4+ required (mapfile)\n"

    def test_WHEN_path_bash_is_legacy_and_brew_bash_is_modern_SHOULD_reexec_verified_candidate(self):
        """SHOULD re-exec only the verified modern Bash candidate."""
        self._write_formatter_stubs()
        install_legacy_bash_path(self.bin_dir, brew_prefix=self.root / "fake-brew")
        shell_script = self.root / "shell-tool"
        shell_script.write_text("#!/usr/bin/env bash\nprintf ok\n", encoding="utf-8")

        result = run(
            [str(self.root / "bin/fmt"), "--check", "--type", "sh", "shell-tool"],
            cwd=self.root,
            env=self.env,
            check=False,
            timeout=2,
        )

        assert result.returncode == 0, result.stderr
        assert self.log_path.read_text(encoding="utf-8").splitlines() == ["shfmt -d shell-tool"]


if __name__ == "__main__":
    unittest.main()
