from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401
from _test_support import REPO

CLI = REPO / "home" / "exact_lib" / "exact_,image-local" / "main.py"


def _load():
    import importlib.util

    spec = importlib.util.spec_from_file_location("sd_image_local_under_test", CLI)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {CLI}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load()

SAMPLE_MANIFEST = """\
# comment
klein|leejet/FLUX.2-klein-9B-GGUF|flux-2-klein-9b-Q8_0.gguf
klein_llm|unsloth/Qwen3-8B-GGUF|Qwen3-8B-Q4_K_M.gguf
vae|Comfy-Org/flux2-dev|split_files/vae/flux2-vae.safetensors|flux2_ae.safetensors
"""

GEN_PATHS = {
    "klein": Path("/tmp/sd-image-models/flux-2-klein-9b-Q8_0.gguf"),
    "klein_llm": Path("/tmp/sd-image-models/Qwen3-8B-Q4_K_M.gguf"),
    "vae": Path("/tmp/sd-image-models/flux2_ae.safetensors"),
}


class TestCommandIdentity(unittest.TestCase):
    """WHEN the local image command surface is inspected."""

    def test_it_should_use_only_the_image_local_command_and_library_names(self) -> None:
        self.assertEqual(MOD.build_parser().prog, ",image-local")
        launcher = (REPO / "home" / "exact_bin" / "executable_,image-local.tmpl").read_text(encoding="utf-8")
        self.assertIn("lib/,image-local/main.py", launcher)
        self.assertNotIn("lib/,image/main.py", launcher)


def _fake_png(width: int, height: int) -> bytes:
    import struct

    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"\x00" * 20


def _touch_roles(root: Path, entries: list, roles: tuple[str, ...]) -> None:
    for role, _repo, _hf, dest in entries:
        if role in roles:
            (root / dest).write_bytes(b"x")


def _env(root: Path, *, offload: bool | None = None) -> dict[str, str]:
    env = {
        **os.environ,
        "SD_IMAGE_MANIFEST": str(root / "models.txt"),
        "SD_IMAGE_MODELS_ROOT": str(root),
        "SD_IMAGE_SD_CLI": "/usr/bin/true",
    }
    if offload is None:
        env.pop("SD_IMAGE_OFFLOAD_TO_CPU", None)
    else:
        env["SD_IMAGE_OFFLOAD_TO_CPU"] = "1" if offload else "0"
    return env


class TestParseManifest(unittest.TestCase):
    """WHEN the sd-image models.txt manifest is parsed."""

    def test_it_should_parse_the_deployed_manifest(self) -> None:
        path = REPO / "home" / "dot_config" / "sd-image" / "readonly_models.txt"
        entries = MOD.parse_manifest(path.read_text(encoding="utf-8").splitlines())
        self.assertEqual([entry[0] for entry in entries], list(MOD.KNOWN_ROLES))
        self.assertTrue(all(entry[2].endswith((".gguf", ".safetensors")) for entry in entries))
        vae = next(entry for entry in entries if entry[0] == "vae")
        self.assertEqual(vae[3], "flux2_ae.safetensors")
        self.assertIn("split_files/vae/", vae[2])
        self.assertNotIn("ideogram", [entry[0] for entry in entries])

    def test_it_should_keep_role_repo_file_and_optional_dest(self) -> None:
        entries = MOD.parse_manifest(io.StringIO(SAMPLE_MANIFEST))
        self.assertEqual([entry[0] for entry in entries], list(MOD.KNOWN_ROLES))
        self.assertEqual(entries[0][3], "flux-2-klein-9b-Q8_0.gguf")
        self.assertEqual(entries[2][3], "flux2_ae.safetensors")

    def test_it_should_reject_unknown_and_duplicate_roles(self) -> None:
        with self.assertRaises(ValueError):
            MOD.parse_manifest(io.StringIO("clip|owner/repo|file.gguf\n"))
        with self.assertRaises(ValueError):
            MOD.parse_manifest(io.StringIO("ideogram|leejet/ideogram-4-GGUF|ideogram4-Q4_0.gguf\n"))
        with self.assertRaises(ValueError):
            MOD.parse_manifest(io.StringIO("vae|a/b|one.safetensors\nvae|a/b|two.safetensors\n"))


