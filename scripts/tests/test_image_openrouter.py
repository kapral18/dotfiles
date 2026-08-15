from __future__ import annotations

import base64
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import zlib
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401
from _test_support import REPO

CLI = REPO / "home" / "exact_lib" / "exact_,image-openrouter" / "main.py"
COMPLETION = REPO / "home" / "dot_config" / "fish" / "completions" / "readonly_,image-openrouter.fish"


def _load():
    import importlib.util

    spec = importlib.util.spec_from_file_location("image_openrouter_under_test", CLI)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {CLI}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load()


def _png_with_metadata(secret: str) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xff\x00\x00\x00\xff\x00")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"tEXt", b"Comment\x00" + secret.encode("utf-8"))
        + chunk(b"IDAT", pixels)
        + chunk(b"IEND", b"")
    )


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()


class TestCommandIdentity(unittest.TestCase):
    """WHEN the OpenRouter image command surface is inspected."""

    def test_it_should_use_the_openrouter_command_and_library_names(self) -> None:
        self.assertEqual(MOD.build_parser().prog, ",image-openrouter")
        launcher = (REPO / "home" / "exact_bin" / "executable_,image-openrouter").read_text(encoding="utf-8")
        self.assertIn("lib/,image-openrouter/main.py", launcher)

    @unittest.skipUnless(shutil.which("fish"), "fish is not installed")
    def test_it_should_complete_the_curated_zdr_generation_and_editing_models(self) -> None:
        result = subprocess.run(
            [
                shutil.which("fish") or "fish",
                "-c",
                "source $argv[1]; complete -C ',image-openrouter --model '",
                str(COMPLETION),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "bytedance-seed/seedream-5-0-lite\tHigh-resolution value; generation/editing; 2K/4K",
                "bytedance-seed/seedream-5-0-pro\tDefault; quality/value; generation/editing; 1K/2K",
                "google/gemini-3.1-flash-image\tGoogle generation/editing; 512/1K/2K/4K",
                "google/gemini-3.1-flash-lite-image\tFast 1K value; generation/editing",
                "microsoft/mai-image-2.5\tSingle-reference generation/editing",
            ],
        )


