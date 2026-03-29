#!/usr/bin/env python3

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

signal.signal(signal.SIGPIPE, signal.SIG_DFL)
cache_file = sys.argv[1]
mutations_file = os.environ.get("MUTATIONS_FILE", "")
pending_file = os.environ.get("PENDING_FILE", "")
mutation_ttl = int(os.environ.get("MUTATION_TTL", "300") or "300")
live_grace = int(os.environ.get("SESSION_TOMBSTONE_LIVE_GRACE_S", "2") or "2")

path_prefixes = set()
session_targets = set()
fresh_session_targets = set()
if mutations_file and os.path.exists(mutations_file):
    now = int(time.time())
    with open(mutations_file, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            ts_s, kind, value = parts
            if not value:
                continue
            try:
                ts = int(ts_s)
            except Exception:
                continue
            if mutation_ttl >= 0 and (now - ts) > mutation_ttl:
                continue
            if kind == "PATH_PREFIX":
                path_prefixes.add(value)
            elif kind == "SESSION_TARGET":
                session_targets.add(value)
                if live_grace >= 0 and (now - ts) <= live_grace:
                    fresh_session_targets.add(value)

live_session_names = set()
try:
    out = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout
    for row in (out or "").splitlines():
        if row.strip():
            live_session_names.add(row.strip())
except Exception:
    pass


def resolve_path(p):
    try:
        return str(Path(p).resolve())
    except Exception:
        return p


def normalize_branch_name(br: str) -> str:
    br = (br or "").strip()
    if not br:
        return ""
    if br.lower() in (".invalid", "invalid", "(invalid)"):
        return ""
    return br


def gitdir_for_path(p: str) -> str:
    try:
        cur = Path(p)
        if cur.is_file():
            cur = cur.parent
        gitp = cur / ".git"
        if gitp.is_dir():
            return str(gitp)
        if gitp.is_file():
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if not first.startswith("gitdir:"):
                return ""
            raw = first.split(":", 1)[1].strip()
            gitdir = (cur / raw) if raw and not os.path.isabs(raw) else Path(raw)
            try:
                return str(gitdir.resolve())
            except Exception:
                return str(gitdir)
    except Exception:
        return ""
    return ""


def head_branch(gitdir: str) -> str:
    if not gitdir:
        return ""
    try:
        head = Path(gitdir, "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        if ref.startswith("refs/heads/"):
            return normalize_branch_name(ref[len("refs/heads/") :])
    return ""


def has_linked_worktrees(gitdir: str) -> bool:
    try:
        wt_dir = Path(gitdir) / "worktrees"
        if not wt_dir.is_dir():
            return False
        return any(True for _ in wt_dir.iterdir())
    except Exception:
        return False


def default_branch_for_repo(repo_root: str) -> str:
    repo_root = resolve_path(repo_root)
    if not repo_root:
        return ""
    try:
        import subprocess
    except Exception:
        return ""
    for remote in ("origin", "upstream"):
        try:
            out = subprocess.run(
                ["git", "-C", repo_root, "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            ).stdout.strip()
        except Exception:
            out = ""
        if out:
            if out.startswith(remote + "/"):
                out = out[len(remote) + 1 :]
            else:
                out = out.split("/", 1)[-1]
            out = normalize_branch_name(out)
            if out:
                return out
    for cand in ("main", "master", "trunk", "develop", "dev"):
        for ref in (f"refs/heads/{cand}", f"refs/remotes/origin/{cand}", f"refs/remotes/upstream/{cand}"):
            try:
                rc = subprocess.run(
                    ["git", "-C", repo_root, "show-ref", "--verify", "--quiet", ref],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
            except Exception:
                rc = 1
            if rc == 0:
                return cand
    return "main"


def worktree_meta_for_path(p: str) -> str:
    gd = gitdir_for_path(p)
    br = head_branch(gd)
    if gd and Path(gd).name == ".git" and not has_linked_worktrees(gd):
        default_br = default_branch_for_repo(str(Path(gd).parent))
        if default_br:
            br = default_br
    return f"wt_root:{br}" if br else ""


if pending_file and os.path.exists(pending_file):
    # Pending removals should not hide *live sessions*.
    # This light path only runs when the cache has sessions only, so pending
    # worktree suppression is not relevant here.
    pass


def path_tombstoned(kind, p):
    if kind not in ("dir", "worktree", "session") or not p:
        return False
    for base in path_prefixes:
        if p == base or p.startswith(base + "/"):
            return True
    return False


def session_tombstoned(name):
    return bool(name and name in session_targets)


with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            print(line)
            continue
        kind, path, target = parts[1], parts[2], parts[4] if len(parts) > 4 else ""
        rpath = resolve_path(path) if path else ""
        if path_tombstoned(kind, rpath):
            continue
        if kind == "session" and session_tombstoned(target) and target not in live_session_names:
            # Keep the path selectable even when the session is killed/hidden.
            if rpath:
                base = os.path.basename(rpath.rstrip("/")) or rpath
                meta = worktree_meta_for_path(rpath)
                br = meta.split(":", 1)[1] if ":" in meta else ""
                mk = f"{base}|{br} {base} {rpath}" if br else f"{base} {rpath}"
                # Prefer a "worktree-like" entry when it's a git checkout.
                if os.path.exists(os.path.join(rpath, ".git")):
                    print(f"  {rpath}\tworktree\t{rpath}\t{meta}\t{rpath}\t{mk}")
                else:
                    print(f"  {rpath}\tdir\t{rpath}\t\t\t{mk}")
            continue
        if kind == "session" and target in fresh_session_targets:
            # Optimistic hide for recently-killed sessions should still keep the
            # underlying path selectable.
            if rpath:
                base = os.path.basename(rpath.rstrip("/")) or rpath
                meta = worktree_meta_for_path(rpath)
                br = meta.split(":", 1)[1] if ":" in meta else ""
                mk = f"{base}|{br} {base} {rpath}" if br else f"{base} {rpath}"
                if os.path.exists(os.path.join(rpath, ".git")):
                    print(f"  {rpath}\tworktree\t{rpath}\t{meta}\t{rpath}\t{mk}")
                else:
                    print(f"  {rpath}\tdir\t{rpath}\t\t\t{mk}")
            continue
        print(line)
