#!/usr/bin/env bash
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
session_tombstone_live_grace_s="${PICK_SESSION_SESSION_TOMBSTONE_LIVE_GRACE_S:-2}"

ansi_wrap() {
  local code="$1"
  local text="$2"
  printf '\033[%sm%s\033[0m' "$code" "$text"
}

display_session_entry() {
  local name="$1"
  local path_display="$2"
  printf '%s  %s  %s' \
    "$(ansi_wrap '38;5;42' '')" \
    "$(ansi_wrap '1;38;5;81' "$name")" \
    "$(ansi_wrap '2;38;5;246' "$path_display")"
}

display_dir_entry() {
  local path_display="$1"
  printf '%s  %s' "$(ansi_wrap '38;5;75' '')" "$(ansi_wrap '38;5;110' "$path_display")"
}

wait_ms="${PICK_SESSION_CACHE_WAIT_MS:-0}"
mutation_ttl="${PICK_SESSION_MUTATION_TOMBSTONE_TTL:-300}"
if [ -n "${TMUX:-}" ]; then
  wait_ms="$(tmux show-option -gqv '@pick_session_cache_wait_ms' 2>/dev/null || printf '%s' "$wait_ms")"
  mutation_ttl="$(tmux show-option -gqv '@pick_session_mutation_tombstone_ttl' 2>/dev/null || printf '%s' "$mutation_ttl")"
  session_tombstone_live_grace_s="$(tmux show-option -gqv '@pick_session_session_tombstone_live_grace_s' 2>/dev/null || printf '%s' "$session_tombstone_live_grace_s")"
fi
case "$wait_ms" in
'' | *[!0-9]*) wait_ms=0 ;;
esac
case "$mutation_ttl" in
'' | *[!0-9]*) mutation_ttl=300 ;;
esac
case "$session_tombstone_live_grace_s" in
'' | *[!0-9]*) session_tombstone_live_grace_s=2 ;;
esac

if [ -f "$cache_file" ]; then
  # Keep the UI correct even if the cache is slightly stale:
  # - Don't show the current session's path as a worktree/dir entry
  # - If a cached worktree/dir now has a session, show it as a session
  # - Preserve cached ordering/grouping whenever possible
  if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ] && command -v python3 >/dev/null 2>&1; then
    scan_roots_raw="$(tmux show-option -gqv '@pick_session_worktree_scan_roots' 2>/dev/null || printf '%s' "$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share")"
    MUTATIONS_FILE="$mutation_file" MUTATION_TTL="$mutation_ttl" SESSION_TOMBSTONE_LIVE_GRACE_S="$session_tombstone_live_grace_s" PICK_SESSION_SCAN_ROOTS="$scan_roots_raw" python3 -u - "$cache_file" <<'PY'
import os
import re
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

def display_session_entry(name, path_display):
    return f"{color('38;5;42', '')}  {color('1;38;5;81', name)}  {color('2;38;5;246', path_display)}"

def display_session_entry_with_suffix(name, path_display, suffix=""):
    suffix = suffix or ""
    return f"{color('38;5;42', '')}  {color('1;38;5;81', name)}{suffix}  {color('2;38;5;246', path_display)}"

def display_worktree_entry(path_display):
    return f"{color('38;5;214', '')}  {color('38;5;221', path_display)}"

def display_dir_entry(path_display):
    return f"{color('38;5;75', '')}  {color('38;5;110', path_display)}"

def resolve_path(p: str) -> str:
    try:
        return str(Path(p).resolve())
    except Exception:
        return p

