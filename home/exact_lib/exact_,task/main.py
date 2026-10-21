#!/usr/bin/env python3
# Description: Keep an agent's intent card per worktree and check scope, progress, and completion against it.
"""Intent cards that keep agent sessions on the user's goal, in any harness.

A card holds the goal, the agent's reading of the request, numbered `Done when`
items, the `Scope` the task may touch, and what it leaves alone. The agent writes
it with `,task card set`; harness adapters (Claude mod, Pi/OMP extension, Codex
hooks, OpenCode plugin) call `,task hook <event>` to inject it, flag edits outside
`Scope`, prompt a zoom-out every few steps, and send a stop back while a
`Done when` item is still open.

State lives in `$AGENT_TASK_DIR` (default `~/.local/share/agent-tasks`): one
directory per worktree with session-keyed cards and turn state, plus
`preferences.jsonl` and `steering.jsonl`.
"""

from __future__ import annotations

import argparse
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ZOOM_EVERY = 25
# A session that prompted within this many seconds may still be writing a card here.
RECENT = 6 * 3600
# A card set by hand (no session) is claimed by the first session that prompts within this many seconds.
CLAIM_WINDOW = 3600
# The card keeps the latest user corrections verbatim; older ones stay in the steering log.
MAX_CORRECTIONS = 5
MAX_CONTINUES = 3
CARD_SOFT_LIMIT = 2048
SCOPE_CHANGES_SHOWN = 5
SHELL_TOOLS = frozenset({"bash", "shell", "exec_command", "write_stdin", "python", "powershell", "eval"})
WRITE_TOOLS = frozenset({"edit", "write", "multiedit", "notebookedit", "apply_patch", "applypatch", "patch"})
SECTIONS = {
    "goal": "goal",
    "reading": "reading",
    "done when": "done",
    "scope": "scope",
    "not doing": "not_doing",
}
LIST_SECTIONS = frozenset({"done", "scope", "not_doing"})
# A user prompt that corrects the agent rather than asking for something new.
CORRECTION = re.compile(
    r"^\s*(?:no|nope|wrong)\s*[,.!]|^\s*(?:stop|not that)\b"
    r"|\bi (?:didn'?t|did not|never) (?:ask|say|want|mean)"
    r"|\b(?:that'?s|this is|it'?s) not what i\b|\bnot what i (?:asked|meant|want)"
    r"|\bi (?:said|asked for|meant)\b|\bwhy (?:did|do|are) you\b|\byou (?:misunderstood|missed|forgot|ignored)\b"
    r"|\byou should(?:n'?t| not)? have\b",
    re.IGNORECASE,
)
# A correction that states a lasting rule, worth saving as a preference.
PREFERENCE = re.compile(r"\b(?:we (?:don'?t|never|always|do not)|in general|from now on|always|never)\b", re.IGNORECASE)


# --- storage -----------------------------------------------------------------


def root_dir() -> Path:
    override = os.environ.get("AGENT_TASK_DIR")
    return Path(override) if override else Path.home() / ".local/share/agent-tasks"


def git(cwd: Path, *args: str) -> str | None:
    try:
        run = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return run.stdout if run.returncode == 0 else None


def worktree_root(cwd: Path) -> Path | None:
    top = git(cwd, "rev-parse", "--show-toplevel")
    return Path(top.strip()).resolve() if top else None


def task_dir(cwd: Path) -> Path:
    base = worktree_root(cwd) or cwd.resolve()
    slug = re.sub(r"[^a-z0-9._-]+", "-", base.name.lower()).strip("-.") or "root"
    digest = hashlib.sha1(str(base).encode()).hexdigest()[:8]
    return root_dir() / f"{slug[:48]}-{digest}"


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)


