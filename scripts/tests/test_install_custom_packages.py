from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl"

# These fakes own the external download/mount boundaries for DMG and release
# binary rows. File discovery, copying, extraction, registry dispatch, and
# cleanup stay real inside a scratch root. A failed `gh` download leaves a
# partial file behind, as an interrupted transfer can.
DEPENDENCIES = r"""
curl() {
  printf 'curl %s\n' "$*" >> "$CALLS"
  [[ "${DOWNLOAD_FAIL:-0}" == 0 ]] || return 22
  [[ "$1 $2 $3 $4" == '--fail --location --show-error --output' ]] || return 2
  printf dmg > "$5"
}
gh() {
  printf 'gh %s\n' "$*" >> "$CALLS"
  [[ "${GH_READS_STDIN:-0}" == 0 ]] || cat >/dev/null
  if [[ "$1 $2" == "release view" ]]; then printf 'v9\n'; return; fi
  local pattern="" dir=""
  while (($#)); do
    case "$1" in
    --pattern) pattern="$2"; shift ;;
    --dir) dir="$2"; shift ;;
    esac
    shift
  done
  if [[ "${DOWNLOAD_FAIL:-0}" != 0 ]]; then printf partial > "$dir/partial"; return 1; fi
  case "$pattern" in
  *.dmg) printf dmg > "$dir/release.dmg" ;;
  *.tar.gz)
    mkdir "$dir/src" && printf payload > "$dir/src/tool"
    tar -czf "$dir/$pattern" -C "$dir/src" tool && rm -r "$dir/src"
    ;;
  *) printf payload > "$dir/$pattern" ;;
  esac
}
hdiutil() {
  printf 'hdiutil %s\n' "$*" >> "$CALLS"
  if [[ "$1" == attach ]]; then
    [[ "${FAIL_STAGE:-}" != mount ]] || return 1
    while [[ "$1" != -mountpoint ]]; do shift; done
    mkdir -p "$2/$BUNDLE"
    printf payload > "$2/$BUNDLE/content"
  fi
}
cp() {
  [[ "${FAIL_STAGE:-}" != copy ]] || return 1
  command cp "$@"
}
"""


def render(template: str) -> str:
    result = subprocess.run(
        ["chezmoi", "execute-template"], input=template, capture_output=True, text=True, check=True, cwd=REPO
    )
    return result.stdout


