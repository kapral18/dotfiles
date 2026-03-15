#!/usr/bin/env python3

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

cache_file = sys.argv[1]

# fzf reload/focus can terminate the producer early; exit quietly on SIGPIPE.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

RESET = "\033[0m"


def color(code, text):
    return f"\033[{code}m{text}{RESET}"


BADGE_STALE = color("2;38;5;214", " \u26a0 stale")
BADGE_GONE = color("2;38;5;196", " \u2717 gone")
BADGE_DIRTY = color("2;38;5;214", " \u2217")

BADGE_PR_OPEN = color("38;5;42", " \uf407")
BADGE_PR_MERGED = color("38;5;141", " \uf407")
BADGE_PR_CLOSED = color("38;5;196", " \uf4dc")
BADGE_ISSUE_OPEN = color("38;5;42", " \uf41b")
BADGE_ISSUE_CLOSED = color("38;5;141", " \uf41d")


def _parse_status_flags(meta: str) -> set:
    for part in (meta or "").split("|"):
        if part.startswith("status="):
            return set(part[7:].split(",")) if part[7:] else set()
    return set()


def _status_badge(flags: set) -> str:
    if "gone" in flags:
        return BADGE_GONE
    if "stale" in flags:
        return BADGE_STALE
    if "dirty" in flags:
        return BADGE_DIRTY
    return ""


def _pr_badge(state: str) -> str:
    s = (state or "").upper()
    if s == "OPEN":
        return BADGE_PR_OPEN
    if s == "MERGED":
        return BADGE_PR_MERGED
    if s == "CLOSED":
        return BADGE_PR_CLOSED
    return ""


def _issue_badge(state: str) -> str:
    s = (state or "").upper()
    if s == "OPEN":
        return BADGE_ISSUE_OPEN
    if s in ("CLOSED", "COMPLETED", "NOT_PLANNED"):
        return BADGE_ISSUE_CLOSED
    return ""


def _gh_badges_from_meta(meta: str) -> str:
    out = ""
    for part in (meta or "").split("|"):
        if part.startswith("pr="):
            fields = part[3:].split(":", 2)
            if len(fields) >= 2:
                out += _pr_badge(fields[1])
        elif part.startswith("issue="):
            fields = part[6:].split(":", 2)
            if len(fields) >= 2:
                out += _issue_badge(fields[1])
    return out


def display_session_entry_with_suffix(name, path_display, suffix=""):
    suffix = suffix or ""
    return f"{color('38;5;42', '')}  {color('1;38;5;81', name)}{suffix}"


def display_worktree_entry(path_display):
    return f"{color('38;5;214', '')}  {color('38;5;221', path_display)}"


def display_dir_entry(path_display):
    return f"{color('38;5;75', '')}  {color('38;5;110', path_display)}"


def tildefy(p: str) -> str:
    home = os.path.expanduser("~")
    if p == home:
        return "~"
    if p.startswith(home + "/"):
        return "~/" + p[len(home) + 1 :]
    return p


def match_key(*parts: str) -> str:
    out = []
    for p in parts:
        p = (p or "").strip()
        if p:
            out.append(p)
    return " ".join(out)


def resolve_path(p):
    try:
        return str(Path(p).resolve())
    except Exception:
        return p


def is_bag_path(p: str) -> bool:
    if not p:
        return False
    s = p.replace("\\", "/")
    return "/.bag/" in s or s.endswith("/.bag")


def tmux_out(args):
    return subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout


def is_git_dir(p: str) -> bool:
    try:
        pp = Path(p)
        return (pp / ".git").exists() or (pp / "HEAD").exists()
    except Exception:
        return False


DEFAULT_BRANCH_DIRS = {"main", "master", "trunk", "develop", "dev"}
DEFAULT_BRANCH_DIRS_ORDER = ("main", "master", "trunk", "develop", "dev")


def normalize_branch_name(br: str) -> str:
    br = (br or "").strip()
    if not br:
        return ""
    if br.lower() in (".invalid", "invalid", "(invalid)"):
        return ""
    return br


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
    for cand in DEFAULT_BRANCH_DIRS_ORDER:
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


def home_rel(p: str) -> str:
    if not p:
        return ""
    try:
        rp = resolve_path(p)
    except Exception:
        rp = p
    home = os.path.expanduser("~")
    if rp == home:
        return ""
    if rp.startswith(home + os.sep):
        rel = rp[len(home) + 1 :]
        return rel.strip("/").replace(os.sep, "/")
    return rp.replace(os.sep, "/").strip("/")


