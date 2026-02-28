#!/usr/bin/env bash
set -euo pipefail

need_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1
}

tmux_opt() {
  local key="$1"
  local default_value="$2"
  local value=""
  value="$(tmux show-option -gqv "${key}" 2>/dev/null || true)"
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

DIR_ICON_COLORED=$'\033[38;5;75m\033[0m'
DIR_PATH_COLOR_PREFIX=$'\033[38;5;110m'
ANSI_RESET=$'\033[0m'

tildefy_to_reply() {
  local p="$1"
  # shellcheck disable=SC2034,SC2088
  case "$p" in
  "$HOME") REPLY="~" ;;
  "$HOME"/*) REPLY="~/${p#"$HOME"/}" ;;
  *) REPLY="$p" ;;
  esac
}

print_dir_row() {
  local path="$1"
  tildefy_to_reply "$path"
  local base="${path##*/}"
  [ -n "$base" ] || base="$path"
  local mk
  mk="${base} ${REPLY} ${path}"
  printf '%s  %s%s%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${DIR_ICON_COLORED}" "$DIR_PATH_COLOR_PREFIX" "$REPLY" "$ANSI_RESET" \
    "dir" "$path" "" "" "${base} ${REPLY} ${path}"
}

is_git_repo() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1
}

emit_home_dirs() {
  local root="$HOME"
  local max_depth exclude_list include_hidden
  local exclude_file="${1:-}"
  max_depth="$(tmux_opt '@pick_session_dir_max_depth' '4')"
  exclude_list="$(tmux_opt '@pick_session_dir_exclude' '.git,.git/*,.git/**,.cache,.cache/*,.cache/**,.bazel-cache,.bazel-cache/*,.bazel-cache/**,.amp,.amp/*,.amp/**,Library,Library/*,Library/**,.gradle,.gradle/*,.gradle/**,.npm,.npm/*,.npm/**,.pnpm-store,.pnpm-store/*,.pnpm-store/**,node_modules,bazel-*,dist,build,out,target,__pycache__,.pytest_cache,.mypy_cache,.ruff_cache,.tox,.venv,venv,.terraform,.terragrunt-cache')"
  include_hidden="$(tmux_opt '@pick_session_dir_include_hidden' 'on')"

  declare -A exclude_exact=()
  local -a wt_roots=()
  if [ -n "$exclude_file" ] && [ -f "$exclude_file" ]; then
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      if printf '%s' "$line" | grep -q $'\t'; then
        local tag p
        IFS=$'\t' read -r tag p <<<"$line"
        [ -n "$p" ] || continue
        case "$tag" in
        WT)
          wt_roots+=("$p")
          exclude_exact["$p"]=1
          ;;
        EX)
          exclude_exact["$p"]=1
          ;;
        *)
          exclude_exact["$p"]=1
          ;;
        esac
      else
        exclude_exact["$line"]=1
      fi
    done <"$exclude_file"
  fi

  if [ -z "${exclude_exact["$root"]+x}" ]; then
    print_dir_row "$root"
  fi

  need_cmd fd || return 0

  local fd_args=()
  fd_args+=(--type d)
  case "$include_hidden" in
  1 | true | yes | on) fd_args+=(--hidden) ;;
  esac
  if [ -n "$max_depth" ]; then
    fd_args+=(--max-depth "$max_depth")
  fi
  if [ -n "$exclude_list" ]; then
    local exclude
    IFS=',' read -r -a exclude_items <<<"$exclude_list"
    for exclude in "${exclude_items[@]}"; do
      [ -n "$exclude" ] || continue
      fd_args+=(--exclude "$exclude")
    done
  fi
  if [ ${#wt_roots[@]} -gt 0 ]; then
    local wr rel
    for wr in "${wt_roots[@]}"; do
      case "$wr" in
      "$root"/*)
        rel="${wr#"$root"/}"
        [ -n "$rel" ] || continue
        fd_args+=(--exclude "$rel")
        ;;
      esac
    done
  fi
  fd "${fd_args[@]}" . "$root" 2>/dev/null | LC_ALL=C sort -u | while IFS= read -r p; do
    [ -z "$p" ] && continue
    p="${p%/}"
    [ "$p" = "$root" ] && continue
    if [ -n "${exclude_exact["$p"]+x}" ]; then
      continue
    fi
    print_dir_row "$p"
  done
}

emit_home_dirs_seeded() {
  local root="$HOME"
  local exclude_list include_hidden
  local exclude_file="${1:-}"
  exclude_list="$(tmux_opt '@pick_session_dir_exclude' '.git,.git/*,.git/**,.cache,.cache/*,.cache/**,.bazel-cache,.bazel-cache/*,.bazel-cache/**,.amp,.amp/*,.amp/**,Library,Library/*,Library/**,.gradle,.gradle/*,.gradle/**,.npm,.npm/*,.npm/**,.pnpm-store,.pnpm-store/*,.pnpm-store/**,node_modules,bazel-*,dist,build,out,target,__pycache__,.pytest_cache,.mypy_cache,.ruff_cache,.tox,.venv,venv,.terraform,.terragrunt-cache')"
  include_hidden="$(tmux_opt '@pick_session_dir_include_hidden' 'on')"

  declare -A exclude_exact=()
  if [ -n "$exclude_file" ] && [ -f "$exclude_file" ]; then
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      if printf '%s' "$line" | grep -q $'\t'; then
        local tag p
        IFS=$'\t' read -r tag p <<<"$line"
        [ -n "$p" ] || continue
        exclude_exact["$p"]=1
      else
        exclude_exact["$line"]=1
      fi
    done <"$exclude_file"
  fi

  declare -A seeded=()
  if [ -z "${exclude_exact["$root"]+x}" ]; then
    seeded["$root"]=1
  fi

  need_cmd fd || {
    for p in "${!seeded[@]}"; do
      print_dir_row "$p"
    done | LC_ALL=C sort -u
    return 0
  }

  local fd_args=()
  fd_args+=(--type d --max-depth 1)
  case "$include_hidden" in
  1 | true | yes | on) fd_args+=(--hidden) ;;
  esac
  if [ -n "$exclude_list" ]; then
    local exclude
    IFS=',' read -r -a exclude_items <<<"$exclude_list"
    for exclude in "${exclude_items[@]}"; do
      [ -n "$exclude" ] || continue
      fd_args+=(--exclude "$exclude")
    done
  fi

  while IFS= read -r p; do
    [ -z "$p" ] && continue
    p="${p%/}"
    [ "$p" = "$root" ] && continue
    [ -n "${exclude_exact["$p"]+x}" ] && continue
    seeded["$p"]=1
  done < <(fd "${fd_args[@]}" . "$root" 2>/dev/null || true)

  # Seed configured worktree roots (and their home-relative ancestors) so
  # hidden hubs like ~/.local/share are matchable immediately on first refresh.
  local roots_raw wr cur
  roots_raw="$(tmux_opt '@pick_session_worktree_scan_roots' "$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share")"
  IFS=',' read -r -a wt_roots <<<"$roots_raw"
  for wr in "${wt_roots[@]}"; do
    wr="${wr#"${wr%%[![:space:]]*}"}"
    wr="${wr%"${wr##*[![:space:]]}"}"
    [ -n "$wr" ] || continue
    case "$wr" in
    "~") wr="$HOME" ;;
    "~/"*) wr="$HOME/${wr#~/}" ;;
    esac
    if [ -d "$wr" ]; then
      wr="$(cd "$wr" && pwd -P)"
    fi
    case "$wr" in
    "$root"/*)
      cur="$wr"
      while :; do
        [ -n "${exclude_exact["$cur"]+x}" ] || seeded["$cur"]=1
        [ "$cur" = "$root" ] && break
        cur="$(dirname "$cur")"
        case "$cur" in
        "$root" | "$root"/*) ;;
        *) break ;;
        esac
      done
      ;;
    esac
  done

  printf '%s\n' "${!seeded[@]}" | LC_ALL=C sort -u | while IFS= read -r p; do
    [ -n "$p" ] || continue
    print_dir_row "$p"
  done
}

emit_sessions_worktrees_and_dirs() {
  need_cmd tmux || return 0

  export PICK_SESSION_SCAN_ROOTS
  export PICK_SESSION_SCAN_DEPTH
  export PICK_SESSION_QUICK
  export PICK_SESSION_SESSIONS_ONLY
  export PICK_SESSION_EXCLUDE_LIST
  export PICK_SESSION_DIR_MAX_DEPTH
  export PICK_SESSION_DIR_INCLUDE_HIDDEN

  PICK_SESSION_SCAN_ROOTS="$(tmux_opt '@pick_session_worktree_scan_roots' "$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share")"
  PICK_SESSION_SCAN_DEPTH="$(tmux_opt '@pick_session_worktree_scan_depth' '6')"
  PICK_SESSION_EXCLUDE_LIST="$(tmux_opt '@pick_session_dir_exclude' '.git,.git/*,.git/**,.cache,.cache/*,.cache/**,.bazel-cache,.bazel-cache/*,.bazel-cache/**,.amp,.amp/*,.amp/**,Library,Library/*,Library/**,.gradle,.gradle/*,.gradle/**,.npm,.npm/*,.npm/**,.pnpm-store,.pnpm-store/*,.pnpm-store/**,node_modules,bazel-*,dist,build,out,target,__pycache__,.pytest_cache,.mypy_cache,.ruff_cache,.tox,.venv,venv,.terraform,.terragrunt-cache')"
  PICK_SESSION_QUICK="$quick_mode"
  PICK_SESSION_SESSIONS_ONLY="$sessions_only"
  PICK_SESSION_DIR_MAX_DEPTH="$(tmux_opt '@pick_session_dir_max_depth' '4')"
  PICK_SESSION_DIR_INCLUDE_HIDDEN="$(tmux_opt '@pick_session_dir_include_hidden' 'on')"

  python3 -u - <<'PY'
import os
import re
import subprocess
from pathlib import Path
import shutil
import signal
import time
import concurrent.futures

# If the consumer (fzf) exits early, don't spam tracebacks.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

RESET = "\033[0m"

def color(code, text):
    return f"\033[{code}m{text}{RESET}"

def display_session_entry(name, path_display):
    return f"{color('38;5;42', '')}  {color('1;38;5;81', name)}  {color('2;38;5;246', path_display)}"

def display_worktree_entry(path_display):
    return f"{color('38;5;214', '')}  {color('38;5;221', path_display)}"

def display_dir_entry(path_display):
    return f"{color('38;5;75', '')}  {color('38;5;110', path_display)}"

def tildefy(p):
    home = os.path.expanduser("~")
    if p == home:
        return "~"
    if p.startswith(home + "/"):
        return "~/" + p[len(home) + 1 :]
    return p

def resolve_path(p):
    try:
        return str(Path(p).resolve())
    except Exception:
        return p

def match_key(*parts):
    return " ".join([ (p or "").strip() for p in parts if (p or "").strip() ])

def head_branch(gitdir):
    try:
        head = Path(gitdir, "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        if ref.startswith("refs/heads/"):
            return ref[len("refs/heads/") :]
    return ""

def tmux_sanitize_session_name(s: str) -> str:
    s = (s or "").strip().lower()
    if not s:
        return ""
    s = re.sub(r"[^a-z0-9_@|/~-]+", "_", s)
    s = re.sub(r"[.:]+", "_", s)
    s = s.strip("_")
    return s

def git_config_path_for_root(root: str):
    cfg = Path(root) / ".git" / "config"
    if cfg.exists():
        return cfg
    cfg = Path(root) / "config"
    if cfg.exists():
        return cfg
    return None

def origin_url_for_root(root: str) -> str:
    cfg = git_config_path_for_root(root)
    if cfg is None:
        return ""
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'\[remote "(origin|upstream)"\].*?url\s*=\s*(.+)', text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(2).splitlines()[0].strip()
    except Exception:
        pass
    return ""

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
    try:
        base = Path(root).name
        if base in DEFAULT_BRANCH_DIRS:
            return Path(root).parent.name or base
        return base
    except Exception:
        pass
    repo = repo_name_from_url(origin_url_for_root(root))
    if repo:
        return repo
    name = Path(root).name
    if name.startswith(".") and len(name) > 1:
        name = name.lstrip(".")
    return name

def is_git_repo_dir(p: str) -> bool:
    try:
        path = Path(p)
        return (path / ".git").exists() or (path / "HEAD").exists()
    except Exception:
        return False

def find_wrapper_root_checkout_for_path(p: str, scan_roots_set: set[str]) -> str:
    cur = Path(p)
    if cur.is_file():
        cur = cur.parent
    try:
        cur = cur.resolve()
    except Exception:
        cur = Path(p)

    for _ in range(10):
        wrapper = cur
        w = resolve_path(str(wrapper))
        if w and w not in scan_roots_set:
            for d in DEFAULT_BRANCH_DIRS_ORDER:
                root_checkout = wrapper / d
                if root_checkout.is_dir() and is_git_repo_dir(str(root_checkout)):
                    return resolve_path(str(root_checkout))
        if wrapper.parent == wrapper:
            break
        cur = wrapper.parent
    return ""

def remote_names_for_root(root: str) -> set[str]:
    cfg = git_config_path_for_root(root)
    if cfg is None:
        return set()
    remotes = set()
    try:
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r'\[remote "(.+)"\]', line, flags=re.IGNORECASE)
            if m:
                remotes.add(m.group(1))
    except Exception:
        pass
    return remotes

def branch_from_wrapper_path(root: str, wt_path: str, remotes: set[str]) -> str:
    try:
        wrapper = str(Path(root).parent)
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
    except Exception:
        return ""

def worktree_info(worktree_dir):
    wt = Path(worktree_dir)
    gitp = wt / ".git"
    if gitp.is_dir():
        gitdir = resolve_path(str(gitp))
        root_wt = resolve_path(str(wt))
        br = head_branch(gitdir)
        wrapper_root = find_wrapper_root_checkout_for_path(root_wt, scan_roots_set)
        if wrapper_root and wrapper_root != root_wt and is_git_repo_dir(wrapper_root):
            remotes = remote_names_for_root(wrapper_root)
            derived = branch_from_wrapper_path(wrapper_root, root_wt, remotes)
            if derived: br = derived
            root_wt = wrapper_root
        return { "path": resolve_path(str(wt)), "root": root_wt, "gitdir": gitdir, "branch": br }

    if gitp.is_file():
        try:
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if not first.startswith("gitdir:"): return None
            raw = first.split(":", 1)[1].strip()
            gitdir = resolve_path(str(wt / raw) if not os.path.isabs(raw) else raw)
            norm = gitdir.replace("\\", "/")
            if "/worktrees/" in norm:
                common_dir = resolve_path(str(Path(gitdir).parent.parent))
                root_wt = resolve_path(str(Path(common_dir).parent)) if Path(common_dir).name == ".git" else common_dir
            else:
                root_wt = resolve_path(str(wt))
            return { "path": resolve_path(str(wt)), "root": root_wt, "gitdir": gitdir, "branch": head_branch(gitdir) }
        except Exception: pass
    return None

def find_worktree_root_for_path(p, stop_at):
    cur = Path(p)
    if cur.is_file(): cur = cur.parent
    try: cur = cur.resolve()
    except Exception: cur = Path(p)
    stop_at = Path(stop_at).resolve() if stop_at else None
    for _ in range(12):
        if (cur / ".git").exists(): return str(cur)
        if stop_at and str(cur) == str(stop_at): break
        if cur.parent == cur: break
        cur = cur.parent
    return ""

def list_worktrees_under_root(root: str):
    out = subprocess.run([ "git", "-C", root, "worktree", "list", "--porcelain" ], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
    worktree_path, branch, detached, results = "", "", False, {}
    for line in out.splitlines():
        line = line.strip()
        if not line: continue
        if line.startswith("worktree "):
            if worktree_path: results[resolve_path(worktree_path)] = branch if not detached else ""
            worktree_path = line.split(" ", 1)[1].strip()
            branch, detached = "", False
        elif line.startswith("branch "):
            ref = line.split(" ", 1)[1].strip()
            branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif line == "detached": detached = True
    if worktree_path: results[resolve_path(worktree_path)] = branch if not detached else ""
    return results

def has_worktrees(root_dir: str) -> bool:
    gitp = Path(root_dir) / ".git"
    if gitp.is_dir(): return (gitp / "worktrees").is_dir()
    return (Path(root_dir) / "worktrees").is_dir()

def scan_for_git_repos(roots, depth, exclude_list):
    candidates = set()
    fd_args = ["fd", "--hidden", "--no-ignore", "--absolute-path", "--type", "f", "--type", "d", "--max-depth", str(depth), "--glob", ".git"]
    # Filter out .git patterns from the exclude list for the repo scan itself
    for ex in exclude_list.split(","):
        ex = ex.strip()
        if ex and not ex.startswith(".git"):
            fd_args.extend(["--exclude", ex])

    for r in roots:
        out = subprocess.run(fd_args + [r], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
        for gitp in out.splitlines():
            p = gitp.strip()
            if p: candidates.add(resolve_path(str(Path(p).parent)))

    accepted = []
    for wt_dir in sorted(candidates, key=lambda p: (len(p), p)):
        if not any(wt_dir == a or wt_dir.startswith(a + os.sep) for a in accepted):
            accepted.append(wt_dir)
    return accepted

def get_home_dirs(root, depth, exclude_list, include_hidden):
    fd_args = ["fd", "--type", "d", "--max-depth", str(depth), "--absolute-path"]
    if include_hidden in ("1", "true", "yes", "on"): fd_args.append("--hidden")
    for ex in exclude_list.split(","):
        ex = ex.strip()
        if ex: fd_args.extend(["--exclude", ex])

    out = subprocess.run(fd_args + [".", root], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]

scan_roots_raw = os.environ.get("PICK_SESSION_SCAN_ROOTS", "").strip()
scan_roots = [resolve_path(os.path.expanduser(x.strip())) for x in scan_roots_raw.split(",") if x.strip()]
scan_roots = [r for r in scan_roots if os.path.isdir(r)]
scan_roots_set = set(scan_roots)
quick = os.environ.get("PICK_SESSION_QUICK", "").lower() in ("1", "true", "yes", "on")
sessions_only = os.environ.get("PICK_SESSION_SESSIONS_ONLY", "").lower() in ("1", "true", "yes", "on")
exclude_list_raw = os.environ.get("PICK_SESSION_EXCLUDE_LIST", "").strip()

groups = {}
def ensure_group(root_wt):
    root_wt = resolve_path(root_wt)
    if root_wt not in groups: groups[root_wt] = { "repo": "", "wt_map": {}, "sessions_by_wt": {} }

# 1. Discover worktrees
if not quick and not sessions_only and shutil.which("fd"):
    for wt_dir in scan_for_git_repos(scan_roots, int(os.environ.get("PICK_SESSION_SCAN_DEPTH", 6)), exclude_list_raw):
        info = worktree_info(wt_dir)
        if info:
            ensure_group(info["root"])
            groups[info["root"]]["wt_map"][info["path"]] = { "branch": info.get("branch", "") }

# 2. Add sessions
current_session = subprocess.run([ "tmux", "display-message", "-p", "#S" ], check=False, stdout=subprocess.PIPE, text=True).stdout.strip()
sess_out = subprocess.run([ "tmux", "list-sessions", "-F", "#{session_name}\t#{session_path}" ], check=False, stdout=subprocess.PIPE, text=True).stdout
sessions = []
home = os.path.expanduser("~")
for row in sess_out.splitlines():
    if not row: continue
    name, _, path = row.partition("\t")
    name, path = name.strip(), path.strip()
    rp = resolve_path(path)
    sessions.append({ "name": name, "path": path, "rpath": rp, "is_current": (name == current_session) })
    wt_root = find_worktree_root_for_path(rp, home)
    if wt_root:
        info = worktree_info(wt_root)
        if info:
            ensure_group(info["root"])
            groups[info["root"]]["wt_map"].setdefault(info["path"], { "branch": info.get("branch", "") })
            groups[info["root"]]["sessions_by_wt"].setdefault(info["path"], []).append(name)

# 3. Parallel worktree expansion
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    future_to_root = {executor.submit(list_worktrees_under_root, r): r for r in groups if has_worktrees(r)}
    for future in concurrent.futures.as_completed(future_to_root):
        root = future_to_root[future]
        try:
            for wt_path, br in future.result().items():
                if os.path.isdir(wt_path):
                    groups[root]["wt_map"].setdefault(wt_path, { "branch": br or "" })
        except Exception: pass

# 4. Output results
exclude_exact = set()
exclude_worktree_roots = set()

def emit_sessions_and_worktrees():
    for root in sorted(groups.keys(), key=lambda r: repo_display_for_root(r).lower()):
        repo = repo_display_for_root(root)
        wt_map = groups[root]["wt_map"]
        sessions_by_wt = groups[root]["sessions_by_wt"]

        # Sessions first
        for wt_path in sorted(wt_map.keys()):
            for sess_name in sorted(sessions_by_wt.get(wt_path, [])):
                br = wt_map.get(wt_path, {}).get("branch", "")
                expected = tmux_sanitize_session_name(f"{repo}|{br}" if br else repo)
                meta = f"sess_root:{br}" if wt_path == root else f"sess_wt:{br}"
                if expected and sess_name != expected: meta += f"|expected={expected}"
                disp = display_session_entry(sess_name if not expected or sess_name.startswith(expected) else expected, tildefy(wt_path))
                mk = match_key(sess_name, expected, repo, br, Path(wt_path).name, tildefy(wt_path))
                print(f"{disp}\tsession\t{wt_path}\t{meta}\t{sess_name}\t{mk}")
                exclude_worktree_roots.add(wt_path)

        # Worktrees second (skip entirely in sessions-only mode).
        if not sessions_only:
            for wt_path in sorted(wt_map.keys()):
                if wt_path in sessions_by_wt: continue
                br = wt_map[wt_path].get("branch", "")
                meta = f"wt_root:{br}" if wt_path == root else f"wt:{br}"
                wt_name = f"{repo}|{br}" if br else repo
                mk = match_key(wt_name, Path(wt_path).name, tildefy(wt_path))
                print(f"{display_worktree_entry(tildefy(wt_path))}\tworktree\t{wt_path}\t{meta}\t{root}\t{mk}")
                exclude_worktree_roots.add(wt_path)

emit_sessions_and_worktrees()

# 5. Directories
if not sessions_only:
    # Keep directory output intentionally small and stable:
    # - emit wrapper directories for detected repo roots
    # - plus $HOME
    wrapper_dirs = set()
    for root in groups.keys():
        try:
            base = Path(root).name
        except Exception:
            base = ""
        if base in DEFAULT_BRANCH_DIRS:
            wrapper_dirs.add(resolve_path(str(Path(root).parent)))
        else:
            wrapper_dirs.add(resolve_path(str(Path(root))))
    wrapper_dirs.add(resolve_path(home))
    for p in sorted(wrapper_dirs):
        if not p or p in exclude_worktree_roots:
            continue
        mk = match_key(Path(p).name, tildefy(p), p)
        print(f"{display_dir_entry(tildefy(p))}\tdir\t{p}\t\t\t{mk}")
PY
}

quick_mode=0
sessions_only=0
while [ $# -gt 0 ]; do
  case "$1" in
  --quick) quick_mode=1 ;;
  --sessions-only) sessions_only=1 ;;
  esac
  shift
done

emit_sessions_worktrees_and_dirs
