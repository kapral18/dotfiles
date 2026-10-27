"""Evidence provenance and durable decisions for an intent card.

Matching proves that a source exists, not that it entails the claim. The reviewer
gets both. Claude transcripts are read locally; file claims work in any harness.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path


def normalized(text: str) -> str:
    return text.replace("\r\n", "\n")


def text_blocks(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b["text"] for b in content or [] if b.get("type") == "text")


def blocks(row: dict) -> list[dict]:
    content = row.get("message", {}).get("content")
    return content if isinstance(content, list) else []


def transcript(session: str) -> list[dict]:
    """Read this session's main transcript, excluding API copies and sidechains."""
    if not re.fullmatch(r"[\w-]+", session):
        return []
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    paths = list((config / "projects").glob(f"*/{session}.jsonl"))
    if len(paths) != 1:
        return []
    rows = []
    try:
        with paths[0].open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # A currently appended row can be incomplete.
                if row.get("sessionId") == session and not row.get("isSidechain") and row.get("uuid"):
                    rows.append(row)
    except OSError:
        return []
    # Rewinds leave abandoned rows. Walk only the current ancestry, including
    # the links compaction preserves outside the ordinary parent chain.
    by_id = {row["uuid"]: row for row in rows}
    pending, seen = [rows[-1]["uuid"]] if rows else [], set()
    while pending:
        identity = pending.pop()
        row = by_id.get(identity)
        if row is None or identity in seen:
            continue
        seen.add(identity)
        pending.append(row.get("parentUuid"))
        if row.get("subtype") == "compact_boundary":
            pending.append(row.get("logicalParentUuid"))
            segment = row.get("compactMetadata", {}).get("preservedSegment", {})
            pending.extend((segment.get("headUuid"), segment.get("tailUuid")))
    # A parallel batch writes one row per tool call of one API message, chained in
    # issue order, hangs each result off its own call row, and continues from the
    # result that finished last. Calls of a message on the ancestry belong to it,
    # and so do their results; a rewound branch is another message, and a rewound
    # prompt under an ancestry row is no tool result, so both stay out.
    messages = {by_id[identity].get("message", {}).get("id") for identity in seen} - {None}
    calls = {
        row["uuid"]: {block["id"] for block in blocks(row) if block.get("type") == "tool_use"}
        for row in rows
        if row.get("type") == "assistant" and (row["uuid"] in seen or row.get("message", {}).get("id") in messages)
    }

    def result_of_call(row: dict) -> bool:
        results = [block.get("tool_use_id") for block in blocks(row) if block.get("type") == "tool_result"]
        return row.get("type") == "user" and bool(results) and set(results) <= calls.get(row.get("parentUuid"), set())

    return [row for row in rows if row["uuid"] in seen or row["uuid"] in calls or result_of_call(row)]


def observations(session: str) -> list[dict]:
    calls, found = {}, []
    for row in transcript(session):
        try:
            stamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError):
            continue
        content = row.get("message", {}).get("content", [])
        if row.get("type") == "user" and row.get("origin", {}).get("kind") == "human":
            found.append(
                {
                    "id": row["uuid"],
                    "kind": "user",
                    "time": stamp,
                    "text": text_blocks(content),
                }
            )
        for block in blocks(row):
            if row.get("type") == "assistant" and block.get("type") == "tool_use":
                calls[block["id"]] = block
            if row.get("type") != "user" or block.get("type") != "tool_result":
                continue
            call = calls.get(block.get("tool_use_id"))
            # Admit known local read/execution tools; other tools need file claims.
            if not call or call["name"] not in ("Bash", "Read", "Grep", "Glob"):
                continue
            # Ledger echoes and other models' reports cannot corroborate themselves.
            # Keep shell command text opaque; Read/Grep inputs and descriptions are data.
            if call["name"] == "Bash" and ",task" in call.get("input", {}).get("command", ""):
                continue
            found.append(
                {
                    "id": row["uuid"],
                    "kind": "tool",
                    "time": stamp,
                    "text": text_blocks(block.get("content")),
                    "tool": call["name"],
                    "is_error": bool(block.get("is_error")),
                }
            )
    return found


