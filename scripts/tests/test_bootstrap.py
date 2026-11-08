from __future__ import annotations

import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "home/.bootstrap.sh"
PERMISSIONS = SCRIPT.with_name(".require-terminal-permissions.sh")


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for tool in ("/bin/cat", "/bin/mkdir", "/usr/bin/tr"):
            (self.bin / Path(tool).name).symlink_to(tool)
        self.prefix = self.root / "homebrew"
        (self.prefix / "bin").mkdir(parents=True)
        self.log = self.root / "calls"
        self.env = {
            "HOME": str(self.root),
            "PATH": f"{self.prefix / 'bin'}:{self.bin}",
            "CALL_LOG": str(self.log),
            "BREW_PREFIX": str(self.prefix),
            "CHEZMOI_COMMAND": "init",
            "SSH_AUTH_SOCK": str(self.root / "unrelated-agent.sock"),
            "ONEPASSWORD_APP": str(self.root / "applications/1Password.app"),
            "OP_STUB": str(self.root / "op"),
        }
        (self.root / PERMISSIONS.name).write_text(PERMISSIONS.read_text())
        self.script = self.root / ".bootstrap.sh"
        self.script.write_text(
            SCRIPT.read_text()
            .replace("/opt/homebrew", str(self.prefix))
            .replace("/usr/local", str(self.prefix))
            .replace('"/Applications/1Password.app"', shlex.quote(self.env["ONEPASSWORD_APP"]))
        )
        self.fake("uname", 'case "$1" in -s) echo Darwin;; -m) echo arm64;; esac')
        self.fake("open", 'echo open >> "$CALL_LOG"')
        self.fake(
            "defaults",
            'case "$1 $3" in\n'
            '"write chezmoiAccessProbe") exit "${DEFAULTS_STATUS:-0}";;\n'
            '"delete chezmoiAccessProbe") ;;\n'
            "*) exit 9;;\n"
            "esac",
        )
        self.fake(
            "gh",
            'case "$1 $2" in\n'
            '"auth status") exit "${GH_AUTH_STATUS:-0}";;\n'
            '"auth login") echo gh-login >> "$CALL_LOG";;\n'
            '"api meta") echo "github.com ssh-ed25519 KEY";;\n'
            "*) exit 9;;\n"
            "esac",
        )
        self.fake(
            "ssh-keygen", 'case "$(cat "$HOME/.ssh/known_hosts" 2> /dev/null)" in "github.com "*) exit 0;; esac\nexit 1'
        )
        self.fake("op", 'echo authenticate >> "$CALL_LOG"; exit "${AUTH_STATUS:-0}"')
        (self.bin / "op").rename(self.root / "op")
        self.fake(
            "ssh-add",
            '[ "$SSH_AUTH_SOCK" = "$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock" ] || exit 9\n'
            '[ "$*" = -l ] || exit 9\n'
            'echo ssh-agent >> "$CALL_LOG"\n'
            'exit "${SSH_AGENT_STATUS:-0}"',
        )
        self.brew = self.root / "brew"
        self.brew.write_text(
            '#!/bin/sh\ncase "$1" in\n'
            'shellenv) echo "export PATH=$BREW_PREFIX/bin:$PATH";;\n'
            'list) [ -f "$BREW_PREFIX/$4.installed" ];;\n'
            'install|reinstall) echo "brew $*" >> "$CALL_LOG"\n'
            '[ "${INSTALL_STATUS:-0}" = 0 ] || exit "$INSTALL_STATUS"\n'
            'brew_action="$1"\n'
            "shift 2\n"
            "for package do\n"
            'if [ "$brew_action" = install ] && [ -f "$BREW_PREFIX/$package.installed" ]; then continue; fi\n'
            'case "$package" in\n'
            '1password) /bin/mkdir -p "$ONEPASSWORD_APP";;\n'
            '1password-cli) /bin/cp "$OP_STUB" "$BREW_PREFIX/bin/op";;\n'
            "*) exit 9;;\n"
            "esac\n"
            ': > "$BREW_PREFIX/$package.installed"\n'
            "done;;\n"
            "esac\n"
        )
        self.brew.chmod(0o755)
        installer = (
            'echo install-homebrew >> "$CALL_LOG"\n'
            f"/bin/cp {shlex.quote(str(self.brew))} {shlex.quote(str(self.prefix / 'bin/brew'))}\n"
        )
        self.fake("curl", f"printf '%s' {shlex.quote(installer)}")

    def fake(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)

    def run_bootstrap(self, input_text: str = "\n") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/bash", str(self.script)],
            input=input_text,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_init_installs_missing_prerequisites_and_skips_ready_setup(self) -> None:
        for fresh in (True, False):
            with self.subTest(fresh=fresh):
                self.log.write_text("")
                result = self.run_bootstrap("\n" if fresh else "")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    self.log.read_text().splitlines(),
                    (
                        [
                            "install-homebrew",
                            "brew install --cask 1password",
                            "brew install --cask 1password-cli",
                            "open",
                        ]
                        if fresh
                        else []
                    )
                    + ["authenticate", "ssh-agent"],
                )

        (self.prefix / "1password.installed").unlink()
        (self.prefix / "bin/op").unlink()
        self.log.write_text("")
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.log.read_text().splitlines(),
            ["brew reinstall --cask 1password-cli", "open", "authenticate", "ssh-agent"],
        )

        (self.prefix / "bin/brew").unlink()
        self.log.write_text("")
        result = self.run_bootstrap("")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ["install-homebrew", "authenticate", "ssh-agent"])

        self.env["GH_AUTH_STATUS"] = "1"
        self.log.write_text("")
        result = self.run_bootstrap("")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ["authenticate", "ssh-agent", "gh-login"])
        self.assertEqual((self.root / ".ssh/known_hosts").read_text(), "github.com ssh-ed25519 KEY\n")

        self.env["CHEZMOI_COMMAND"] = "apply"
        self.log.write_text("")
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text(), "")

    def test_install_command_updates_a_stale_clean_clone_first(self) -> None:
        (self.bin / "git").symlink_to("/usr/bin/git")
        self.brew.rename(self.prefix / "bin/brew")
        origin = self.root / "origin"
        clone = self.root / "clone"

        def git(*args: str, cwd: Path = clone) -> str:
            return subprocess.run(
                ["/usr/bin/git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                cwd=cwd,
                env=self.env,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

        origin.mkdir()
        git("init", "-q", "-b", "main", cwd=origin)
        git("commit", "-q", "--allow-empty", "-m", "one", cwd=origin)
        git("clone", "-q", str(origin), str(clone), cwd=self.root)
        git("remote", "set-url", "origin", "https://github.com/owner/dotfiles.git")
        git("config", f"url.{origin}.insteadOf", "https://github.com/owner/dotfiles.git")
        git("commit", "-q", "--allow-empty", "-m", "two", cwd=origin)
        self.env["CHEZMOI_WORKING_TREE"] = str(clone)

        for plain_init in (
            "chezmoi init --apply",
            "chezmoi init --branch owner",
            "chezmoi init -S dotfiles",
            f"chezmoi init -S {clone}",
        ):
            self.env["CHEZMOI_ARGS"] = plain_init
            self.assertEqual(self.run_bootstrap().returncode, 0)
            self.assertNotEqual(git("rev-parse", "HEAD"), git("rev-parse", "HEAD", cwd=origin))

        self.env["CHEZMOI_ARGS"] = "chezmoi init --apply Owner"
        (clone / "local").write_text("edit")
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local changes", result.stderr)
        (clone / "local").unlink()

        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rerun", result.stderr)
        self.assertEqual(git("rev-parse", "HEAD"), git("rev-parse", "HEAD", cwd=origin))

        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_prerequisites_fail_init(self) -> None:
        for failure, last_call in (
            ("DEFAULTS_STATUS", "open"),
            ("INSTALL_STATUS", "brew install --cask 1password"),
            ("AUTH_STATUS", "authenticate"),
            ("SSH_AGENT_STATUS", "ssh-agent"),
        ):
            with self.subTest(failure=failure):
                for name in ("DEFAULTS_STATUS", "INSTALL_STATUS", "AUTH_STATUS", "SSH_AGENT_STATUS"):
                    self.env.pop(name, None)
                self.env[failure] = "2" if failure == "SSH_AGENT_STATUS" else "1"
                self.log.write_text("")
                result = self.run_bootstrap()
                self.assertNotEqual(result.returncode, 0)
                calls = self.log.read_text().splitlines()
                self.assertTrue(calls, result.stderr)
                self.assertEqual(calls[-1], last_call)
                if failure == "SSH_AGENT_STATUS":
                    self.assertFalse(any(call.startswith(("brew install", "brew reinstall")) for call in calls))


if __name__ == "__main__":
    unittest.main()
