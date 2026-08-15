#!/usr/bin/env python3
"""Install a GitHub release zip into ~/.local/opt/<name> and write a PATH wrapper.

Usage:
    install_github_zip_bundle.py <repo> <tag> <asset-pattern> <opt_dir> <bin-in-zip> <wrapper_path>

The zip is extracted and the directory that contains <bin-in-zip> (plus sibling
dylibs) is copied to opt_dir. A wrapper at wrapper_path execs that binary with
DYLD_FALLBACK_LIBRARY_PATH / LD_LIBRARY_PATH set to opt_dir.

Skip when opt_dir/.release-tag already matches <tag> and the wrapper plus binary
exist. sd-cli --version does not print the GitHub release tag, so this file is
the idempotency gate (not binary_matches_release_tag).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path

DownloadFn = Callable[[str, str, str, Path], Path]


class InstallError(Exception):
    """Fatal install failure with a user-facing message."""


def download_release_zip(repo: str, tag: str, pattern: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "gh",
        "release",
        "download",
        tag,
        "--repo",
        repo,
        "--pattern",
        pattern,
        "--dir",
        str(dest_dir),
        "--clobber",
    ]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise InstallError("error: `gh` CLI not found on PATH") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise InstallError(
            f"error: gh release download failed for {repo}@{tag} (exit {result.returncode})"
            + (f": {detail}" if detail else "")
        )
    zips = sorted(dest_dir.glob("*.zip"))
    if len(zips) != 1:
        names = ", ".join(path.name for path in zips) or "(none)"
        raise InstallError(f"error: expected exactly one zip matching {pattern!r}, found: {names}")
    return zips[0]


def find_bundle_root(extract_dir: Path, bin_name: str) -> Path:
    matches = [path for path in extract_dir.rglob(bin_name) if path.is_file()]
    if len(matches) != 1:
        raise InstallError(f"error: expected exactly one {bin_name} in zip, found {len(matches)}")
    return matches[0].parent


def write_wrapper(wrapper_path: Path, opt_dir: Path, bin_name: str) -> None:
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    root = str(opt_dir.resolve())
    body = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"ROOT={root!r}\n"
        'export DYLD_FALLBACK_LIBRARY_PATH="$ROOT${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"\n'
        'export LD_LIBRARY_PATH="$ROOT${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
        f'exec "$ROOT/{bin_name}" "$@"\n'
    )
    wrapper_path.write_text(body, encoding="utf-8")
    wrapper_path.chmod(0o755)


def already_installed(opt_dir: Path, wrapper_path: Path, bin_name: str, tag: str) -> bool:
    tag_path = opt_dir / ".release-tag"
    binary = opt_dir / bin_name
    if not tag_path.is_file() or not wrapper_path.is_file() or not binary.is_file():
        return False
    return tag_path.read_text(encoding="utf-8").strip() == tag


def install_bundle(
    *,
    repo: str,
    tag: str,
    pattern: str,
    opt_dir: Path,
    bin_name: str,
    wrapper_path: Path,
    download: DownloadFn = download_release_zip,
) -> str:
    """Return ``skipped`` or ``installed``."""

    opt_dir = opt_dir.expanduser()
    wrapper_path = wrapper_path.expanduser()
    if Path(bin_name).name != bin_name:
        raise InstallError(f"error: bin-in-zip must be a basename, got {bin_name!r}")
    if already_installed(opt_dir, wrapper_path, bin_name, tag):
        return "skipped"

    with tempfile.TemporaryDirectory(prefix="zip-opt-") as tmp:
        tmp_path = Path(tmp)
        zip_path = download(repo, tag, pattern, tmp_path / "dl")
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)
        bundle_root = find_bundle_root(extract_dir, bin_name)
        staging = tmp_path / "opt"
        shutil.copytree(bundle_root, staging)
        (staging / ".release-tag").write_text(tag + "\n", encoding="utf-8")
        binary = staging / bin_name
        binary.chmod(binary.stat().st_mode | 0o111)
        opt_dir.parent.mkdir(parents=True, exist_ok=True)
        if opt_dir.exists():
            shutil.rmtree(opt_dir)
        shutil.move(str(staging), str(opt_dir))

    write_wrapper(wrapper_path, opt_dir, bin_name)
    return "installed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="GitHub owner/repo")
    parser.add_argument("tag", help="Release tag")
    parser.add_argument("pattern", help="gh --pattern glob for the zip asset")
    parser.add_argument("opt_dir", type=Path, help="Install directory, e.g. ~/.local/opt/sd-cli")
    parser.add_argument("bin_name", help="Basename of the binary inside the zip")
    parser.add_argument("wrapper_path", type=Path, help="PATH wrapper to write, e.g. ~/.local/bin/sd-cli")
    args = parser.parse_args(argv)

    try:
        result = install_bundle(
            repo=args.repo,
            tag=args.tag,
            pattern=args.pattern,
            opt_dir=args.opt_dir,
            bin_name=args.bin_name,
            wrapper_path=args.wrapper_path,
        )
    except InstallError as exc:
        print(exc, file=sys.stderr)
        return 1

    tool = args.wrapper_path.name
    if result == "skipped":
        print(f"{tool} is up to date ({args.tag})")
    else:
        print(f"{tool} installed ({args.tag})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
