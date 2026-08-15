#!/usr/bin/env python3
"""Generate or edit raster images through OpenAI's native GPT Image 2 API."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable

VERSION = "1.0.0"
MODEL = "gpt-image-2"
GENERATION_URL = "https://api.openai.com/v1/images/generations"
EDIT_URL = "https://api.openai.com/v1/images/edits"
HTTP_TIMEOUT_S = 300
PASS_ENTRY = "openai/api/token"
MAX_INPUT_BYTES = 50_000_000

_EXT_BY_FORMAT = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}
_SUFFIXES_BY_FORMAT = {"png": {".png"}, "jpeg": {".jpg", ".jpeg"}, "webp": {".webp"}}
_KEY_FRAGMENT = re.compile(r"sk-[A-Za-z0-9_.*-]+")

OpenUrl = Callable[..., object]


def api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        result = subprocess.run(
            ["pass", "show", PASS_ENTRY],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        result = None
    if result is not None and result.returncode == 0:
        lines = result.stdout.splitlines()
        if lines and lines[0].strip():
            return lines[0].strip()
    raise RuntimeError(f"set OPENAI_API_KEY or pass entry {PASS_ENTRY}")


def _magick() -> str:
    executable = shutil.which("magick")
    if not executable:
        raise RuntimeError("ImageMagick is required to strip input metadata before upload")
    return executable


def _run_magick(arguments: list[str], *, context: str) -> None:
    result = subprocess.run(
        [_magick(), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or str(result.returncode)).strip()
        raise RuntimeError(f"{context}: {detail}")


def image_info(path: Path) -> tuple[int, int, str]:
    result = subprocess.run(
        [_magick(), "identify", "-format", "%w %h %[channels]", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or str(result.returncode)).strip()
        raise RuntimeError(f"could not inspect image {path}: {detail}")
    try:
        width, height, channels = result.stdout.strip().split(maxsplit=2)
        return int(width), int(height), channels.split()[0]
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"could not inspect image {path}: invalid ImageMagick output") from exc


def _check_upload(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"image preparation produced no image: {path}")
    if path.stat().st_size >= MAX_INPUT_BYTES:
        raise ValueError(f"prepared image must be smaller than 50MB: {path}")


def prepare_uploads(inputs: list[Path], mask: Path | None, destination: Path) -> tuple[list[Path], Path | None]:
    destination.mkdir(parents=True, exist_ok=True)
    prepared: list[Path] = []
    for index, source in enumerate(inputs):
        if not source.is_file():
            raise FileNotFoundError(f"input image not found: {source}")
        output = destination / f"image-{index}.png"
        _run_magick(
            [str(source), "-auto-orient", "-strip", str(output)],
            context=f"input metadata stripping failed for {source}",
        )
        _check_upload(output)
        prepared.append(output)

    if mask is None:
        return prepared, None
    if not mask.is_file():
        raise FileNotFoundError(f"mask image not found: {mask}")

    normalized = destination / "mask-normalized.png"
    prepared_mask = destination / "mask.png"
    _run_magick(
        [str(mask), "-auto-orient", "-strip", str(normalized)],
        context=f"mask preparation failed for {mask}",
    )
    if image_info(normalized)[2].lower().endswith("a"):
        shutil.copyfile(normalized, prepared_mask)
    else:
        _run_magick(
            [str(normalized), "-colorspace", "gray", "-alpha", "copy", "-strip", str(prepared_mask)],
            context=f"mask alpha conversion failed for {mask}",
        )
    _check_upload(prepared_mask)
    if not image_info(prepared_mask)[2].lower().endswith("a"):
        raise RuntimeError(f"prepared mask has no alpha channel: {mask}")
    if image_info(prepared[0])[:2] != image_info(prepared_mask)[:2]:
        raise ValueError("mask and first input must have the same dimensions")
    return prepared, prepared_mask


def parse_size(value: str) -> str:
    if value == "auto":
        return value
    match = re.fullmatch(r"([0-9]+)x([0-9]+)", value)
    if not match:
        raise ValueError("size must be auto or WIDTHxHEIGHT")
    width, height = (int(part) for part in match.groups())
    pixels = width * height
    if width > 3840 or height > 3840:
        raise ValueError("size edges must not exceed 3840 pixels")
    if width % 16 or height % 16:
        raise ValueError("size edges must be multiples of 16 pixels")
    if max(width, height) > 3 * min(width, height):
        raise ValueError("size aspect ratio must not exceed 3:1")
    if not 655_360 <= pixels <= 8_294_400:
        raise ValueError("size must contain between 655360 and 8294400 pixels")
    return value


def parse_compression(value: str) -> int:
    try:
        compression = int(value)
    except ValueError as exc:
        raise ValueError("compression must be an integer from 0 to 100") from exc
    if not 0 <= compression <= 100:
        raise ValueError("compression must be an integer from 0 to 100")
    return compression


def validate_options(inputs: list[Path], mask: Path | None, output_format: str, compression: int | None) -> None:
    if mask is not None and not inputs:
        raise ValueError("mask requires at least one input image")
    if compression is not None and output_format == "png":
        raise ValueError("compression requires jpeg or webp output format")


def _fields(
    prompt: str,
    *,
    quality: str,
    size: str,
    output_format: str,
    compression: int | None,
    background: str,
) -> dict[str, str | int]:
    fields: dict[str, str | int] = {
        "model": MODEL,
        "prompt": prompt,
        "n": 1,
        "quality": quality,
        "size": size,
        "output_format": output_format,
        "background": background,
    }
    if compression is not None:
        fields["output_compression"] = compression
    return fields


def _multipart(fields: dict[str, str | int], inputs: list[Path], mask: Path | None) -> tuple[bytes, str]:
    boundary = f"image-openai-{uuid.uuid4().hex}"
    body = bytearray()

    def line(value: bytes) -> None:
        body.extend(value + b"\r\n")

    for name, value in fields.items():
        line(f"--{boundary}".encode())
        line(f'Content-Disposition: form-data; name="{name}"'.encode())
        line(b"")
        line(str(value).encode("utf-8"))
    for source in inputs:
        line(f"--{boundary}".encode())
        line(f'Content-Disposition: form-data; name="image[]"; filename="{source.name}"'.encode())
        line(b"Content-Type: image/png")
        line(b"")
        line(source.read_bytes())
    if mask is not None:
        line(f"--{boundary}".encode())
        line(f'Content-Disposition: form-data; name="mask"; filename="{mask.name}"'.encode())
        line(b"Content-Type: image/png")
        line(b"")
        line(mask.read_bytes())
    line(f"--{boundary}--".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _redact_error_detail(detail: str, key: str) -> str:
    if key:
        detail = detail.replace(key, "sk-REDACTED")
    return _KEY_FRAGMENT.sub("sk-REDACTED", detail)


def request_image(
    prompt: str,
    *,
    key: str,
    inputs: list[Path],
    mask: Path | None,
    quality: str,
    size: str,
    output_format: str,
    compression: int | None,
    background: str,
    open_url: OpenUrl = urllib.request.urlopen,
) -> bytes:
    fields = _fields(
        prompt,
        quality=quality,
        size=size,
        output_format=output_format,
        compression=compression,
        background=background,
    )
    if inputs:
        data, content_type = _multipart(fields, inputs, mask)
        url = EDIT_URL
    else:
        data = json.dumps(fields).encode("utf-8")
        content_type = "application/json"
        url = GENERATION_URL
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": content_type},
        method="POST",
    )
    try:
        with open_url(request, timeout=HTTP_TIMEOUT_S) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:2000]
        detail = _redact_error_detail(detail, key)
        raise RuntimeError(f"OpenAI request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI network failure: {exc.reason}") from exc
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"invalid OpenAI response: {exc}") from exc
    images = (payload.get("data") or []) if isinstance(payload, dict) else []
    if not images or not isinstance(images[0], dict) or not images[0].get("b64_json"):
        raise RuntimeError("OpenAI response contained no image data")
    try:
        image = base64.b64decode(images[0]["b64_json"], validate=True)
    except (binascii.Error, TypeError) as exc:
        raise RuntimeError("OpenAI returned invalid base64 image data") from exc
    if not image:
        raise RuntimeError("OpenAI returned an empty image")
    return image


def default_output(prompt: str, inputs: list[Path], output_format: str) -> Path:
    if inputs:
        name = f"{inputs[0].stem}-openai-edit"
    else:
        slug = "".join(char if char.isalnum() else "-" for char in prompt.lower())
        name = "-".join(filter(None, slug.split("-")))[:50] or "image-openai"
    return Path(name + _EXT_BY_FORMAT[output_format]).resolve()


def resolve_output(requested: str | None, prompt: str, inputs: list[Path], output_format: str) -> Path:
    if not requested:
        return default_output(prompt, inputs, output_format)
    output = Path(requested).expanduser().resolve()
    if output.suffix.lower() not in _SUFFIXES_BY_FORMAT[output_format]:
        corrected = output.with_suffix(_EXT_BY_FORMAT[output_format])
        print(f"note: requested format is {output_format}; writing {corrected} instead of {output}", file=sys.stderr)
        return corrected
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=",image-openai",
        description="Generate or edit a raster image through OpenAI's native GPT Image 2 API.",
        epilog=(
            "Inputs are auto-oriented and stripped of metadata before upload. GPT Image 2 always uses high "
            "input fidelity. Masks guide edits but may not constrain their exact shape."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("prompt", help="generate or edit instruction")
    parser.add_argument("-i", "--input", action="append", default=[], metavar="IMAGE", help="input image (repeatable)")
    parser.add_argument(
        "--mask", metavar="IMAGE", help="edit mask for the first input; grayscale is converted to alpha"
    )
    parser.add_argument("-o", "--output", help="output file path")
    parser.add_argument("-q", "--quality", choices=("auto", "low", "medium", "high"), default="auto")
    parser.add_argument("-s", "--size", type=parse_size, default="auto", help="auto or WIDTHxHEIGHT")
    parser.add_argument("-f", "--format", dest="output_format", choices=("png", "jpeg", "webp"), default="png")
    parser.add_argument("-c", "--compression", type=parse_compression, help="JPEG/WebP compression from 0 to 100")
    parser.add_argument("-b", "--background", choices=("auto", "opaque"), default="auto")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = [Path(value).expanduser().resolve() for value in args.input]
    mask = Path(args.mask).expanduser().resolve() if args.mask else None
    try:
        validate_options(inputs, mask, args.output_format, args.compression)
        key = api_key()
        with tempfile.TemporaryDirectory(prefix="image-openai-") as tmp:
            prepared, prepared_mask = prepare_uploads(inputs, mask, Path(tmp))
            image = request_image(
                args.prompt,
                key=key,
                inputs=prepared,
                mask=prepared_mask,
                quality=args.quality,
                size=args.size,
                output_format=args.output_format,
                compression=args.compression,
                background=args.background,
            )
        output = resolve_output(args.output, args.prompt, inputs, args.output_format)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(image)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
