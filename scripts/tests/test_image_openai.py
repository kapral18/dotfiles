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
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401
from _test_support import REPO

CLI = REPO / "home" / "exact_lib" / "exact_,image-openai" / "main.py"
COMPLETION = REPO / "home" / "dot_config" / "fish" / "completions" / "readonly_,image-openai.fish"


def _load():
    import importlib.util

    spec = importlib.util.spec_from_file_location("image_openai_under_test", CLI)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {CLI}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    """WHEN the native OpenAI image command surface is inspected."""

    def test_it_should_use_the_openai_command_and_library_names(self) -> None:
        self.assertEqual(MOD.build_parser().prog, ",image-openai")
        launcher = (REPO / "home" / "exact_bin" / "executable_,image-openai").read_text(encoding="utf-8")
        self.assertIn("lib/,image-openai/main.py", launcher)

    @unittest.skipUnless(shutil.which("fish"), "fish is not installed")
    def test_it_should_complete_all_native_output_and_mask_controls(self) -> None:
        result = subprocess.run(
            [
                shutil.which("fish") or "fish",
                "-c",
                "source $argv[1]; complete -C ',image-openai -'",
                str(COMPLETION),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout
        for option in ("--input", "--mask", "--quality", "--size", "--format", "--compression", "--background"):
            self.assertIn(option, output)


class TestOptions(unittest.TestCase):
    """WHEN native GPT Image 2 controls are parsed."""

    def test_it_should_accept_auto_and_valid_arbitrary_sizes(self) -> None:
        self.assertEqual(MOD.parse_size("auto"), "auto")
        self.assertEqual(MOD.parse_size("2048x1152"), "2048x1152")

    def test_it_should_reject_sizes_outside_gpt_image_2_constraints(self) -> None:
        for size in ("1025x1024", "4096x1024", "512x512", "3072x512", "not-a-size"):
            with self.subTest(size=size), self.assertRaises(ValueError):
                MOD.parse_size(size)

    def test_it_should_require_input_for_masks_and_non_png_for_compression(self) -> None:
        with self.assertRaisesRegex(ValueError, "mask requires at least one input"):
            MOD.validate_options([], Path("mask.png"), "png", None)
        with self.assertRaisesRegex(ValueError, "compression requires jpeg or webp"):
            MOD.validate_options([], None, "png", 50)


class TestInputPreparation(unittest.TestCase):
    """WHEN local images and masks are prepared for upload."""

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick is not installed")
    def test_it_should_strip_metadata_without_modifying_the_source(self) -> None:
        secret = "secret-location-metadata"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "family.png"
            original = _png_with_metadata(secret)
            source.write_bytes(original)
            prepared, mask = MOD.prepare_uploads([source], None, root / "prepared")
            uploaded = prepared[0].read_bytes()
            self.assertIsNone(mask)
            self.assertEqual(source.read_bytes(), original)
            self.assertNotIn(secret.encode(), uploaded)
            self.assertEqual(MOD.image_info(prepared[0])[:2], (2, 1))

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick is not installed")
    def test_it_should_convert_a_black_and_white_mask_to_matching_png_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "image.png"
            mask = root / "mask.png"
            subprocess.run(["magick", "-size", "16x16", "xc:red", str(source)], check=True)
            subprocess.run(["magick", "-size", "16x16", "xc:black", str(mask)], check=True)
            prepared, prepared_mask = MOD.prepare_uploads([source], mask, root / "prepared")
            self.assertIsNotNone(prepared_mask)
            self.assertEqual(MOD.image_info(prepared[0])[:2], MOD.image_info(prepared_mask)[:2])
            self.assertIn("a", MOD.image_info(prepared_mask)[2].lower())

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick is not installed")
    def test_it_should_reject_a_mask_with_different_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "image.png"
            mask = root / "mask.png"
            subprocess.run(["magick", "-size", "16x16", "xc:red", str(source)], check=True)
            subprocess.run(["magick", "-size", "32x16", "xc:black", str(mask)], check=True)
            with self.assertRaisesRegex(ValueError, "same dimensions"):
                MOD.prepare_uploads([source], mask, root / "prepared")


class TestRequests(unittest.TestCase):
    """WHEN generation and edit requests are sent to the native Images API."""

    def test_it_should_send_generation_as_json_with_gpt_image_2_controls(self) -> None:
        captured: dict = {}
        image = b"png"

        def open_url(request: urllib.request.Request, *, timeout: int):
            captured["request"] = request
            captured["timeout"] = timeout
            body = json.dumps({"data": [{"b64_json": base64.b64encode(image).decode()}]}).encode()
            return _Response(body)

        result = MOD.request_image(
            "draw",
            key="key",
            inputs=[],
            mask=None,
            quality="high",
            size="2048x2048",
            output_format="webp",
            compression=80,
            background="opaque",
            open_url=open_url,
        )
        request = captured["request"]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, MOD.GENERATION_URL)
        self.assertEqual(payload["model"], "gpt-image-2")
        self.assertEqual(payload["quality"], "high")
        self.assertEqual(payload["size"], "2048x2048")
        self.assertEqual(payload["output_format"], "webp")
        self.assertEqual(payload["output_compression"], 80)
        self.assertNotIn("input_fidelity", payload)
        self.assertEqual(result, image)

    def test_it_should_send_repeatable_images_and_mask_as_multipart(self) -> None:
        captured: dict = {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "image-0.png"
            second = root / "image-1.png"
            mask = root / "mask.png"
            for path, data in ((first, b"first"), (second, b"second"), (mask, b"mask")):
                path.write_bytes(data)

            def open_url(request: urllib.request.Request, *, timeout: int):
                captured["request"] = request
                body = json.dumps({"data": [{"b64_json": base64.b64encode(b"edit").decode()}]}).encode()
                return _Response(body)

            MOD.request_image(
                "edit",
                key="key",
                inputs=[first, second],
                mask=mask,
                quality="medium",
                size="auto",
                output_format="png",
                compression=None,
                background="auto",
                open_url=open_url,
            )

        request = captured["request"]
        body = request.data
        self.assertEqual(request.full_url, MOD.EDIT_URL)
        self.assertEqual(body.count(b'name="image[]"'), 2)
        self.assertIn(b'name="mask"', body)
        self.assertIn(b'name="quality"\r\n\r\nmedium', body)
        self.assertNotIn(b"input_fidelity", body)

    def test_it_should_redact_api_key_fragments_from_provider_errors(self) -> None:
        def open_url(_request: urllib.request.Request, *, timeout: int):
            body = io.BytesIO(b'{"message":"Incorrect API key: sk-ABC********XYZ"}')
            raise urllib.error.HTTPError(MOD.GENERATION_URL, 401, "unauthorized", {}, body)

        with self.assertRaises(RuntimeError) as raised:
            MOD.request_image(
                "draw",
                key="sk-complete-secret",
                inputs=[],
                mask=None,
                quality="auto",
                size="auto",
                output_format="png",
                compression=None,
                background="auto",
                open_url=open_url,
            )
        self.assertIn("sk-REDACTED", str(raised.exception))
        self.assertNotIn("ABC", str(raised.exception))
        self.assertNotIn("complete-secret", str(raised.exception))


class TestCredentialsAndMain(unittest.TestCase):
    """WHEN credentials resolve and an image is written."""

    def test_it_should_prefer_the_environment_then_use_the_first_pass_line(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": " env-key "}, clear=True):
            self.assertEqual(MOD.api_key(), "env-key")
        pass_result = subprocess.CompletedProcess(["pass"], 0, stdout="pass-key\nmetadata\n", stderr="")
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(MOD.subprocess, "run", return_value=pass_result),
        ):
            self.assertEqual(MOD.api_key(), "pass-key")

    def test_it_should_write_the_requested_format_and_print_the_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested" / "result.png"
            stdout = io.StringIO()
            with (
                mock.patch.object(MOD, "api_key", return_value="key"),
                mock.patch.object(MOD, "request_image", return_value=b"image"),
                mock.patch.object(sys, "stdout", stdout),
            ):
                code = MOD.main(["draw", "-o", str(output), "--quality", "high"])
            self.assertEqual(code, 0)
            self.assertEqual(output.read_bytes(), b"image")
            self.assertEqual(stdout.getvalue().strip(), str(output.resolve()))


MOD = _load()


if __name__ == "__main__":
    unittest.main()
