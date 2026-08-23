from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from assets import ambient_theme_style, detect_ambient_theme, inject_ambient_theme, starter_html
from feedback import active_poller_record, active_poller_records, clear_ended, poll_feedback, stop_poller_record
from paths import artifact_path, artifacts_dir, cache_root, context, ensure_session, session_dir
from server import live_script_command, live_start_command, read_server_state, run_server, server_base_url, start_server


def write_artifact(args: argparse.Namespace) -> Path:
    ensure_session()
    path = artifact_path(args.name)
    if args.file:
        content = Path(args.file).expanduser().read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        content = starter_html(args.title or path.stem)
    if not args.no_theme:
        content = inject_ambient_theme(content)
    path.write_text(content, encoding="utf-8")
    return path


def open_url(url: str) -> None:
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    if shutil.which(opener):
        subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def list_artifacts(_: argparse.Namespace) -> None:
    ensure_session()
    rows = []
    for path in sorted(artifacts_dir().glob("*.htm*")):
        rows.append({"name": path.name, "path": str(path), "bytes": path.stat().st_size})
    print(json.dumps({"session": context(), "artifacts": rows}, indent=2))


def list_pollers(_: argparse.Namespace) -> None:
    ensure_session()
    print(json.dumps({"session": context(), "pollers": active_poller_records()}, indent=2))


def poll_stop(args: argparse.Namespace) -> None:
    ensure_session()
    if args.all:
        records = active_poller_records()
    else:
        record = active_poller_record(args.name)
        records = [record] if record else []
    for record in records:
        stop_poller_record(record)
    print(json.dumps({"stopped": len(records), "session": context()}, indent=2))


def clean(args: argparse.Namespace) -> None:
    root = cache_root() if args.all else session_dir()
    if root.exists():
        shutil.rmtree(root)
    print(root)


def stop(_: argparse.Namespace) -> None:
    sdir = session_dir()
    for record in active_poller_records():
        stop_poller_record(record)
    if not server_base_url(sdir):
        return
    state = read_server_state(sdir)
    if not state:
        return
    pid = state.get("pid")
    if isinstance(pid, int):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def path_command(args: argparse.Namespace) -> None:
    ensure_session()
    print(artifact_path(args.name))


def open_command(args: argparse.Namespace) -> None:
    ensure_session()
    path = artifact_path(args.name)
    if not path.exists():
        path.write_text(inject_ambient_theme(starter_html(args.title or path.stem)), encoding="utf-8")
    clear_ended(path.name)
    url = start_server(session_dir())
    session_url = f"{url}/session/{path.name}"
    if not args.no_open:
        open_url(session_url)
    print(session_url)


def write_command(args: argparse.Namespace) -> None:
    path = write_artifact(args)
    clear_ended(path.name)
    print(path)
    if args.open:
        open_args = argparse.Namespace(name=path.name, title=args.title, no_open=False)
        open_command(open_args)


def theme_command(args: argparse.Namespace) -> None:
    theme = detect_ambient_theme()
    if args.css:
        print(ambient_theme_style(theme), end="")
        return
    if args.json:
        print(json.dumps(theme, indent=2))
        return
    print(f"{theme['label']} ({theme['name']})")
    print(f"root: {theme['root']}")
    print(f"markers: {', '.join(theme['markers'])}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=",artifact", description="Cache-only HTML artifact review loop.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("path", help="print the cache path for an artifact")
    p.add_argument("name", nargs="?", default="artifact")
    p.set_defaults(func=path_command)

    p = sub.add_parser("write", help="write stdin or a file to a cached artifact")
    p.add_argument("name", nargs="?", default="artifact")
    p.add_argument("-f", "--file", help="read HTML from file instead of stdin")
    p.add_argument("-t", "--title", help="starter title when no input is provided")
    p.add_argument("--open", action="store_true", help="open after writing")
    p.add_argument("--no-theme", action="store_true", help="do not inject the detected ambient theme")
    p.set_defaults(func=write_command)

    p = sub.add_parser("open", help="open or create a cached artifact review page")
    p.add_argument("name", nargs="?", default="artifact")
    p.add_argument("-t", "--title", help="starter title when creating a new artifact")
    p.add_argument("--no-open", action="store_true", help="print URL without opening a browser")
    p.set_defaults(func=open_command)

    p = sub.add_parser("poll", help="wait for browser feedback")
    p.add_argument("name", nargs="?", default="artifact")
    p.add_argument("--timeout", type=float, help="seconds to wait before returning waiting status")
    p.set_defaults(func=poll_feedback)

    p = sub.add_parser("pollers", help="list active feedback pollers for this session")
    p.set_defaults(func=list_pollers)

    p = sub.add_parser("poll-stop", help="stop feedback pollers for this session")
    p.add_argument("name", nargs="?", default="artifact")
    p.add_argument("--all", action="store_true", help="stop all pollers in this artifact session")
    p.set_defaults(func=poll_stop)

    p = sub.add_parser("list", help="list cached artifacts for this context")
    p.set_defaults(func=list_artifacts)

    p = sub.add_parser("theme", help="show the detected ambient artifact theme")
    p.add_argument("--json", action="store_true", help="print theme metadata as JSON")
    p.add_argument("--css", action="store_true", help="print the injectable CSS style block")
    p.set_defaults(func=theme_command)

    p = sub.add_parser("live", help="prepare a feedback overlay for an already-open live page")
    live_sub = p.add_subparsers(dest="live_command", required=True)

    live = live_sub.add_parser("start", help="start the local server and print the live overlay script URL")
    live.add_argument("name", nargs="?", default="live")
    live.add_argument("--json", action="store_true", help="print live overlay metadata as JSON")
    live.set_defaults(func=live_start_command)

    live = live_sub.add_parser("script", help="print the live overlay JavaScript for Playwriter injection")
    live.add_argument("name", nargs="?", default="live")
    live.set_defaults(func=live_script_command)

    p = sub.add_parser("clean", help="remove cached artifacts")
    p.add_argument("--all", action="store_true", help="remove all agent-artifacts cache, not just this context")
    p.set_defaults(func=clean)

    p = sub.add_parser("stop", help="stop the background server for this context")
    p.set_defaults(func=stop)

    p = sub.add_parser("server", help=argparse.SUPPRESS)
    p.add_argument("--session-dir", required=True)
    p.set_defaults(func=run_server)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)
