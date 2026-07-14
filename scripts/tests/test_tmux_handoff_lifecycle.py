#!/usr/bin/env python3
"""Lifecycle tests for the real tmux handoff popup wrappers.

Covers an isolated deployed-layout fixture that copies the actual
``gh_popup.sh`` wrapper, the actual session ``popup.sh`` wrapper, the real
``handoff_namespace.py`` core, and the real palantir apply helper into a fake
``$HOME``. Inner GH/session picker commands and ``tmux`` are stubbed so the
wrappers execute synchronously, record every ``display-popup -e`` token
injection and command chain, and never talk to a live tmux server.

Compatibility impact: none.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import TMUX_PICKERS, modern_bash

GH_POPUP_SRC = TMUX_PICKERS / "github/executable_gh_popup.sh"
SESSION_POPUP_SRC = TMUX_PICKERS / "session/executable_popup.sh"
CORE_SRC = TMUX_PICKERS / "lib/executable_handoff_namespace.py"
PALANTIR_HELPER_SRC = TMUX_PICKERS / "lib/executable_handoff_to_palantir_apply.sh"

LEGACY_TOP_LEVEL = (
    "gh_picker_pin",
    "pick_session_pin",
    "gh_picker_create_pin",
    "gh_picker_palantir_pin",
    "gh_picker_switch_sessions",
    "pick_session_switch_gh",
)
TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
RETAINED_NAME_RE = re.compile(r"^[0-9a-f]{32}\.md$")

TMUX_STUB_SCRIPT = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    from __future__ import annotations

    import json
    import os
    import subprocess
    import sys
    import time
    from pathlib import Path


    def append_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(payload)
        payload.setdefault("ts", time.time_ns())
        encoded = (json.dumps(payload, sort_keys=True) + "\\n").encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)


    LOG_PATH = Path(os.environ["LIFECYCLE_TMUX_LOG"])


    def record(event: str, **fields: object) -> None:
        append_json(LOG_PATH, {"source": "tmux", "event": event, **fields})


    def split_commands(args: list[str]) -> list[list[str]]:
        commands: list[list[str]] = []
        current: list[str] = []
        for arg in args:
            if arg == ";":
                if current:
                    commands.append(current)
                    current = []
                continue
            current.append(arg)
        if current:
            commands.append(current)
        return commands


    def handle_display_message(args: list[str]) -> int:
        if "-p" in args:
            rendered = "|".join(
                [
                    os.environ.get("TMUX_STUB_POPUP_HEIGHT", "40"),
                    os.environ.get("TMUX_STUB_POPUP_WIDTH", "80"),
                    os.environ.get("TMUX_STUB_DEFAULT_SHELL", "/bin/zsh"),
                ]
            )
            sys.stdout.write(rendered + "\\n")
            record("display-message", argv=args, rendered=rendered, label=os.environ.get("LIFECYCLE_LABEL"))
            return 0
        message = args[-1] if args else ""
        record("display-message", argv=args, message=message, label=os.environ.get("LIFECYCLE_LABEL"))
        return 0


    def handle_set_option(args: list[str]) -> int:
        record("set-option", argv=args, label=os.environ.get("LIFECYCLE_LABEL"))
        return 0


    def handle_command_prompt(args: list[str]) -> int:
        seed = None
        prompt = None
        if "-I" in args:
            try:
                seed = args[args.index("-I") + 1]
            except IndexError:
                seed = None
        if "-p" in args:
            try:
                prompt = args[args.index("-p") + 1]
            except IndexError:
                prompt = None
        record(
            "command-prompt",
            argv=args,
            label=os.environ.get("LIFECYCLE_LABEL"),
            seed=seed,
            prompt=prompt,
        )
        return 0


    def handle_display_popup(args: list[str]) -> int:
        env_updates: dict[str, str] = {}
        command = None
        idx = 1
        while idx < len(args):
            arg = args[idx]
            if arg == "-e" and idx + 1 < len(args):
                key, _, value = args[idx + 1].partition("=")
                env_updates[key] = value
                idx += 2
                continue
            if arg in {"-h", "-w", "-d", "-x", "-y", "-T", "-s"} and idx + 1 < len(args):
                idx += 2
                continue
            if arg.startswith("-"):
                idx += 1
                continue
            command = arg
            idx += 1
        record(
            "display-popup",
            argv=args,
            label=os.environ.get("LIFECYCLE_LABEL"),
            env=env_updates,
            command=command,
        )
        if not command:
            return 0
        popup_env = dict(os.environ)
        popup_env.update(env_updates)
        proc = subprocess.run([command], env=popup_env, cwd=os.environ.get("HOME"))
        return proc.returncode


    def handle_segment(args: list[str]) -> int:
        if not args:
            return 0
        verb = args[0]
        if verb == "display-message":
            return handle_display_message(args)
        if verb == "set-option":
            return handle_set_option(args)
        if verb == "display-popup":
            return handle_display_popup(args)
        if verb == "command-prompt":
            return handle_command_prompt(args)
        record("passthrough", argv=args, label=os.environ.get("LIFECYCLE_LABEL"))
        return 0


    def main() -> int:
        commands = split_commands(sys.argv[1:])
        rc = 0
        for command in commands:
            rc = handle_segment(command)
            if rc != 0:
                break
        return rc


    if __name__ == "__main__":
        raise SystemExit(main())
    """
)