class TestMissingRoles(unittest.TestCase):
    """WHEN required klein weights are missing on disk."""

    def test_it_should_name_missing_klein_roles_and_mention_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = MOD.parse_manifest(io.StringIO(SAMPLE_MANIFEST))
            (root / "models.txt").write_text(SAMPLE_MANIFEST, encoding="utf-8")
            self.assertEqual(MOD.missing_roles(entries, root, MOD.REQUIRED_ROLES), list(MOD.REQUIRED_ROLES))
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, _env(root), clear=True), mock.patch.object(sys, "stderr", stderr):
                code = MOD.main(["a cat sitting on a windowsill"])
            self.assertEqual(code, 1)
            self.assertIn(",image-local sync", stderr.getvalue())
            self.assertIn("klein", stderr.getvalue())

    def test_it_should_refuse_edit_when_klein_weights_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = MOD.parse_manifest(io.StringIO(SAMPLE_MANIFEST))
            (root / "models.txt").write_text(SAMPLE_MANIFEST, encoding="utf-8")
            _touch_roles(root, entries, ("vae",))
            png = root / "in.png"
            png.write_bytes(_fake_png(64, 64))
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, _env(root), clear=True), mock.patch.object(sys, "stderr", stderr):
                code = MOD.main(["-i", str(png), "-p", "wear shorts"])
            self.assertEqual(code, 1)
            self.assertIn("klein", stderr.getvalue())
            self.assertIn(",image-local sync", stderr.getvalue())


class TestBuildGenArgv(unittest.TestCase):
    """WHEN sd-cli argv is built for FLUX.2 klein 9B generate."""

    def test_it_should_use_klein_plain_prompt_four_steps_and_omit_canvas(self) -> None:
        argv = MOD.build_gen_argv(
            sd_cli="/opt/sd-cli",
            paths=GEN_PATHS,
            prompt="a cat sitting on a windowsill",
            output=Path("/tmp/out.png"),
            width=None,
            height=None,
            steps=MOD.DEFAULT_STEPS,
            cfg=MOD.DEFAULT_CFG,
            seed=7,
            offload=True,
        )
        self.assertEqual(argv[0], "/opt/sd-cli")
        self.assertEqual(argv[argv.index("--diffusion-model") + 1], str(GEN_PATHS["klein"]))
        self.assertEqual(argv[argv.index("--llm") + 1], str(GEN_PATHS["klein_llm"]))
        self.assertEqual(argv[argv.index("--vae") + 1], str(GEN_PATHS["vae"]))
        self.assertEqual(argv[argv.index("-p") + 1], "a cat sitting on a windowsill")
        self.assertNotIn("-W", argv)
        self.assertNotIn("-H", argv)
        self.assertEqual(argv[argv.index("--steps") + 1], "4")
        self.assertEqual(argv[argv.index("--cfg-scale") + 1], "1.0")
        self.assertEqual(argv[argv.index("--seed") + 1], "7")
        self.assertIn("--diffusion-fa", argv)
        self.assertIn("--offload-to-cpu", argv)
        self.assertNotIn("-r", argv)
        self.assertNotIn("--uncond-diffusion-model", argv)
        self.assertNotIn("--sampling-method", argv)
        self.assertNotIn("--cache-mode", argv)
        self.assertNotIn("--llm_vision", argv)
        self.assertNotIn("{", argv[argv.index("-p") + 1])

    def test_it_should_pass_canvas_only_when_width_and_height_are_set(self) -> None:
        argv = MOD.build_gen_argv(
            sd_cli="/opt/sd-cli",
            paths=GEN_PATHS,
            prompt="a cat",
            output=Path("/tmp/out.png"),
            width=1024,
            height=1024,
            steps=MOD.DEFAULT_STEPS,
            cfg=MOD.DEFAULT_CFG,
            seed=None,
            offload=False,
        )
        self.assertEqual(argv[argv.index("-W") + 1], "1024")
        self.assertEqual(argv[argv.index("-H") + 1], "1024")


