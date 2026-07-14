#!/usr/bin/env python3
"""tmux pane composer classifier for ,palantir.

The palantir supervisor must never inject new word into a pane that is
mid-turn. ``tmux capture-pane`` returns the visible buffer including ANSI escape
sequences and ghost renders left by spinners and progress UIs, so a pane that is
actually idle can look busy to a naive check. ``composer.py`` is the single
palantir-wide owner of that decision: it strips ANSI/OSC/ghost artifacts and
classifies a pane into one of four verdicts.

Verdicts (fail-safe: only ``empty`` authorizes an inject):

  empty   - idle shell; the last line is a prompt (or the pane is blank+prompt).
  pending - last line carries a known waiting marker (spinner, "Thinking", a
            trailing "..." with no prompt). Still mid-turn; do not inject.
  busy    - substantial content with no fresh prompt and no waiting marker.
  unknown - capture failed or text is unclassifiable. Never authorizes inject.

Inject-safety rule (used by the palantir supervisor everywhere): inject only when
``verdict == "empty"``. Every other verdict blocks the inject; ``unknown`` never
authorizes one. This is a heuristic classifier by design -- when busy and
pending cannot be told apart it prefers ``busy`` so the inject is blocked.

CLI (stdlib only, thin-shell/typed-core):

  composer.py classify [--target SESSION:WINDOW.PANE | --input PATH] [--json]
  composer.py strip   --input PATH|-            (print ANSI-stripped text)
  composer.py idle    [--target ... | --input PATH]   (print true/false)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# CSI sequences (colors, cursor moves, clear-line), OSC sequences (title set,
# terminated by BEL or ST), and single-char C1 escapes. Together these cover the
# ghost artifacts a spinner/progress UI leaves in the capture-pane buffer.
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[A-Za-z]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|\x1b[=>N~]"
    r"|\x1b."
)

# Braille / ascii spinner glyphs and the common "still working" words. Matched
# against the final non-empty line to recognize a pending pane.
_SPINNER_RE = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]")
_PENDING_WORDS_RE = re.compile(
    r"\b(Thinking|Working|Generating|Processing|Analyzing|Updating|Running|Loading)\b",
    re.IGNORECASE,
)

# A fresh shell or agent prompt: ends in one of the common prompt terminators
# (optionally followed by whitespace) and is short. Copilot's interactive input
# uses the Unicode `❯` terminator.
_PROMPT_RE = re.compile(r"^(.*[\$#>%❯])\s*$")
_SEPARATOR_RE = re.compile(r"^[─━-]{10,}$")
_PI_STATUS_RE = re.compile(r"^MCP:\s+\d+/\d+\s+servers$")
_COPILOT_INPUT_RE = re.compile(r"^\s*❯\s*(.*)$")
_COPILOT_FOOTER_CONTINUATION_RE = re.compile(r"^.*·.*\b(?:context|tokens?|AIC)\b.*$", re.IGNORECASE)

CAPTURE_LINES = 50


def strip_ansi(text: str) -> str:
    """Remove ANSI/OSC escapes and collapse carriage-return overwrites.

    Spinners rewrite the same line with ``\\r`` between frames, leaving a buffer
    like ``"⠋ Loading\\r⠙ Loading\\r⠹ Loading"``. Per logical line we split on
    ``\\r`` and keep the final segment, which drops the ghost frames before ANSI
    stripping. Other control characters (except newline and tab) are removed.
    """
    out_lines: list[str] = []
    for line in text.split("\n"):
        # Keep the last \r-delimited segment of each logical line (spinner frame).
        segments = line.split("\r")
        last = segments[-1]
        last = _ANSI_RE.sub("", last)
        # Drop remaining control chars except tab/newline (already split).
        last = "".join(ch for ch in last if ch == "\t" or (ord(ch) >= 0x20))
        out_lines.append(last)
    return "\n".join(out_lines)


def _meaningful_lines(cleaned: str) -> list[str]:
    return [ln.rstrip() for ln in cleaned.split("\n") if ln.strip() != ""]


def _pi_input_line(cleaned: str) -> "str | None":
    lines = [line.rstrip() for line in cleaned.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    if (
        len(lines) >= 6
        and _PI_STATUS_RE.match(lines[-1].strip())
        and _SEPARATOR_RE.match(lines[-4].strip())
        and _SEPARATOR_RE.match(lines[-6].strip())
    ):
        return lines[-5].strip()
    return None


def _copilot_input_line(cleaned: str) -> "str | None":
    lines = [line.rstrip() for line in cleaned.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    for footer_index in range(len(lines) - 1, 2, -1):
        if "/ commands" not in lines[footer_index]:
            continue
        continuation = [line.strip() for line in lines[footer_index + 1 :] if line.strip()]
        if len(continuation) > 2 or any(_COPILOT_FOOTER_CONTINUATION_RE.match(line) is None for line in continuation):
            continue
        if not _SEPARATOR_RE.match(lines[footer_index - 1].strip()):
            continue
        if not _SEPARATOR_RE.match(lines[footer_index - 3].strip()):
            continue
        match = _COPILOT_INPUT_RE.match(lines[footer_index - 2])
        if match is not None:
            return match.group(1).strip()
    return None


def classify(text: str) -> tuple[str, str]:
    """Return ``(verdict, reason)`` for a captured pane buffer.

    Order: unknown (nothing to read) -> empty (last line is a prompt) -> pending
    (last line carries a waiting marker) -> busy (content, no prompt, no marker).
    """
    cleaned = strip_ansi(text)
    copilot_input = _copilot_input_line(cleaned)
    if copilot_input is not None:
        if not copilot_input:
            return ("empty", "Copilot input area is empty")
        return ("busy", "Copilot input area contains an active prompt")
    pi_input = _pi_input_line(cleaned)
    if pi_input is not None:
        if not pi_input:
            return ("empty", "Pi input area is empty")
        return ("busy", "Pi input area contains an active prompt")
    lines = _meaningful_lines(cleaned)
    if not lines:
        return ("unknown", "no meaningful content captured")

    last = lines[-1]
    if _PROMPT_RE.match(last) and len(last) <= 120:
        return ("empty", "last line is a fresh prompt")
    if _SPINNER_RE.search(last) or _PENDING_WORDS_RE.search(last) or last.endswith("...") or last.endswith("…"):
        return ("pending", "last line carries a waiting marker")
    return ("busy", "content present with no fresh prompt")


def tmux_command(*args: str) -> list[str]:
    command = ["tmux"]
    socket = os.environ.get("OUTER_TMUX_SOCKET")
    if socket:
        command.extend(["-S", socket])
    command.extend(args)
    return command


def run_tmux(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(tmux_command(*args), capture_output=True, text=True, check=False)


def capture(target: str, lines: int) -> str:
    proc = run_tmux("capture-pane", "-p", "-t", target, "-e", "-S", f"-{lines}")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"tmux capture-pane failed for {target}")
    return proc.stdout


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _resolve_text(args: argparse.Namespace) -> str:
    if args.target and args.input:
        raise SystemExit("composer: --target and --input are mutually exclusive")
    if args.target:
        return capture(args.target, args.lines)
    if args.input:
        return _read_input(args.input)
    raise SystemExit("composer: one of --target or --input is required")


def cmd_classify(args: argparse.Namespace) -> int:
    text = _resolve_text(args)
    verdict, reason = classify(text)
    if args.json:
        cleaned = strip_ansi(text)
        lines = _meaningful_lines(cleaned)
        payload = {
            "verdict": verdict,
            "reason": reason,
            "idle": verdict == "empty",
            "meaningful_lines": len(lines),
            "last_line": lines[-1] if lines else "",
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"{verdict}\t{reason}")
    return 0


def cmd_strip(args: argparse.Namespace) -> int:
    print(strip_ansi(_read_input(args.input)), end="")
    return 0


def cmd_idle(args: argparse.Namespace) -> int:
    text = _resolve_text(args)
    verdict, _reason = classify(text)
    print("true" if verdict == "empty" else "false")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="composer.py", description=",palantir tmux pane composer classifier")
    sub = parser.add_subparsers(dest="command", required=True)

    classify_p = sub.add_parser("classify", help="classify a pane as empty/pending/busy/unknown")
    classify_p.add_argument("--target", help="tmux pane target (session:window.pane)")
    classify_p.add_argument("--input", help="read pane text from path (- for stdin)")
    classify_p.add_argument("--lines", type=int, default=CAPTURE_LINES, help="capture-pane lookback lines")
    classify_p.add_argument("--json", action="store_true", help="emit a JSON verdict object")
    classify_p.set_defaults(func=cmd_classify)

    strip_p = sub.add_parser("strip", help="print ANSI-stripped pane text")
    strip_p.add_argument("--input", required=True, help="read pane text from path (- for stdin)")
    strip_p.set_defaults(func=cmd_strip)

    idle_p = sub.add_parser("idle", help="print true when the pane is idle (verdict == empty)")
    idle_p.add_argument("--target", help="tmux pane target (session:window.pane)")
    idle_p.add_argument("--input", help="read pane text from path (- for stdin)")
    idle_p.add_argument("--lines", type=int, default=CAPTURE_LINES, help="capture-pane lookback lines")
    idle_p.set_defaults(func=cmd_idle)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