def match_quote(records: list[dict], text: str, kind: str, before: float, after: float = 0) -> dict | None:
    return next(
        (
            r
            for r in reversed(records)
            if r["kind"] == kind and after < r["time"] <= before and normalized(text) in normalized(r["text"])
        ),
        None,
    )


def file_source(path: str, line: int, text: str) -> dict:
    target = Path(path)
    content = target.read_bytes()
    lines = normalized(content.decode("utf-8")).splitlines()
    if line < 1 or line > len(lines) or lines[line - 1] != normalized(text):
        raise ValueError("file line does not match")
    return {
        "digest": hashlib.sha256(content).hexdigest(),
        "time": target.stat().st_mtime_ns / 1e9,
    }


def verify(claim: dict, records: list[dict]) -> dict:
    source = claim["source"]
    try:
        if source["kind"] == "file":
            current = file_source(source["path"], source["line"], source["text"])
            if current["digest"] != source["digest"]:
                raise ValueError("file changed since the claim was recorded")
            return {"verified": True, "time": source["time"]}
        if source["kind"] == "quote":
            found = match_quote(records, source["text"], "tool", claim["created"])
            if found and found["id"] == source.get("id"):
                return {
                    "verified": True,
                    "time": found["time"],
                    "tool": found["tool"],
                    "is_error": found["is_error"],
                }
            raise ValueError("quote is not in its original tool result in this session")
        raise ValueError(source["reason"])
    except (OSError, UnicodeError, ValueError) as error:
        return {"verified": False, "reason": str(error)}


def get(card: dict, group: str, identity: str) -> dict:
    found = next((r for r in card.get(group, []) if r["id"] == identity.upper()), None)
    if found is None:
        raise ValueError(f"unknown {identity}")
    return found


def verified_claim(card: dict, identity: str, records: list[dict]) -> tuple[dict, dict]:
    claim = get(card, "claims", identity)
    result = verify(claim, records)
    if not result["verified"]:
        raise ValueError(f"{identity}: {result['reason']}")
    return claim, result


def append(card: dict, group: str, prefix: str, **fields) -> dict:
    entries = card.setdefault(group, [])
    entry = {"id": f"{prefix}{len(entries) + 1}", "created": time.time(), **fields}
    entries.append(entry)
    return entry


def add_claim(card: dict, args, records: list[dict]) -> dict:
    if not args.text.strip():
        raise ValueError("claim text must not be empty")
    if args.file:
        path, separator, line = args.file.rpartition(":")
        if not separator or not line.isdigit() or args.line_text is None:
            raise ValueError("--file needs path:line and --text with the exact line")
        path = str(Path(path).expanduser().absolute())
        source = {
            "kind": "file",
            "path": path,
            "line": int(line),
            "text": args.line_text,
            **file_source(path, int(line), args.line_text),
        }
    elif args.quote is not None:
        if not args.quote.strip():
            raise ValueError("quote must not be empty")
        found = match_quote(records, args.quote, "tool", time.time())
        if found is None:
            raise ValueError("quote not found in this session's tool results; use a file claim or --unknown")
        source = {"kind": "quote", "text": args.quote, "id": found["id"]}
    else:
        if not args.unknown.strip():
            raise ValueError("unknown needs a reason")
        source = {"kind": "unknown", "reason": args.unknown}
    return append(card, "claims", "C", text=args.text, source=source)


def set_stance(card: dict, args, records: list[dict]) -> dict:
    if not args.key.strip() or not args.value.strip():
        raise ValueError("stance key and value must not be empty")
    previous = next((s for s in reversed(card.get("stances", [])) if s["key"] == args.key), None)
    after = previous["created"] if previous and previous["value"] != args.value else 0
    if args.because:
        claim, evidence = verified_claim(card, args.because, records)
        if evidence["time"] <= after:
            raise ValueError("changing a stance needs evidence produced after the previous stance")
        reason = {"claim": claim["id"]}
    else:
        if not args.user.strip():
            raise ValueError("user quote must not be empty")
        found = match_quote(records, args.user, "user", time.time(), after)
        if not found:
            raise ValueError("user quote not found after the previous stance")
        reason = {"user": args.user, "source": found["id"], "time": found["time"]}
    if previous and previous["value"] == args.value and previous["reason"] == reason:
        return previous
    return append(
        card,
        "stances",
        "S",
        key=args.key,
        value=args.value,
        reason=reason,
        previous=previous["id"] if previous else None,
    )


