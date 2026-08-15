#!/usr/bin/env python3
"""Local FLUX.2 klein 9B generate and edit via sd-cli.

On-device. Not an agent-invoked tool. General cloud generate/edit uses ``,image-openrouter``.

Usage:
    ,image-local sync
    ,image-local status
    ,image-local "a cat sitting on a windowsill"
    ,image-local -i photo.png -p "make the smaller kid wear shorts"
    ,image-local --version
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "2.0.0"
SD_CLI_DEFAULT_SIZE = 512
DEFAULT_STEPS = 4
DEFAULT_CFG = 1.0
EDIT_SAMPLING = "euler"
COMPLETE_SUFFIXES = {".gguf", ".safetensors"}
REQUIRED_ROLES = ("klein", "klein_llm", "vae")
KNOWN_ROLES = REQUIRED_ROLES
OFFLOAD_ENV = "SD_IMAGE_OFFLOAD_TO_CPU"

ManifestEntry = tuple[str, str, str, str]


def models_root() -> Path:
    override = os.environ.get("SD_IMAGE_MODELS_ROOT")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".local/share/sd-image/models"


def manifest_path() -> Path:
    override = os.environ.get("SD_IMAGE_MANIFEST")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config/sd-image/models.txt"


def sd_cli_path() -> str | None:
    override = os.environ.get("SD_IMAGE_SD_CLI")
    if override:
        return override
    return shutil.which("sd-cli")


def parse_manifest(stream) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    seen_roles: set[str] = set()
    for raw in stream:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 3:
            role, hf_repo, hf_file = parts
            dest = Path(hf_file).name
        elif len(parts) == 4:
            role, hf_repo, hf_file, dest = parts
        else:
            raise ValueError(f"malformed manifest line: {line!r}")
        if not role or not hf_repo or not hf_file or not dest or Path(dest).name != dest:
            raise ValueError(f"malformed manifest line: {line!r}")
        if role not in KNOWN_ROLES:
            raise ValueError(f"unknown manifest role {role!r} in line: {line!r}")
        if role in seen_roles:
            raise ValueError(f"duplicate manifest role {role!r}")
        seen_roles.add(role)
        entries.append((role, hf_repo, hf_file, dest))
    return entries


def is_model_complete(target: Path) -> bool:
    return target.is_file() and target.suffix.lower() in COMPLETE_SUFFIXES and target.stat().st_size > 0


def missing_roles(entries: list[ManifestEntry], root: Path, required: tuple[str, ...]) -> list[str]:
    present = {role for role, _repo, _file, dest in entries if is_model_complete(root / dest)}
    missing: list[str] = []
    for role in required:
        declared = any(entry[0] == role for entry in entries)
        if not declared or role not in present:
            missing.append(role)
    return missing


def resolved_paths(entries: list[ManifestEntry], root: Path) -> dict[str, Path]:
    return {role: root / dest for role, _repo, _file, dest in entries}


def download_one(hf_repo: str, hf_file: str, dest: str, root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    dest_path = root / dest
    staged_root: Path | None = None
    local_dir = root
    if dest != hf_file:
        staged_root = root / ".hf-download" / dest
        if staged_root.exists():
            shutil.rmtree(staged_root)
        staged_root.mkdir(parents=True, exist_ok=True)
        local_dir = staged_root
    print(f"==> hf download {hf_repo} {hf_file} -> {local_dir}", flush=True)
    cmd = ["hf", "download", hf_repo, hf_file, "--local-dir", str(local_dir)]
    try:
        try:
            result = subprocess.run(cmd, check=False)
        except FileNotFoundError:
            print("error: `hf` CLI not found on PATH (brew install hf)", file=sys.stderr)
            return 127
        if result.returncode != 0:
            print(
                f"error: hf download failed for {hf_repo}/{hf_file} (exit {result.returncode})\n"
                f"if the repo is gated, accept the license at https://huggingface.co/{hf_repo}",
                file=sys.stderr,
            )
            return result.returncode
        if dest != hf_file:
            src = local_dir / hf_file
            if not src.is_file():
                print(f"error: hf download did not produce {src}", file=sys.stderr)
                return 1
            src.replace(dest_path)
        return 0
    finally:
        if staged_root is not None:
            shutil.rmtree(staged_root, ignore_errors=True)
            parent = root / ".hf-download"
            try:
                parent.rmdir()
            except OSError:
                pass


def use_offload_to_cpu() -> bool:
    raw = os.environ.get(OFFLOAD_ENV)
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _append_accel_flags(argv: list[str], *, offload: bool) -> None:
    argv.append("--diffusion-fa")
    if offload:
        argv.append("--offload-to-cpu")
    argv.append("-v")


def build_gen_argv(
    *,
    sd_cli: str,
    paths: dict[str, Path],
    prompt: str,
    output: Path,
    width: int | None,
    height: int | None,
    steps: int | None,
    cfg: float | None,
    seed: int | None,
    offload: bool,
) -> list[str]:
    argv = [
        sd_cli,
        "--diffusion-model",
        str(paths["klein"]),
        "--vae",
        str(paths["vae"]),
        "--llm",
        str(paths["klein_llm"]),
        "-p",
        prompt,
        "-o",
        str(output),
    ]
    if width is not None and height is not None:
        argv.extend(["-W", str(width), "-H", str(height)])
    _append_accel_flags(argv, offload=offload)
    return _append_sample_flags(argv, steps=steps, cfg=cfg, seed=seed)


def build_edit_argv(
    *,
    sd_cli: str,
    paths: dict[str, Path],
    refs: list[Path],
    prompt: str,
    output: Path,
    steps: int,
    cfg: float,
    seed: int | None,
    offload: bool,
) -> list[str]:
    argv = [
        sd_cli,
        "--diffusion-model",
        str(paths["klein"]),
        "--vae",
        str(paths["vae"]),
        "--llm",
        str(paths["klein_llm"]),
        "-p",
        prompt,
        "-o",
        str(output),
        "--steps",
        str(steps),
        "--cfg-scale",
        str(cfg),
        "--sampling-method",
        EDIT_SAMPLING,
    ]
    _append_accel_flags(argv, offload=offload)
    for ref in refs:
        argv.extend(["-r", str(ref)])
    return _append_sample_flags(argv, steps=None, cfg=None, seed=seed)


def _append_sample_flags(argv: list[str], *, steps: int | None, cfg: float | None, seed: int | None) -> list[str]:
    if steps is not None:
        argv.extend(["--steps", str(steps)])
    if cfg is not None:
        argv.extend(["--cfg-scale", str(cfg)])
    if seed is not None:
        argv.extend(["--seed", str(seed)])
    return argv


def load_manifest() -> list[ManifestEntry]:
    path = manifest_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"error: image manifest not found at {path}\n"
            "deploy it with: chezmoi apply --no-tty ~/.config/sd-image/models.txt"
        )
    return parse_manifest(path.read_text(encoding="utf-8").splitlines())


def cmd_sync() -> int:
    try:
        entries = load_manifest()
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    root = models_root()
    pending = [
        (hf_repo, hf_file, dest) for _role, hf_repo, hf_file, dest in entries if not is_model_complete(root / dest)
    ]
    if not pending:
        print("All ,image-local weights already present; nothing to download.")
        return 0
    if shutil.which("hf") is None:
        print("error: `hf` CLI not found on PATH (brew install hf)", file=sys.stderr)
        return 127
    failures = 0
    for hf_repo, hf_file, dest in pending:
        if download_one(hf_repo, hf_file, dest, root) != 0:
            failures += 1
    if failures:
        print(f"Completed with {failures} failure(s).", file=sys.stderr)
        return 1
    print("All ,image-local weights synced.")
    return 0


def cmd_status() -> int:
    sd_cli = sd_cli_path()
    print(f"sd-cli: {sd_cli or 'MISSING (chezmoi apply installs the zip_opt wrapper)'}")
    try:
        entries = load_manifest()
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    root = models_root()
    print(f"models root: {root}")
    print(f"manifest: {manifest_path()}")
    for role, hf_repo, hf_file, dest in entries:
        target = root / dest
        state = "present" if is_model_complete(target) else "MISSING"
        print(f"{role}: {state}  {target}  ({hf_repo}/{hf_file})")
    missing = missing_roles(entries, root, REQUIRED_ROLES)
    if missing:
        print(f"missing roles: {', '.join(missing)}")
        print("run: ,image-local sync")
        return 1
    return 0


def default_gen_output(prompt: str) -> Path:
    slug = "".join(char if char.isalnum() else "-" for char in prompt.lower())
    slug = "-".join(filter(None, slug.split("-")))[:50] or "image"
    return Path(f"{slug}.png").resolve()


def default_edit_output(images: list[Path]) -> Path:
    return Path(f"{images[0].stem}-edit.png").resolve()


def require_runtime(required: tuple[str, ...]) -> tuple[str, list[ManifestEntry], Path] | int:
    sd_cli = sd_cli_path()
    if not sd_cli:
        print("error: sd-cli not found on PATH\ninstall it with: chezmoi apply", file=sys.stderr)
        return 127
    try:
        entries = load_manifest()
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    root = models_root()
    missing = missing_roles(entries, root, required)
    if missing:
        print(f"error: missing ,image-local weights: {', '.join(missing)}\nrun: ,image-local sync", file=sys.stderr)
        return 1
    return sd_cli, entries, root


def run_sd_cli(argv: list[str], output: Path, dry_run: bool) -> int:
    if dry_run:
        print(shlex.join(argv))
        return 0
    result = subprocess.run(argv, stdout=sys.stderr, check=False)
    if result.returncode != 0:
        return result.returncode
    if not output.is_file():
        print(f"error: sd-cli exited 0 but did not write {output}", file=sys.stderr)
        return 1
    print(output)
    return 0


def cmd_generate(args: argparse.Namespace, prompt: str) -> int:
    prepared = require_runtime(REQUIRED_ROLES)
    if isinstance(prepared, int):
        return prepared
    sd_cli, entries, root = prepared
    output = Path(args.output).expanduser().resolve() if args.output else default_gen_output(prompt)
    output.parent.mkdir(parents=True, exist_ok=True)
    argv = build_gen_argv(
        sd_cli=sd_cli,
        paths=resolved_paths(entries, root),
        prompt=prompt,
        output=output,
        width=args.width,
        height=args.height,
        steps=DEFAULT_STEPS if args.steps is None else args.steps,
        cfg=DEFAULT_CFG if args.cfg is None else args.cfg,
        seed=args.seed,
        offload=use_offload_to_cpu(),
    )
    return run_sd_cli(argv, output, args.dry_run)


def cmd_edit(args: argparse.Namespace, prompt: str) -> int:
    prepared = require_runtime(REQUIRED_ROLES)
    if isinstance(prepared, int):
        return prepared
    sd_cli, entries, root = prepared
    images = [Path(image).expanduser().resolve() for image in args.images]
    for image in images:
        if not image.is_file():
            print(f"error: input image not found: {image}", file=sys.stderr)
            return 1
    output = Path(args.output).expanduser().resolve() if args.output else default_edit_output(images)
    output.parent.mkdir(parents=True, exist_ok=True)
    argv = build_edit_argv(
        sd_cli=sd_cli,
        paths=resolved_paths(entries, root),
        refs=images,
        prompt=prompt,
        output=output,
        steps=DEFAULT_STEPS if args.steps is None else args.steps,
        cfg=DEFAULT_CFG if args.cfg is None else args.cfg,
        seed=args.seed,
        offload=use_offload_to_cpu(),
    )
    return run_sd_cli(argv, output, args.dry_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=",image-local",
        description="Local FLUX.2 klein 9B generate and edit via sd-cli.",
        epilog="Subcommands: sync (~15 GB weights), status. Default is generate. -i edits. Not an agent skill.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("prompt", nargs="?", help="generate or edit instruction")
    parser.add_argument(
        "-i", "--image", action="append", dest="images", metavar="IMAGE", help="input image (edit; repeatable)"
    )
    parser.add_argument(
        "-p", "--prompt", dest="prompt_flag", metavar="PROMPT", help="instruction (overrides the positional prompt)"
    )
    parser.add_argument("-o", "--output", help="output path")
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help=f"generate canvas width (omit for sd-cli default {SD_CLI_DEFAULT_SIZE}; edit follows the input image)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help=f"generate canvas height (omit for sd-cli default {SD_CLI_DEFAULT_SIZE}; edit follows the input image)",
    )
    parser.add_argument("--steps", type=int, default=None, help=f"diffusion steps (default: {DEFAULT_STEPS})")
    parser.add_argument("--cfg", type=float, default=None, help=f"CFG scale (default: {DEFAULT_CFG})")
    parser.add_argument("--seed", type=int, default=None, help="optional RNG seed")
    parser.add_argument("--dry-run", action="store_true", help="print sd-cli argv and exit")
    return parser


def resolved_prompt(args: argparse.Namespace) -> str:
    if args.prompt_flag:
        return args.prompt_flag
    return args.prompt or ""


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] == "sync":
        if raw[1:]:
            print("error: sync takes no arguments", file=sys.stderr)
            return 2
        return cmd_sync()
    if raw and raw[0] == "status":
        if raw[1:]:
            print("error: status takes no arguments", file=sys.stderr)
            return 2
        return cmd_status()
    parser = build_parser()
    args = parser.parse_args(raw)
    prompt = resolved_prompt(args).strip()
    if not prompt:
        parser.error("prompt required (positional or -p/--prompt); or use sync/status")
    if (args.width is None) != (args.height is None):
        parser.error("--width and --height must be passed together")
    if args.images:
        if args.width is not None or args.height is not None:
            parser.error("edit follows the input image size; do not pass --width/--height")
        return cmd_edit(args, prompt)
    return cmd_generate(args, prompt)


if __name__ == "__main__":
    raise SystemExit(main())