def repo_id_for_root_checkout(root_checkout: str) -> str:
    if not root_checkout:
        return ""
    try:
        rc = Path(root_checkout)
        repo_path = str(rc.parent) if rc.name in DEFAULT_BRANCH_DIRS else str(rc)
        return home_rel(repo_path)
    except Exception:
        return home_rel(root_checkout)


def worktree_branch_for_path(p: str) -> str:
    p = resolve_path(p)
    if not p or not os.path.isdir(p):
        return ""
    try:
        gitp = Path(p) / ".git"
        gitdir = ""
        if gitp.is_dir():
            gitdir = str(gitp)
        elif gitp.is_file():
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if first.startswith("gitdir:"):
                raw = first.split(":", 1)[1].strip()
                gp = (Path(p) / raw) if raw and not os.path.isabs(raw) else Path(raw)
                gitdir = resolve_path(str(gp))
        if not gitdir:
            return ""
        if Path(gitdir).name == ".git" and not has_linked_worktrees(gitdir):
            default_br = default_branch_for_repo(str(Path(gitdir).parent))
            if default_br:
                return default_br
        head = Path(gitdir, "HEAD").read_text(encoding="utf-8", errors="replace").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            if ref.startswith("refs/heads/"):
                return normalize_branch_name(ref[len("refs/heads/") :])
        return ""
    except Exception:
        return ""