class TestBuildEditArgv(unittest.TestCase):
    """WHEN sd-cli argv is built for FLUX.2 klein 9B edit."""

    def test_it_should_use_klein_four_step_euler_and_omit_canvas(self) -> None:
        argv = MOD.build_edit_argv(
            sd_cli="sd-cli",
            paths=GEN_PATHS,
            refs=[Path("/tmp/a.png")],
            prompt="make the smaller kid wear shorts",
            output=Path("/tmp/out.png"),
            steps=MOD.DEFAULT_STEPS,
            cfg=MOD.DEFAULT_CFG,
            seed=None,
            offload=True,
        )
        self.assertEqual(argv[argv.index("--diffusion-model") + 1], str(GEN_PATHS["klein"]))
        self.assertEqual(argv[argv.index("--llm") + 1], str(GEN_PATHS["klein_llm"]))
        self.assertEqual(argv[argv.index("-p") + 1], "make the smaller kid wear shorts")
        self.assertEqual(argv[argv.index("--steps") + 1], "4")
        self.assertEqual(argv[argv.index("--cfg-scale") + 1], "1.0")
        self.assertEqual(argv[argv.index("--sampling-method") + 1], "euler")
        self.assertEqual(argv[argv.index("-r") + 1], "/tmp/a.png")
        self.assertIn("--diffusion-fa", argv)
        self.assertIn("--offload-to-cpu", argv)
        self.assertNotIn("-W", argv)
        self.assertNotIn("-H", argv)
        self.assertNotIn("--uncond-diffusion-model", argv)
        self.assertNotIn("--cache-mode", argv)
        self.assertNotIn("--llm_vision", argv)
        self.assertNotIn("{", argv[argv.index("-p") + 1])


class TestOffloadToCpu(unittest.TestCase):
    """WHEN work vs personal selects sd-cli --offload-to-cpu."""

    def test_it_should_keep_offload_when_the_env_is_unset(self) -> None:
        env = {key: value for key, value in os.environ.items() if key != MOD.OFFLOAD_ENV}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(MOD.use_offload_to_cpu())

    def test_it_should_skip_offload_on_personal_and_keep_it_on_work(self) -> None:
        with mock.patch.dict(os.environ, {MOD.OFFLOAD_ENV: "0"}, clear=False):
            self.assertFalse(MOD.use_offload_to_cpu())
        with mock.patch.dict(os.environ, {MOD.OFFLOAD_ENV: "1"}, clear=False):
            self.assertTrue(MOD.use_offload_to_cpu())
        personal = MOD.build_gen_argv(
            sd_cli="sd-cli",
            paths=GEN_PATHS,
            prompt="a cat",
            output=Path("/tmp/out.png"),
            width=None,
            height=None,
            steps=MOD.DEFAULT_STEPS,
            cfg=MOD.DEFAULT_CFG,
            seed=None,
            offload=False,
        )
        work = MOD.build_gen_argv(
            sd_cli="sd-cli",
            paths=GEN_PATHS,
            prompt="a cat",
            output=Path("/tmp/out.png"),
            width=None,
            height=None,
            steps=MOD.DEFAULT_STEPS,
            cfg=MOD.DEFAULT_CFG,
            seed=None,
            offload=True,
        )
        self.assertNotIn("--offload-to-cpu", personal)
        self.assertIn("--diffusion-fa", personal)
        self.assertIn("--offload-to-cpu", work)
        launcher = (REPO / "home" / "exact_bin" / "executable_,image-local.tmpl").read_text(encoding="utf-8")
        self.assertIn("eq .isWork true", launcher)
        self.assertIn(f"{MOD.OFFLOAD_ENV}=1", launcher)
        self.assertIn(f"{MOD.OFFLOAD_ENV}=0", launcher)


class TestMissingSdCli(unittest.TestCase):
    """WHEN sd-cli is not on PATH."""

    def test_it_should_tell_the_user_to_chezmoi_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "models.txt").write_text(SAMPLE_MANIFEST, encoding="utf-8")
            env = {
                "SD_IMAGE_MANIFEST": str(root / "models.txt"),
                "SD_IMAGE_MODELS_ROOT": str(root),
                "PATH": "/nonexistent",
            }
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, "stderr", stderr):
                code = MOD.main(["a cat"])
            self.assertEqual(code, 127)
            self.assertIn("chezmoi apply", stderr.getvalue())


