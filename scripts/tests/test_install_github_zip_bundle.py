from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

import _test_support  # noqa: F401
from install_github_zip_bundle import (
    InstallError,
    already_installed,
    find_bundle_root,
    install_bundle,
    write_wrapper,
)


def _make_zip(tmp: Path, *, nested: bool = False) -> Path:
    bundle = tmp / "bundle"
    root = bundle / "nested" if nested else bundle
    root.mkdir(parents=True)
    binary = root / "sd-cli"
    binary.write_text("#!/bin/sh\necho fake-sd\n", encoding="utf-8")
    binary.chmod(0o755)
    (root / "libstable-diffusion.dylib").write_bytes(b"dylib")
    zip_path = tmp / "sd.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for path in root.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(bundle if nested else root).as_posix())
    return zip_path


class TestInstallGithubZipBundle(unittest.TestCase):
    """WHEN a GitHub zip_opt bundle is installed without gh."""

    def test_it_should_copy_sibling_dylib_and_write_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            zip_path = _make_zip(tmp_path)
            opt_dir = tmp_path / "opt" / "sd-cli"
            wrapper = tmp_path / "bin" / "sd-cli"

            def download(repo, tag, pattern, dest_dir):
                dest_dir.mkdir(parents=True)
                copied = dest_dir / zip_path.name
                copied.write_bytes(zip_path.read_bytes())
                return copied

            result = install_bundle(
                repo="leejet/stable-diffusion.cpp",
                tag="master-820-de298c2",
                pattern="sd-*-bin-Darwin-macOS-*-arm64.zip",
                opt_dir=opt_dir,
                bin_name="sd-cli",
                wrapper_path=wrapper,
                download=download,
            )

            self.assertEqual(result, "installed")
            self.assertTrue((opt_dir / "sd-cli").is_file())
            self.assertTrue((opt_dir / "libstable-diffusion.dylib").is_file())
            self.assertEqual((opt_dir / ".release-tag").read_text(encoding="utf-8").strip(), "master-820-de298c2")
            body = wrapper.read_text(encoding="utf-8")
            self.assertIn("DYLD_FALLBACK_LIBRARY_PATH", body)
            self.assertIn('exec "$ROOT/sd-cli"', body)
            self.assertTrue(wrapper.stat().st_mode & 0o111)

    def test_it_should_skip_when_release_tag_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            opt_dir = tmp_path / "opt" / "sd-cli"
            opt_dir.mkdir(parents=True)
            (opt_dir / "sd-cli").write_text("#!/bin/sh\n", encoding="utf-8")
            (opt_dir / ".release-tag").write_text("master-820-de298c2\n", encoding="utf-8")
            wrapper = tmp_path / "bin" / "sd-cli"
            write_wrapper(wrapper, opt_dir, "sd-cli")

            def download(*_args):
                raise AssertionError("download must not run when the tag already matches")

            result = install_bundle(
                repo="leejet/stable-diffusion.cpp",
                tag="master-820-de298c2",
                pattern="*.zip",
                opt_dir=opt_dir,
                bin_name="sd-cli",
                wrapper_path=wrapper,
                download=download,
            )
            self.assertEqual(result, "skipped")
            self.assertTrue(already_installed(opt_dir, wrapper, "sd-cli", "master-820-de298c2"))

    def test_it_should_use_nested_zip_directory_as_bundle_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            zip_path = _make_zip(tmp_path, nested=True)
            extract = tmp_path / "extract"
            extract.mkdir()
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract)
            root = find_bundle_root(extract, "sd-cli")
            self.assertEqual(root.name, "nested")
            self.assertTrue((root / "libstable-diffusion.dylib").is_file())

    def test_it_should_reject_a_bin_name_with_a_slash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with self.assertRaises(InstallError):
                install_bundle(
                    repo="owner/repo",
                    tag="v1",
                    pattern="*.zip",
                    opt_dir=tmp_path / "opt",
                    bin_name="bin/sd-cli",
                    wrapper_path=tmp_path / "sd-cli",
                    download=lambda *_: tmp_path / "missing.zip",
                )


if __name__ == "__main__":
    unittest.main()