class TestInstallCustomPackages(unittest.TestCase):
    """WHEN the custom registry installs a DMG or a GitHub release binary."""

    @classmethod
    def setUpClass(cls):
        rendered = render(INSTALLER.read_text())
        cls.functions = rendered.split('if [[ ! -f "$CUSTOM_PACKAGES_TEMPLATE" ]]')[0]
        # Through the registry loop and its status exit; the tail fetches unrelated tools.
        cls.registry_run = rendered.split("# Install command-line tools")[0]

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.apps = self.root / "Applications"
        self.apps.mkdir()
        self.downloads = self.root / "downloads"
        self.downloads.mkdir()
        self.calls = self.root / "calls"
        self.calls.touch()

    def run_row(
        self, source: str, *, tag: str = "latest", fail: bool = False, bundle: str = "Notes.app", fail_stage: str = ""
    ):
        return self.run_line(
            f"dmg|Meeting Notes|{source}|{tag}|{bundle}|.dmg", fail=fail, bundle=bundle, fail_stage=fail_stage
        )

    def run_line(self, row: str, *, fail: bool = False, bundle: str = "Notes.app", fail_stage: str = ""):
        functions = self.functions.replace("/Applications/", f"{self.apps}/")
        script = functions + DEPENDENCIES + f"\nif ! process_custom_package_line {shlex.quote(row)}; then exit 1; fi\n"
        return subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "HOME": str(self.root),
                "TMPDIR": str(self.downloads),
                "CALLS": str(self.calls),
                "BUNDLE": bundle,
                "DOWNLOAD_FAIL": str(int(fail)),
                "FAIL_STAGE": fail_stage,
            },
        )

    def test_SHOULD_install_https_dmg_without_github(self):
        actual = self.run_row("https://example.test/notes.dmg", bundle="Réunion Notes.app")

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual((self.apps / "Réunion Notes.app/content").read_text(), "payload")
        self.assertNotIn("gh ", self.calls.read_text())
        self.assertIn("hdiutil detach", self.calls.read_text())
        self.assertEqual(list(self.downloads.iterdir()), [])

    def test_SHOULD_skip_existing_app_before_download(self):
        (self.apps / "Notes.app").mkdir()
        (self.apps / "Notes.app/content").write_text("keep")

        actual = self.run_row("https://example.test/notes.dmg")

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual((self.apps / "Notes.app/content").read_text(), "keep")
        self.assertEqual(self.calls.read_text(), "")

    def test_SHOULD_skip_existing_symlink_to_app(self):
        target = self.root / "existing.app"
        target.mkdir()
        (self.apps / "Notes.app").symlink_to(target)

        actual = self.run_row("https://example.test/notes.dmg")

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertTrue((self.apps / "Notes.app").is_symlink())
        self.assertEqual(self.calls.read_text(), "")

    def test_SHOULD_stop_and_clean_up_failed_https_download(self):
        actual = self.run_row("https://example.test/notes.dmg", fail=True)

        self.assertEqual(actual.returncode, 1)
        self.assertIn("Could not download Meeting Notes", actual.stderr)
        self.assertNotIn("hdiutil", self.calls.read_text())
        self.assertEqual(list(self.apps.iterdir()), [])
        self.assertEqual(list(self.downloads.iterdir()), [])

    def test_SHOULD_fail_when_dmg_cannot_mount(self):
        actual = self.run_row("https://example.test/notes.dmg", fail_stage="mount")

        self.assertEqual(actual.returncode, 1)
        self.assertNotIn("installed successfully", actual.stdout)
        self.assertEqual(list(self.apps.iterdir()), [])
        self.assertEqual(list(self.downloads.iterdir()), [])

    def test_SHOULD_detach_when_copy_fails(self):
        actual = self.run_row("https://example.test/notes.dmg", fail_stage="copy")

        self.assertEqual(actual.returncode, 1)
        self.assertNotIn("installed successfully", actual.stdout)
        self.assertIn("hdiutil detach", self.calls.read_text())
        self.assertEqual(list(self.downloads.iterdir()), [])

    def test_SHOULD_preserve_github_release_downloads(self):
        for tag, expected in (("latest", "gh release download --repo"), ("v1.2", "gh release download v1.2 --repo")):
            with self.subTest(tag=tag):
                actual = self.run_row("owner/notes", tag=tag, bundle=f"{tag}.app")

                self.assertEqual(actual.returncode, 0, actual.stderr)
                self.assertEqual((self.apps / f"{tag}.app/content").read_text(), "payload")
                self.assertIn(expected, self.calls.read_text())
                self.assertNotIn("curl ", self.calls.read_text())

    def install_release_binary(self, tag: str = "v1.2", *, fail: bool = False):
        return self.run_line(f"file|Tool|owner/tool|{tag}|tool-darwin|tool", fail=fail)

    @staticmethod
    def file_record(tag: str, pattern: str = "tool-darwin") -> str:
        return f"{tag}|owner/tool|{pattern}|"

    @property
    def binary(self) -> Path:
        return self.root / ".local/bin/tool"

    @property
    def record(self) -> Path:
        return self.root / ".local/state/custom-packages/tool.release"

    def existing_install(self, record: str | None):
        """An installed binary that leaves a marker if the installer ever executes it."""
        self.binary.parent.mkdir(parents=True, exist_ok=True)
        self.binary.write_text(f'#!/bin/sh\ntouch "{self.root}/executed"\n')
        self.binary.chmod(0o755)
        self.record.unlink(missing_ok=True)
        if record is not None:
            self.record.parent.mkdir(parents=True, exist_ok=True)
            self.record.write_text(record + "\n")

    def test_SHOULD_skip_release_binary_when_record_matches(self):
        self.existing_install(self.file_record("v1.2"))

        actual = self.install_release_binary()

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertIn("Tool is up to date (v1.2)", actual.stdout)
        self.assertEqual(self.calls.read_text(), "")
        self.assertFalse((self.root / "executed").exists())

    def test_SHOULD_reinstall_release_binary_without_running_it(self):
        cases = (
            ("tag differs", self.file_record("v1.1")),
            ("asset differs", self.file_record("v1.2", "tool-darwin-x64")),
            ("no record", None),
        )
        for case, record in cases:
            with self.subTest(case=case):
                self.existing_install(record)

                actual = self.install_release_binary()

                self.assertEqual(actual.returncode, 0, actual.stderr)
                self.assertEqual(self.binary.read_text(), "payload")
                self.assertEqual(self.record.read_text(), self.file_record("v1.2") + "\n")
                self.assertFalse((self.root / "executed").exists())

    def test_SHOULD_reinstall_missing_binary_despite_record(self):
        self.record.parent.mkdir(parents=True)
        self.record.write_text(self.file_record("v1.2") + "\n")

        actual = self.install_release_binary()

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual(self.binary.read_text(), "payload")
        self.assertIn("gh release download v1.2 --repo owner/tool", self.calls.read_text())

    def test_SHOULD_keep_old_install_when_release_download_fails_midway(self):
        self.existing_install(self.file_record("v1.1"))

        actual = self.install_release_binary(fail=True)

        self.assertEqual(actual.returncode, 1)
        self.assertNotIn("installed", actual.stdout)
        self.assertIn("executed", self.binary.read_text())
        self.assertEqual(self.record.read_text(), self.file_record("v1.1") + "\n")

    def test_SHOULD_install_latest_archive_binary_once(self):
        row = "tar_gz_bin|Tool|owner/tool|latest|tool.tar.gz|tool|tool"

        first = self.run_line(row)
        second = self.run_line(row)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("Tool installed (v9)", first.stdout)
        self.assertEqual(self.binary.read_text(), "payload")
        self.assertEqual(self.record.read_text(), "v9|owner/tool|tool.tar.gz|tool\n")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("Tool is up to date (v9)", second.stdout)
        self.assertEqual(self.calls.read_text().count("gh release download"), 1)

    def test_SHOULD_install_every_row_when_a_row_child_reads_stdin(self):
        rows = "file|Tool A|owner/a|v1|a-darwin|a\nfile|Tool B|owner/b|v1|b-darwin|b"
        fakes = DEPENDENCIES + 'chezmoi() { cat >/dev/null; printf "%s\\n" "$ROWS"; }\n'

        actual = subprocess.run(
            ["bash", "-c", fakes + self.registry_run],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "HOME": str(self.root),
                "TMPDIR": str(self.downloads),
                "CALLS": str(self.calls),
                "ROWS": rows,
                "GH_READS_STDIN": "1",
            },
        )

        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertIn("Tool A installed (v1)", actual.stdout)
        self.assertIn("Tool B installed (v1)", actual.stdout)
        self.assertEqual((self.root / ".local/bin/b").read_text(), "payload")


if __name__ == "__main__":
    unittest.main()