def expand_root(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    if p == "~":
        return os.path.expanduser("~")
    if p.startswith("~/"):
        return os.path.join(os.path.expanduser("~"), p[2:])
    return p

scan_roots_raw = os.environ.get("PICK_SESSION_SCAN_ROOTS", "").strip()
scan_roots = [ expand_root(x) for x in scan_roots_raw.split(",") if x.strip() ] if scan_roots_raw else []
scan_roots = [ resolve_path(r) for r in scan_roots if r and Path(r).is_dir() ]
scan_roots_set = set(scan_roots)

def find_worktree_root_for_path(p: str) -> str:
    cur = Path(p)
    if cur.is_file():
        cur = cur.parent
    try:
        cur = cur.resolve()
    except Exception:
        cur = Path(p)
    for _ in range(12):
        if (cur / ".git").exists():
            return resolve_path(str(cur))
        if cur.parent == cur:
            break
        cur = cur.parent
    return ""

def worktree_group_root_for_path(p: str) -> str:
    wt = find_worktree_root_for_path(p)
    if not wt:
        return ""
    gitp = Path(wt) / ".git"
    # Wrapper layout (``,w``): checkouts are stored under `<wrapper>/<branch...>`,
    # and the "root" checkout lives under `<wrapper>/<default-branch>`.
    def wrapper_root_checkout_for_path(repo_root: str) -> str:
        cur = Path(repo_root)
        try:
            cur = cur.resolve()
        except Exception:
            cur = Path(repo_root)
        for _ in range(10):
            wrapper = cur
            w = resolve_path(str(wrapper))
            if w and w not in scan_roots_set:
                for d in DEFAULT_BRANCH_DIRS_ORDER:
                    root_checkout = wrapper / d
                    if root_checkout.is_dir() and (root_checkout / ".git").exists():
                        return resolve_path(str(root_checkout))
            if wrapper.parent == wrapper:
                break
            cur = wrapper.parent
        return ""
    try:
        if gitp.is_dir():
            wr = wrapper_root_checkout_for_path(wt)
            return wr if wr else wt
        if gitp.is_file():
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if not first.startswith("gitdir:"):
                return wt
            raw = first.split(":", 1)[1].strip()
            gitdir = Path(raw) if os.path.isabs(raw) else (Path(wt) / raw)
            gitdir = Path(resolve_path(str(gitdir)))
            norm = str(gitdir).replace("\\", "/")
            if "/worktrees/" in norm:
                common_dir = Path(resolve_path(str(gitdir.parent.parent)))
                if common_dir.name == ".git":
                    return resolve_path(str(common_dir.parent))
                return resolve_path(str(common_dir))
    except Exception:
        return wt
    return wt

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

def head_branch_for_worktree_root(root: str) -> str:
    gitp = Path(root) / ".git"
    gitdir = None
    try:
        if gitp.is_dir():
            gitdir = gitp
        elif gitp.is_file():
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if first.startswith("gitdir:"):
                raw = first.split(":", 1)[1].strip()
                gitdir = Path(raw) if os.path.isabs(raw) else (Path(root) / raw)
    except Exception:
        gitdir = None
    if gitdir is None:
        return ""
    try:
        head = Path(gitdir).resolve().joinpath("HEAD").read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        if ref.startswith("refs/heads/"):
            return ref[len("refs/heads/") :]
    return ""

def tmux_sanitize_session_name(s: str) -> str:
    """
    Make a tmux-safe session name that matches tmux's normalization behavior
    (notably '.' -> '_'), while preserving common branch separators like '/'.
    """
    s = (s or "").strip().lower()
    if not s:
        return ""
    s = re.sub(r"[^a-z0-9_@|/~-]+", "_", s)
    s = re.sub(r"[.:]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def git_config_path_for_root(root: str):
    """
    Return the git config path for a repo root.
    - non-bare repo: <root>/.git/config
    - bare repo: <root>/config
    """
    cfg = Path(root) / ".git" / "config"
    if cfg.exists():
        return cfg
    cfg = Path(root) / "config"
    if cfg.exists():
        return cfg
    return None

def remote_url_for_root(root: str, remote: str) -> str:
    cfg = git_config_path_for_root(root)
    if cfg is None:
        return ""
    remote = (remote or "").strip()
    if not remote:
        return ""
    in_remote = False
    try:
        for raw in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                in_remote = (line.lower() == f'[remote "{remote.lower()}"]')
                continue
            if not in_remote:
                continue
            m = re.match(r"^url\\s*=\\s*(.+)$", line, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
    except Exception:
        return ""
    return ""

def origin_url_for_root(root: str) -> str:
    url = remote_url_for_root(root, "origin")
    if url:
        return url
    return remote_url_for_root(root, "upstream")

def repo_name_from_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    tail = url.split("/")[-1]
    tail = tail.split(":")[-1]
    if tail.endswith(".git"):
        tail = tail[: -len(".git")]
    return tail.strip()

DEFAULT_BRANCH_DIRS = { "main", "master", "trunk", "develop", "dev" }
DEFAULT_BRANCH_DIRS_ORDER = ("main", "master", "trunk", "develop", "dev")

def repo_display_for_root(root: str) -> str:
    repo = repo_name_from_url(origin_url_for_root(root))
    if repo:
        return repo
    try:
        base = Path(root).name
    except Exception:
        base = (root or "").rstrip("/").split("/")[-1]
    if base in DEFAULT_BRANCH_DIRS:
        try:
            return Path(root).parent.name or base
        except Exception:
            return base
    return base

def tmux_out(args):
    return subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout

def remote_names_for_root(root: str) -> set[str]:
    cfg = git_config_path_for_root(root)
    if cfg is None:
        return set()
    remotes: set[str] = set()
    try:
        for raw in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.lower().startswith("[remote ") and line.endswith("]") and '"' in line:
                try:
                    name = line.split('"', 2)[1].strip()
                except Exception:
                    name = ""
                if name:
                    remotes.add(name)
    except Exception:
        return remotes
    return remotes

def branch_from_wrapper_path(root: str, wt_path: str, remotes: set[str]) -> str:
    try:
        wrapper = str(Path(root).parent)
    except Exception:
        return ""
    if not wrapper:
        return ""
    w = resolve_path(wrapper)
    p = resolve_path(wt_path)
    if not (p == w or p.startswith(w + os.sep)):
        return ""
    rel = os.path.relpath(p, w)
    rel = rel.replace(os.sep, "/").strip("./")
    if not rel or rel == ".":
        return ""
    if "/" in rel:
        first, rest = rel.split("/", 1)
        if first in remotes and first not in ("origin", "upstream") and rest:
            return f"{first}__{rest}"
    return rel

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

mutation_path_prefixes, mutation_session_targets, fresh_session_targets = load_mutation_tombstones()

def path_tombstoned(kind: str, p: str) -> bool:
    if kind not in ("dir", "worktree", "session"):
        return False
    if not p:
        return False
    for base in mutation_path_prefixes:
        if p == base or p.startswith(base + "/"):
            return True
    return False

def session_tombstoned(name: str) -> bool:
    return bool(name and name in mutation_session_targets)

current_name = tmux_out([ "tmux", "display-message", "-p", "#S" ]).strip()
current_path = tmux_out([ "tmux", "display-message", "-p", "#{session_path}" ]).strip()
current_rp = resolve_path(current_path) if current_path else ""
current_wt_root = find_worktree_root_for_path(current_rp) if current_rp else ""

sess_out = tmux_out([ "tmux", "list-sessions", "-F", "#{session_name}\t#{session_path}" ])
sess_by_rpath = {}  # rpath -> name (also keyed by worktree root when detected)
live_session_names = set()
for row in sess_out.splitlines():
    if not row:
        continue
    name, _, path = row.partition("\t")
    name = name.strip()
    path = path.strip()
    if not name:
        continue
    rp = resolve_path(path) if path else ""
    if not rp:
        continue
    if path_tombstoned("session", rp):
        continue
    if name in fresh_session_targets:
        continue
    live_session_names.add(name)
    sess_by_rpath[rp] = name
    wt_root = find_worktree_root_for_path(rp)
    if wt_root:
        sess_by_rpath.setdefault(wt_root, name)

printed_sessions = set()
missing_sessions_emitted = False

# Track known worktree roots from the cache so we don't promote nested git
# directories (submodules/nested repos) to top-level worktree entries.
known_worktree_roots: list[str] = []
known_worktree_roots_set: set[str] = set()

def record_worktree_root(p: str):
    rp = resolve_path(p) if p else ""
    if not rp or rp in known_worktree_roots_set:
        return
    known_worktree_roots_set.add(rp)
    known_worktree_roots.append(rp)

def under_known_worktree(p: str) -> bool:
    if not p:
        return False
    for base in known_worktree_roots:
        if p == base or p.startswith(base + os.sep):
            return True
    return False

def emit_missing_sessions():
    global missing_sessions_emitted
    if missing_sessions_emitted:
        return
    missing_sessions_emitted = True
    # Sessions not represented by cache lines should appear in the "sessions"
    # section (before directories), otherwise they look stuck at the bottom
    # until the next reindex.
    for rp, name in sorted(sess_by_rpath.items(), key=lambda x: x[1]):
        if name in printed_sessions or rp in printed_sessions:
            continue
        if path_tombstoned("session", rp):
            continue
        root = worktree_group_root_for_path(rp) if rp else ""
        branch = ""
        is_root = False
        try:
            is_root = bool(root and resolve_path(rp) == resolve_path(root))
        except Exception:
            is_root = False
        if root:
            try:
                if is_root:
                    branch = Path(root).name
                else:
                    remotes = remote_names_for_root(root)
                    branch = branch_from_wrapper_path(root, rp, remotes)
            except Exception:
                branch = ""
        if root and branch:
            rec = { "rpath": rp, "group_root": root, "branch": branch, "is_root": is_root }
            print(synthesize_worktree_session_row(rec, name))
            printed_sessions.add(name)
            printed_sessions.add(rp)
            continue

        suffix = color("2;38;5;244", " (current)") if name == current_name else ""
        disp = display_session_entry_with_suffix(name, tildefy(rp), suffix)
        mk = match_key_for_session(name, rp, "")
        print(f"{disp}\tsession\t{rp}\t\t{name}\t{mk}")
        printed_sessions.add(name)
        printed_sessions.add(rp)
def parse_worktree_meta(meta: str):
    if meta.startswith("wt_root:"):
        return (meta[len("wt_root:") :], True)
    if meta.startswith("wt:"):
        return (meta[len("wt:") :], False)
    return ("", False)

def parse_session_worktree_meta(meta: str):
    meta_base = meta.split("|", 1)[0]
    if meta_base.startswith("sess_root:"):
        return (meta_base[len("sess_root:") :], True)
    if meta_base.startswith("sess_wt:"):
        return (meta_base[len("sess_wt:") :], False)
    return (None, None)

def match_key_for_dir(rpath: str) -> str:
    try:
        base = Path(rpath).name if rpath else ""
    except Exception:
        base = ""
    return match_key(base, tildefy(rpath), rpath)

def match_key_for_worktree(rpath: str, meta: str, target: str) -> str:
    branch, _is_root = parse_worktree_meta(meta or "")
    root = (target or "").strip()
    repo = repo_display_for_root(root) if root else ""
    wt_name_raw = f"{repo}|{branch}" if (repo and branch) else repo
    wt_name = tmux_sanitize_session_name(wt_name_raw) if wt_name_raw else ""
    try:
        base = Path(rpath).name if rpath else ""
    except Exception:
        base = ""
    return match_key(wt_name_raw, wt_name, base, tildefy(rpath), rpath)

def match_key_for_session(target: str, rpath: str, meta: str) -> str:
    target = (target or "").strip()
    expected = ""
    if meta and "|expected=" in meta:
        expected = meta.split("|expected=", 1)[1].strip()

    branch, is_root = parse_session_worktree_meta(meta or "")
    root = ""
    if is_root is True and rpath:
        root = rpath
    elif is_root is False and rpath:
        root = worktree_group_root_for_path(rpath)
    repo = repo_display_for_root(root) if root else ""
    wt_name_raw = f"{repo}|{branch}" if (repo and branch) else (expected if expected else "")
    wt_name = tmux_sanitize_session_name(wt_name_raw) if wt_name_raw else ""

    try:
        base = Path(rpath).name if rpath else ""
    except Exception:
        base = ""
    return match_key(target, expected, wt_name_raw, wt_name, base, tildefy(rpath), rpath)

def wrapper_expected_for_session_path(rpath: str):
    """
    For wrapper layouts created by `,w` (e.g. `<wrapper>/<default-branch>` plus
    siblings under `<wrapper>/<branch...>`), derive the canonical session name
    from the path, independent of the currently checked-out git branch.
    Returns (expected, branch, is_root) or ("", "", False) when not a wrapper.
    """
    if not rpath:
        return ("", "", False)
    root = worktree_group_root_for_path(rpath)
    if not root:
        return ("", "", False)
    try:
        # Only treat it as a wrapper when the group root checkout looks like a
        # default-branch checkout (`.../main`, `.../master`, etc).
        if Path(root).name not in DEFAULT_BRANCH_DIRS:
            return ("", "", False)
    except Exception:
        return ("", "", False)

    try:
        is_root = resolve_path(root) == resolve_path(rpath)
    except Exception:
        is_root = False

    branch = ""
    try:
        if is_root:
            branch = Path(root).name
        else:
            branch = branch_from_wrapper_path(root, rpath, remote_names_for_root(root))
    except Exception:
        branch = ""
    if not branch:
        return ("", "", False)
    expected_raw = f"{repo_display_for_root(root)}|{branch}"
    expected = tmux_sanitize_session_name(expected_raw)
    return (expected, branch, is_root)

def synthesize_worktree_session_row(rec, live_name: str):
    rpath = rec["rpath"]
    branch = rec.get("branch") or ""
    root = rec.get("group_root") or ""
    is_root = bool(rec.get("is_root"))

    # Re-derive wrapper layout naming from the path so stale cache metadata
    # cannot regress the displayed label.
    exp, br, br_is_root = wrapper_expected_for_session_path(rpath)
    if exp and br:
        root = worktree_group_root_for_path(rpath)
        branch = br
        is_root = br_is_root
    expected = ""
    if branch and root:
        expected_raw = f"{repo_display_for_root(root)}|{branch}"
        expected = tmux_sanitize_session_name(expected_raw)
    label = live_name
    if expected and live_name and live_name != expected and not live_name.startswith(expected + "@"):
        label = expected
    meta_base = f"sess_root:{branch}" if is_root else f"sess_wt:{branch}"
    meta = meta_base
    if expected and live_name and live_name != expected:
        meta = f"{meta_base}|expected={expected}"
    suffix = color("2;38;5;244", " (current)") if live_name == current_name else ""
    mk = match_key_for_session(live_name, rpath, meta)
    return f"{display_session_entry_with_suffix(label, tildefy(rpath), suffix)}\tsession\t{rpath}\t{meta}\t{live_name}\t{mk}"

def cache_session_row_label(row):
    return row["target"]

def output_session_row(line: str, rpath: str, meta: str, target: str):
    # Ignore stale cached `|expected=...` when a wrapper-derived canonical name
    # can be computed from the path. This prevents regressions like displaying
    # `ecs|1_8` for sessions that are already named `kibana|fix/...`.
    wexp, wbranch, wis_root = wrapper_expected_for_session_path(rpath)
    if wexp and wbranch:
        meta_base = f"sess_root:{wbranch}" if wis_root else f"sess_wt:{wbranch}"
        if target and (target == wexp or target.startswith(wexp + "@")):
            meta = meta_base
            label = target
        else:
            meta = f"{meta_base}|expected={wexp}"
            label = wexp
    else:
        label = target
        if meta and "|expected=" in meta:
            exp = meta.split("|expected=", 1)[1].strip()
            if exp and target and (target != exp) and (not target.startswith(exp + "@")):
                label = exp
    if target:
        printed_sessions.add(target)
    if rpath:
        printed_sessions.add(rpath)
    if label and rpath:
        suffix = color("2;38;5;244", " (current)") if target == current_name else ""
        mk = match_key_for_session(target, rpath, meta)
        print(f"{display_session_entry_with_suffix(label, tildefy(rpath), suffix)}\tsession\t{rpath}\t{meta}\t{target}\t{mk}")
    else:
        print(line)

def output_dir_or_promoted_dir(row):
    rpath = row["rpath"]
    if rpath and rpath in sess_by_rpath:
        # Don't keep "promoted" sessions anchored in the directory section;
        # they get emitted in the session section (before directories).
        return

    # Promote a cached directory row to a worktree row when the directory is a
    # git worktree root. This keeps kind-based hoisting correct immediately
    # (dir -> worktree) without waiting for a background re-index.
    try:
        if rpath and (not under_known_worktree(rpath)) and (Path(rpath) / ".git").exists():
            root = worktree_group_root_for_path(rpath) if rpath else ""
            root = root or rpath
            is_root = False
            try:
                is_root = bool(root and resolve_path(rpath) == resolve_path(root))
            except Exception:
                is_root = False

            br = ""
            try:
                if is_root:
                    br = Path(root).name if root else ""
                else:
                    remotes = remote_names_for_root(root) if root else set()
                    br = branch_from_wrapper_path(root, rpath, remotes) if root else ""
                    if not br:
                        br = head_branch_for_worktree_root(rpath)
            except Exception:
                br = head_branch_for_worktree_root(rpath)

            meta = f"wt_root:{br}" if (br and is_root) else (f"wt:{br}" if br else "")
            mk = match_key_for_worktree(rpath, meta, root)
            print(f"{display_worktree_entry(tildefy(rpath))}\tworktree\t{row['path']}\t{meta}\t{root}\t{mk}")
            return
    except Exception:
        pass
    mk = match_key_for_dir(rpath)
    print(f"{display_dir_entry(tildefy(rpath))}\tdir\t{row['path']}\t{row['meta']}\t{row['target']}\t{mk}")

def group_row_info(row):
    kind = row["kind"]
    rpath = row["rpath"]
    meta = row["meta"]
    target = row["target"]
    if kind == "worktree":
        branch, is_root = parse_worktree_meta(meta)
        root = target or ""
        if not root:
            return None
        return { "group_root": root, "branch": branch, "is_root": is_root }
    if kind == "session":
        # Don't trust cached `sess_root:*` metadata blindly: quick-only cache
        # updates may refresh sessions without refreshing worktree rows, and
        # older caches may have stale worktree classification. Re-derive wrapper
        # layout info from the session path so labels and grouping update
        # immediately.
        if rpath:
            root = worktree_group_root_for_path(rpath)
            if root and root != rpath:
                remotes = remote_names_for_root(root)
                derived = branch_from_wrapper_path(root, rpath, remotes)
                if derived:
                    return { "group_root": root, "branch": derived, "is_root": False }

        branch, is_root = parse_session_worktree_meta(meta)
        if branch is None:
            return None
        root = rpath if is_root else worktree_group_root_for_path(rpath)
        if not root:
            return None
        return { "group_root": root, "branch": branch or "", "is_root": bool(is_root) }
    return None

def flush_group(rows):
    if not rows:
        return
    grouped = {}
    group_root = rows[0]["group_root"]
    for row in rows:
        path = row["rpath"]
        if not path:
            continue
        rec = grouped.setdefault(path, {
            "rpath": path,
            "group_root": row["group_root"],
            "branch": row.get("branch", ""),
            "is_root": row.get("is_root", False),
            "worktree_row": None,
            "session_row": None,
        })
        if row["kind"] == "worktree":
            rec["worktree_row"] = row
            rec["branch"] = row.get("branch", rec["branch"])
            rec["is_root"] = row.get("is_root", rec["is_root"])
        elif row["kind"] == "session":
            rec["session_row"] = row
            if row.get("branch") is not None:
                rec["branch"] = row.get("branch", rec["branch"])
            rec["is_root"] = row.get("is_root", rec["is_root"])

    def wt_sort_key(item):
        path, rec = item
        br = rec.get("branch", "") or ""
        return (0 if path == group_root or rec.get("is_root") else 1, br, path)

    emitted_paths = set()
    # Sessions first in group (live promotions + existing cached session rows).
    for path, rec in sorted(grouped.items(), key=wt_sort_key):
        live_name = sess_by_rpath.get(path, "")
        if live_name:
            # If the session is already listed elsewhere (for example because a
            # quick-only cache refresh moved sessions to the top), don't emit a
            # duplicate session row here; keep the worktree row.
            if live_name in printed_sessions:
                continue
            print(synthesize_worktree_session_row(rec, live_name))
            printed_sessions.add(live_name)
            printed_sessions.add(path)
            emitted_paths.add(path)
            continue

        row = rec.get("session_row")
        if not row:
            continue
        target = row.get("target", "")
        if target and target in printed_sessions:
            continue
        # If the cache still contains a session row for a session that no
        # longer exists, treat it as stale so the worktree row can take over.
        if target and target not in live_session_names:
            continue
        if session_tombstoned(target) and target not in live_session_names:
            continue
        # As above: render canonical wrapper names even if the cache has stale
        # `|expected=...` metadata.
        label = cache_session_row_label(row)
        rmeta = row.get("meta", "")
        wexp, wbranch, wis_root = wrapper_expected_for_session_path(path)
        if wexp and wbranch:
            meta_base = f"sess_root:{wbranch}" if wis_root else f"sess_wt:{wbranch}"
            if target and (target == wexp or target.startswith(wexp + "@")):
                rmeta = meta_base
                label = target
            else:
                rmeta = f"{meta_base}|expected={wexp}"
                label = wexp
        suffix = color("2;38;5;244", " (current)") if target == current_name else ""
        mk = match_key_for_session(target, path, rmeta)
        print(f"{display_session_entry_with_suffix(label, tildefy(path), suffix)}\tsession\t{row['path']}\t{rmeta}\t{target}\t{mk}")
        if target:
            printed_sessions.add(target)
        printed_sessions.add(path)
        emitted_paths.add(path)

    # Then remaining worktrees.
    for path, rec in sorted(grouped.items(), key=wt_sort_key):
        if path in emitted_paths:
            continue
        row = rec.get("worktree_row")
        if not row:
            continue
        mk = match_key_for_worktree(path, row.get("meta", ""), row.get("target", ""))
        print(f"{display_worktree_entry(tildefy(path))}\tworktree\t{row['path']}\t{row['meta']}\t{row['target']}\t{mk}")

def parse_cache_row(raw_line: str):
    line = raw_line.rstrip("\n")
    if not line:
        return None
    parts = line.split("\t")
    if len(parts) < 5:
        return { "raw": line, "parts": parts, "kind": "", "path": "", "meta": "", "target": "", "rpath": "", "match_key": "" }
    _display, kind, path, meta, target = parts[:5]
    mk = parts[5] if len(parts) >= 6 else ""
    rpath = path if path else ""
    row = {
        "raw": line,
        "kind": kind,
        "path": path,
        "meta": meta,
        "target": target,
        "rpath": rpath,
        "match_key": mk,
    }
    info = group_row_info(row)
    if info:
        row.update(info)
    return row

current_group_rows = []
current_group_root = ""

def flush_current_group():
    global current_group_rows, current_group_root
    if current_group_rows:
        flush_group(current_group_rows)
        current_group_rows = []
        current_group_root = ""

with open(cache_file, "r", encoding="utf-8", errors="replace") as f:
    for raw in f:
        row = parse_cache_row(raw)
        if row is None:
            continue

        if len(row.get("parts", [])) and row.get("kind", "") == "":
            flush_current_group()
            print(row["raw"])
            continue

        kind = row["kind"]
        rpath = row["rpath"]
        meta = row["meta"]
        target = row["target"]

        if kind == "worktree" and rpath:
            record_worktree_root(rpath)

        if path_tombstoned(kind, rpath):
            continue
        if kind == "session" and session_tombstoned(target) and target not in live_session_names:
            continue
        if kind == "session" and target and target not in live_session_names:
            continue

        # Never show the current session path (or its worktree root) as a
        # directory/worktree candidate.
        if kind in ("dir", "worktree"):
            if current_rp and rpath == current_rp:
                continue
            if current_wt_root and rpath == current_wt_root:
                continue

        group_root = row.get("group_root", "")
        if group_root and kind in ("worktree", "session"):
            if current_group_root and group_root != current_group_root:
                flush_current_group()
            current_group_root = group_root
            current_group_rows.append(row)
            continue

        flush_current_group()

        if kind == "session":
            output_session_row(row["raw"], rpath, meta, target)
            continue

        if kind == "dir" and not missing_sessions_emitted:
            emit_missing_sessions()

        if kind == "dir" and rpath:
            output_dir_or_promoted_dir(row)
            continue

        if kind == "worktree" and rpath:
            mk = row.get("match_key") or match_key_for_worktree(rpath, meta, target)
            print(f"{display_worktree_entry(tildefy(rpath))}\t{kind}\t{row['path']}\t{meta}\t{target}\t{mk}")
            continue

        if kind == "dir" and rpath:
            mk = row.get("match_key") or match_key_for_dir(rpath)
            print(f"{display_dir_entry(tildefy(rpath))}\t{kind}\t{row['path']}\t{meta}\t{target}\t{mk}")
            continue

        print(row["raw"])

flush_current_group()

# Ensure any sessions not represented by cache lines are visible.
emit_missing_sessions()
PY
    exit 0
  fi

  # If python isn't available, still emit a 6th "match key" field so fzf can
  # prioritize name matching before paths.
  awk -F $'\t' '
	    BEGIN { OFS = "\t" }
	    NF < 5 { print; next }
	    NF >= 6 { print; next }
	    {
      kind = $2
      path = $3
      meta = $4
      target = $5
      base = path
      sub(".*/", "", base)
      mk = ""
      if (kind == "session") {
        mk = target " " base " " path
      } else if (kind == "worktree") {
        mk = base " " path
      } else if (kind == "dir") {
        mk = base " " path
	      } else {
	        mk = base " " path
	      }
	      print $1, kind, path, meta, target, mk
	    }
	  ' "$cache_file"
  exit 0
fi

# Kick off a background refresh if we're inside tmux.
if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux run-shell -b "$HOME/.config/tmux/scripts/pick_session_index_update.sh --quiet --quick-only" 2>/dev/null || true
fi

# Give the background updater a moment to produce the cache on first run.
elapsed=0
while [ "$elapsed" -lt "$wait_ms" ]; do
  if [ -f "$cache_file" ]; then
    cat "$cache_file"
    exit 0
  fi
  sleep 0.03
  elapsed="$((elapsed + 30))"
done

# Fallback: show tmux sessions (fast) + home.
if command -v tmux >/dev/null 2>&1; then
  cur="$(tmux display-message -p '#S' 2>/dev/null || true)"
  tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null | while IFS=$'\t' read -r name path; do
    [ -n "$name" ] || continue
    [ "$name" = "$cur" ] && continue
    tpath="$path"
    # shellcheck disable=SC2088
    case "$path" in
    "$HOME") tpath="~" ;;
    "$HOME"/*) tpath="~/${path#"$HOME"/}" ;;
    esac
    # shellcheck disable=SC2088
    base="$(basename "$path" 2>/dev/null || printf '%s' "$path")"
    mk="${name} ${base} ${tpath} ${path}"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(display_session_entry "$name" "$tpath")" "session" "$path" "" "$name" "$mk"
  done
fi

mk="home ~ $HOME"
printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(display_dir_entry '~')" "dir" "$HOME" "" "" "$mk"
