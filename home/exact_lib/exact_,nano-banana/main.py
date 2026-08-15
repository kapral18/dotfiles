#!/usr/bin/env python3
"""Generate, edit, compose, or inpaint a Nano Banana (Gemini) raster image.

Calls the Generative Language API ``:generateContent`` endpoint.
Default model is Nano Banana 2 (``gemini-3.1-flash-image``).
``-i`` / ``--url`` media is uploaded to Google.

Usage:
    ,nano-banana "a cat astronaut, watercolor"
    ,nano-banana "make the sky sunset" -i photo.png
    ,nano-banana "put the logo on the shirt" -i person.png -i logo.png -o out.jpg
    ,nano-banana "poster of this video" --url 'https://www.youtube.com/watch?v=...'
    ,nano-banana "PROMPT" -m gemini-3-pro-image
"""

from __future__ import annotations

import argparse
import base64
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

VERSION = "1.2.0"
DEFAULT_MODEL = "gemini-3.1-flash-image"
PRO_MODEL = "gemini-3-pro-image"
FLASH_VIDEO_MODEL = DEFAULT_MODEL
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GENERATE_PREFIX = "Generate an image of: "
MAX_REFERENCE_IMAGES = 14
MAX_INLINE_BYTES = 7 * 1024 * 1024
MAX_YOUTUBE_URLS = 1
VIDEO_FPS = 0.5
HTTP_TIMEOUT_S = 300
SIPS_SIDES = (2048, 1600, 1280, 1024, 768, 512)

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}
_VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mpeg", ".mpg", ".m4v"}
_EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _api_key() -> str:
    for var in ("NANOBANANA_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        key = os.environ.get(var)
        if key:
            return key
    sys.exit("ERROR: set NANOBANANA_API_KEY (or GEMINI_API_KEY) in the environment")


def allows_video(model: str) -> bool:
    return "flash-image" in model


def prompt_text(prompt: str, has_media: bool) -> str:
    if has_media:
        return prompt
    return GENERATE_PREFIX + prompt


def generation_config(aspect_ratio: str | None, size: str | None) -> dict:
    config: dict = {"responseModalities": ["TEXT", "IMAGE"]}
    image_config: dict[str, str] = {}
    if aspect_ratio:
        image_config["aspectRatio"] = aspect_ratio
    if size:
        image_config["imageSize"] = size
    if image_config:
        config["imageConfig"] = image_config
    return config


def mime_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _VIDEO_SUFFIXES:
        sys.exit(f"ERROR: local video files are not inlined; use --url with a YouTube URL and -m {FLASH_VIDEO_MODEL}")
    if suffix == ".gif":
        sys.exit(f"ERROR: GIF is not an accepted Gemini image MIME; convert to png/jpeg/webp first ({path})")
    mime = _MIME_BY_SUFFIX.get(suffix) or (mimetypes.guess_type(path.name)[0] or "")
    if not mime.startswith("image/"):
        sys.exit(f"ERROR: unsupported input type for {path} (need png/jpeg/webp/heic/heif)")
    return mime


def fit_inline_image(path: Path, max_bytes: int = MAX_INLINE_BYTES) -> tuple[bytes, str]:
    data = path.read_bytes()
    mime = mime_for_path(path)
    if len(data) <= max_bytes:
        return data, mime
    sips = shutil.which("sips")
    if not sips:
        sys.exit(f"ERROR: {path} exceeds {max_bytes} byte inline limit and sips is not available to shrink it")
    fd, tmp_name = tempfile.mkstemp(suffix=".jpg", prefix="nano-banana-")
    os.close(fd)
    dest = Path(tmp_name)
    try:
        for side in SIPS_SIDES:
            result = subprocess.run(
                [
                    sips,
                    "-s",
                    "format",
                    "jpeg",
                    "-s",
                    "formatOptions",
                    "70",
                    "-Z",
                    str(side),
                    str(path),
                    "--out",
                    str(dest),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or str(result.returncode)).strip()
                sys.exit(f"ERROR: sips failed shrinking {path}: {detail}")
            data = dest.read_bytes()
            if len(data) <= max_bytes:
                print(
                    f"note: shrank {path.name} to {len(data)} bytes for the 7MB inline limit",
                    file=sys.stderr,
                )
                return data, "image/jpeg"
        sys.exit(f"ERROR: {path} still exceeds {max_bytes} bytes after shrinking")
    finally:
        dest.unlink(missing_ok=True)


def image_part(path: Path, max_bytes: int = MAX_INLINE_BYTES) -> dict:
    if not path.is_file():
        sys.exit(f"ERROR: input not found: {path}")
    data, mime = fit_inline_image(path, max_bytes)
    return {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode("ascii")}}


def video_url_part(url: str) -> dict:
    return {"fileData": {"fileUri": url}, "videoMetadata": {"fps": VIDEO_FPS}}


def build_payload(
    prompt: str,
    *,
    inputs: list[Path],
    urls: list[str],
    aspect_ratio: str | None = None,
    size: str | None = None,
    model: str = DEFAULT_MODEL,
) -> dict:
    if urls and not allows_video(model):
        sys.exit(f"ERROR: --url video-to-image is flash-only. Pass -m {FLASH_VIDEO_MODEL} (got {model})")
    if len(urls) > MAX_YOUTUBE_URLS:
        sys.exit(f"ERROR: at most {MAX_YOUTUBE_URLS} --url YouTube URL")
    total = len(inputs) + len(urls)
    if total > MAX_REFERENCE_IMAGES:
        sys.exit(f"ERROR: at most {MAX_REFERENCE_IMAGES} inputs (-i/--url combined)")
    has_media = total > 0
    parts: list[dict] = [{"text": prompt_text(prompt, has_media)}]
    parts.extend(image_part(path) for path in inputs)
    parts.extend(video_url_part(url) for url in urls)
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config(aspect_ratio, size),
    }


