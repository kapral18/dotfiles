#!/usr/bin/env python3
"""Focused tests for copilot."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestCopilotWrapper(unittest.TestCase):
    """WHEN launching or resuming Copilot through the managed wrapper."""

    def _write_session(
        self,
        home: Path,
        session_id: str,
        *,
        cwd: Path,
        summary: str,
        updated_at: str,
    ) -> None:
        copilot_home = home / ".copilot"
        copilot_home.mkdir(parents=True, exist_ok=True)
        database = sqlite3.connect(copilot_home / "session-store.db")
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                cwd TEXT,
                repository TEXT,
                branch TEXT,
                summary TEXT,
                created_at TEXT,
                updated_at TEXT,
                host_type TEXT
            )
            """
        )
        database.execute(
            """
            INSERT INTO sessions (id, cwd, repository, branch, summary, created_at, updated_at, host_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                str(cwd),
                "owner/repo",
                "main",
                summary,
                updated_at,
                updated_at,
                "github",
            ),
        )
        database.commit()
        database.close()
        state = copilot_home / "session-state" / session_id
        state.mkdir(parents=True)
        (state / "events.jsonl").write_text("{}\n")

    def _write_real_copilot(self, bindir: Path) -> Path:
        real = bindir / "copilot-real"
        real.write_text("#!/usr/bin/env bash\nprintf 'ARGS='; printf '<%s>' \"$@\"; printf '\\n'\n")
        real.chmod(0o755)
        return real

    def test_SHOULD_replace_bare_resume_with_the_selected_exact_session_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "workspace"
            home.mkdir()
            bindir.mkdir()
            workspace.mkdir()
            older = "11111111-1111-4111-8111-111111111111"
            selected = "22222222-2222-4222-8222-222222222222"
            self._write_session(
                home,
                older,
                cwd=workspace,
                summary="Older session",
                updated_at="2026-07-21T10:00:00.000Z",
            )
            self._write_session(
                home,
                selected,
                cwd=workspace,
                summary="Selected session",
                updated_at="2026-07-22T10:00:00.000Z",
            )
            fzf_input = root / "fzf-input"
            fzf = bindir / "fzf"
            fzf.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "rows = sys.stdin.read().splitlines()\n"
                "open(os.environ['FZF_INPUT'], 'w').write('\\n'.join(rows))\n"
                "print(rows[0])\n"
            )
            fzf.chmod(0o755)
            real = self._write_real_copilot(bindir)

            result = subprocess.run(
                [sys.executable, str(COPILOT_COMMAND), "--yolo", "--resume"],
                capture_output=True,
                text=True,
                cwd=workspace,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "COPILOT_REAL_BIN": str(real),
                    "FZF_INPUT": str(fzf_input),
                },
            )
            picker_rows = fzf_input.read_text()

        assert result.returncode == 0, result.stderr
        assert f"<--session-id={selected}>" in result.stdout
        assert "<--resume>" not in result.stdout
        assert "Selected session" in picker_rows
        assert older in picker_rows

    def test_SHOULD_pass_explicit_resume_through_without_opening_the_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            real = self._write_real_copilot(bindir)

            result = subprocess.run(
                [sys.executable, str(COPILOT_COMMAND), "--yolo", "--resume=abc1234"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}/bin:/usr/bin",
                    "COPILOT_REAL_BIN": str(real),
                },
            )

        assert result.returncode == 0, result.stderr
        assert "ARGS=<--yolo><--resume=abc1234>" in result.stdout

    def test_SHOULD_pass_a_space_separated_resume_value_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            real = self._write_real_copilot(bindir)

            result = subprocess.run(
                [sys.executable, str(COPILOT_COMMAND), "--resume", "session name", "--yolo"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}/bin:/usr/bin",
                    "COPILOT_REAL_BIN": str(real),
                },
            )

        assert result.returncode == 0, result.stderr
        assert "ARGS=<--resume><session name><--yolo>" in result.stdout

    def test_SHOULD_resolve_a_path_searchable_real_copilot_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_real_copilot(bindir)

            result = subprocess.run(
                [sys.executable, str(COPILOT_COMMAND), "--version"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}/bin:/usr/bin",
                    "COPILOT_REAL_BIN": "copilot-real",
                },
            )

        assert result.returncode == 0, result.stderr
        assert "ARGS=<--version>" in result.stdout


if __name__ == "__main__":
    unittest.main()