class TestGenerateThroughMain(unittest.TestCase):
    """WHEN a positional prompt with no -i selects generate."""

    def test_it_should_dry_run_generate_argv_without_edit_flags_or_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = MOD.parse_manifest(io.StringIO(SAMPLE_MANIFEST))
            (root / "models.txt").write_text(SAMPLE_MANIFEST, encoding="utf-8")
            _touch_roles(root, entries, MOD.REQUIRED_ROLES)
            stdout = io.StringIO()
            with (
                mock.patch.dict(os.environ, _env(root, offload=False), clear=True),
                mock.patch.object(sys, "stdout", stdout),
            ):
                code = MOD.main(["a cat sitting on a windowsill", "--dry-run"])
            self.assertEqual(code, 0)
            printed = stdout.getvalue()
            self.assertIn("a cat sitting on a windowsill", printed)
            self.assertIn("flux-2-klein-9b-Q8_0.gguf", printed)
            self.assertNotIn(" -W ", f" {printed} ")
            self.assertNotIn(" -H ", f" {printed} ")
            self.assertIn("--steps 4", printed)
            self.assertIn("--cfg-scale 1.0", printed)
            self.assertNotIn("high_level_description", printed)
            self.assertNotIn("--uncond-diffusion-model", printed)
            self.assertNotIn(" -r ", f" {printed} ")
            self.assertNotIn("--sampling-method", printed)
            self.assertNotIn("--offload-to-cpu", printed)

    def test_it_should_pass_canvas_when_both_width_and_height_are_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = MOD.parse_manifest(io.StringIO(SAMPLE_MANIFEST))
            (root / "models.txt").write_text(SAMPLE_MANIFEST, encoding="utf-8")
            _touch_roles(root, entries, MOD.REQUIRED_ROLES)
            stdout = io.StringIO()
            with (
                mock.patch.dict(os.environ, _env(root, offload=False), clear=True),
                mock.patch.object(sys, "stdout", stdout),
            ):
                code = MOD.main(["a cat sitting on a windowsill", "--width", "1024", "--height", "1024", "--dry-run"])
            self.assertEqual(code, 0)
            printed = stdout.getvalue()
            self.assertIn("-W 1024", printed)
            self.assertIn("-H 1024", printed)

    def test_it_should_refuse_width_without_height(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            with self.assertRaises(SystemExit):
                MOD.main(["a cat", "--width", "1024", "--dry-run"])
        self.assertIn("together", stderr.getvalue())


class TestEditThroughMain(unittest.TestCase):
    """WHEN -i selects the klein edit path."""

    def test_it_should_dry_run_edit_argv_without_wrapping_the_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = MOD.parse_manifest(io.StringIO(SAMPLE_MANIFEST))
            (root / "models.txt").write_text(SAMPLE_MANIFEST, encoding="utf-8")
            _touch_roles(root, entries, MOD.REQUIRED_ROLES)
            png = root / "in.png"
            png.write_bytes(_fake_png(960, 1280))
            stdout = io.StringIO()
            with (
                mock.patch.dict(os.environ, _env(root, offload=True), clear=True),
                mock.patch.object(sys, "stdout", stdout),
            ):
                code = MOD.main(["-i", str(png), "-p", "wear shorts", "--dry-run"])
            self.assertEqual(code, 0)
            printed = stdout.getvalue()
            self.assertIn("wear shorts", printed)
            self.assertNotIn("high_level_description", printed)
            self.assertNotIn(" -W ", f" {printed} ")
            self.assertIn(" -r ", f" {printed} ")
            self.assertIn("--sampling-method euler", printed)
            self.assertIn("--offload-to-cpu", printed)

    def test_it_should_refuse_width_height_on_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = MOD.parse_manifest(io.StringIO(SAMPLE_MANIFEST))
            (root / "models.txt").write_text(SAMPLE_MANIFEST, encoding="utf-8")
            _touch_roles(root, entries, MOD.REQUIRED_ROLES)
            png = root / "in.png"
            png.write_bytes(_fake_png(960, 1280))
            stderr = io.StringIO()
            with (
                mock.patch.dict(os.environ, _env(root, offload=True), clear=True),
                mock.patch.object(sys, "stderr", stderr),
            ):
                with self.assertRaises(SystemExit):
                    MOD.main(["-i", str(png), "-p", "wear shorts", "--width", "512", "--height", "512", "--dry-run"])
            self.assertIn("input image", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