class TestPayload(unittest.TestCase):
    """WHEN generation or editing payloads are built."""

    def test_it_should_default_to_the_quality_value_model_and_private_routing(self) -> None:
        payload = MOD.build_payload(
            "a cat astronaut",
            model=MOD.DEFAULT_MODEL,
            inputs=[],
            aspect_ratio="16:9",
            resolution="1K",
        )
        self.assertEqual(payload["model"], "bytedance-seed/seedream-5-0-pro")
        self.assertEqual(
            payload["provider"],
            {"data_collection": "deny", "zdr": True, "sort": "latency"},
        )
        self.assertEqual(payload["aspect_ratio"], "16:9")
        self.assertEqual(payload["resolution"], "1K")
        self.assertNotIn("input_references", payload)

    def test_it_should_encode_stripped_repeatable_local_inputs_as_data_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "one.png"
            second = Path(tmp) / "two.jpg"
            first.write_bytes(b"png-bytes")
            second.write_bytes(b"jpeg-bytes")
            with mock.patch.object(
                MOD,
                "stripped_image_bytes",
                side_effect=[b"stripped-png", b"stripped-jpeg"],
            ):
                payload = MOD.build_payload(
                    "combine these",
                    model=MOD.DEFAULT_MODEL,
                    inputs=[first, second],
                    aspect_ratio=None,
                    resolution=None,
                )
        urls = [item["image_url"]["url"] for item in payload["input_references"]]
        self.assertEqual(urls[0], "data:image/png;base64," + base64.b64encode(b"stripped-png").decode("ascii"))
        self.assertEqual(urls[1], "data:image/jpeg;base64," + base64.b64encode(b"stripped-jpeg").decode("ascii"))

    def test_it_should_reject_missing_or_non_image_inputs_before_a_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.png"
            text = Path(tmp) / "input.txt"
            text.write_text("not an image", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                MOD.input_reference(missing)
            with self.assertRaises(ValueError):
                MOD.input_reference(text)


class TestInputPrivacy(unittest.TestCase):
    """WHEN a local image is prepared for cloud upload."""

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick is not installed")
    def test_it_should_strip_metadata_without_modifying_the_source_pixels_or_file(self) -> None:
        secret = "secret-location-metadata"
        original = _png_with_metadata(secret)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "family.png"
            source.write_bytes(original)
            reference = MOD.input_reference(source)
            uploaded = base64.b64decode(reference["image_url"]["url"].split(",", 1)[1])
            self.assertEqual(source.read_bytes(), original)
        self.assertNotIn(secret.encode("utf-8"), uploaded)
        self.assertEqual(uploaded[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", uploaded[16:24]), (2, 1))

    def test_it_should_fail_closed_when_imagemagick_is_unavailable_or_rejects_the_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "family.png"
            source.write_bytes(_png_with_metadata("secret"))
            with mock.patch.object(MOD.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "ImageMagick is required"):
                    MOD.input_reference(source)
            failed = subprocess.CompletedProcess(["magick"], 1, stdout="", stderr="decode failed")
            with (
                mock.patch.object(MOD.shutil, "which", return_value="/opt/homebrew/bin/magick"),
                mock.patch.object(MOD.subprocess, "run", return_value=failed),
            ):
                with self.assertRaisesRegex(RuntimeError, "metadata stripping failed.*decode failed"):
                    MOD.input_reference(source)


class TestRequestImage(unittest.TestCase):
    """WHEN OpenRouter returns a dedicated Images API response."""

    def test_it_should_post_bearer_json_and_decode_the_first_image(self) -> None:
        captured: dict = {}
        png = b"\x89PNG\r\n\x1a\nfixture"

        def open_url(request: urllib.request.Request, *, timeout: int):
            captured["request"] = request
            captured["timeout"] = timeout
            body = json.dumps(
                {"data": [{"b64_json": base64.b64encode(png).decode("ascii"), "media_type": "image/png"}]}
            ).encode("utf-8")
            return _Response(body)

        payload = {"model": MOD.DEFAULT_MODEL, "prompt": "a cat"}
        image, mime = MOD.request_image(payload, "fixture-key", open_url=open_url)
        request = captured["request"]
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/images")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-key")
        self.assertEqual(json.loads(request.data), payload)
        self.assertEqual(captured["timeout"], MOD.HTTP_TIMEOUT_S)
        self.assertEqual((image, mime), (png, "image/png"))

    def test_it_should_reject_missing_or_invalid_image_data(self) -> None:
        def response(payload: dict):
            return lambda _request, timeout: _Response(json.dumps(payload).encode("utf-8"))

        with self.assertRaisesRegex(RuntimeError, "no image data"):
            MOD.request_image({}, "key", open_url=response({"data": []}))
        with self.assertRaisesRegex(RuntimeError, "invalid base64"):
            MOD.request_image({}, "key", open_url=response({"data": [{"b64_json": "%%%"}]}))


class TestApiKey(unittest.TestCase):
    """WHEN OpenRouter credentials are resolved."""

    def test_it_should_prefer_the_environment_then_use_the_first_pass_line(self) -> None:
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": " env-key "}, clear=True):
            self.assertEqual(MOD.api_key(), "env-key")
        pass_result = subprocess.CompletedProcess(["pass"], 0, stdout="pass-key\nmetadata\n", stderr="")
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(MOD.subprocess, "run", return_value=pass_result),
        ):
            self.assertEqual(MOD.api_key(), "pass-key")

    def test_it_should_fail_closed_without_a_key(self) -> None:
        missing = subprocess.CompletedProcess(["pass"], 1, stdout="", stderr="missing")
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(MOD.subprocess, "run", return_value=missing),
        ):
            with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
                MOD.api_key()


class TestMain(unittest.TestCase):
    """WHEN a generated or edited image is written."""

    def test_it_should_write_the_requested_output_and_print_its_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested" / "result.png"
            stdout = io.StringIO()
            with (
                mock.patch.object(MOD, "api_key", return_value="key"),
                mock.patch.object(MOD, "request_image", return_value=(b"image", "image/png")),
                mock.patch.object(sys, "stdout", stdout),
            ):
                code = MOD.main(["a cat", "-o", str(output)])
            self.assertEqual(code, 0)
            self.assertEqual(output.read_bytes(), b"image")
            self.assertEqual(stdout.getvalue().strip(), str(output.resolve()))

    def test_it_should_correct_an_explicit_suffix_that_disagrees_with_the_returned_media_type(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            output = MOD.resolve_output("result.png", "a cat", [], "image/jpeg")
        self.assertEqual(output, (Path.cwd() / "result.jpg").resolve())
        self.assertIn("returned image/jpeg", stderr.getvalue())
        self.assertIn("result.jpg", stderr.getvalue())
        self.assertEqual(MOD.resolve_output("result.jpeg", "a cat", [], "image/jpeg").suffix, ".jpeg")

    def test_it_should_derive_edit_output_from_the_first_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "photo.png"
            source.write_bytes(_png_with_metadata("fixture"))
            previous = Path.cwd()
            os.chdir(root)
            try:
                with (
                    mock.patch.object(MOD, "api_key", return_value="key"),
                    mock.patch.object(MOD, "request_image", return_value=(b"edited", "image/webp")),
                    mock.patch.object(sys, "stdout", io.StringIO()),
                ):
                    code = MOD.main(["make it blue", "-i", str(source)])
                output = root / "photo-edit.webp"
                self.assertEqual(code, 0)
                self.assertEqual(output.read_bytes(), b"edited")
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