def append_jsonl(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Task:
    """The card and hook state of one worktree."""

    def __init__(self, cwd: Path, session: str | None = None):
        self.cwd = cwd
        self.root = worktree_root(cwd)
        self.dir = task_dir(cwd)
        self.cards_path = self.dir / "cards.json"
        self.state_path = self.dir / "state.json"
        self.cards = read_json(self.cards_path, {})
        self.state = read_json(self.state_path, {})
        self.session_id = self.session(session)
        self.card = self.cards.get(self.session_id)

    def session(self, given: str | None = None) -> str:
        explicit = given or os.environ.get("AGENT_TASK_SESSION")
        if explicit:
            return explicit
        recent = self.recent_sessions()
        if len(recent) > 1:
            print(",task: several sessions are active; pass --session <id>", file=sys.stderr)
            raise SystemExit(2)
        return recent[0] if recent else "unknown"

    def turn(self, session: str) -> dict:
        """One session's turn state: several sessions in a worktree each keep their own."""
        recent = set(self.recent_sessions()) | {session}
        turns = {sid: value for sid, value in (self.state.get("turns") or {}).items() if sid in recent}
        self.state["turns"] = turns
        return turns.setdefault(session, {})

    def recent_sessions(self) -> list[str]:
        """Sessions that prompted in this worktree within the last RECENT seconds."""
        cutoff = time.time() - RECENT
        return [sid for sid, seen in (self.state.get("sessions") or {}).items() if seen >= cutoff]

    def card_for(self, session: str) -> dict | None:
        """Only the named session's card; an unowned card is claimed on prompt."""
        return self.cards.get(session)

    def relative(self, path: str) -> str:
        """A path as `git status` names it: relative to the worktree root when inside it."""
        absolute = os.path.realpath(os.path.join(str(self.cwd), os.path.expanduser(path)))
        if self.root and (absolute == str(self.root) or absolute.startswith(str(self.root) + "/")):
            return os.path.relpath(absolute, self.root)
        return absolute

    def save_card(self) -> None:
        self.cards[self.session_id] = self.card
        write_json(self.cards_path, self.cards)

    def save_state(self) -> None:
        write_json(self.state_path, self.state)

    def dirty(self) -> list[str]:
        return [path for path, _ in self.status()]

    def snapshot(self) -> dict[str, str]:
        """Each dirty path's mtime and size, `U` marking an untracked one, to tell which a tool call changed."""
        shot: dict[str, str] = {}
        for path, code in self.status():
            try:
                st = os.stat(os.path.join(str(self.root), path))
                mark = f"{st.st_mtime_ns}:{st.st_size}"
            except OSError:
                mark = "gone"
            shot[path] = ("U" if code == "??" else "T") + mark
        return shot

    def status(self) -> list[tuple[str, str]]:
        if not self.root:
            return []
        out = git(self.root, "--no-optional-locks", "status", "--porcelain=v1", "-z", "--untracked-files=all")
        if out is None:
            return []
        paths: list[tuple[str, str]] = []
        tokens = out.split("\0")
        i = 0
        while i < len(tokens):
            entry = tokens[i]
            if len(entry) >= 4:
                paths.append((entry[3:], entry[:2]))
                if "R" in entry[:2] or "C" in entry[:2]:
                    i += 1
            i += 1
        return paths


# --- card --------------------------------------------------------------------


def parse_card(text: str) -> dict:
    card: dict = {"goal": "", "reading": "", "done": [], "scope": [], "not_doing": []}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        match = re.match(r"^\s*(?:[*_#>-]\s*)*([A-Za-z][A-Za-z ]*?)(?:\*\*|__)?\s*:\s*(.*)$", line)
        key = SECTIONS.get(match.group(1).strip().lower()) if match else None
        if match and key:
            current = key
            # A bold heading (`**Goal:** text`) leaves its closing marker after the colon.
            rest = match.group(2).strip()
            if re.match(r"^\s*(?:\*\*|__)", line):
                rest = re.sub(r"^(?:\*\*|__)\s*", "", rest)
            if rest:
                if key in LIST_SECTIONS:
                    # Inline items split on `;`; scope paths split on `,` too.
                    pattern = r"\s*[;,]\s*" if key == "scope" else r"\s*;\s*"
                    card[key].extend(item.strip() for item in re.split(pattern, rest) if item.strip())
                else:
                    card[key] = rest
            continue
        if current is None or not line.strip():
            continue
        item = re.sub(r"^\s*(?:(?:[-*+]|\d+[.)]|\[[ xX!]\]|D\d+[.:)]?)\s+)+", "", line).strip()
        if not item:
            continue
        if current in LIST_SECTIONS:
            card[current].append(item)
        else:
            card[current] = f"{card[current]} {item}".strip()
    return card


def validate(card: dict) -> list[str]:
    problems = []
    if not card["goal"]:
        problems.append("`Goal:` is missing")
    if not card["done"]:
        problems.append("`Done when:` needs at least one checkable item")
    if not card["scope"]:
        problems.append("`Scope:` needs at least one path, glob, or `*`")
    return problems


def render(card: dict, *, full: bool = True, notes: bool = True, all_changes: bool = False) -> str:
    lines = [f"Goal: {card['goal']}"]
    if card.get("reading"):
        lines.append(f"Reading: {card['reading']}")
    lines.append("Done when:")
    for item in card["done"]:
        mark = {"checked": "x", "blocked": "!"}.get(item["status"], " ")
        note = f" — {item['note']}" if notes and item.get("note") else ""
        lines.append(f"- [{mark}] {item['id']}: {item['text']}{note}")
    lines.append("Scope: " + ", ".join(card["scope"]))
    if card.get("not_doing"):
        lines.append("Not doing: " + "; ".join(card["not_doing"]))
    if full:
        changes = card.get("scope_changes", [])
        # Hooks inject the latest few, so the card stays short each turn; `card show` and scope checks use them all.
        if not all_changes and len(changes) > SCOPE_CHANGES_SHOWN:
            lines.append(f"Scope changes: {len(changes) - SCOPE_CHANGES_SHOWN} older ones, listed by `,task card show`")
        for change in changes if all_changes else changes[-SCOPE_CHANGES_SHOWN:]:
            lines.append(f"Scope change: {change['path']} — {change['reason']}")
        # Only the latest earlier goal: the rest stay in the store, so the card injected each turn does not grow.
        for old in card.get("goal_history", [])[-1:]:
            lines.append(f"Earlier goal: {old}")
        for text in card.get("corrections", []):
            lines.append(f"User correction (verbatim): {text}")
    return "\n".join(lines)


def open_items(card: dict) -> list[dict]:
    return [item for item in card["done"] if item["status"] == "open"]


# --- scope -------------------------------------------------------------------


def scratch(path: str) -> bool:
    roots = ["/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/", str(root_dir()) + "/"]
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        roots.append(tmpdir.rstrip("/") + "/")
    home = str(Path.home())
    roots += [f"{home}/.claude/plans/", f"{home}/.claude/projects/", f"{home}/.local/share/agent-handoffs/"]
    return any(path.startswith(root) for root in roots)


def inside(root: Path | None, absolute: str) -> bool:
    return bool(root) and (absolute == str(root) or absolute.startswith(str(root) + "/"))


def resolve(task: Task, path: str) -> str:
    """The absolute path with symlinks resolved, as git reports the worktree root."""
    return os.path.realpath(os.path.join(str(task.cwd), os.path.expanduser(path)))


def free(task: Task, path: str) -> bool:
    """Scratch space outside the worktree, which no card has to cover."""
    absolute = resolve(task, path)
    return scratch(absolute) and not inside(task.root, absolute)


def in_scope(task: Task, path: str) -> bool:
    absolute = resolve(task, path)
    if free(task, path):
        return True
    card = task.card or {}
    entries = list(card.get("scope", [])) + [change["path"] for change in card.get("scope_changes", [])]
    for raw in entries:
        entry = raw.strip().strip("`")
        if entry in ("*", "**", "."):
            return True
        target = os.path.realpath(os.path.join(str(task.root or task.cwd), os.path.expanduser(entry))).rstrip("/")
        if absolute == target or absolute.startswith(target + "/") or fnmatch.fnmatch(absolute, target):
            return True
        # `**/*.py` also covers `a.py` at the root.
        if entry.startswith("**/"):
            direct = os.path.join(str(task.root or task.cwd), entry[3:])
            if fnmatch.fnmatch(absolute, direct):
                return True
    return False


def patch_paths(text: str) -> list[str]:
    paths = re.findall(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$", text, re.MULTILINE)
    # OMP's normalized event supplies hashline headers; MV destinations remain in the patch.
    moves = re.findall(r"^[ \t]*MV[ \t]+(.+)$", text, re.MULTILINE)
    for raw in moves:
        path = raw.strip()
        if len(path) > 1 and path[0] == path[-1] and path[0] in "\"'":
            path = path[1:-1].strip()
        paths.append(path)
    return paths


# --- preferences and steering ------------------------------------------------


def repo_name(task: Task) -> str:
    common = git(task.cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    path = Path(common.strip()).resolve() if common else task.cwd.resolve()
    name = (path.parent if path.name == ".git" else path).name or "root"
    return name + "-" + hashlib.sha256(str(path).encode()).hexdigest()[:16]


def preferences(task: Task) -> list[dict]:
    repo = repo_name(task)
    entries = []
    try:
        lines = (root_dir() / "preferences.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("scope") in ("global", repo):
            entries.append(entry)
    return entries


def log_steering(task: Task, harness: str, text: str, answer: str = "") -> None:
    append_jsonl(
        root_dir() / "steering.jsonl",
        {
            "time": now(),
            "repo": repo_name(task),
            "worktree": str(task.root or task.cwd),
            "harness": harness,
            "text": text[:4000],
            "answer_head": answer[:600],
            "goal": (task.card or {}).get("goal", ""),
        },
    )


# --- hooks -------------------------------------------------------------------

CARD_RULE = (
    "Write the intent card before your first edit (~/AGENTS.md §3 step 0): "
    "`,task card set <<'CARD'` with `Goal:`, `Reading:`, `Done when:` (checkable items), `Scope:` (paths or globs), `Not doing:`, then `CARD`."
)


def hook_prompt(task: Task, data: dict, harness: str) -> dict:
    session = task.session(data.get("session"))
    text = data.get("text") or ""
    sessions = {sid: seen for sid, seen in (task.state.get("sessions") or {}).items() if seen >= time.time() - RECENT}
    first = session not in sessions
    sessions[session] = time.time()
    task.state.update(active_session=session, sessions=sessions)
    turn = task.turn(session)
    compacted = turn.pop("compacted", False)
    # Shell snapshots belong to individual calls; a prompt starts a new turn's attribution.
    turn.update(continues=0, last_unmet=None, steps=0, pending={}, until_stop={}, touched=[], wrote=False)
    parts: list[str] = []
    unowned = task.cards.get("unknown")
    if unowned and not task.card and session != "unknown":
        created = time.mktime(time.strptime(unowned["created"][:19], "%Y-%m-%dT%H:%M:%S"))
        if created >= time.time() - CLAIM_WINDOW:
            task.card = task.cards.pop("unknown")
            task.card["session"] = session
            task.save_card()
    if first or compacted:
        prefs = preferences(task)
        if prefs:
            parts.append(
                "User preferences (saved earlier; follow them):\n" + "\n".join(f"- {p['text']}" for p in prefs)
            )
    card = task.card_for(session)
    if card:
        parts.append(
            f"Intent card for this task (keep to it; update it with `,task card set --session {session}` "
            "when the user changes the goal; when evidence shows the ask misses its goal, note it in `Reading:` and tell the user):\n"
            + render(card)
        )
        if CORRECTION.search(text):
            card["corrections"] = (card.get("corrections", []) + [text.strip()[:1000]])[-MAX_CORRECTIONS:]
            task.save_card()
            log_steering(task, harness, text, turn.get("last_answer", ""))
            note = (
                "This message corrects you. What the user wants is theirs to say: update the card's `Reading:` or `Goal:` "
                "to match it before you continue. If it corrects a fact or a method and the evidence says otherwise, "
                "say so in one line with that evidence (~/AGENTS.md §1)."
            )
            if PREFERENCE.search(text):
                note += ' It states a lasting preference: save it with `,task pref add "<rule in the user\'s words>"`.'
            parts.append(note)
    elif CORRECTION.search(text) and not first:
        log_steering(task, harness, text, turn.get("last_answer", ""))
    if not card and len(task.recent_sessions()) > 1:
        parts.append(
            f"intent-guard: other sessions share this worktree; write this task's card with `,task card set --session {session}`."
        )
    task.save_state()
    return {"context": "\n\n".join(parts)} if parts else {}


def hook_tool(task: Task, data: dict, harness: str) -> dict:
    session = task.session(data.get("session"))
    tool = (data.get("tool") or "").lower()
    paths = [p for p in data.get("paths") or [] if p] + patch_paths(data.get("patch") or "")
    is_write = tool in WRITE_TOOLS or bool(data.get("write"))
    before = data.get("phase") == "before"
    complete = data.get("phase") == "complete"
    card = task.card_for(session)
    turn = task.turn(session)
    notes: list[str] = []
    if is_write and not card and paths and not all(free(task, p) for p in paths):
        asked = task.state.get("card_asked") or []
        if session not in asked:
            task.state["card_asked"] = [*asked, session][-20:]
            task.save_state()
            rule = CARD_RULE.replace(",task card set", f",task card set --session {session}")
            return {"deny": f"intent-guard: no intent card for this task yet. {rule} Then retry this edit."}
    if tool in SHELL_TOOLS:
        pending = turn.setdefault("pending", {})
        background = turn.setdefault("background", {})
        until_stop = turn.setdefault("until_stop", {})
        call_id = str(data.get("call_id") or tool)
        background_id = str(data.get("background_id") or call_id)
        if before:
            pending[call_id] = task.snapshot()
        else:
            start = pending.pop(call_id, None)
            if start is None:
                start = background.pop(background_id, None)
            if start is None:
                start = until_stop.pop(background_id, None)
            if start is not None:
                shot = task.snapshot()
                paths = [str(task.root / p) for p in start.keys() | shot.keys() if start.get(p) != shot.get(p)]
                if data.get("background"):
                    (until_stop if data.get("until_stop") else background)[background_id] = shot
    if not before and paths and (is_write or tool in SHELL_TOOLS):
        touched = [p for p in paths if not free(task, p)]
        if touched:
            turn["wrote"] = True
            turn["touched"] = sorted(set(turn.get("touched", [])) | {task.relative(p) for p in touched})
        outside = [p for p in paths if card and not in_scope(task, p)]
        if outside:
            notes.append(
                "intent-guard: " + ", ".join(outside[:20]) + " is outside the card's `Scope:`. "
                'If the Goal or a defect in the change\'s impact (§3 step 1) needs it, record why with `,task scope add <path> --reason "..."`; if not, undo your change.'
            )
    steps = int(turn.get("steps", 0)) + (0 if before or complete else 1)
    if card and not before and not complete and (steps >= ZOOM_EVERY or turn.get("compacted")):
        steps = 0
        turn.pop("compacted", None)
        unmet = ", ".join(item["id"] for item in open_items(card)) or "none"
        notes.append(
            "intent-guard: zoom out. Re-read the card below. In one line, say whether the current work still serves the Goal "
            f"and what is left (open: {unmet}). If you drifted, say so and change course. "
            "If what you learned shows the Goal or the ask itself is off, tell the user with the evidence.\n"
            + render(card)
        )
    turn["steps"] = steps
    task.save_state()
    return {"note": "\n\n".join(notes)} if notes else {}


def hook_compact(task: Task, data: dict, harness: str) -> dict:
    session = task.session(data.get("session"))
    task.turn(session)["compacted"] = True
    task.save_state()
    card = task.card_for(session)
    if not card:
        return {}
    return {
        "instructions": "Keep this intent card verbatim in the summary, with each Done-when item's status, "
        "every user correction word for word, and the files changed so far:\n" + render(card)
    }


def hook_stop(task: Task, data: dict, harness: str) -> dict:
    session = task.session(data.get("session"))
    # Kept so a correction in the next prompt is logged with the answer it corrects.
    turn = task.turn(session)
    # Headless shells killed at the final response send no completion notice; sample them at each Stop.
    for call_id in list(turn.get("until_stop", {})):
        hook_tool(
            task,
            {
                "session": session,
                "tool": "bash",
                "call_id": call_id,
                "phase": "complete",
                "background": True,
                "until_stop": True,
            },
            harness,
        )
    turn["last_answer"] = (data.get("answer") or "")[:600]
    task.save_state()
    card = task.card_for(session)
    if not card:
        return {}
    now_dirty = task.dirty()
    touched = set(turn.get("touched") or [])
    # A turn whose tools wrote nothing (a question, a status check) is not held to the card's open items.
    if not turn.get("wrote"):
        return {}
    unmet = open_items(card)
    # Only files observed in this turn's edits count; a user edit between calls is left alone.
    outside = [p for p in now_dirty if p in touched and not in_scope(task, os.path.join(str(task.root), p))]
    if not unmet and not outside:
        turn.update(continues=0, last_unmet=None)
        task.save_state()
        return {}
    signature = sorted(item["id"] for item in unmet) + sorted(outside)
    if int(turn.get("continues", 0)) >= MAX_CONTINUES or turn.get("last_unmet") == signature:
        return {}
    turn["continues"] = int(turn.get("continues", 0)) + 1
    turn["last_unmet"] = signature
    task.save_state()
    lines = ["intent-guard: the task is not done against its intent card."]
    if unmet:
        lines.append("Open `Done when` items:")
        lines += [f"- {item['id']}: {item['text']}" for item in unmet]
        # The §1 limits, worded as STEP in the stop-review mod (home/dot_claude/exact_mods/stop-review/hooks/readonly_checks.ts).
        lines.append(
            "Do each one that is a step ~/AGENTS.md §1 makes part of the task "
            "(named by the request, or reversible and changing nothing outside this machine the request did not name, "
            "when it is in the request's scope (fixes from a review the request ran on the user's own work count) "
            "or fixes a defect in the change's impact (§3 step 1); or a §3 step 7 cleanup k-cleanup allows; "
            "never a §5 action §5 does not allow, a live check §3 step 4 keeps for the user's ask, "
            "or a step the user asked you to ask about first), then mark it with "
            '`,task check <id> --evidence "<command and result>"`. '
            "For one you cannot do now (it waits on a user decision or a blocker), "
            'run `,task block <id> --reason "..."` and list it under `Open:` or `Decision needed:` with that id.'
        )
    if outside:
        lines.append("Changed files outside the card's `Scope:`: " + ", ".join(outside[:20]))
        lines.append(
            'For each one you changed, record why the Goal or a defect in the change\'s impact (§3 step 1) needs it with `,task scope add <path> --reason "..."`, '
            "or undo your change; a k-cleanup deletion (§3 step 7) gets the reason, not an undo. Leave a change the user made alone."
        )
    lines.append("Then write the whole final answer again; it replaces your last one.")
    return {"block": "\n".join(lines)}


HOOKS = {"prompt": hook_prompt, "tool": hook_tool, "compact": hook_compact, "stop": hook_stop}


def codex_event(data: dict) -> tuple[str, dict]:
    """Map a Codex hook payload to a hook event and its input."""
    name = data.get("hook_event_name", "")
    session = str(data.get("session_id") or "")
    if name == "UserPromptSubmit":
        return "prompt", {"session": session, "text": data.get("prompt", "")}
    if name == "SessionStart":
        return ("compact" if data.get("source") == "compact" else "start"), {"session": session}
    if name in ("PreToolUse", "PostToolUse"):
        tool_input = data.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {"command": str(tool_input)}
        paths = [tool_input.get(key) for key in ("file_path", "path") if isinstance(tool_input.get(key), str)]
        patch = tool_input.get("patch") or tool_input.get("input") or tool_input.get("command") or ""
        return ("tool" if name == "PreToolUse" else "tool_after"), {
            "session": session,
            "tool": data.get("tool_name", ""),
            "call_id": data.get("tool_use_id"),
            "phase": "before" if name == "PreToolUse" else "after",
            "paths": paths,
            "patch": patch if isinstance(patch, str) else "",
        }
    if name == "Stop":
        return "stop", {"session": session, "answer": data.get("last_assistant_message") or ""}
    return "", {}


def codex_output(name: str, event: str, result: dict) -> dict:
    if event == "prompt" and result.get("context"):
        return {"hookSpecificOutput": {"hookEventName": name, "additionalContext": result["context"]}}
    if event in ("compact", "start"):
        text = result.get("instructions") or result.get("context")
        return {"hookSpecificOutput": {"hookEventName": name, "additionalContext": text}} if text else {}
    if event == "tool" and result.get("deny"):
        return {
            "hookSpecificOutput": {
                "hookEventName": name,
                "permissionDecision": "deny",
                "permissionDecisionReason": result["deny"],
            }
        }
    if event == "tool_after" and result.get("note"):
        return {"hookSpecificOutput": {"hookEventName": name, "additionalContext": result["note"]}}
    if event == "stop" and result.get("block"):
        return {"decision": "block", "reason": result["block"]}
    return {}


def cmd_hook(args: argparse.Namespace) -> int:
    data = args.data
    cwd = Path(data.get("cwd") or os.getcwd())
    task = Task(cwd, data.get("session_id") if args.event == "codex" else data.get("session"))
    if args.event == "codex":
        name = data.get("hook_event_name", "")
        event, payload = codex_event(data)
        if event == "start":
            result = hook_prompt(task, {**payload, "text": ""}, "codex")
        elif event == "compact":
            # Codex reports compaction once it is done: the card comes back here as the current intent, so no zoom-out repeats it.
            card = task.card_for(task.session(payload.get("session")))
            result = (
                {"context": "The conversation was compacted. Intent card for this task (keep to it):\n" + render(card)}
                if card
                else {}
            )
        elif event == "tool_after":
            # Codex reports the edit after it ran: the scope and zoom-out notes go back as context, never as a refusal.
            result = hook_tool(task, payload, "codex")
            result.pop("deny", None)
        elif event == "tool":
            # PreToolUse only refuses the first uncarded edit; PostToolUse counts the step and adds the notes.
            result = hook_tool(task, payload, "codex")
            result.pop("note", None)
        elif event in HOOKS:
            result = HOOKS[event](task, payload, "codex")
        else:
            result = {}
        out = codex_output(name, event, result)
    else:
        out = HOOKS[args.event](task, data, args.harness)
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0


# --- commands ----------------------------------------------------------------


def cmd_card_set(args: argparse.Namespace) -> int:
    task = Task(Path.cwd(), getattr(args, "session", None))
    parsed = parse_card(sys.stdin.read())
    problems = validate(parsed)
    if problems:
        print(",task: card not saved: " + "; ".join(problems), file=sys.stderr)
        print(CARD_RULE, file=sys.stderr)
        return 2
    session = task.session(args.session)
    old = task.card_for(session)
    done = [{"id": f"D{i}", "text": text, "status": "open"} for i, text in enumerate(parsed["done"], 1)]
    goal_changed = bool(old) and old["goal"] != parsed["goal"]
    if old and not goal_changed:
        # Keep the status of items that survive a rewrite of the card; a new goal needs its own evidence.
        by_text = {item["text"]: item for item in old["done"]}
        for item in done:
            prior = by_text.get(item["text"])
            if prior:
                item.update(status=prior["status"], note=prior.get("note", ""))
    # A new goal archives the old goal's scope changes as a record; the new goal records its own.
    archived = old.get("scope_changes", []) if goal_changed else []
    card = {
        "session": session,
        "created": old["created"] if old else now(),
        "updated": now(),
        "goal": parsed["goal"],
        "reading": parsed["reading"],
        "done": done,
        "scope": parsed["scope"],
        "not_doing": parsed["not_doing"],
        "scope_changes": old.get("scope_changes", []) if old and not goal_changed else [],
        "earlier_scope_changes": (old.get("earlier_scope_changes", []) if old else []) + archived,
        "corrections": old.get("corrections", []) if old else [],
        "goal_history": (old.get("goal_history", []) if old else []) + ([old["goal"]] if goal_changed else []),
    }
    if archived:
        print(
            ",task: the new goal archived these scope changes: "
            + ", ".join(change["path"] for change in archived)
            + '. Run `,task scope add <path> --reason "..."` for each one the new goal still needs.',
            file=sys.stderr,
        )
    task.card = card
    task.save_card()
    task.turn(session).update(continues=0, last_unmet=None, steps=0)
    task.save_state()
    # The limit counts only what the agent wrote: no evidence notes, scope changes, or earlier goals.
    size = len(render(card, full=False, notes=False).encode())
    if size > CARD_SOFT_LIMIT:
        print(
            f",task: card saved; its Goal, Reading, Done when, Scope, and Not doing take {size} bytes (limit {CARD_SOFT_LIMIT}). "
            "Shorten the longest of them in the next `card set`.",
            file=sys.stderr,
        )
    print(render(card))
    return 0


def require_card(task: Task, session: str | None = None) -> dict:
    if not task.card:
        raise SystemExit(f",task: no card for session {task.session_id} in {task.root or task.cwd}. {CARD_RULE}")
    if session and not task.card_for(session):
        raise SystemExit(f",task: the card in {task.root or task.cwd} belongs to another session")
    return task.card


def cmd_card_show(args: argparse.Namespace) -> int:
    task = Task(Path.cwd(), getattr(args, "session", None))
    card = require_card(task, args.session)
    print(json.dumps(card, indent=2, ensure_ascii=False) if args.json else render(card, all_changes=True))
    return 0


def cmd_card_clear(args: argparse.Namespace) -> int:
    task = Task(Path.cwd(), getattr(args, "session", None))
    task.cards.pop(task.session_id, None)
    write_json(task.cards_path, task.cards)
    task.state.get("turns", {}).pop(task.session_id, None)
    task.save_state()
    return 0


def set_item(args: argparse.Namespace, status: str, note: str) -> int:
    task = Task(Path.cwd(), getattr(args, "session", None))
    card = require_card(task, args.session)
    wanted = args.id.upper()
    for item in card["done"]:
        if item["id"] == wanted:
            item.update(status=status, note=note)
            card["updated"] = now()
            task.save_card()
            print(render(card, full=False))
            return 0
    raise SystemExit(f",task: no item {wanted}; the card has " + ", ".join(i["id"] for i in card["done"]))


def cmd_check(args: argparse.Namespace) -> int:
    return set_item(args, "checked", args.evidence)


def cmd_block(args: argparse.Namespace) -> int:
    return set_item(args, "blocked", args.reason)


def cmd_reopen(args: argparse.Namespace) -> int:
    return set_item(args, "open", "")


def cmd_scope_add(args: argparse.Namespace) -> int:
    task = Task(Path.cwd(), getattr(args, "session", None))
    card = require_card(task, args.session)
    card.setdefault("scope_changes", []).append({"path": args.path, "reason": args.reason, "time": now()})
    task.save_card()
    print(f"Scope change: {args.path} — {args.reason}")
    return 0


def cmd_scope_check(args: argparse.Namespace) -> int:
    task = Task(Path.cwd(), getattr(args, "session", None))
    require_card(task, args.session)
    outside = [p for p in args.paths if not in_scope(task, p)]
    for path in outside:
        print(path)
    return 1 if outside else 0


def cmd_status(args: argparse.Namespace) -> int:
    task = Task(Path.cwd(), getattr(args, "session", None))
    card = require_card(task, args.session)
    unmet = open_items(card)
    for item in unmet:
        print(f"{item['id']}: {item['text']}")
    return 1 if unmet else 0


def cmd_correct(args: argparse.Namespace) -> int:
    task = Task(Path.cwd(), getattr(args, "session", None))
    card = require_card(task)
    card.setdefault("corrections", []).append(args.text)
    task.save_card()
    log_steering(task, args.harness, args.text)
    return 0


def cmd_pref_add(args: argparse.Namespace) -> int:
    task = Task(Path.cwd(), "unknown")
    scope = "global" if args.glob else repo_name(task)
    append_jsonl(root_dir() / "preferences.jsonl", {"time": now(), "scope": scope, "text": args.text})
    print(f"{scope}: {args.text}")
    return 0


def cmd_pref_list(args: argparse.Namespace) -> int:
    for entry in preferences(Task(Path.cwd(), "unknown")):
        print(f"{entry['scope']}: {entry['text']}")
    return 0


def cmd_steering_report(args: argparse.Namespace) -> int:
    try:
        lines = (root_dir() / "steering.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        print("no steering log yet")
        return 0
    cutoff = time.time() - args.days * 86400
    entries = []
    for line in lines:
        try:
            entry = json.loads(line)
            stamp = time.mktime(time.strptime(entry["time"][:19], "%Y-%m-%dT%H:%M:%S"))
        except (ValueError, KeyError):
            continue
        if stamp >= cutoff:
            entries.append(entry)
    counts: dict[tuple[str, str], int] = {}
    for entry in entries:
        key = (entry.get("repo", "?"), entry.get("harness", "?"))
        counts[key] = counts.get(key, 0) + 1
    print(f"{len(entries)} correction(s) in the last {args.days} day(s)")
    for (repo, harness), count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4d}  {repo}  ({harness})")
    for entry in entries[-args.recent :]:
        print(f"\n{entry['time']}  {entry.get('repo')}  {entry.get('harness')}")
        if entry.get("goal"):
            print(f"  goal: {entry['goal'][:200]}")
        print(f"  user: {entry['text'][:400]}")
    return 0


SESSION_HELP = "refuse unless this session wrote the card"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=",task", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    card = sub.add_parser("card", help="write, show, or clear the intent card").add_subparsers(
        dest="card", required=True
    )
    card_set = card.add_parser("set", help="save the card on stdin (Goal, Reading, Done when, Scope, Not doing)")
    card_set.add_argument("--session", help="harness session id (default: the session that last prompted here)")
    card_set.set_defaults(func=cmd_card_set)
    card_show = card.add_parser("show", help="print the card")
    card_show.add_argument("--json", action="store_true", help="print the stored JSON")
    card_show.add_argument("--session", help="print it only if this session wrote it")
    card_show.set_defaults(func=cmd_card_show)
    card_clear = card.add_parser("clear", help="drop this session's card and turn state")
    card_clear.add_argument("--session", help=SESSION_HELP)
    card_clear.set_defaults(func=cmd_card_clear)

    for name, func, label, help_text in (
        ("check", cmd_check, "--evidence", "mark a Done-when item met, with its evidence"),
        ("block", cmd_block, "--reason", "mark a Done-when item blocked, with the blocker"),
    ):
        item = sub.add_parser(name, help=help_text)
        item.add_argument("id", help="item id, e.g. D1")
        item.add_argument(label, required=True, dest=label.strip("-"))
        item.add_argument("--session", help=SESSION_HELP)
        item.set_defaults(func=func)
    reopen = sub.add_parser("reopen", help="mark a Done-when item open again")
    reopen.add_argument("id")
    reopen.add_argument("--session", help=SESSION_HELP)
    reopen.set_defaults(func=cmd_reopen)
    status = sub.add_parser("status", help="list open Done-when items (exit 1 while any is open)")
    status.add_argument("--session", help=SESSION_HELP)
    status.set_defaults(func=cmd_status)

    scope = sub.add_parser("scope", help="extend or check the card's scope").add_subparsers(dest="scope", required=True)
    scope_add = scope.add_parser(
        "add", help="record a path the goal or a defect in the change's impact needs beyond the original scope"
    )
    scope_add.add_argument("path")
    scope_add.add_argument("--reason", required=True)
    scope_add.add_argument("--session", help=SESSION_HELP)
    scope_add.set_defaults(func=cmd_scope_add)
    scope_check = scope.add_parser("check", help="print paths outside the scope (exit 1 if any)")
    scope_check.add_argument("paths", nargs="+")
    scope_check.add_argument("--session", help=SESSION_HELP)
    scope_check.set_defaults(func=cmd_scope_check)

    correct = sub.add_parser("correct", help="record a user correction verbatim on the card and in the steering log")
    correct.add_argument("text")
    correct.add_argument("--harness", default="manual")
    correct.add_argument("--session", help=SESSION_HELP)
    correct.set_defaults(func=cmd_correct)

    pref = sub.add_parser("pref", help="lasting user preferences loaded into new sessions").add_subparsers(
        dest="pref", required=True
    )
    pref_add = pref.add_parser("add", help="save a preference for this repo (or --global)")
    pref_add.add_argument("text")
    pref_add.add_argument("--global", dest="glob", action="store_true", help="apply in every repo")
    pref_add.set_defaults(func=cmd_pref_add)
    pref.add_parser("list", help="print the preferences that apply here").set_defaults(func=cmd_pref_list)

    report = sub.add_parser("steering", help="report the corrections logged by the hooks")
    report.add_argument("--days", type=int, default=7)
    report.add_argument("--recent", type=int, default=10, help="recent entries to print")
    report.set_defaults(func=cmd_steering_report)

    hook = sub.add_parser("hook", help="harness adapter entry point: JSON in, JSON out")
    hook.add_argument("event", choices=[*HOOKS, "codex"])
    hook.add_argument("--harness", default="unknown")
    hook.add_argument("--input", help="JSON input (default: stdin)")
    hook.set_defaults(func=cmd_hook)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Atomic JSON replacement lets readers use a read-only store, including in sandboxes.
    if args.func in (cmd_card_show, cmd_status, cmd_scope_check, cmd_pref_list, cmd_steering_report):
        return args.func(args)
    cwd = Path.cwd()
    if args.command == "hook":
        raw = args.input if args.input is not None else sys.stdin.read()
        try:
            args.data = json.loads(raw) if raw.strip() else {}
        except ValueError:
            args.data = {}
        cwd = Path(args.data.get("cwd") or cwd)
    directory = task_dir(cwd)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
