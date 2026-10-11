from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl"

# The DMG integration owns these external download/mount boundaries. Keep file
# discovery, copying, registry dispatch, and cleanup real inside a scratch root.
DEPENDENCIES = r"""
curl() {
  printf 'curl %s\n' "$*" >> "$CALLS"
  [[ "${DOWNLOAD_FAIL:-0}" == 0 ]] || return 22
  [[ "$1 $2 $3 $4" == '--fail --location --show-error --output' ]] || return 2
  printf dmg > "$5"
}
gh() {
  printf 'gh %s\n' "$*" >> "$CALLS"
  [[ "${DOWNLOAD_FAIL:-0}" == 0 ]] || return 1
  while [[ "$1" != --dir ]]; do shift; done
  printf dmg > "$2/release.dmg"
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
    """WHEN the custom registry installs a DMG from HTTPS or GitHub."""

    @classmethod
    def setUpClass(cls):
        rendered = render(INSTALLER.read_text())
        cls.functions = rendered.split('if [[ ! -f "$CUSTOM_PACKAGES_TEMPLATE" ]]')[0]

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
        row = f"dmg|Meeting Notes|{source}|{tag}|{bundle}|.dmg"
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


if __name__ == "__main__":
    unittest.main()
