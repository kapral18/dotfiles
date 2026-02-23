#!/usr/bin/env bash
set -euo pipefail

sel_file="${1:-}"
mode="${2:-}"
items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"

if [ -z "$sel_file" ] || [ ! -f "$sel_file" ] || [ ! -x "$items_cmd" ]; then
  exec "$items_cmd"
fi

python3 -u - "$sel_file" "$items_cmd" "$mode" <<'PY'
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sel_file = sys.argv[1]
items_cmd = sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else ""

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

selected = set()
selected_rows = []
with open(sel_file, "r", encoding="utf-8", errors="replace") as f:
    for raw in f:
        line = raw.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        _display, kind, path, meta, target = parts[:5]
        selected.add((kind, path, target))
        selected_rows.append((kind, path, meta, target))

def append_mutation_tombstones():
    if mode not in ("kill", "remove"):
        return
    xdg_cache = os.environ.get("XDG_CACHE_HOME", "").strip()
    cache_dir = Path(xdg_cache) / "tmux" if xdg_cache else (Path.home() / ".cache" / "tmux")
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return
    mutation_file = cache_dir / "pick_session_mutations.tsv"
    now = int(time.time())
    lines = []
    if mode == "kill":
        for kind, _path, _meta, target in selected_rows:
            if kind == "session" and target:
                lines.append(f"{now}\tSESSION_TARGET\t{target}\n")
    elif mode == "remove":
        for kind, path, meta, _target in selected_rows:
            if not path:
                continue
            if kind == "worktree":
                lines.append(f"{now}\tPATH_PREFIX\t{path}\n")
                continue
            if kind == "session":
                meta_base = (meta or "").split("|", 1)[0]
                if meta_base.startswith("sess_root:") or meta_base.startswith("sess_wt:"):
                    lines.append(f"{now}\tPATH_PREFIX\t{path}\n")
    if not lines:
        return
    try:
        with open(mutation_file, "a", encoding="utf-8") as mf:
            mf.writelines(lines)
    except Exception:
        pass

append_mutation_tombstones()

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
