#!/usr/bin/env python3
"""Generate or edit raster images through OpenRouter's Images API.

Reference images are auto-oriented and stripped of metadata before upload.
Requests require provider zero-data-retention and no-data-collection routing.

Usage:
    ,image-openrouter "a cat astronaut, watercolor"
    ,image-openrouter "make the sky sunset" -i photo.png
    ,image-openrouter "put the logo on the shirt" -i person.png -i logo.png -o out.png
    ,image-openrouter "a product photo" -a 16:9 -r 1K
    ,image-openrouter "PROMPT" -m google/gemini-3.1-flash-image
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

VERSION = "1.2.0"
DEFAULT_MODEL = "bytedance-seed/seedream-5-0-pro"
API_URL = "https://openrouter.ai/api/v1/images"
HTTP_TIMEOUT_S = 300
PASS_ENTRY = "openrouter/api/token"

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}
_EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
_SUFFIXES_BY_MIME = {
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/webp": {".webp"},
    "image/svg+xml": {".svg"},
}

OpenUrl = Callable[..., object]


def api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
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
    raise RuntimeError(f"set OPENROUTER_API_KEY or pass entry {PASS_ENTRY}")


def image_mime(path: Path) -> str:
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower()) or (mimetypes.guess_type(path.name)[0] or "")
    if not mime.startswith("image/"):
        raise ValueError(f"unsupported input type for {path} (need an image file)")
    return mime


def stripped_image_bytes(path: Path) -> bytes:
    magick = shutil.which("magick")
    if not magick:
        raise RuntimeError("ImageMagick is required to strip input metadata before upload")
    with tempfile.TemporaryDirectory(prefix="image-openrouter-") as tmp:
        output = Path(tmp) / f"stripped{path.suffix.lower()}"
        result = subprocess.run(
            [magick, str(path), "-auto-orient", "-strip", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or str(result.returncode)).strip()
            raise RuntimeError(f"input metadata stripping failed for {path}: {detail}")
        try:
            data = output.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"input metadata stripping produced no image for {path}") from exc
    if not data:
        raise RuntimeError(f"input metadata stripping produced an empty image for {path}")
    return data


def input_reference(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"input image not found: {path}")
    mime = image_mime(path)
    encoded = base64.b64encode(stripped_image_bytes(path)).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{encoded}"},
    }


def build_payload(
    prompt: str,
    *,
    model: str,
    inputs: list[Path],
    aspect_ratio: str | None,
    resolution: str | None,
) -> dict:
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "provider": {
            # Omit sort so default load balancing keeps uptime, then price.
            "data_collection": "deny",
            "zdr": True,
        },
    }
    if inputs:
        payload["input_references"] = [input_reference(path) for path in inputs]
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if resolution:
        payload["resolution"] = resolution
    return payload


def request_image(
    payload: dict,
    key: str,
    *,
    open_url: OpenUrl = urllib.request.urlopen,
) -> tuple[bytes, str]:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with open_url(request, timeout=HTTP_TIMEOUT_S) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:2000]
        raise RuntimeError(f"OpenRouter request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenRouter network failure: {exc.reason}") from exc
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"invalid OpenRouter response: {exc}") from exc

    images = result.get("data") or []
    if not images or not isinstance(images[0], dict) or not images[0].get("b64_json"):
        raise RuntimeError("OpenRouter response contained no image data")
    mime = images[0].get("media_type") or "image/png"
    if not isinstance(mime, str) or not mime.startswith("image/"):
        raise RuntimeError(f"OpenRouter returned unsupported media type: {mime!r}")
    try:
        data = base64.b64decode(images[0]["b64_json"], validate=True)
    except (binascii.Error, TypeError) as exc:
        raise RuntimeError("OpenRouter returned invalid base64 image data") from exc
    if not data:
        raise RuntimeError("OpenRouter returned an empty image")
    return data, mime.split(";", 1)[0].lower()


def default_output(prompt: str, inputs: list[Path], mime: str) -> Path:
    if inputs:
        name = f"{inputs[0].stem}-edit"
    else:
        slug = "".join(char if char.isalnum() else "-" for char in prompt.lower())
        name = "-".join(filter(None, slug.split("-")))[:50] or "image-openrouter"
    return Path(name + _EXT_BY_MIME.get(mime, ".png")).resolve()


def resolve_output(requested: str | None, prompt: str, inputs: list[Path], mime: str) -> Path:
    if not requested:
        return default_output(prompt, inputs, mime)
    output = Path(requested).expanduser().resolve()
    expected_suffix = _EXT_BY_MIME.get(mime)
    accepted_suffixes = _SUFFIXES_BY_MIME.get(mime, set())
    if expected_suffix and output.suffix.lower() not in accepted_suffixes:
        corrected = output.with_suffix(expected_suffix)
        print(f"note: OpenRouter returned {mime}; writing {corrected} instead of {output}", file=sys.stderr)
        return corrected
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=",image-openrouter",
        description="Generate or edit a raster image through OpenRouter.",
        epilog=(
            "Inputs are auto-oriented and stripped of metadata before upload. Provider routing enforces "
            "zero data retention and denies data collection. "
            f"Default: {DEFAULT_MODEL}."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("prompt", help="generate or edit instruction")
    parser.add_argument(
        "-o",
        "--output",
        help="output file path (suffix is normalized to the returned media type)",
    )
    parser.add_argument(
        "-m", "--model", default=DEFAULT_MODEL, help=f"OpenRouter image model (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        default=[],
        metavar="IMAGE",
        help="local reference/edit image (repeatable; metadata stripped before upload)",
    )
    parser.add_argument("-a", "--aspect-ratio", help="aspect ratio supported by the selected model, e.g. 1:1 or 16:9")
    parser.add_argument("-r", "--resolution", help="resolution tier supported by the selected model, e.g. 1K or 2K")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = [Path(value).expanduser().resolve() for value in args.input]
    try:
        payload = build_payload(
            args.prompt,
            model=args.model,
            inputs=inputs,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
        )
        image, mime = request_image(payload, api_key())
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    output = resolve_output(args.output, args.prompt, inputs, mime)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