POPUP_ACTOR_SCRIPT = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    from __future__ import annotations

    import json
    import os
    import stat
    import subprocess
    import sys
    import time
    from pathlib import Path


    def append_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(payload)
        payload.setdefault("ts", time.time_ns())
        encoded = (json.dumps(payload, sort_keys=True) + "\\n").encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)


    EVENT_LOG = Path(os.environ["LIFECYCLE_EVENT_LOG"])
    STATE_DIR = Path(os.environ["LIFECYCLE_STATE_DIR"])
    BARRIER_DIR = Path(os.environ["LIFECYCLE_BARRIER_DIR"])
    SCENARIO = os.environ["LIFECYCLE_SCENARIO"]
    LABEL = os.environ["LIFECYCLE_LABEL"]
    TOKEN = os.environ.get("TMUX_PICKER_HANDOFF_TOKEN", "")
    COMMAND = Path(sys.argv[0]).name
    CORE = Path(os.environ["HOME"]) / ".config/tmux/scripts/pickers/lib/handoff_namespace.py"


    def record(event: str, **fields: object) -> None:
        append_json(EVENT_LOG, {"source": "actor", "event": event, "scenario": SCENARIO, "label": LABEL, **fields})


    def counter_path() -> Path:
        return STATE_DIR / f"{SCENARIO}.{LABEL}.{COMMAND}.count"


    def next_count() -> int:
        path = counter_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        current = int(path.read_text(encoding="utf-8")) if path.exists() else 0
        current += 1
        path.write_text(str(current), encoding="utf-8")
        return current


    COUNT = next_count()


    def run_core(*args: str) -> str:
        proc = subprocess.run(
            [sys.executable, str(CORE), *args],
            capture_output=True,
            text=True,
            env={**os.environ, "XDG_CACHE_HOME": os.environ["XDG_CACHE_HOME"]},
        )
        if proc.returncode != 0:
            record("core-fail", argv=list(args), stderr=proc.stderr.strip())
            raise SystemExit(proc.returncode)
        return proc.stdout.strip()


    def slot_path(slot: str) -> Path:
        return Path(run_core("path", slot, "--token", TOKEN))


    def write_slot(slot: str, content: str) -> Path:
        path = slot_path(slot)
        path.write_text(content, encoding="utf-8")
        record("write-slot", slot=slot, path=str(path), content=content.rstrip("\\n"), token=TOKEN)
        return path


    def touch_slot(slot: str) -> Path:
        return write_slot(slot, "1\\n")


    def consume_slot(slot: str) -> dict | None:
        path = slot_path(slot)
        if not path.exists():
            record("consume-miss", slot=slot, path=str(path), token=TOKEN)
            return None
        text = path.read_text(encoding="utf-8")
        line = text.splitlines()[0] if text else ""
        parts = line.split("\t")
        while len(parts) < 5:
            parts.append("")
        kind, repo, num, owner, url = parts[:5]
        path.unlink()
        record(
            "consume-slot",
            slot=slot,
            path=str(path),
            token=TOKEN,
            owner=owner,
            kind=kind,
            repo=repo,
            num=num,
            url=url,
        )
        return {"kind": kind, "repo": repo, "num": num, "owner": owner, "url": url}


    def barrier_arrive(name: str) -> None:
        marker = BARRIER_DIR / name
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("ready\\n", encoding="utf-8")
        record("barrier-arrive", name=name)


    def barrier_wait(name: str) -> None:
        marker = BARRIER_DIR / name
        deadline = time.monotonic() + 10.0
        record("barrier-wait", name=name)
        while time.monotonic() < deadline:
            if marker.exists():
                record("barrier-release", name=name)
                return
            time.sleep(0.01)
        record("barrier-timeout", name=name)
        raise SystemExit(99)


    def write_palantir_handoff() -> None:
        pin = slot_path("gh_picker_palantir_pin")
        context = pin.with_suffix(pin.suffix + ".context.md")
        context.write_text("RICH PALANTIR CONTEXT\\n", encoding="utf-8")
        fields = [
            "pr",
            "owner/repo",
            "9",
            "https://example.test/9",
            "Some Title",
            "/some/worktree",
            str(context),
            "pr owner/repo#9: Some Title",
            "1",
        ]
        pin.write_text("\t".join(fields) + "\\n", encoding="utf-8")
        record("write-palantir", path=str(pin), context=str(context), token=TOKEN)


    def main() -> int:
        record("inner-start", command=COMMAND, count=COUNT, token=TOKEN)
        if COMMAND == "gh_dashboard.sh":
            if SCENARIO in {"gh-wrapper-roundtrip", "legacy-globals-unchanged"}:
                if COUNT == 1:
                    write_slot("pick_session_pin", f"pr\towner/repo\t42\t{LABEL}\\n")
                    touch_slot("gh_picker_switch_sessions")
                elif COUNT == 2:
                    consume_slot("gh_picker_pin")
                return 0
            if SCENARIO == "gh-concurrent-isolation":
                write_slot("pick_session_pin", f"pr\towner/repo\t{100 + (0 if LABEL == 'A' else 1)}\t{LABEL}\\n")
                touch_slot("gh_picker_switch_sessions")
                barrier_arrive(f"ready-{LABEL}")
                barrier_wait("release")
                return 0
            if SCENARIO == "normal-exit-cleanup":
                return 0
            if SCENARIO == "palantir-retained-context":
                write_palantir_handoff()
                return 0
        if COMMAND == "pick_session.sh":
            if SCENARIO in {"gh-wrapper-roundtrip", "legacy-globals-unchanged", "gh-concurrent-isolation"}:
                consumed = consume_slot("pick_session_pin")
                if SCENARIO != "gh-concurrent-isolation" and consumed:
                    write_slot(
                        "gh_picker_pin",
                        f"{consumed['kind']}\t{consumed['repo']}\t{consumed['num']}\t{LABEL}\\n",
                    )
                    touch_slot("pick_session_switch_gh")
                return 0
            if SCENARIO == "session-wrapper-roundtrip":
                if COUNT == 1:
                    write_slot("gh_picker_pin", f"pr\towner/repo\t43\t{LABEL}\\n")
                    touch_slot("pick_session_switch_gh")
                elif COUNT == 2:
                    consume_slot("pick_session_pin")
                return 0
        if COMMAND == "gh_picker.sh" and SCENARIO == "session-wrapper-roundtrip":
            consumed = consume_slot("gh_picker_pin")
            if consumed:
                write_slot(
                    "pick_session_pin",
                    f"{consumed['kind']}\t{consumed['repo']}\t{consumed['num']}\t{LABEL}\\n",
                )
                touch_slot("gh_picker_switch_sessions")
            return 0
        record("inner-noop", command=COMMAND, count=COUNT, token=TOKEN)
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    """
)


def _resolved_wrapper_bash() -> str:
    try:
        return modern_bash()
    except Exception:  # noqa: BLE001 - fallback outside unittest contexts
        return shutil.which("bash") or "/bin/bash"


def append_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    data.setdefault("ts", time.time_ns())
    encoded = (json.dumps(data, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def wait_for_paths(paths: list[Path], *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    missing = list(paths)
    while time.monotonic() < deadline:
        missing = [path for path in paths if not path.exists()]
        if not missing:
            return
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {[str(path) for path in missing]}")


class HandoffLifecycleFixture:
    """Isolated deployed-layout fixture for the real popup wrappers."""

    def __init__(self, root: Path, case_name: str, trace_sink: list[str] | None = None) -> None:
        self.root = root
        self.case_name = case_name
        self.trace_sink = trace_sink
        self.wrapper_bash = _resolved_wrapper_bash()

    def reset(self, *, include_core: bool = True, failing_core: bool = False) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        self.home = self.root / "home"
        self.cache = self.root / "cache"
        self.bin = self.root / "bin"
        self.logs = self.root / "logs"
        self.barriers = self.root / "barriers"
        self.state = self.root / "state"
        self.events_log = self.logs / "events.jsonl"
        self.tmux_log = self.logs / "tmux.jsonl"
        for path in (self.home, self.cache, self.bin, self.logs, self.barriers, self.state):
            path.mkdir(parents=True, exist_ok=True)

        self.github_dir = self.home / ".config/tmux/scripts/pickers/github"
        self.session_dir = self.home / ".config/tmux/scripts/pickers/session"
        self.lib_dir = self.home / ".config/tmux/scripts/pickers/lib"
        for path in (self.github_dir, self.session_dir, self.lib_dir):
            path.mkdir(parents=True, exist_ok=True)

        self._copy_exec(GH_POPUP_SRC, self.github_dir / "gh_popup.sh")
        self._copy_exec(SESSION_POPUP_SRC, self.session_dir / "popup.sh")
        self._copy_exec(PALANTIR_HELPER_SRC, self.lib_dir / "handoff_to_palantir_apply.sh")
        if include_core:
            if failing_core:
                self._write_exec(
                    self.lib_dir / "handoff_namespace.py",
                    "#!/usr/bin/env bash\nexit 1\n",
                )
            else:
                self._copy_exec(CORE_SRC, self.lib_dir / "handoff_namespace.py")

        for path in (
            self.github_dir / "gh_dashboard.sh",
            self.github_dir / "gh_picker.sh",
            self.session_dir / "pick_session.sh",
        ):
            self._write_exec(path, POPUP_ACTOR_SCRIPT)
        self._write_exec(self.bin / "tmux", TMUX_STUB_SCRIPT)

    def _copy_exec(self, src: Path, dest: Path) -> None:
        shutil.copy2(src, dest)
        os.chmod(dest, 0o755)

    def _write_exec(self, dest: Path, content: str) -> None:
        dest.write_text(content, encoding="utf-8")
        os.chmod(dest, 0o755)

    def base_env(self, *, scenario: str, label: str) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "HOME": str(self.home),
                "XDG_CACHE_HOME": str(self.cache),
                "PATH": str(self.bin) + os.pathsep + env.get("PATH", ""),
                "TMUX": "stub-session",
                "LIFECYCLE_SCENARIO": scenario,
                "LIFECYCLE_LABEL": label,
                "LIFECYCLE_EVENT_LOG": str(self.events_log),
                "LIFECYCLE_TMUX_LOG": str(self.tmux_log),
                "LIFECYCLE_BARRIER_DIR": str(self.barriers),
                "LIFECYCLE_STATE_DIR": str(self.state),
                "TMUX_STUB_POPUP_HEIGHT": "40",
                "TMUX_STUB_POPUP_WIDTH": "80",
                "TMUX_STUB_DEFAULT_SHELL": "/bin/zsh",
            }
        )
        return env

    def run_wrapper(self, wrapper: str, *, scenario: str, label: str = "A") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.wrapper_bash, str(self.wrapper_path(wrapper))],
            capture_output=True,
            text=True,
            cwd=str(self.root),
            env=self.base_env(scenario=scenario, label=label),
        )

    def start_wrapper(self, wrapper: str, *, scenario: str, label: str) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [self.wrapper_bash, str(self.wrapper_path(wrapper))],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.root),
            env=self.base_env(scenario=scenario, label=label),
        )

    def wrapper_path(self, wrapper: str) -> Path:
        if wrapper == "gh_popup.sh":
            return self.github_dir / wrapper
        if wrapper == "popup.sh":
            return self.session_dir / wrapper
        raise ValueError(f"unknown wrapper {wrapper}")

    def log_driver(self, event: str, **fields: Any) -> None:
        append_json(self.events_log, {"source": "driver", "event": event, "case": self.case_name, **fields})

    def wait_for_barriers(self, *names: str) -> None:
        wait_for_paths([self.barriers / name for name in names])

    def release_barrier(self, name: str) -> None:
        marker = self.barriers / name
        marker.write_text("release\n", encoding="utf-8")
        self.log_driver("barrier-release", name=name)

    def handoff_root(self) -> Path:
        return self.cache / "tmux" / "handoff-v1"

    def token_dirs(self) -> list[Path]:
        root = self.handoff_root()
        if not root.exists():
            return []
        return sorted(path for path in root.iterdir() if path.is_dir() and TOKEN_RE.match(path.name))

    def retained_files(self) -> list[Path]:
        retained_dir = self.handoff_root() / "retained-context"
        if not retained_dir.exists():
            return []
        return sorted(path for path in retained_dir.iterdir() if RETAINED_NAME_RE.match(path.name))

    def events(self) -> list[dict[str, Any]]:
        return read_jsonl(self.events_log)

    def tmux_events(self) -> list[dict[str, Any]]:
        return read_jsonl(self.tmux_log)

    def merged_trace_lines(self) -> list[str]:
        merged = self.events() + self.tmux_events()
        merged.sort(key=lambda row: row.get("ts", 0))
        lines: list[str] = []
        for row in merged:
            source = row.get("source")
            event = row.get("event")
            if source == "tmux" and event == "display-popup":
                token = row.get("env", {}).get("TMUX_PICKER_HANDOFF_TOKEN")
                lines.append(
                    f"TMUX label={row.get('label')} display-popup token={token} cmd={Path(row.get('command', '')).name} argv={row.get('argv')}"
                )
            elif source == "tmux" and event == "command-prompt":
                lines.append(
                    f"TMUX label={row.get('label')} command-prompt seed={row.get('seed')} prompt={row.get('prompt')}"
                )
            elif source == "tmux" and event == "display-message":
                rendered = row.get("rendered") or row.get("message")
                lines.append(f"TMUX label={row.get('label')} display-message {rendered}")
            elif source == "actor" and event == "inner-start":
                lines.append(
                    f"INNER label={row.get('label')} command={row.get('command')} count={row.get('count')} token={row.get('token')}"
                )
            elif source == "actor" and event in {"write-slot", "consume-slot", "consume-miss", "write-palantir"}:
                parts = [f"ACTOR {event}", f"label={row.get('label')}"]
                for key in ("slot", "owner", "token", "path", "context"):
                    if row.get(key) is not None:
                        parts.append(f"{key}={row.get(key)}")
                lines.append(" ".join(parts))
            elif source in {"actor", "driver"} and "barrier" in str(event):
                lines.append(f"BARRIER source={source} event={event} name={row.get('name')}")
        return lines

    def emit_trace(self) -> None:
        if self.trace_sink is not None:
            self.trace_sink.extend(self.merged_trace_lines())

    def poison_legacy_globals(self) -> dict[str, bytes]:
        cache_tmux = self.cache / "tmux"
        cache_tmux.mkdir(parents=True, exist_ok=True)
        poisoned: dict[str, bytes] = {}
        for name in LEGACY_TOP_LEVEL:
            payload = f"POISON {name} do-not-touch\\n".encode("utf-8")
            path = cache_tmux / name
            path.write_bytes(payload)
            poisoned[name] = payload
        return poisoned

    def legacy_bytes(self) -> dict[str, bytes]:
        cache_tmux = self.cache / "tmux"
        return {name: (cache_tmux / name).read_bytes() for name in LEGACY_TOP_LEVEL}

    def case_gh_wrapper_roundtrip(self) -> dict[str, Any]:
        self.reset()
        result = self.run_wrapper("gh_popup.sh", scenario="gh-wrapper-roundtrip")
        tmux_events = self.tmux_events()
        popup_events = [row for row in tmux_events if row["event"] == "display-popup"]
        popup_commands = [Path(row["command"]).name for row in popup_events]
        popup_tokens = [row.get("env", {}).get("TMUX_PICKER_HANDOFF_TOKEN") for row in popup_events]
        actor_events = self.events()
        inner_tokens = [row["token"] for row in actor_events if row.get("event") == "inner-start"]
        token = popup_tokens[0] if popup_tokens else None
        session_consume = next(
            (
                row
                for row in actor_events
                if row.get("event") == "consume-slot"
                and row.get("slot") == "pick_session_pin"
                and row.get("label") == "A"
            ),
            None,
        )
        gh_consume = next(
            (
                row
                for row in actor_events
                if row.get("event") == "consume-slot" and row.get("slot") == "gh_picker_pin" and row.get("label") == "A"
            ),
            None,
        )
        observed = {
            "returncode": result.returncode,
            "popup_commands": popup_commands,
            "stable_token": bool(
                popup_tokens and len(set(popup_tokens)) == 1 and set(popup_tokens) == set(inner_tokens)
            ),
            "session_consumed_owner": session_consume.get("owner") if session_consume else None,
            "gh_return_consumed_owner": gh_consume.get("owner") if gh_consume else None,
            "namespace_removed": bool(token and not (self.handoff_root() / token).exists()),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "display_popup_tokens": popup_tokens,
            "inner_tokens": inner_tokens,
        }
        self.emit_trace()
        return observed

    def case_session_wrapper_roundtrip(self) -> dict[str, Any]:
        self.reset()
        result = self.run_wrapper("popup.sh", scenario="session-wrapper-roundtrip")
        tmux_events = self.tmux_events()
        popup_events = [row for row in tmux_events if row["event"] == "display-popup"]
        popup_commands = [Path(row["command"]).name for row in popup_events]
        popup_tokens = [row.get("env", {}).get("TMUX_PICKER_HANDOFF_TOKEN") for row in popup_events]
        actor_events = self.events()
        inner_tokens = [row["token"] for row in actor_events if row.get("event") == "inner-start"]
        token = popup_tokens[0] if popup_tokens else None
        gh_consume = next(
            (
                row
                for row in actor_events
                if row.get("event") == "consume-slot" and row.get("slot") == "gh_picker_pin" and row.get("label") == "A"
            ),
            None,
        )
        session_return = next(
            (
                row
                for row in actor_events
                if row.get("event") == "consume-slot"
                and row.get("slot") == "pick_session_pin"
                and row.get("label") == "A"
            ),
            None,
        )
        observed = {
            "returncode": result.returncode,
            "popup_commands": popup_commands,
            "stable_token": bool(
                popup_tokens and len(set(popup_tokens)) == 1 and set(popup_tokens) == set(inner_tokens)
            ),
            "gh_consumed_owner": gh_consume.get("owner") if gh_consume else None,
            "session_return_consumed_owner": session_return.get("owner") if session_return else None,
            "namespace_removed": bool(token and not (self.handoff_root() / token).exists()),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "display_popup_tokens": popup_tokens,
            "inner_tokens": inner_tokens,
        }
        self.emit_trace()
        return observed

    def case_concurrent_wrappers_isolated(self) -> dict[str, Any]:
        self.reset()
        proc_a = self.start_wrapper("gh_popup.sh", scenario="gh-concurrent-isolation", label="A")
        proc_b = self.start_wrapper("gh_popup.sh", scenario="gh-concurrent-isolation", label="B")
        try:
            self.wait_for_barriers("ready-A", "ready-B")
            token_dirs = self.token_dirs()
            tokens = [path.name for path in token_dirs]
            self.log_driver("concurrent-ready", tokens=tokens)
            self.release_barrier("release")
            stdout_a, stderr_a = proc_a.communicate(timeout=10)
            stdout_b, stderr_b = proc_b.communicate(timeout=10)
        finally:
            for proc in (proc_a, proc_b):
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=5)
        consume_events = [
            row for row in self.events() if row.get("event") == "consume-slot" and row.get("slot") == "pick_session_pin"
        ]
        consumed_owner_by_label = {row["label"]: row.get("owner") for row in consume_events}
        observed = {
            "returncodes": {"A": proc_a.returncode, "B": proc_b.returncode},
            "shared_cache_root": len(token_dirs) == 2,
            "distinct_tokens": len(set(tokens)) == 2,
            "tokens": tokens,
            "consumed_owner_by_label": consumed_owner_by_label,
            "namespaces_removed": not self.token_dirs(),
            "stdout": {"A": stdout_a, "B": stdout_b},
            "stderr": {"A": stderr_a, "B": stderr_b},
        }
        self.emit_trace()
        return observed

    def case_normal_exit_cleanup(self) -> dict[str, Any]:
        self.reset()
        result = self.run_wrapper("gh_popup.sh", scenario="normal-exit-cleanup")
        popup_events = [row for row in self.tmux_events() if row["event"] == "display-popup"]
        tokens = [row.get("env", {}).get("TMUX_PICKER_HANDOFF_TOKEN") for row in popup_events]
        token = tokens[0] if tokens else None
        observed = {
            "returncode": result.returncode,
            "popup_commands": [Path(row["command"]).name for row in popup_events],
            "namespace_removed": bool(token and not (self.handoff_root() / token).exists()),
            "retained_context_files": len(self.retained_files()),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        self.emit_trace()
        return observed

    def case_palantir_retained_context(self) -> dict[str, Any]:
        self.reset()
        result = self.run_wrapper("gh_popup.sh", scenario="palantir-retained-context")
        tmux_events = self.tmux_events()
        popup_events = [row for row in tmux_events if row["event"] == "display-popup"]
        tokens = [row.get("env", {}).get("TMUX_PICKER_HANDOFF_TOKEN") for row in popup_events]
        token = tokens[0] if tokens else None
        command_prompt = next((row for row in tmux_events if row["event"] == "command-prompt"), None)
        retained = self.retained_files()
        retained_path = retained[0] if retained else None
        observed = {
            "returncode": result.returncode,
            "popup_commands": [Path(row["command"]).name for row in popup_events],
            "command_prompt_queued": command_prompt is not None,
            "retained_context_readable_after_end": bool(
                retained_path
                and retained_path.is_file()
                and retained_path.read_text(encoding="utf-8") == "RICH PALANTIR CONTEXT\n"
            ),
            "retained_context_mode": oct(stat.S_IMODE(retained_path.stat().st_mode)) if retained_path else None,
            "retained_path": str(retained_path) if retained_path else None,
            "seed": command_prompt.get("seed") if command_prompt else None,
            "namespace_removed": bool(token and not (self.handoff_root() / token).exists()),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        self.emit_trace()
        return observed

    def case_legacy_globals_unchanged(self) -> dict[str, Any]:
        self.reset()
        poisoned = self.poison_legacy_globals()
        result = self.run_wrapper("gh_popup.sh", scenario="legacy-globals-unchanged")
        observed = {
            "returncode": result.returncode,
            "byte_identical": self.legacy_bytes() == poisoned,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        self.emit_trace()
        return observed

    def case_missing_core_blocks_popup(self) -> dict[str, Any]:
        self.reset(include_core=False)
        result = self.run_wrapper("popup.sh", scenario="missing-core")
        tmux_events = self.tmux_events()
        observed = {
            "returncode": result.returncode,
            "popup_executed": any(row["event"] == "display-popup" for row in tmux_events),
            "message_emitted": any(
                row["event"] == "display-message" and row.get("message", "").startswith("tmux: missing script")
                for row in tmux_events
            ),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        self.emit_trace()
        return observed

    def case_failed_core_blocks_popup(self) -> dict[str, Any]:
        self.reset(include_core=True, failing_core=True)
        result = self.run_wrapper("gh_popup.sh", scenario="failed-core")
        tmux_events = self.tmux_events()
        observed = {
            "returncode": result.returncode,
            "popup_executed": any(row["event"] == "display-popup" for row in tmux_events),
            "message_emitted": any(
                row["event"] == "display-message" and row.get("message") == "picker handoff: unavailable"
                for row in tmux_events
            ),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        self.emit_trace()
        return observed


REAL_WRAPPER_CASES = {
    "gh_wrapper_round_trip_token": "case_gh_wrapper_roundtrip",
    "session_wrapper_round_trip_token": "case_session_wrapper_roundtrip",
    "concurrent_wrappers_isolated": "case_concurrent_wrappers_isolated",
    "normal_exit_cleanup": "case_normal_exit_cleanup",
    "palantir_retained_context": "case_palantir_retained_context",
    "legacy_globals_unchanged": "case_legacy_globals_unchanged",
    "missing_core_blocks_popup": "case_missing_core_blocks_popup",
    "failed_core_blocks_popup": "case_failed_core_blocks_popup",
}


def run_real_wrapper_harness_case(case: str, *, root: Path, trace_sink: list[str] | None = None) -> dict[str, Any]:
    fixture = HandoffLifecycleFixture(root=root, case_name=case, trace_sink=trace_sink)
    method_name = REAL_WRAPPER_CASES[case]
    method = getattr(fixture, method_name)
    return method()


class TestRealWrapperLifecycle(unittest.TestCase):
    """WHEN driving the real popup wrappers inside an isolated deployed layout."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "handoff-lifecycle"

    def test_should_preserve_one_token_through_gh_session_gh_successors(self) -> None:
        observed = run_real_wrapper_harness_case(
            "gh_wrapper_round_trip_token",
            root=self.root / "gh-roundtrip",
        )
        self.assertEqual(observed["returncode"], 0, observed["stderr"])
        self.assertEqual(observed["popup_commands"], ["gh_dashboard.sh", "pick_session.sh", "gh_dashboard.sh"])
        self.assertTrue(observed["stable_token"])
        self.assertEqual(observed["session_consumed_owner"], "A")
        self.assertEqual(observed["gh_return_consumed_owner"], "A")
        self.assertTrue(observed["namespace_removed"])

    def test_should_preserve_one_token_through_session_gh_session_successors(self) -> None:
        observed = run_real_wrapper_harness_case(
            "session_wrapper_round_trip_token",
            root=self.root / "session-roundtrip",
        )
        self.assertEqual(observed["returncode"], 0, observed["stderr"])
        self.assertEqual(observed["popup_commands"], ["pick_session.sh", "gh_picker.sh", "pick_session.sh"])
        self.assertTrue(observed["stable_token"])
        self.assertEqual(observed["gh_consumed_owner"], "A")
        self.assertEqual(observed["session_return_consumed_owner"], "A")
        self.assertTrue(observed["namespace_removed"])

    def test_should_isolate_two_concurrent_wrappers_sharing_one_cache(self) -> None:
        observed = run_real_wrapper_harness_case(
            "concurrent_wrappers_isolated",
            root=self.root / "concurrent",
        )
        self.assertEqual(observed["returncodes"], {"A": 0, "B": 0}, observed["stderr"])
        self.assertTrue(observed["shared_cache_root"])
        self.assertTrue(observed["distinct_tokens"])
        self.assertEqual(observed["consumed_owner_by_label"], {"A": "A", "B": "B"})
        self.assertTrue(observed["namespaces_removed"])

    def test_should_remove_normal_namespaces_on_exit(self) -> None:
        observed = run_real_wrapper_harness_case(
            "normal_exit_cleanup",
            root=self.root / "cleanup",
        )
        self.assertEqual(observed["returncode"], 0, observed["stderr"])
        self.assertEqual(observed["popup_commands"], ["gh_dashboard.sh"])
        self.assertTrue(observed["namespace_removed"])
        self.assertEqual(observed["retained_context_files"], 0)

    def test_should_retain_palantir_context_after_normal_namespace_end(self) -> None:
        observed = run_real_wrapper_harness_case(
            "palantir_retained_context",
            root=self.root / "palantir",
        )
        self.assertEqual(observed["returncode"], 0, observed["stderr"])
        self.assertEqual(observed["popup_commands"], ["gh_dashboard.sh"])
        self.assertTrue(observed["command_prompt_queued"])
        self.assertEqual(observed["retained_context_mode"], "0o600")
        self.assertTrue(observed["retained_context_readable_after_end"])
        self.assertTrue(observed["namespace_removed"])
        self.assertIn("retained-context", observed["seed"])
        self.assertIn(observed["retained_path"], observed["seed"])

    def test_should_leave_poisoned_legacy_global_files_byte_identical(self) -> None:
        observed = run_real_wrapper_harness_case(
            "legacy_globals_unchanged",
            root=self.root / "legacy",
        )
        self.assertEqual(observed["returncode"], 0, observed["stderr"])
        self.assertTrue(observed["byte_identical"])

    def test_should_block_popup_execution_when_core_is_missing(self) -> None:
        observed = run_real_wrapper_harness_case(
            "missing_core_blocks_popup",
            root=self.root / "missing-core",
        )
        self.assertEqual(observed["returncode"], 0, observed["stderr"])
        self.assertFalse(observed["popup_executed"])
        self.assertTrue(observed["message_emitted"])

    def test_should_block_popup_execution_when_core_begin_fails(self) -> None:
        observed = run_real_wrapper_harness_case(
            "failed_core_blocks_popup",
            root=self.root / "failed-core",
        )
        self.assertEqual(observed["returncode"], 1, observed["stderr"])
        self.assertFalse(observed["popup_executed"])
        self.assertTrue(observed["message_emitted"])


if __name__ == "__main__":
    unittest.main()