def resolve_finding(card: dict, identity: str, claim_id: str, status: str, records: list[dict]) -> dict:
    finding = get(card, "findings", identity)
    claim, _ = verified_claim(card, claim_id, records)
    finding.update(status=status, claim=claim["id"], resolved=time.time())
    return finding


def remember_findings(card: dict, candidates: list[dict], records: list[dict]) -> list[dict]:
    kept = []
    for candidate in candidates[:5]:
        anchor, concern = candidate.get("anchor"), candidate.get("concern")
        if not isinstance(anchor, str) or not anchor.strip() or not isinstance(concern, str) or not concern.strip():
            raise ValueError("each finding needs an anchor and concern")
        previous = next(
            (f for f in reversed(card.get("findings", [])) if f["anchor"] == anchor and f["concern"] == concern),
            None,
        )
        if previous and previous["status"] != "open":
            claim = get(card, "claims", previous["claim"])
            quote = candidate.get("quote")
            newer = (
                isinstance(quote, str)
                and quote.strip()
                and match_quote(records, quote, "tool", time.time(), previous["resolved"])
            )
            if verify(claim, records)["verified"] and not newer:
                continue
        if previous and previous["status"] == "open":
            kept.append(previous)
        else:
            kept.append(append(card, "findings", "F", anchor=anchor, concern=concern, status="open"))
    return kept


_LIST = re.compile(r"^( {0,3}(?:[-+*]|\d{1,9}[.)]))( +|$)")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_HTML_BLOCK = re.compile(
    r"^ {0,3}</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|"
    r"dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|"
    r"iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|"
    r"table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:[ \t]|/?>|$)",
    re.I,
)


def _html_end(text: str, paragraph: bool):
    for opening, closing in ((r"<!--", r"-->"), (r"<\?", r"\?>"), (r"<!\[CDATA\[", r"\]\]>"), (r"<![A-Z]", r">")):
        if re.match(r"^ {0,3}" + opening, text):
            return re.compile(closing)
    raw = re.match(r"^ {0,3}<(pre|script|style|textarea)(?:[ \t>]|$)", text, re.I)
    if raw:
        return re.compile(r"</" + raw[1] + ">", re.I)
    if _HTML_BLOCK.match(text):
        return re.compile(r"^ *$")
    if not paragraph and re.match(
        r"^ {0,3}(?:</[A-Za-z][A-Za-z0-9-]*[ \t]*>|<[A-Za-z][A-Za-z0-9-]*"
        r"(?:[ \t]+[A-Za-z_:][\w.:-]*(?:[ \t]*=[ \t]*(?:[^\"'=<>` \t]+|'[^']*'|\"[^\"]*\"))?)*[ \t]*/?>)[ \t]*$",
        text,
    ):
        return re.compile(r"^ *$")
    return None


def _opens_fence(marker):
    return marker is not None and (marker[1][0] != "`" or "`" not in marker[2])


