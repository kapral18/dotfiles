#!/usr/bin/env python3
"""End-to-end tests for patch receipt through the ,wh command core."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WH_MAIN = REPO / "home/exact_lib/exact_,wh/main.sh"


class WhPatchReceiveTests(unittest.TestCase):
    """WHEN ,wh receives a patch into a Git worktree."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.worktree = self.root / "worktree"
        self.worktree.mkdir()
        self.patch = self.root / "transfer.patch"
        self.received_patch = self.root / "received.patch"
        self.bindir = self.root / "bin"
        self.bindir.mkdir()

        self.git("init", "-q")
        self.git("config", "user.name", "WH Test")
        self.git("config", "user.email", "wh-test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.target = self.worktree / "conflict.txt"
        self.target.write_text("base\n", encoding="utf-8")
        self.git("add", "conflict.txt")
        self.git("commit", "-qm", "base")

        wormhole = self.bindir / "wormhole"
        wormhole.write_text(
            '#!/usr/bin/env bash\nset -euo pipefail\ncp "$WH_TEST_PATCH" staged.patch\n',
            encoding="utf-8",
        )
        wormhole.chmod(0o755)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.worktree,
            check=check,
            capture_output=True,
            text=True,
        )

    def make_patch(self, incoming: str) -> None:
        self.target.write_text(incoming, encoding="utf-8")
        self.git("add", "conflict.txt")
        patch = self.git("diff", "--cached", "--binary").stdout
        self.patch.write_text(patch, encoding="utf-8")
        self.git("reset", "--hard", "-q", "HEAD")

    def receive(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(WH_MAIN), "recv", "8-asteroid"],
            cwd=self.worktree,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{self.bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                "WH_PATCH_FILE": str(self.received_patch),
                "WH_TEST_PATCH": str(self.patch),
            },
        )

    def test_WHEN_direct_apply_succeeds_SHOULD_keep_the_change_unstaged(self) -> None:
        self.make_patch("incoming\n")

        result = self.receive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "incoming\n")
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout, "")
        self.assertEqual(self.git("ls-files", "-u").stdout, "")

    def test_WHEN_direct_apply_fails_SHOULD_preserve_three_way_conflicts(self) -> None:
        self.make_patch("incoming\n")
        self.target.write_text("receiver\n", encoding="utf-8")
        self.git("add", "conflict.txt")
        self.git("commit", "-qm", "receiver")

        result = self.receive()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Patch applied with conflicts", result.stderr)
        self.assertIn("<<<<<<< ours", self.target.read_text(encoding="utf-8"))
        self.assertIn(">>>>>>> theirs", self.target.read_text(encoding="utf-8"))
        self.assertTrue(self.git("ls-files", "-u").stdout)
        self.assertIn("UU conflict.txt", self.git("status", "--short").stdout)
        self.assertTrue(self.received_patch.is_file())

    def test_WHEN_three_way_apply_merges_cleanly_SHOULD_stage_the_result(self) -> None:
        self.target.write_text("one\ntwo\nthree\n", encoding="utf-8")
        self.git("add", "conflict.txt")
        self.git("commit", "-qm", "expand base")
        self.make_patch("incoming\ntwo\nthree\n")
        self.target.write_text("one\ntwo\nreceiver\n", encoding="utf-8")
        self.git("add", "conflict.txt")
        self.git("commit", "-qm", "receiver")

        result = self.receive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Patch applied with a three-way merge", result.stdout)
        self.assertEqual(
            self.target.read_text(encoding="utf-8"),
            "incoming\ntwo\nreceiver\n",
        )
        self.assertEqual(
            self.git("diff", "--cached", "--name-only").stdout,
            "conflict.txt\n",
        )
        self.assertEqual(self.git("ls-files", "-u").stdout, "")

    def test_WHEN_conflicts_already_exist_SHOULD_not_attempt_three_way_apply(self) -> None:
        self.make_patch("incoming\n")
        self.target.write_text("receiver\n", encoding="utf-8")
        self.git("add", "conflict.txt")
        self.git("commit", "-qm", "receiver")
        preexisting = self.worktree / "preexisting.txt"
        preexisting.write_text("base\n", encoding="utf-8")
        base_blob = self.git("hash-object", "-w", "preexisting.txt").stdout.strip()
        preexisting.write_text("ours\n", encoding="utf-8")
        ours_blob = self.git("hash-object", "-w", "preexisting.txt").stdout.strip()
        preexisting.write_text("theirs\n", encoding="utf-8")
        theirs_blob = self.git("hash-object", "-w", "preexisting.txt").stdout.strip()
        preexisting.write_text("ours\n", encoding="utf-8")
        index_info = (
            f"100644 {base_blob} 1\tpreexisting.txt\n"
            f"100644 {ours_blob} 2\tpreexisting.txt\n"
            f"100644 {theirs_blob} 3\tpreexisting.txt\n"
        )
        subprocess.run(
            ["git", "update-index", "--index-info"],
            cwd=self.worktree,
            check=True,
            input=index_info,
            text=True,
        )

        result = self.receive()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already has unresolved conflicts", result.stderr)
        self.assertNotIn("attempting: git apply --3way", result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "receiver\n")
        self.assertIn("preexisting.txt", self.git("ls-files", "-u").stdout)

    def test_WHEN_patch_is_malformed_SHOULD_fail_without_claiming_conflicts(self) -> None:
        self.patch.write_text("not a patch\n", encoding="utf-8")

        result = self.receive()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Patch could not be applied", result.stderr)
        self.assertNotIn("Patch applied with conflicts", result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "base\n")
        self.assertEqual(self.git("ls-files", "-u").stdout, "")


