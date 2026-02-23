#!/usr/bin/env bash
set -euo pipefail

sel_file="${1:-}"
items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"

if [ -z "$sel_file" ] || [ ! -f "$sel_file" ] || [ ! -x "$items_cmd" ]; then
  exec "$items_cmd"
fi

python3 -u - "$sel_file" "$items_cmd" <<'PY'
import signal
import subprocess
import sys

sel_file = sys.argv[1]
items_cmd = sys.argv[2]

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

selected = set()
with open(sel_file, "r", encoding="utf-8", errors="replace") as f:
    for raw in f:
        line = raw.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        _display, kind, path, _meta, target = parts[:5]
        selected.add((kind, path, target))

proc = subprocess.run([items_cmd], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
for raw in proc.stdout.splitlines():
    if not raw:
        continue
    parts = raw.split("\t")
    if len(parts) < 5:
        print(raw)
        continue
    _display, kind, path, _meta, target = parts[:5]
    if (kind, path, target) in selected:
        continue
    print(raw)
PY