def _thematic_break(text: str):
    return re.match(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$", text) is not None


def _interrupts_paragraph(text: str):
    return (
        not text.strip(" ")
        or _opens_fence(_FENCE.match(text))
        or _thematic_break(text)
        or _html_end(text, True) is not None
        or re.match(r"^ {0,3}(?:#{1,6}(?:[ \t]|$)|>|(?:[-+*]|0{0,8}1[.)])[ \t]+[^ \t])", text) is not None
    )


def _continue_containers(text: str, containers: list[tuple[int | None, bool]]):
    # None denotes a quote; a list stores its content indent and whether it is empty.
    matched = 0
    for index, (indent, empty) in enumerate(containers):
        if indent is None:
            quote = re.match(r"^ {0,3}> ?", text)
            if not quote:
                break
            text = text[quote.end() :]
        elif not text.strip(" "):
            if empty:
                break
        else:
            if len(text) - len(text.lstrip(" ")) < indent:
                break
            text = text[indent:]
            containers[index] = (indent, False)
        matched += 1
    return text, matched


def _open_containers(text: str, containers: list[tuple[int | None, bool]]):
    while True:
        quote = re.match(r"^ {0,3}> ?", text)
        if quote:
            containers.append((None, False))
            text = text[quote.end() :]
            continue
        item = _LIST.match(text)
        if not item or _thematic_break(text):
            return text
        empty = item.end() == len(text)
        indent = len(item[1]) + (1 if len(item[2]) > 4 or empty else len(item[2]))
        containers.append((indent, empty))
        text = text[indent:]


def _report_prose(answer: str):
    """Follow the Markdown containers used by stop-review's prose checks."""
    containers: list[tuple[int | None, bool]] = []
    fence, html, paragraph = None, None, False
    for line in answer.splitlines():
        text, matched = _continue_containers(line.expandtabs(4), containers)
        lazy = matched < len(containers) and paragraph and not _LIST.match(text) and not _interrupts_paragraph(text)
        if not lazy and matched < len(containers):
            del containers[matched:]
            fence, html, paragraph = None, None, False
        depth = len(containers)
        if not (fence or html or lazy or (paragraph and not _interrupts_paragraph(text))):
            text = _open_containers(text, containers)
        if len(containers) != depth:
            paragraph = False
        marker = _FENCE.match(text)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip(" \t"):
                fence = None
            continue
        if not html and not lazy and _opens_fence(marker):
            fence, paragraph = marker[1], False
            continue
        if not html and not lazy:
            html = _html_end(text, paragraph)
        is_html = html is not None
        if html and html.search(text):
            html = None
        setext = not lazy and paragraph and re.match(r"^ {0,3}(?:=+|-+)[ \t]*$", text)
        paragraph = (
            not is_html
            and bool(text.strip(" "))
            and not setext
            and not _interrupts_paragraph(text)
            and (paragraph or not text.startswith("    "))
        )
        if not any(indent is None for indent, _ in containers):
            yield line


def report_items(answer: str):
    """Extract report prose; each bullet needs its own citation."""
    section, item, reported = None, "", False
    for line in _report_prose(answer):
        stripped = line.strip()
        match = re.match(
            r"^[\s*_#+-]*(Checked|Assumptions|Proposed|Decision needed|Open)(?:\*\*|__)?"
            r"(?:[ \t]*\([^)\n]*\))?(?::(?:\*\*|__)?\s*(.*)|[ \t]*)$",
            stripped,
        )
        bullet = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$", line)
        if match or bullet or stripped.startswith("#"):
            if section and (item.strip() or ((match or stripped.startswith("#")) and not reported)):
                yield section, item
                reported = True
            item = ""
            if match:
                section, item = match[1], match[2] or ""
                reported = False
            elif stripped.startswith("#"):
                section = None
            elif bullet:
                item = bullet[1]
        elif section and stripped:
            item += " " + stripped
    if section and (item.strip() or not reported):
        yield section, item


def check_answer(card: dict, answer: str, records: list[dict]) -> list[str]:
    problems = []
    for section, item in report_items(answer):
        if section == "Open" or item.strip().lower().rstrip(".") in (
            "none",
            "n/a",
            "nothing",
        ):
            continue
        prefix = "C" if section == "Checked" else "S"
        ids = re.findall(rf"\[({prefix}\d+)\]", item)
        if not ids:
            problems.append(f"{section}: each item needs a [{prefix}<n>] citation: {item}")
        for identity in ids:
            try:
                if prefix == "C":
                    verified_claim(card, identity, records)
                else:
                    stance = get(card, "stances", identity)
                    latest = next(s for s in reversed(card["stances"]) if s["key"] == stance["key"])
                    if latest["id"] != identity:
                        raise ValueError(f"{identity} is superseded by {latest['id']}")
                    reason = stance["reason"]
                    if "claim" in reason:
                        verified_claim(card, reason["claim"], records)
                    elif not any(
                        r["id"] == reason["source"]
                        and r["kind"] == "user"
                        and normalized(reason["user"]) in normalized(r["text"])
                        for r in records
                    ):
                        raise ValueError(f"{identity}: user quote no longer verifiable")
            except ValueError as error:
                problems.append(str(error))
    for item in card["done"]:
        if item["status"] == "checked":
            try:
                verified_claim(card, item.get("claim", "missing claim"), records)
            except ValueError as error:
                problems.append(f"{item['id']}: {error}; reopen or cite current evidence")
    return problems


def context(card: dict, records: list[dict]) -> dict:
    return {
        **card,
        "claims": [{**c, **verify(c, records)} for c in card.get("claims", [])],
    }
