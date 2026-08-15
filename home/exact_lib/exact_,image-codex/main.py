#!/usr/bin/env python3
"""Generate or edit images through Codex's subscription-backed image_gen tool."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

VERSION = "1.0.0"
CODEX_TIMEOUT_S = 600

Runner = Callable[..., subprocess.CompletedProcess]


def _magick() -> str:
    executable = shutil.which("magick")
    if not executable:
        raise RuntimeError("ImageMagick is required to strip input metadata before upload")
    return executable


def sanitize_inputs(inputs: list[Path], destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    prepared: list[Path] = []
    for index, source in enumerate(inputs):
        if not source.is_file():
            raise FileNotFoundError(f"input image not found: {source}")
        output = destination / f"image-{index}.png"
        result = subprocess.run(
            [_magick(), str(source), "-auto-orient", "-strip", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            detail = (result.stderr or result.stdout or str(result.returncode)).strip()
            raise RuntimeError(f"input metadata stripping failed for {source}: {detail}")
        prepared.append(output)
    return prepared


def agent_prompt(prompt: str, input_count: int) -> str:
    if input_count:
        mode = (
            f"This is an edit of the {input_count} attached sanitized image(s). "
            f"Set num_last_images_to_include={input_count}. Omit referenced_image_paths."
        )
    else:
        mode = "This is a new generation. Omit both referenced_image_paths and num_last_images_to_include."
    return (
        "Call image_gen.imagegen exactly once. "
        f"{mode} Use this exact image prompt: {json.dumps(prompt)}. "
        "Do not call shell, web, or any other tool. After image_gen completes, return only JSON matching the "
        "output schema, with output_path set to the absolute saved image path reported by image_gen."
    )


def _schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"output_path": {"type": "string"}},
        "required": ["output_path"],
        "additionalProperties": False,
    }


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()


def run_codex(
    prompt: str,
    inputs: list[Path],
    *,
    runner: Runner = subprocess.run,
    codex: str | None = None,
) -> Path:
    executable = codex or shutil.which("codex")
    if not executable:
        raise RuntimeError("codex is not installed")

    with tempfile.TemporaryDirectory(prefix="image-codex-") as tmp:
        root = Path(tmp)
        prepared = sanitize_inputs(inputs, root / "inputs")
        schema_path = root / "output-schema.json"
        result_path = root / "last-message.json"
        schema_path.write_text(json.dumps(_schema()), encoding="utf-8")

        argv = [
            executable,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--enable",
            "image_generation",
            "--sandbox",
            "read-only",
            "--cd",
            str(root),
            "--color",
            "never",
        ]
        if prepared:
            argv.extend(["--image", *(str(path) for path in prepared)])
        argv.extend(
            [
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(result_path),
                agent_prompt(prompt, len(prepared)),
            ]
        )
        environment = os.environ.copy()
        environment.pop("OPENAI_API_KEY", None)
        result = runner(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=CODEX_TIMEOUT_S,
            env=environment,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()[-2000:]
            raise RuntimeError(f"Codex image generation failed: {detail}")
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            generated = Path(payload["output_path"]).expanduser().resolve()
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Codex returned no valid generated image path") from exc

    generated_root = (_codex_home() / "generated_images").resolve()
    if generated_root not in generated.parents:
        raise RuntimeError(f"Codex reported a path outside Codex generated_images: {generated}")
    if not generated.is_file() or generated.suffix.lower() != ".png":
        raise RuntimeError(f"Codex generated image is missing or not PNG: {generated}")
    return generated


def default_output(prompt: str, inputs: list[Path]) -> Path:
    if inputs:
        name = f"{inputs[0].stem}-codex-edit"
    else:
        slug = "".join(char if char.isalnum() else "-" for char in prompt.lower())
        name = "-".join(filter(None, slug.split("-")))[:50] or "image-codex"
    return Path(f"{name}.png").resolve()


def resolve_output(requested: str | None, prompt: str, inputs: list[Path]) -> Path:
    if not requested:
        return default_output(prompt, inputs)
    output = Path(requested).expanduser().resolve()
    if output.suffix.lower() != ".png":
        corrected = output.with_suffix(".png")
        print(f"note: Codex image_gen returns PNG; writing {corrected} instead of {output}", file=sys.stderr)
        return corrected
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=",image-codex",
        description="Generate or edit a PNG through Codex's built-in GPT Image 2 tool.",
        epilog=(
            "Uses Codex ChatGPT login, not OPENAI_API_KEY. Inputs are auto-oriented and stripped of metadata. "
            "Codex fixes quality, size, and background to auto and does not expose masks."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("prompt", help="generate or edit instruction")
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        default=[],
        metavar="IMAGE",
        help="local reference/edit image (repeatable; metadata stripped before upload)",
    )
    parser.add_argument("-o", "--output", help="output PNG path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = [Path(value).expanduser().resolve() for value in args.input]
    try:
        generated = run_codex(args.prompt, inputs)
        output = resolve_output(args.output, args.prompt, inputs)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(generated, output)
    except (FileNotFoundError, OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
