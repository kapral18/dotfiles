from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "home/.chezmoiscripts/run_onchange_after_09-install-redtab.sh.tmpl"
CLIENT_CONFIG = REPO / "home/dot_config/redtab/readonly_config.toml"

# gh, cargo, and docker are the external boundaries; tar and install stay real.
# The fake `cargo build` copies the source tree's BUILD_ID file to the binary
# path, so a test can tell which source tree was built.
FAKES = r"""
gh() { printf 'gh %s\n' "$*" >> "$CALLS"; cat "$SRC_TARBALL"; }
cargo() {
  printf 'cargo %s\n' "$*" >> "$CALLS"
  [[ "$CARGO_FAILS" == 1 ]] && return 101
  local manifest="" target=""
  while (($#)); do
    case "$1" in
    --manifest-path) manifest="$2"; shift ;;
    --target-dir) target="$2"; shift ;;
    esac
    shift
  done
  mkdir -p "$target/release"
  cp "$(dirname "$manifest")/BUILD_ID" "$target/release/redtab"
}
docker() {
  if [[ "$1" == info ]]; then [[ "$DOCKER_UP" == 1 ]]; return; fi
  printf 'docker %s\n' "$*" >> "$CALLS"
}
"""


def render(template: str, *, source: Path = REPO / "home") -> subprocess.CompletedProcess[str]:
    # --source: chezmoi otherwise resolves `include` against its configured source,
    # not the checkout under test.
    return subprocess.run(
        ["chezmoi", "--source", str(source), "execute-template"],
        input=template,
        capture_output=True,
        text=True,
        check=False,
    )


def hook_value(name: str) -> str:
    return re.search(rf'^{name}="([^"]+)"$', HOOK.read_text(), re.MULTILINE).group(1)


def config_value(key: str):
    # The values used here are strings and string arrays, which read as JSON.
    raw = re.search(rf"^{key} = (.+)$", CLIENT_CONFIG.read_text(), re.MULTILINE).group(1)
    return json.loads(raw)


class TestInstallRedtab(unittest.TestCase):
    """WHEN the redtab hook builds the pinned client and starts Redlib."""

    @classmethod
    def setUpClass(cls):
        rendered = render(HOOK.read_text())
        assert rendered.returncode == 0, rendered.stderr
        cls.hook = rendered.stdout

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.calls = self.root / "calls"
        self.calls.touch()
        (self.root / "tmp").mkdir()

    def calls_starting(self, prefix: str) -> list[str]:
        return [line for line in self.calls.read_text().splitlines() if line.startswith(prefix)]

    def source_tarball(self) -> Path:
        tarball = self.root / "src.tar.gz"
        data = b"redtab source tree"
        with tarfile.open(tarball, "w:gz") as archive:
            member = tarfile.TarInfo("kapral18-redtab-4cc10c5/BUILD_ID")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        return tarball

    def run_hook(self, *, docker_up: bool = True, cargo_fails: bool = False):
        return subprocess.run(
            ["bash", "-c", FAKES + self.hook],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "HOME": str(self.root),
                "TMPDIR": str(self.root / "tmp"),
                "CALLS": str(self.calls),
                "SRC_TARBALL": str(self.source_tarball()),
                "DOCKER_UP": str(int(docker_up)),
                "CARGO_FAILS": str(int(cargo_fails)),
            },
        )

    @property
    def binary(self) -> Path:
        return self.root / ".local/bin/redtab"

    def test_SHOULD_publish_redlib_on_the_client_config_address_on_loopback(self):
        address = urlsplit(config_value("redlib_url")).netloc

        actual = self.run_hook()

        self.assertEqual(actual.returncode, 0, actual.stderr)
        [run] = self.calls_starting("docker run")
        self.assertIn(f"--publish {address}:8080", run)
        self.assertIn("--restart unless-stopped", run)

    def test_SHOULD_install_a_locked_release_build_of_the_pinned_commit(self):
        actual = self.run_hook()

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual(
            self.calls_starting("gh"), [f"gh api repos/kapral18/redtab/tarball/{hook_value('REDTAB_COMMIT')}"]
        )
        [build] = self.calls_starting("cargo")
        self.assertIn("build --release --locked", build)
        self.assertEqual(self.binary.read_text(), "redtab source tree")

    def test_SHOULD_fail_before_downloading_when_docker_is_down(self):
        actual = self.run_hook(docker_up=False)

        self.assertEqual(actual.returncode, 1)
        self.assertIn("Docker is not running", actual.stderr)
        self.assertEqual(self.calls.read_text(), "")
        self.assertFalse(self.binary.exists())

    def test_SHOULD_keep_the_running_redlib_when_the_build_fails(self):
        actual = self.run_hook(cargo_fails=True)

        self.assertNotEqual(actual.returncode, 0)
        self.assertFalse(self.binary.exists())
        self.assertEqual(self.calls_starting("docker"), [])

    def test_SHOULD_offer_to_start_the_container_the_hook_runs(self):
        start = config_value("redlib_start_command")

        self.assertEqual(start, ["docker", "start", hook_value("REDLIB_CONTAINER")])

    def test_SHOULD_refuse_to_render_a_redlib_url_docker_cannot_publish(self):
        cases = (
            ("hostname", "http://localhost:8085"),
            ("no port", "http://127.0.0.1"),
            ("empty port", "http://127.0.0.1:"),
            ("port out of range", "http://127.0.0.1:65536"),
        )
        for case, url in cases:
            with self.subTest(case=case):
                source = self.root / case
                config = source / "dot_config/redtab/readonly_config.toml"
                config.parent.mkdir(parents=True)
                config.write_text(f'redlib_url = "{url}"\n')

                actual = render(HOOK.read_text(), source=source)

                self.assertNotEqual(actual.returncode, 0)
                self.assertIn("redtab redlib_url must", actual.stderr)


if __name__ == "__main__":
    unittest.main()
