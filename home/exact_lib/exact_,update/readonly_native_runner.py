#!/usr/bin/env python3
"""Own the native dekit runner for ,update's selected package categories."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

CATEGORIES = {"brew", "gh", "mise", "cargo", "pnpm", "gems", "go", "uv"}
XDG_KEYS = ("XDG_RUNTIME_DIR", "XDG_STATE_HOME")


class NativeRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root: Path | None = None
        self.env = dict(os.environ)
        self.child: subprocess.Popen | None = None
        self.interrupted = 0
        self.cleaning = False
        self.cleanup_needed = False

    def on_signal(self, signum: int, _frame: object) -> None:
        if not self.interrupted:
            self.interrupted = signum
        if not self.cleaning and self.child is not None:
            try:
                self.child.terminate()
            except ProcessLookupError:
                pass

    def command(self, *args: str, capture: bool = False) -> int:
        self.child = subprocess.Popen(
            [self.dekit, "-C", str(self.root), *args],
            env=self.env,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
        if self.interrupted and not self.cleaning:
            self.child.terminate()
        try:
            stdout, stderr = self.child.communicate()
            if capture and self.child.returncode:
                for output in (stdout, stderr):
                    if output:
                        sys.stderr.buffer.write(output)
            return self.child.returncode
        finally:
            self.child = None

    def prepare(self) -> None:
        binary = shutil.which("dekit")
        if binary is None:
            raise RuntimeError("dekit is not installed")
        self.root = Path(tempfile.mkdtemp(prefix="du-", dir="/tmp")).resolve()
        self.dekit = str(self.root / "dekit")
        shutil.copy2(Path(binary).resolve(), self.dekit)
        for name, key in (("runtime", "XDG_RUNTIME_DIR"), ("state", "XDG_STATE_HOME")):
            directory = self.root / name
            directory.mkdir(mode=0o700)
            self.env[key] = str(directory)
        task_env = {key: os.environ.get(key) for key in XDG_KEYS}
        tasks = {}
        for category in self.args.categories:
            wrapper = self.root / f"{category}.sh"
            command = ["bash", str(Path(self.args.script).resolve()), "--only", category]
            if self.args.verbose:
                command.append("--verbose")
            completion = shlex.quote(str(self.root / f"{category}.rc"))
            wrapper.write_text(
                "#!/usr/bin/env bash\n"
                + shlex.join(command)
                + '\nrc=$?\nprintf "%s\\n" "$rc" > '
                + completion
                + '\nexit "$rc"\n',
                encoding="utf-8",
            )
            tasks[category] = {
                "type": "job",
                "autostart": True,
                "cmd": ["bash", str(wrapper)],
                "cwd": os.getcwd(),
                "env": task_env,
            }
        (self.root / "dekit.yaml").write_text(
            json.dumps({"kernel": {"path": self.dekit}, "tasks": tasks}), encoding="utf-8"
        )

    def collect(self) -> None:
        updated = 0
        for category in self.args.categories:
            try:
                token = (self.root / f"{category}.rc").read_text(encoding="utf-8") if self.root else ""
            except (OSError, UnicodeError):
                token = ""
            if token in ("0", "0\n"):
                updated += 1
        Path(self.args.results).write_text(f"{updated} {len(self.args.categories) - updated}\n", encoding="utf-8")

    def run(self) -> int:
        rc = 0
        stopped = False
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, self.on_signal)
        try:
            self.prepare()
            if not self.interrupted:
                self.cleanup_needed = True
                rc = self.command("up", capture=True)
                if rc == 0 and not self.interrupted:
                    rc = self.command("attach", "--no-start")
        except (OSError, RuntimeError) as error:
            print(f"native dekit: {error}", file=sys.stderr)
            rc = 1
        finally:
            self.cleaning = True
            if self.cleanup_needed:
                try:
                    stopped = self.command("runner", "stop", capture=True) == 0
                except OSError as error:
                    print(f"native dekit stop: {error}", file=sys.stderr)
                if not stopped:
                    print(
                        f"native dekit cleanup failed; retained runner root: {self.root}\n"
                        f"Recovery: XDG_RUNTIME_DIR={shlex.quote(str(self.root / 'runtime'))} "
                        f"XDG_STATE_HOME={shlex.quote(str(self.root / 'state'))} "
                        f"{shlex.quote(self.dekit)} -C {shlex.quote(str(self.root))} runner stop",
                        file=sys.stderr,
                    )
                    rc = 1
            try:
                self.collect()
            except OSError as error:
                print(f"native dekit results: {error}", file=sys.stderr)
                rc = 1
            if self.root and (stopped or not self.cleanup_needed):
                shutil.rmtree(self.root)
        return 128 + self.interrupted if self.interrupted else (1 if rc else 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("categories", nargs="+")
    args = parser.parse_args()
    if not set(args.categories) <= CATEGORIES or len(set(args.categories)) != len(args.categories):
        parser.error("categories must be unique package update categories")
    return NativeRunner(args).run()


if __name__ == "__main__":
    sys.exit(main())