def _generate(payload: dict, model: str, key: str) -> tuple[bytes, str]:
    url = f"{API_BASE}/{model}:generateContent"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        sys.exit(f"ERROR: API call failed ({exc.code}): {detail}")
    except urllib.error.URLError as exc:
        sys.exit(f"ERROR: network failure: {exc.reason}")

    if os.environ.get("NANOBANANA_DEBUG"):
        print(json.dumps(data, indent=2), file=sys.stderr)

    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content", {}).get("parts") if candidates else None) or []
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            return base64.b64decode(inline["data"]), mime

    text = next((p["text"] for p in parts if p.get("text")), None)
    reasons = []
    block_reason = (data.get("promptFeedback") or {}).get("blockReason")
    if block_reason:
        reasons.append(f"blockReason={block_reason}")
    finish_reason = candidates[0].get("finishReason") if candidates else None
    if finish_reason:
        reasons.append(f"finishReason={finish_reason}")
    suffix = f" ({', '.join(reasons)})" if reasons else ""
    if text:
        suffix += f": {text[:300]}"
    sys.exit(f"ERROR: no image in response{suffix} [set NANOBANANA_DEBUG=1 for raw response]")


def _default_output(prompt: str, mime: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in prompt.lower())
    slug = "-".join(filter(None, slug.split("-")))[:50] or "nano-banana"
    return slug + _EXT_BY_MIME.get(mime, ".png")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=",nano-banana",
        description="Generate or edit a Nano Banana (Gemini) raster image.",
        epilog=(
            "Inputs are uploaded to Google. Default model is Nano Banana 2 "
            f"({DEFAULT_MODEL}). Video --url works on the default. "
            f"Pro (-m {PRO_MODEL}) rejects video."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("prompt", help="text instruction for generate, edit, compose, or inpaint")
    parser.add_argument("-o", "--output", help="output file path (default: derived from the prompt)")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"model id (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        default=[],
        metavar="IMAGE",
        help="local reference/edit image (repeatable, max 14 with --url)",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        metavar="YOUTUBE_URL",
        help="YouTube URL for video-to-image (one URL; flash models only, including the default)",
    )
    parser.add_argument(
        "-a",
        "--aspect-ratio",
        help="aspect ratio, e.g. 1:1, 16:9, 9:16, 4:3, 3:4 (default: model's choice)",
    )
    parser.add_argument(
        "-s",
        "--size",
        help="image resolution: 512, 1K, 2K, or 4K (case-sensitive; 512 is flash-only)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    inputs = [Path(path).expanduser() for path in args.input]
    payload = build_payload(
        args.prompt,
        inputs=inputs,
        urls=list(args.url),
        aspect_ratio=args.aspect_ratio,
        size=args.size,
        model=args.model,
    )
    image, mime = _generate(payload, args.model, _api_key())
    output = args.output or _default_output(args.prompt, mime)
    with open(output, "wb") as fh:
        fh.write(image)
    print(output)


if __name__ == "__main__":
    main()