class WhClipboardSendTests(unittest.TestCase):
    """WHEN ,wh sends the clipboard, flavor detection drives the AppleScript class."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.bindir = self.root / "bin"
        self.bindir.mkdir()
        self.log = self.root / "tools.log"

        osascript = self.bindir / "osascript"
        osascript.write_text(
            "#!/usr/bin/env bash\n"
            'echo "osascript $*" >> "$WH_TEST_LOG"\n'
            'if [[ "$*" == *"clipboard info"* ]]; then\n'
            '  echo "$WH_TEST_CLIP_INFO"\n'
            "  exit 0\n"
            "fi\n"
            'if [[ "$*" == *"the clipboard as"* ]]; then\n'
            '  args="$*"\n'
            '  path="${args#*POSIX file \\"}"\n'
            '  path="${path%%\\"*}"\n'
            '  printf "fake-image-bytes" > "$path"\n'
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        osascript.chmod(0o755)

        sips = self.bindir / "sips"
        sips.write_text(
            "#!/usr/bin/env bash\n"
            'echo "sips $*" >> "$WH_TEST_LOG"\n'
            'prev=""\n'
            'for a in "$@"; do\n'
            '  if [[ "$prev" == "--out" ]]; then\n'
            '    printf "png-bytes" > "$a"\n'
            "  fi\n"
            '  prev="$a"\n'
            "done\n"
            "exit 0\n",
            encoding="utf-8",
        )
        sips.chmod(0o755)

        wormhole = self.bindir / "wormhole"
        wormhole.write_text(
            '#!/usr/bin/env bash\necho "wormhole $*" >> "$WH_TEST_LOG"\nexit 0\n',
            encoding="utf-8",
        )
        wormhole.chmod(0o755)

        pbpaste = self.bindir / "pbpaste"
        pbpaste.write_text("#!/usr/bin/env bash\nprintf 'clipboard text'\n", encoding="utf-8")
        pbpaste.chmod(0o755)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def send_clip(self, clip_info: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(WH_MAIN), "send", "--clip"],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{self.bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                "WH_TEST_LOG": str(self.log),
                "WH_TEST_CLIP_INFO": clip_info,
            },
        )

    def logged(self) -> str:
        return self.log.read_text(encoding="utf-8") if self.log.exists() else ""

    def test_WHEN_clipboard_is_gif_SHOULD_extract_as_GIFf_and_normalize_to_png(self) -> None:
        # macOS reports GIF clipboards as "GIF picture"; the AppleScript legacy
        # flavor code is GIFf («class GIF » fails coercion with -1700).
        result = self.send_clip("GIF picture, 43")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("«class GIFf»", self.logged())
        self.assertIn("sips -s format png", self.logged())
        self.assertIn("Sending clipboard (png)", result.stdout)
        self.assertIn("wormhole send", self.logged())

    def test_WHEN_clipboard_offers_pngf_and_gif_SHOULD_prefer_pngf(self) -> None:
        # macOS transmutes still images, so PNGf rides along; prefer it and skip sips.
        result = self.send_clip("GIF picture, 43, «class PNGf», 162")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("«class PNGf»", self.logged())
        self.assertNotIn("sips", self.logged())
        self.assertIn("Sending clipboard (png)", result.stdout)

    def test_WHEN_clipboard_is_text_SHOULD_use_pbpaste_without_extraction(self) -> None:
        result = self.send_clip("«class utf8», 4, string, 4")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("the clipboard as", self.logged())
        self.assertIn("Sending clipboard (text)", result.stdout)


if __name__ == "__main__":
    unittest.main()
