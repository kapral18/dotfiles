from __future__ import annotations

import base64
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401
from _test_support import REPO

CLI = REPO / "home" / "exact_lib" / "exact_,nano-banana" / "main.py"


def _load():
    import importlib.util

    spec = importlib.util.spec_from_file_location("nano_banana_under_test", CLI)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {CLI}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load()


def _tiny_png(path: Path) -> Path:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
    return path


class TestDefaultModel(unittest.TestCase):
    """WHEN the CLI default model is chosen."""

    def test_it_should_default_to_nano_banana_2(self) -> None:
        self.assertEqual(MOD.DEFAULT_MODEL, "gemini-3.1-flash-image")
        self.assertEqual(MOD.DEFAULT_MODEL, MOD.FLASH_VIDEO_MODEL)


class TestGeneratePayload(unittest.TestCase):
    """WHEN the prompt has no media."""

    def test_it_should_prefix_generate_and_request_image_modality(self) -> None:
        payload = MOD.build_payload("a red fox", inputs=[], urls=[])
        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts, [{"text": "Generate an image of: a red fox"}])
        self.assertEqual(payload["generationConfig"]["responseModalities"], ["TEXT", "IMAGE"])
        self.assertNotIn("imageConfig", payload["generationConfig"])


class TestEditPayload(unittest.TestCase):
    """WHEN local images are passed with -i."""

    def test_it_should_send_inline_images_without_the_generate_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            photo = _tiny_png(Path(tmp) / "photo.png")
            logo = _tiny_png(Path(tmp) / "logo.png")
            payload = MOD.build_payload("put the logo on the shirt", inputs=[photo, logo], urls=[])
        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[0], {"text": "put the logo on the shirt"})
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/png")
        self.assertEqual(parts[2]["inlineData"]["mimeType"], "image/png")
        decoded = base64.b64decode(parts[1]["inlineData"]["data"])
        self.assertTrue(decoded.startswith(b"\x89PNG"))

    def test_it_should_reject_more_than_fourteen_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = [_tiny_png(Path(tmp) / f"{i}.png") for i in range(15)]
            with self.assertRaises(SystemExit) as caught:
                MOD.build_payload("compose", inputs=paths, urls=[])
        self.assertIn("at most 14", str(caught.exception))

    def test_it_should_reject_a_missing_input_file(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            MOD.build_payload("edit", inputs=[Path("/no/such/photo.png")], urls=[])
        self.assertIn("input not found", str(caught.exception))

    def test_it_should_reject_local_video_on_dash_i(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"not-a-real-video")
            with self.assertRaises(SystemExit) as caught:
                MOD.build_payload("poster", inputs=[video], urls=[])
        self.assertIn("local video", str(caught.exception))

    def test_it_should_reject_gif(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gif = Path(tmp) / "anim.gif"
            gif.write_bytes(b"GIF89a")
            with self.assertRaises(SystemExit) as caught:
                MOD.build_payload("edit", inputs=[gif], urls=[])
        self.assertIn("GIF", str(caught.exception))

    def test_it_should_shrink_oversized_inputs_with_sips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            photo = Path(tmp) / "huge.png"
            photo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (MOD.MAX_INLINE_BYTES + 1))
            shrunk = b"\xff\xd8\xff" + b"y" * 64

            def fake_run(cmd, **_kwargs):
                Path(cmd[cmd.index("--out") + 1]).write_bytes(shrunk)
                return mock.Mock(returncode=0, stderr="", stdout="")

            with (
                mock.patch.object(MOD.shutil, "which", return_value="/usr/bin/sips"),
                mock.patch.object(MOD.subprocess, "run", side_effect=fake_run),
            ):
                payload = MOD.build_payload("edit the photo", inputs=[photo], urls=[])
        part = payload["contents"][0]["parts"][1]["inlineData"]
        self.assertEqual(part["mimeType"], "image/jpeg")
        self.assertEqual(base64.b64decode(part["data"]), shrunk)


class TestVideoUrl(unittest.TestCase):
    """WHEN --url is passed for video-to-image."""

    def test_it_should_reject_url_on_pro(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            MOD.build_payload("poster", inputs=[], urls=["https://www.youtube.com/watch?v=abc"], model=MOD.PRO_MODEL)
        self.assertIn("flash-only", str(caught.exception))
        self.assertIn(MOD.FLASH_VIDEO_MODEL, str(caught.exception))

    def test_it_should_attach_file_data_on_a_flash_model(self) -> None:
        url = "https://www.youtube.com/watch?v=UTdfxFyOQTI"
        payload = MOD.build_payload(
            "poster of this video",
            inputs=[],
            urls=[url],
            model=MOD.DEFAULT_MODEL,
        )
        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[0]["text"], "poster of this video")
        self.assertEqual(parts[1]["fileData"]["fileUri"], url)
        self.assertEqual(parts[1]["videoMetadata"]["fps"], 0.5)

    def test_it_should_reject_a_second_youtube_url(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            MOD.build_payload(
                "poster",
                inputs=[],
                urls=["https://www.youtube.com/watch?v=aaa", "https://www.youtube.com/watch?v=bbb"],
                model=MOD.FLASH_VIDEO_MODEL,
            )
        self.assertIn("at most 1", str(caught.exception))


class TestHelpAndArgs(unittest.TestCase):
    """WHEN --help and argv are parsed."""

    def test_it_should_advertise_input_and_nano_banana_2_default(self) -> None:
        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf), self.assertRaises(SystemExit) as caught:
            MOD.parse_args(["--help"])
        self.assertEqual(caught.exception.code, 0)
        help_text = buf.getvalue()
        self.assertIn("--input", help_text)
        self.assertIn("gemini-3.1-flash-image", help_text)
        self.assertIn("--url", help_text)
        self.assertIn("--version", help_text)

    def test_it_should_report_version(self) -> None:
        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf), self.assertRaises(SystemExit) as caught:
            MOD.parse_args(["--version"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("1.2.0", buf.getvalue())

    def test_it_should_collect_repeatable_inputs(self) -> None:
        args = MOD.parse_args(["-i", "a.png", "-i", "b.png", "edit the pair"])
        self.assertEqual(args.input, ["a.png", "b.png"])
        self.assertEqual(args.prompt, "edit the pair")
        self.assertEqual(args.model, "gemini-3.1-flash-image")


class TestGenerateWritesStdoutPath(unittest.TestCase):
    """WHEN the API returns image bytes."""

    def test_it_should_print_only_the_output_path(self) -> None:
        jpeg = b"\xff\xd8\xfffakejpeg"
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(jpeg).decode()}}]
                    }
                }
            ]
        }
        payload_json = json.dumps(response).encode()

        class _Resp:
            def __enter__(self):
                return io.BytesIO(payload_json)

            def __exit__(self, *args):
                return False

            def read(self):
                return payload_json

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.jpg"
            with (
                mock.patch.object(MOD, "_api_key", return_value="test-key"),
                mock.patch.object(MOD.urllib.request, "urlopen", return_value=_Resp()),
                mock.patch.object(sys, "stdout", io.StringIO()) as stdout,
            ):
                MOD.main(["a red square", "-o", str(out)])
            self.assertEqual(stdout.getvalue(), f"{out}\n")
            self.assertEqual(out.read_bytes(), jpeg)


if __name__ == "__main__":
    unittest.main()
