#!/usr/bin/env python3
"""Preprocess captured pane text and extract URL picker candidates."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from urllib.parse import urlsplit

BORDER_CHARS = "│┃║"
ST = r"(?:\x07|\x1B\\)"
OSC8_LINK_RE = re.compile(
    rf"\x1B]8;[^\x1B\x07]*;([^\x1B\x07]+){ST}(?:(?!\x1B]8;).)*?\x1B]8;[^\x1B\x07]*;{ST}", re.DOTALL
)
OSC8_OPEN_RE = re.compile(rf"\x1B]8;[^\x1B\x07]*;([^\x1B\x07]+){ST}")
OSC8_CLOSE_RE = re.compile(rf"\x1B]8;[^\x1B\x07]*;{ST}")
ANSI_ESCAPE_RE = re.compile(
    r"\x1B(?:\[[0-?]*[ -/]*[@-~]|\][^\x1B\x07]*(?:\x07|\x1B\\)|[PX^_][^\x1B]*(?:\x1B\\)|[@-Z\\-_])"
)
URL_RE = re.compile(r"(?:https?|ftp|file)://[^\s|│┃║]+")
WWW_RE = re.compile(r"www\.[^\s|│┃║]+")
IP_RE = re.compile(r"[0-9]{1,3}(?:\.[0-9]{1,3}){3}(?::[0-9]{1,5})?(?:/[^\s|│┃║]+)?")
GIT_RE = re.compile(r"(?:ssh://)?git@[^\s|│┃║]+")
GH_SHORTHAND_RE = re.compile(r"['\"]([_A-Za-z0-9-]*/[_.A-Za-z0-9-]*)['\"]")
PLAIN_WORD_RE = re.compile(r"^[A-Za-z]+[.,;:!?]?$")
TRAILING_PUNCT = "])>}`\"'.,;:!?\\"
CODE_CITATION_SUFFIX_RE = re.compile(r"(?::\d+(?:-\d+)?){1,2}:[^/\s]*/[^\s]*$")
LINE_RANGE_SUFFIX_RE = re.compile(r"^((?:https?|ftp|file)://.*/[^?#\s:]+):\d+(?:-\d+)?$")
DISCUSSION_OFFSET_RE = re.compile(r"^(https://github\.com/[^/\s]+/[^/\s]+/pull/\d+#discussion_r\d+)[^/]*$")


def _strip_escaped_whitespace(text: str) -> str:
    return re.sub(r"\\+[nrt]", "", text)


def _normalize_osc8_target(target: str) -> str:
    return re.sub(r"\s+", "", _strip_escaped_whitespace(target))


def _join_wrapped_urls(text: str) -> str:
    url_re = re.compile(r"(?P<url>(?:https?|ftp|file)://[^\s│┃║]+)(?P<trail>[\s│┃║]*)$")
    continuation_re = re.compile(r"^(?P<prefix>[\s│┃║]*)(?P<part>[^\s│┃║]+)(?P<rest>.*)$")
    lines = text.split("\n")
    joined: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        while i + 1 < len(lines):
            url_match = url_re.search(line)
            next_match = continuation_re.match(lines[i + 1])
            if not url_match or not next_match:
                break
            # Join only when box-border evidence shows the break was a
            # render-time wrap. Indentation alone is common prose structure,
            # so it must not glue a following path-like sentence onto a
            # complete URL.
            line_prefix = re.match(r"[\s│┃║]*", line).group(0)
            has_border = any(
                char in BORDER_CHARS for char in f"{line_prefix}{url_match.group('trail')}{next_match.group('prefix')}"
            )
            if not has_border:
                break
            part = next_match.group("part")
            if re.match(r"(?:https?|ftp|file)://", part):
                break
            # A render-time wrap splits a URL at an arbitrary column, so the
            # continuation is a bare URL fragment (`gin/transform/...`, `va#L1`)
            # rather than a word. Rejecting plain words keeps bordered prose
            # that merely happens to end on a URL from being glued on, without
            # requiring the fragment to carry a `/`, `?`, or `#` of its own.
            if PLAIN_WORD_RE.match(part):
                break
            line = f"{line[: url_match.start('trail')]}{part}{next_match.group('rest')}"
            i += 1
        joined.append(line)
        i += 1
    return "\n".join(joined)


def _osc8_link_to_url(match: re.Match[str]) -> str:
    return f"{_normalize_osc8_target(match.group(1))} "


def _osc8_open_to_url(match: re.Match[str]) -> str:
    return f"{_normalize_osc8_target(match.group(1))} "


def preprocess_text(text: str) -> str:
    text = "\n".join(line.split("\r")[-1] for line in text.split("\n"))
    text = OSC8_LINK_RE.sub(_osc8_link_to_url, text)
    text = OSC8_OPEN_RE.sub(_osc8_open_to_url, text)
    text = OSC8_CLOSE_RE.sub("", text)
    text = ANSI_ESCAPE_RE.sub("", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    text = _join_wrapped_urls(text)
    return text


def clean_candidate(candidate: str) -> str | None:
    candidate = _strip_escaped_whitespace(candidate).rstrip(TRAILING_PUNCT)
    candidate = CODE_CITATION_SUFFIX_RE.sub("", candidate)
    candidate = LINE_RANGE_SUFFIX_RE.sub(r"\1", candidate)
    candidate = DISCUSSION_OFFSET_RE.sub(r"\1", candidate)
    candidate = candidate.rstrip(TRAILING_PUNCT)
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https", "ftp", "file"} or not (parsed.netloc or parsed.scheme == "file"):
        return None
    if "..." in candidate or "…" in candidate:
        return None
    return candidate


def _add_candidate(candidates: list[str], candidate: str) -> None:
    cleaned = clean_candidate(candidate)
    if cleaned:
        candidates.append(cleaned)


def _run_extra_filter(text: str, extra_filter: str) -> list[str]:
    if not extra_filter:
        return []
    bash = shutil.which("bash") or "/bin/bash"
    result = subprocess.run(
        extra_filter, input=text, text=True, shell=True, executable=bash, capture_output=True, env=os.environ
    )
    return result.stdout.splitlines()


def extract_candidates(raw_text: str, extra_filter: str = "") -> list[str]:
    text = preprocess_text(raw_text)
    candidates: list[str] = []
    for match in URL_RE.finditer(text):
        _add_candidate(candidates, match.group(0))
    for match in WWW_RE.finditer(text):
        value = match.group(0)
        if not value.startswith(("http://", "https://")):
            _add_candidate(candidates, f"http://{value}")
    for match in IP_RE.finditer(text):
        _add_candidate(candidates, f"http://{match.group(0)}")
    for match in GIT_RE.finditer(text):
        converted = match.group(0).rstrip(TRAILING_PUNCT).replace(":", "/")
        converted = re.sub(r"^(?:ssh///)?git@(.*)$", r"https://\1", converted)
        _add_candidate(candidates, converted)
    for match in GH_SHORTHAND_RE.finditer(text):
        _add_candidate(candidates, f"https://github.com/{match.group(1)}")
    for value in _run_extra_filter(text, extra_filter):
        # Extra-filter output is user-defined and need not be a URL, so it is
        # only required to be non-blank (matching the previous `awk 'NF'`).
        value = value.strip()
        if value:
            candidates.append(value)
    return prune_prefix_candidates(candidates)


def prune_prefix_candidates(candidates: list[str]) -> list[str]:
    unique = sorted(set(candidate for candidate in candidates if candidate))
    pruned: list[str] = []
    for index, candidate in enumerate(unique):
        drop = False
        for next_candidate in unique[index + 1 :]:
            if not next_candidate.startswith(candidate):
                break
            if len(next_candidate) > len(candidate) and (
                candidate.endswith("/") or next_candidate[len(candidate)] == "/"
            ):
                drop = True
                break
        if not drop:
            pruned.append(candidate)
    return pruned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extract-candidates", action="store_true", help="emit final URL candidates instead of preprocessed text"
    )
    parser.add_argument("--extra-filter", default="", help="optional shell filter run against preprocessed text")
    args = parser.parse_args()
    raw_text = sys.stdin.read()
    if args.extract_candidates:
        candidates = extract_candidates(raw_text, args.extra_filter)
        if candidates:
            sys.stdout.write("\n".join(candidates) + "\n")
    else:
        sys.stdout.write(preprocess_text(raw_text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
