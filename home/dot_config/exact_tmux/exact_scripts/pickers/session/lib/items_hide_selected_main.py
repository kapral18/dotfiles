#!/usr/bin/env python3
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from pick_session_grouping import grouped_output, simple_resolve

sel_file = sys.argv[1]
items_cmd = sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else ""
query = sys.argv[4] if len(sys.argv) > 4 else ""

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

resolve_path = simple_resolve

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


def path_under_prefix(path, prefix):
    if not path or not prefix:
        return False
    return path == prefix or path.startswith(prefix + "/")


def path_under_any_prefix(path, prefixes):
    for pref in prefixes:
        if path_under_prefix(path, pref):
            return True
    return False


def worktree_dir_for_path(p):
    cur = Path(resolve_path(p))
    if cur.is_file():
        cur = cur.parent
    for _ in range(16):
        if (cur / ".git").exists():
            return str(cur)
        if cur.parent == cur:
            break
        cur = cur.parent
    return ""


def list_worktree_paths(root):
    if not root:
        return []
    try:
        out = subprocess.run(
            ["git", "-C", root, "worktree", "list", "--porcelain"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout
    except Exception:
        return []
    paths = []
    for row in (out or "").splitlines():
        if row.startswith("worktree "):
            wt = row[len("worktree ") :].strip()
            if wt:
                paths.append(resolve_path(wt))
    return paths


def repo_name_from_remote(root):
    if not root:
        return ""
    url = ""
    for remote in ("origin", "upstream"):
        try:
            out = subprocess.run(
                ["git", "-C", root, "remote", "get-url", remote],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            ).stdout.strip()
        except Exception:
            out = ""
        if out:
            url = out
            break
    if not url:
        return ""
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[: -len(".git")]
    if "://" in url:
        return url.rsplit("/", 1)[-1].strip()
    if ":" in url:
        tail = url.split(":", 1)[1]
        return tail.rsplit("/", 1)[-1].strip()
    return url.rsplit("/", 1)[-1].strip()


def nuke_dir_for_root_worktree(root):
    root = resolve_path(root)
    if not root:
        return ""
    wrapper = resolve_path(str(Path(root).parent))
    repo_name = repo_name_from_remote(root)
    home = resolve_path(str(Path.home()))
    if repo_name and os.path.basename(wrapper) == repo_name and wrapper not in ("", "/", home):
        return wrapper
    return root


def remove_path_prefixes_for_selection(rows):
    prefixes = set()
    for kind, path, meta, target in rows:
        if not path:
            continue
        path_r = resolve_path(path)
        meta_base = (meta or "").split("|", 1)[0]

        if kind == "worktree":
            if meta_base.startswith("wt_root:"):
                root = resolve_path(target) if target else path_r
                if root:
                    prefixes.add(nuke_dir_for_root_worktree(root))
                    for wt in list_worktree_paths(root):
                        prefixes.add(resolve_path(wt))
            else:
                prefixes.add(path_r)
            continue

        if kind == "session":
            if meta_base.startswith("sess_root:"):
                root = path_r
                prefixes.add(nuke_dir_for_root_worktree(root))
                for wt in list_worktree_paths(root):
                    prefixes.add(resolve_path(wt))
            elif meta_base.startswith("sess_wt:"):
                wt = worktree_dir_for_path(path_r) or path_r
                prefixes.add(resolve_path(wt))
            else:
                prefixes.add(path_r)
            continue

        if kind == "dir":
            prefixes.add(path_r)

    return {p for p in prefixes if p}


remove_mode_prefixes = remove_path_prefixes_for_selection(selected_rows) if mode == "remove" else set()


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
            meta_base = (_meta or "").split("|", 1)[0]
            if kind == "session" and target:
                lines.append(f"{now}\tSESSION_TARGET\t{target}\n")
                # Folder-based sessions (no sess_root:/sess_wt: meta) also
                # need a path tombstone — otherwise items_full_rehydrate.py
                # re-emits the row as a `dir` fallback and the entry does
                # not visibly disappear (mirrors alt-x behavior).
                if _path and not meta_base.startswith(("sess_root:", "sess_wt:")):
                    lines.append(f"{now}\tPATH_PREFIX\t{resolve_path(_path)}\n")
            elif kind == "dir" and _path:
                lines.append(f"{now}\tPATH_PREFIX\t{resolve_path(_path)}\n")
    elif mode == "remove":
        for pref in sorted(remove_mode_prefixes):
            lines.append(f"{now}\tPATH_PREFIX\t{pref}\n")

        if remove_mode_prefixes:
            try:
                out = subprocess.run(
                    ["tmux", "list-sessions", "-F", "#{session_name}\t#{session_path}"],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).stdout
            except Exception:
                out = ""
            for row in (out or "").splitlines():
                if not row or "\t" not in row:
                    continue
                name, spath = row.split("\t", 1)
                name = (name or "").strip()
                spath = resolve_path((spath or "").strip())
                if not name or not spath:
                    continue
                if path_under_any_prefix(spath, remove_mode_prefixes):
                    lines.append(f"{now}\tSESSION_TARGET\t{name}\n")
    if not lines:
        return
    try:
        with open(mutation_file, "a", encoding="utf-8") as mf:
            mf.writelines(lines)
    except Exception:
        pass


append_mutation_tombstones()

proc = subprocess.run([items_cmd], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
base_rows = []
for raw in proc.stdout.splitlines():
    if not raw:
        continue
    parts = raw.split("\t")
    if len(parts) < 5:
        base_rows.append(raw)
        continue
    _display, kind, path, _meta, target = parts[:5]
    if (kind, path, target) in selected:
        if mode == "kill" and kind == "worktree":
            pass
        else:
            continue
    base_rows.append(raw)

if mode == "remove" and remove_mode_prefixes:
    pruned_rows = []
    for raw in base_rows:
        parts = raw.split("\t")
        if len(parts) < 5:
            pruned_rows.append(raw)
            continue
        kind, path = parts[1], parts[2]
        rp = resolve_path(path) if path else ""
        if kind in ("session", "worktree", "dir") and rp and path_under_any_prefix(rp, remove_mode_prefixes):
            continue
        pruned_rows.append(raw)
    base_rows = pruned_rows


def scan_roots_from_tmux():
    roots_raw = ""
    if os.environ.get("TMUX"):
        try:
            roots_raw = subprocess.run(
                ["tmux", "show-option", "-gqv", "@pick_session_worktree_scan_roots"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            ).stdout.strip()
        except Exception:
            roots_raw = ""
    if not roots_raw:
        roots_raw = (
            f"{Path.home()}/work,{Path.home()}/code,{Path.home()}/.backport/repositories,{Path.home()}/.local/share"
        )
    roots = []
    for part in roots_raw.split(","):
        part = part.strip()
        if not part:
            continue
        roots.append(resolve_path(part))
    home = resolve_path("~")
    if home and home not in roots:
        roots.append(home)
    return roots


scan_roots = scan_roots_from_tmux()

for line in grouped_output(base_rows, scan_roots, resolve_path):
    print(line)
