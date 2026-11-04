#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import fcntl
import os
import sys
import tempfile
from pathlib import Path


def binary_name(module_path: str) -> str:
    path = module_path.split("@", 1)[0].rstrip("/")
    if not path:
        return ""
    segments = path.split("/")
    last = segments[-1]
    if len(segments) >= 2 and len(last) >= 2 and last[0] == "v" and last[1:].isdigit():
        last = segments[-2]
    return last


def load_modules(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.split()[0]
        for raw in path.read_text(encoding="utf-8").splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    ]


@contextlib.contextmanager
def state_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def write_modules(path: Path, modules: list[str]) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("".join(f"{module}\n" for module in dict.fromkeys(modules)))
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def record_install(state_file: Path, module: str) -> None:
    with state_lock(state_file):
        write_modules(state_file, [*load_modules(state_file), module])


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--record":
        record_install(Path(sys.argv[2]), sys.argv[3])
        return 0
    if len(sys.argv) not in (4, 5):
        sys.stderr.write("usage: reconcile_golang_pkgs.py <desired> <gobin> <state> [<installed>]\n")
        return 2

    desired_file, gobin_dir, state_file = map(Path, sys.argv[1:4])
    desired = load_modules(desired_file)
    installed_now = set(load_modules(Path(sys.argv[4]))) if len(sys.argv) == 5 else set(desired)
    desired_names = {binary_name(module) for module in desired}
    with state_lock(state_file):
        previously_managed = load_modules(state_file)
        failed_removals = []
        for module in previously_managed:
            name = binary_name(module)
            if module in desired or not name or name in desired_names:
                continue
            binary = gobin_dir / name
            existed = binary.exists() or binary.is_symlink()
            try:
                binary.unlink(missing_ok=True)
            except OSError as error:
                failed_removals.append(module)
                sys.stderr.write(f"warning: failed to remove {binary}: {error}\n")
            else:
                if existed:
                    print(f"removed go binary: {name} ({module})")
        managed = [module for module in desired if module in installed_now or module in previously_managed]
        write_modules(state_file, [*managed, *failed_removals])
    return 0


if __name__ == "__main__":
    sys.exit(main())
