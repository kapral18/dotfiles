from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401
from _test_support import REPO, load_module, png_with_metadata

CLI = REPO / "home" / "exact_lib" / "exact_,image-codex" / "main.py"
COMPLETION = REPO / "home" / "dot_config" / "fish" / "completions" / "readonly_,image-codex.fish"


class TestCommandIdentity(unittest.TestCase):
    """WHEN the Codex image command surface is inspected."""

    def test_it_should_use_the_codex_command_and_library_names(self) -> None:
        self.assertEqual(MOD.build_parser().prog, ",image-codex")
        launcher = (REPO / "home" / "exact_bin" / "executable_,image-codex").read_text(encoding="utf-8")
        self.assertIn("lib/,image-codex/main.py", launcher)

    @unittest.skipUnless(shutil.which("fish"), "fish is not installed")
    def test_it_should_complete_only_the_supported_codex_options(self) -> None:
        result = subprocess.run(
            [
                shutil.which("fish") or "fish",
                "-c",
                "source $argv[1]; complete -C ',image-codex -'",
                str(COMPLETION),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout
        self.assertIn("--input", output)
        self.assertIn("--output", output)
        self.assertNotIn("--mask", output)
        self.assertNotIn("--quality", output)


class TestCodexInvocation(unittest.TestCase):
    """WHEN generation or editing is delegated to Codex image_gen."""

    def test_it_should_request_generation_without_image_arguments(self) -> None:
        prompt = MOD.agent_prompt("draw a blue square", 0)
        self.assertIn("image_gen.imagegen exactly once", prompt)
        self.assertIn("Omit both referenced_image_paths and num_last_images_to_include", prompt)

    def test_it_should_request_editing_from_the_attached_sanitized_images(self) -> None:
        prompt = MOD.agent_prompt("add shorts", 2)
        self.assertIn("num_last_images_to_include=2", prompt)
        self.assertIn("Omit referenced_image_paths", prompt)

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick is not installed")
    def test_it_should_strip_inputs_and_use_chatgpt_auth_without_openai_api_key(self) -> None:
        secret = "secret-location-metadata"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "family.png"
            original = png_with_metadata(secret)
            source.write_bytes(original)
            codex_home = root / "codex-home"
            generated = codex_home / "generated_images" / "session" / "image.png"
            generated.parent.mkdir(parents=True)
            generated.write_bytes(b"generated")
            captured: dict = {}

            def runner(argv, **kwargs):
                captured["argv"] = argv
                captured["env"] = kwargs["env"]
                image_arg = Path(argv[argv.index("--image") + 1])
                captured["uploaded"] = image_arg.read_bytes()
                result_path = Path(argv[argv.index("--output-last-message") + 1])
                result_path.write_text(json.dumps({"output_path": str(generated)}), encoding="utf-8")
                return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

            with mock.patch.dict(
                os.environ,
                {
                    "CODEX_HOME": str(codex_home),
                    "OPENAI_API_KEY": "must-not-leak",
                    "PATH": os.environ["PATH"],
                },
                clear=True,
            ):
                result = MOD.run_codex("add shorts", [source], runner=runner, codex="/opt/bin/codex")

            self.assertEqual(result, generated.resolve())
            self.assertEqual(source.read_bytes(), original)
            self.assertNotIn(secret.encode(), captured["uploaded"])
            self.assertNotIn("OPENAI_API_KEY", captured["env"])
            self.assertIn("--ignore-user-config", captured["argv"])
            self.assertIn("image_generation", captured["argv"])

    def test_it_should_reject_a_model_reported_path_outside_codex_generated_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.png"
            outside.write_bytes(b"not-generated")

            def runner(argv, **_kwargs):
                result_path = Path(argv[argv.index("--output-last-message") + 1])
                result_path.write_text(json.dumps({"output_path": str(outside)}), encoding="utf-8")
                return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

            with mock.patch.dict(os.environ, {"CODEX_HOME": str(root / "codex-home")}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "outside Codex generated_images"):
                    MOD.run_codex("draw", [], runner=runner, codex="/opt/bin/codex")


class TestMain(unittest.TestCase):
    """WHEN a Codex-generated PNG is copied to its final path."""

    def test_it_should_copy_the_image_and_normalize_the_output_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated = root / "generated.png"
            generated.write_bytes(b"image")
            requested = root / "nested" / "result.jpg"
            stdout = io.StringIO()
            with (
                mock.patch.object(MOD, "run_codex", return_value=generated),
                mock.patch.object(sys, "stdout", stdout),
            ):
                code = MOD.main(["draw", "-o", str(requested)])
            output = root / "nested" / "result.png"
            self.assertEqual(code, 0)
            self.assertEqual(output.read_bytes(), b"image")
            self.assertEqual(stdout.getvalue().strip(), str(output.resolve()))


MOD = load_module("image_codex_under_test", CLI)


if __name__ == "__main__":
    unittest.main()
