from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401
from remove_retired_git_maven_jar import remove_retired


class TestRemoveRetiredGitMavenJar(unittest.TestCase):
    """WHEN the custom-package hook meets state from the retired git_maven_jar format."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.state = self.root / "state" / "git_maven_jar.tsv"
        self.state.parent.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_SHOULD_remove_launchers_and_keep_checkouts(self) -> None:
        launcher = self.bin / "telegramtui"
        launcher.write_text("#!/bin/sh\n")
        dangling = self.bin / "dangling"
        dangling.symlink_to(self.root / "missing-target")
        checkout = self.root / "code" / "telegramtui" / "main"
        (checkout / ".git").mkdir(parents=True)
        self.state.write_text(
            f"telegramtui\t{launcher}\t{checkout}\n"
            f"dangling\t{dangling}\t{self.root / 'gone'}"  # last row without newline
        )

        messages = remove_retired(self.state)

        self.assertFalse(launcher.exists())
        self.assertFalse(dangling.is_symlink())
        self.assertTrue((checkout / ".git").is_dir())
        self.assertEqual(
            messages,
            [
                f"Removed retired launcher for telegramtui: {launcher}",
                f"Retired source checkout left in place; remove it when no longer needed: {checkout}",
                f"Removed retired launcher for dangling: {dangling}",
            ],
        )
        self.assertFalse(self.state.parent.exists())

    def test_SHOULD_never_delete_a_directory_listed_as_launcher(self) -> None:
        checkout = self.root / "repo"
        checkout.mkdir()
        self.state.write_text(f"odd\t{checkout}\t{checkout}\n")

        messages = remove_retired(self.state)

        self.assertTrue(checkout.is_dir())
        self.assertEqual(
            messages, [f"Retired source checkout left in place; remove it when no longer needed: {checkout}"]
        )

    def test_SHOULD_keep_a_state_dir_that_holds_other_files(self) -> None:
        other = self.state.parent / "other"
        other.write_text("x")
        self.state.write_text("")

        self.assertEqual(remove_retired(self.state), [])

        self.assertFalse(self.state.exists())
        self.assertTrue(other.exists())

    def test_SHOULD_do_nothing_when_state_is_absent(self) -> None:
        self.assertEqual(remove_retired(self.state), [])
        self.assertTrue(self.state.parent.is_dir())


if __name__ == "__main__":
    unittest.main()
