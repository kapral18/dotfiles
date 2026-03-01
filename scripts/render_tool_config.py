#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def _parse_bool(s: str) -> bool:
    normalized = s.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean: {s!r}")


def render_codex_config(*, is_work: bool, path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines(True)

    def is_table_header(line: str) -> bool:
        stripped = line.strip()
        return (
            bool(stripped)
            and stripped.startswith("[")
            and stripped.endswith("]")
            and not stripped.startswith("#")
        )

    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if is_table_header(line):
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    sections.append(current)

    work_marker = re.compile(r"^\s*#\s*__isWork__\s*$")

    out: list[str] = []
    for section in sections:
        if not section:
            continue
        is_work_only = any(work_marker.match(line) for line in section)
        if (not is_work) and is_work_only:
            continue
        for line in section:
            if work_marker.match(line):
                continue
            out.append(line)
    return "".join(out)


def _strip_jsonc_comments(text: str) -> str:
    out: list[str] = []
    i = 0
    in_str = False
    escape = False
    n = len(text)
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            i += 1
            continue

        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue

        if c == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                i += 2
                while i < n and text[i] not in "\n\r":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue

        out.append(c)
        i += 1
    return "".join(out)


def _remove_trailing_commas(text: str) -> str:
    out: list[str] = []
    i = 0
    in_str = False
    escape = False
    n = len(text)
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            i += 1
            continue

        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue

        if c == ",":
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            if j < n and text[j] in "}]":
                i += 1
                continue

        out.append(c)
        i += 1
    return "".join(out)


def render_opencode_config(*, is_work: bool, path: Path) -> str:
    src_text = path.read_text(encoding="utf-8")
    lines = src_text.splitlines(True)

    work_only_keys: set[str] = set()
    marker_re = re.compile(r"^\s*//\s*__isWork__\s*$")
    key_re = re.compile(r'^\s*"([^"]+)"\s*:\s*')
    for i, line in enumerate(lines):
        if not marker_re.match(line):
            continue
        j = i + 1
        while j < len(lines) and (lines[j].strip() == "" or lines[j].lstrip().startswith("//")):
            j += 1
        if j >= len(lines):
            continue
        m = key_re.match(lines[j])
        if m:
            work_only_keys.add(m.group(1))

    json_text = _remove_trailing_commas(_strip_jsonc_comments(src_text))
    data = json.loads(json_text)

    if not is_work:
        mcp = data.get("mcp") or {}
        for key in list(mcp.keys()):
            if key in work_only_keys:
                del mcp[key]
        data["mcp"] = mcp

    return json.dumps(data, indent=2) + "\n"


def _render(*, tool: str, is_work: bool, path: Path) -> str:
    if tool == "codex":
        return render_codex_config(is_work=is_work, path=path)
    if tool == "opencode":
        return render_opencode_config(is_work=is_work, path=path)
    raise ValueError(f"unknown tool: {tool!r}")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render filtered tool configs for chezmoi merge scripts.")
    parser.add_argument("tool", choices=["codex", "opencode"])
    parser.add_argument("is_work", help="true/false")
    parser.add_argument("path", type=Path)
    parser.add_argument("--hash-only", action="store_true", help="print sha256 of rendered output")
    args = parser.parse_args(argv)

    try:
        is_work = _parse_bool(args.is_work)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    try:
        rendered = _render(tool=args.tool, is_work=is_work, path=args.path)
    except Exception as e:
        print(f"render failed: {e}", file=sys.stderr)
        return 1

    if args.hash_only:
        sys.stdout.write(_sha256(rendered.rstrip("\n")))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
