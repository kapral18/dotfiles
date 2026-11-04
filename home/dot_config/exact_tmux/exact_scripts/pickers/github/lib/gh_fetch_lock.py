"""Own and preempt the GitHub picker's fetch lock."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from picker_owner import PickerOwner, PickerOwnerError, positive_pid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("acquire", "release"))
    parser.add_argument("cache_file", type=Path)
    parser.add_argument("owner_pid")
    parser.add_argument("generation", nargs="?")
    parser.add_argument("child_pid", nargs="?")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    owner_pid = positive_pid(args.owner_pid)
    child_pid = positive_pid(args.child_pid) if args.child_pid else None
    if owner_pid is None or (args.child_pid and child_pid is None):
        parser.error("process IDs must be positive decimal PIDs")
    lock = PickerOwner(args.cache_file, resource="fetch")
    try:
        if args.operation == "acquire":
            print(lock.acquire(owner_pid, args.refresh))
        elif args.generation is None:
            parser.error("release requires an owner generation")
        else:
            lock.release(owner_pid, args.generation, (child_pid,) if child_pid is not None else ())
    except (PickerOwnerError, OSError, TimeoutError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