def worktree_root_for_path(p: str) -> str:
    p = resolve_path(p)
    if not p or not os.path.isdir(p):
        return ""
    try:
        out = subprocess.run(
            ["git", "-C", p, "rev-parse", "--git-common-dir"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
    except Exception:
        return ""
    if not out:
        return ""
    common = out
    if not common.startswith("/"):
        common = resolve_path(os.path.join(p, common))
    else:
        common = resolve_path(common)
    if os.path.basename(common) == ".git":
        return resolve_path(os.path.dirname(common))
    return common


def load_mutation_tombstones():
    mutation_path = os.environ.get("MUTATIONS_FILE", "").strip()
    ttl_raw = os.environ.get("MUTATION_TTL", "300").strip()
    live_grace_raw = os.environ.get("SESSION_TOMBSTONE_LIVE_GRACE_S", "2").strip()
    try:
        ttl = int(ttl_raw or "300")
    except Exception:
        ttl = 300
    try:
        live_grace = int(live_grace_raw or "2")
    except Exception:
        live_grace = 2
    path_prefixes = set()
    session_targets = set()
    fresh_session_targets = set()
    if not mutation_path or not os.path.exists(mutation_path):
        return path_prefixes, session_targets, fresh_session_targets
    now = int(time.time())
    with open(mutation_path, "r", encoding="utf-8", errors="ignore") as f:
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
            if ttl >= 0 and (now - ts) > ttl:
                continue
            if kind == "PATH_PREFIX":
                path_prefixes.add(value)
            elif kind == "SESSION_TARGET":
                session_targets.add(value)
                if live_grace >= 0 and (now - ts) <= live_grace:
                    fresh_session_targets.add(value)
    return path_prefixes, session_targets, fresh_session_targets


def load_pending_path_prefixes():
    pending_path = os.environ.get("PENDING_FILE", "").strip()
    path_prefixes = set()
    if not pending_path or not os.path.exists(pending_path):
        return path_prefixes
    with open(pending_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            if "\t" in line:
                tag, value = line.split("\t", 1)
                if tag in ("WT", "EX") and value:
                    path_prefixes.add(value)
            else:
                path_prefixes.add(line)
    return path_prefixes


mutation_path_prefixes, mutation_session_targets, fresh_session_targets = load_mutation_tombstones()
pending_path_prefixes = load_pending_path_prefixes()


def path_tombstoned(kind: str, p: str) -> bool:
    if kind not in ("dir", "worktree") or not p:
        return False
    for base in mutation_path_prefixes:
        if p == base or p.startswith(base + "/"):
            return True
    if kind != "session":
        for base in pending_path_prefixes:
            if p == base or p.startswith(base + "/"):
                return True
    return False


current_name = tmux_out(["tmux", "display-message", "-p", "#S"]).strip()
sess_out = tmux_out(["tmux", "list-sessions", "-F", "#{session_name}\t#{session_path}"])
sess_by_rpath = {}
sess_raw_path = {}
live_session_names = set()
for row in sess_out.splitlines():
    if not row:
        continue
    name, _, path = row.partition("\t")
    name, path = name.strip(), path.strip()
    if not name or not path:
        continue
    rpath = resolve_path(path)
    if is_bag_path(rpath):
        continue
    if path_tombstoned("session", rpath) or name in fresh_session_targets:
        continue
    live_session_names.add(name)
    sess_by_rpath[rpath] = name
    sess_raw_path[rpath] = path

printed_sessions = set()
missing_sessions_emitted = False


def emit_missing_sessions():
    global missing_sessions_emitted
    if missing_sessions_emitted:
        return
    missing_sessions_emitted = True
    for rp, name in sorted(sess_by_rpath.items()):
        if name in printed_sessions or rp in printed_sessions:
            continue
        raw = sess_raw_path.get(rp, rp)
        suffix = color("2;38;5;244", " (current)") if name == current_name else ""
        disp = display_session_entry_with_suffix(name, "", suffix)
        print(f"{disp}\tsession\t{rp}\t\t{name}\t{match_key(name)}")
        printed_sessions.add(name)


def parse_cache_row(raw_line: str):
    line = raw_line.rstrip("\n")
    if not line:
        return None
    parts = line.split("\t")
    if len(parts) < 5:
        return None
    return {
        "raw": line,
        "kind": parts[1],
        "path": parts[2],
        "meta": parts[3],
        "target": parts[4],
        "mk": parts[5] if len(parts) > 5 else "",
    }


with open(cache_file, "r", encoding="utf-8", errors="replace") as f:
    for raw in f:
        row = parse_cache_row(raw)
        if not row:
            if raw.strip():
                print(raw.rstrip("\n"))
            continue

        kind, path, target, meta = row["kind"], row["path"], row["target"], row["meta"]
        rpath = resolve_path(path) if path else ""
        if is_bag_path(rpath):
            continue
        if path_tombstoned(kind, rpath):
            continue
        cached_flags = _parse_status_flags(meta)
        badge = _status_badge(cached_flags)
        if kind == "session":
            if target in printed_sessions:
                continue
            if target in fresh_session_targets:
                if rpath:
                    mk = match_key(Path(rpath).name, tildefy(rpath), rpath)
                    if is_git_dir(rpath):
                        root = worktree_root_for_path(rpath) or rpath
                        if root:
                            br = worktree_branch_for_path(rpath)
                            repo_id = repo_id_for_root_checkout(root)
                            meta = f"wt_root:{br}" if br and root == rpath else (f"wt:{br}" if br else "")
                            if repo_id:
                                meta += f"|repo={repo_id}"
                            print(
                                f"{display_worktree_entry(tildefy(rpath))}{badge}\tworktree\t{rpath}\t{meta}\t{root}\t{mk}"
                            )
                    elif os.path.isdir(rpath):
                        print(f"{display_dir_entry(tildefy(rpath))}\tdir\t{rpath}\t\t\t{mk}")
                continue
            if target not in live_session_names:
                if rpath:
                    mk = match_key(Path(rpath).name, tildefy(rpath), rpath)
                    if is_git_dir(rpath):
                        root = worktree_root_for_path(rpath) or rpath
                        if root:
                            br = worktree_branch_for_path(rpath)
                            repo_id = repo_id_for_root_checkout(root)
                            meta = f"wt_root:{br}" if br and root == rpath else (f"wt:{br}" if br else "")
                            if repo_id:
                                meta += f"|repo={repo_id}"
                            print(
                                f"{display_worktree_entry(tildefy(rpath))}{badge}\tworktree\t{rpath}\t{meta}\t{root}\t{mk}"
                            )
                    elif os.path.isdir(rpath):
                        print(f"{display_dir_entry(tildefy(rpath))}\tdir\t{rpath}\t\t\t{mk}")
                continue
            printed_sessions.add(target)
            printed_sessions.add(rpath)
            suffix = color("2;38;5;244", " (current)") if target == current_name else ""
            gh_b = _gh_badges_from_meta(meta)
            mk = match_key(target)
            print(
                f"{display_session_entry_with_suffix(target, '', suffix)}{badge}{gh_b}\tsession\t{path}\t{meta}\t{target}\t{mk}"
            )
            continue

        if rpath in sess_by_rpath:
            continue

        print(row["raw"])

emit_missing_sessions()
