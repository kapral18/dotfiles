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
  local base
  base="$(basename "$path")"
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

emit_sessions_and_worktrees() {
  need_cmd tmux || return 0

  export PICK_SESSION_SCAN_ROOTS
  export PICK_SESSION_SCAN_DEPTH
  export PICK_SESSION_QUICK
  PICK_SESSION_SCAN_ROOTS="$(tmux_opt '@pick_session_worktree_scan_roots' "$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share")"
  PICK_SESSION_SCAN_DEPTH="$(tmux_opt '@pick_session_worktree_scan_depth' '6')"

  python3 -u - <<'PY'
import os
import re
import subprocess
from pathlib import Path
import shutil
import signal

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
    """
    Make a tmux-safe session name that matches tmux's normalization behavior
    (notably '.' -> '_'), while preserving common branch separators like '/'.
    """
    s = (s or "").strip().lower()
    if not s:
        return ""
    # Replace any disallowed characters with underscores, and normalize '.'/':'
    # which tmux itself treats specially.
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
    base = Path(root).name
    if base in DEFAULT_BRANCH_DIRS:
        try:
            return Path(root).parent.name or base
        except Exception:
            return base
    return base

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
                # [remote "origin"]
                try:
                    name = line.split('"', 2)[1].strip()
                except Exception:
                    name = ""
                if name:
                    remotes.add(name)
    except Exception:
        return remotes
    return remotes

def is_wrapper_layout_root(root: str) -> bool:
    try:
        return Path(root).name in DEFAULT_BRANCH_DIRS
    except Exception:
        return False

def is_git_repo_dir(p: str) -> bool:
    try:
        return bool(p) and (Path(p) / ".git").exists()
    except Exception:
        return False

def find_wrapper_root_checkout_for_path(p: str, scan_roots_set: set[str]) -> str:
    """
    Wrapper layout (``,w``): checkouts are stored under `<wrapper>/<branch...>`,
    and the "root" checkout lives under `<wrapper>/<default-branch>`.
    """
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

def branch_from_wrapper_path(root: str, wt_path: str, remotes: set[str]) -> str:
    """
    For wrapper layouts (`,w`): root worktree is usually `<repo>/main`, and
    sibling worktrees live under `<repo>/<branch...>`. Derive the intended
    branch from the path relative to the wrapper.
    """
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
    # Mirror `,w add` convention for fork remotes:
    # `<wrapper>/<remote>/<branch>` -> local branch `<remote>__<branch>`
    if "/" in rel:
        first, rest = rel.split("/", 1)
        if first in remotes and first not in ("origin", "upstream") and rest:
            return f"{first}__{rest}"
    return rel

def worktree_info(worktree_dir):
    """
    Identify worktree root vs non-root by the `.git` shape:
    - root repo: `.git` is a directory
    - linked worktree: `.git` is a file that points to `.../.git/worktrees/<name>`
    """
    wt = Path(worktree_dir)
    gitp = wt / ".git"
    if gitp.is_dir():
        gitdir = resolve_path(str(gitp))
        root_wt = resolve_path(str(wt))
        br = head_branch(gitdir)

        # Support wrapper layouts created by `,w` even when the checkout is a
        # standalone repo (not a linked git worktree). In that layout, branch
        # naming is derived from the directory path under the wrapper.
        wrapper_root = find_wrapper_root_checkout_for_path(root_wt, scan_roots_set)
        if wrapper_root and wrapper_root != root_wt and is_git_repo_dir(wrapper_root):
            remotes = remote_names_for_root(wrapper_root)
            derived = branch_from_wrapper_path(wrapper_root, root_wt, remotes)
            if derived:
                br = derived
            root_wt = wrapper_root

        return { "path": resolve_path(str(wt)), "root": root_wt, "gitdir": gitdir, "branch": br }

    if gitp.is_file():
        try:
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
        except Exception:
            return None
        if not first.startswith("gitdir:"):
            return None
        raw = first.split(":", 1)[1].strip()
        gitdir = raw
        if not os.path.isabs(gitdir):
            gitdir = str((wt / gitdir).resolve())
        gitdir = resolve_path(gitdir)

        norm = gitdir.replace("\\", "/")
        if "/worktrees/" in norm:
            common_dir = resolve_path(str(Path(gitdir).parent.parent))
            try:
                root_wt = resolve_path(str(Path(common_dir).parent)) if Path(common_dir).name == ".git" else common_dir
            except Exception:
                root_wt = common_dir
        else:
            # Submodules (and other layouts) keep gitdir elsewhere; treat the
            # directory itself as its own "root".
            root_wt = resolve_path(str(wt))
        br = head_branch(gitdir)
        return { "path": resolve_path(str(wt)), "root": root_wt, "gitdir": gitdir, "branch": br }

    return None

def find_worktree_root_for_path(p, stop_at):
    """
    Walk upwards to find the nearest directory that has a `.git` file/dir.
    This lets us associate tmux session paths that point to subdirs.
    """
    cur = Path(p)
    if cur.is_file():
        cur = cur.parent
    try:
        cur = cur.resolve()
    except Exception:
        cur = Path(p)

    stop_at = Path(stop_at).resolve() if stop_at else None
    for _ in range(12):
        if (cur / ".git").exists():
            return str(cur)
        if stop_at and str(cur) == str(stop_at):
            break
        if cur.parent == cur:
            break
        cur = cur.parent
    return ""

def expand_root(p):
    p = p.strip()
    if not p:
        return ""
    if p == "~":
        return os.path.expanduser("~")
    if p.startswith("~/"):
        return os.path.join(os.path.expanduser("~"), p[2:])
    return p

current_session = subprocess.run([ "tmux", "display-message", "-p", "#S" ], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout.strip()
current_session_path = subprocess.run([ "tmux", "display-message", "-p", "#{session_path}" ], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout.strip()
exclude_file = os.environ.get("PICK_SESSION_EXCLUDE_FILE", "").strip()

scan_roots_raw = os.environ.get("PICK_SESSION_SCAN_ROOTS", "").strip()
scan_depth_raw = os.environ.get("PICK_SESSION_SCAN_DEPTH", "").strip()
quick_raw = os.environ.get("PICK_SESSION_QUICK", "").strip().lower()
quick = quick_raw in ("1", "true", "yes", "on")
scan_depth = 6
try:
    if scan_depth_raw:
        scan_depth = int(scan_depth_raw)
except Exception:
    scan_depth = 6

scan_roots = [ expand_root(x) for x in scan_roots_raw.split(",") if x.strip() ] if scan_roots_raw else [ os.path.join(os.path.expanduser("~"), "work"), os.path.join(os.path.expanduser("~"), "code"), os.path.join(os.path.expanduser("~"), ".local", "share") ]
scan_roots = [ resolve_path(r) for r in scan_roots if r and Path(r).is_dir() ]
scan_roots_set = set(scan_roots)

groups = {}  # root_wt -> { repo, wt_map, sessions_by_wt }

def ensure_group(root_wt):
    root_wt = resolve_path(root_wt)
    if root_wt in groups:
        return
    groups[root_wt] = { "repo": "", "wt_map": {}, "sessions_by_wt": {} }

# Scan for `.git` *files and dirs* (worktree roots have a `.git` dir; linked
# worktrees have a `.git` file). In quick mode, skip the global scan and rely
# on tmux sessions + per-repo `git worktree list` instead.
if (not quick) and scan_roots and shutil.which("fd"):
    candidates = set()
    for r in scan_roots:
        out = subprocess.run(
            [
                "fd",
                "--hidden",
                "--no-ignore",
                "--absolute-path",
                "--type",
                "f",
                "--type",
                "d",
                "--max-depth",
                str(scan_depth),
                "--glob",
                ".git",
                r,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout
        for gitp in out.splitlines():
            gitp = gitp.strip()
            if not gitp:
                continue

            wt_dir = resolve_path(str(Path(gitp).parent))
            if wt_dir:
                candidates.add(wt_dir)

    # Don't treat nested `.git` hits as new candidates once we already have a
    # parent candidate. This avoids picking up submodules / nested repos as
    # separate "worktrees" and reduces noise + cost.
    accepted = []
    for wt_dir in sorted(candidates, key=lambda p: (len(p), p)):
        if any(wt_dir == a or wt_dir.startswith(a + os.sep) for a in accepted):
            continue
        accepted.append(wt_dir)

        info = worktree_info(wt_dir)
        if not info:
            continue
        ensure_group(info["root"])
        groups[info["root"]]["wt_map"][info["path"]] = { "branch": info.get("branch", "") }

# Collect tmux sessions and associate to worktrees (even outside scan roots).
sess_out = subprocess.run([ "tmux", "list-sessions", "-F", "#{session_name}\t#{session_path}" ], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
sessions = []
for row in sess_out.splitlines():
    if not row:
        continue
    name, _, path = row.partition("\t")
    name = name.strip()
    path = path.strip()
    if not name:
        continue
    rp = resolve_path(path) if path else ""
    sessions.append({ "name": name, "path": path, "rpath": rp, "is_current": (name == current_session) })

home = os.path.expanduser("~")
live_session_names = { s.get("name") for s in sessions if s.get("name") }
worktree_backed_sessions = set()
for s in sessions:
    rp = s.get("rpath") or ""
    if not rp:
        continue
    wt_root = find_worktree_root_for_path(rp, home)
    if not wt_root:
        continue
    info = worktree_info(wt_root)
    if not info:
        continue
    ensure_group(info["root"])
    groups[info["root"]]["wt_map"].setdefault(info["path"], { "branch": info.get("branch", "") })
    groups[info["root"]]["sessions_by_wt"].setdefault(info["path"], []).append(s["name"])
    worktree_backed_sessions.add(s["name"])

def list_worktrees_under_root(root: str):
    """
    Return { worktree_path: branch_name } for all worktrees in this repo.
    """
    out = subprocess.run(
        [ "git", "-C", root, "worktree", "list", "--porcelain" ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout
    worktree_path = ""
    branch = ""
    detached = False
    results = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("worktree "):
            if worktree_path:
                results[resolve_path(worktree_path)] = branch if not detached else ""
            worktree_path = line.split(" ", 1)[1].strip()
            branch = ""
            detached = False
            continue
        if line.startswith("branch "):
            ref = line.split(" ", 1)[1].strip()
            if ref.startswith("refs/heads/"):
                branch = ref[len("refs/heads/") :]
            else:
                branch = ref
            continue
        if line == "detached":
            detached = True
            continue
    if worktree_path:
        results[resolve_path(worktree_path)] = branch if not detached else ""
    return results

if groups:
    # Always expand discovered repo roots with `git worktree list` so deep
    # branch paths (for example `foo/bar/baz/...`) are present even when the
    # fd max-depth scan would miss them and fall back to plain dir entries.
    for root in list(groups.keys()):
        try:
            rootp = resolve_path(root)
            if not rootp or not Path(rootp).is_dir():
                continue
            for wt_path, br in list_worktrees_under_root(rootp).items():
                if wt_path and Path(wt_path).is_dir():
                    groups[root]["wt_map"].setdefault(wt_path, { "branch": br or "" })
        except Exception:
            continue

cwd_root = ""
cwd_wt = find_worktree_root_for_path(os.getcwd(), home)
if cwd_wt:
    info = worktree_info(cwd_wt)
    if info:
        cwd_root = info["root"]
cwd_root_resolved = resolve_path(cwd_root) if cwd_root else ""

current_root = ""
current_wt = find_worktree_root_for_path(current_session_path, home) if current_session_path else ""
if current_wt:
    info = worktree_info(current_wt)
    if info:
        current_root = info["root"]
current_root_resolved = resolve_path(current_root) if current_root else ""

for root, g in groups.items():
    g["repo"] = repo_display_for_root(root)
    if is_wrapper_layout_root(root):
        # Only apply wrapper-branch derivation when the wrapper folder matches
        # the repo name (common `,w` layout: `<repo>/main`).
        try:
            wrapper_name = Path(root).parent.name.lower()
        except Exception:
            wrapper_name = ""
        repo_name = (g.get("repo") or "").lower()
        if wrapper_name and repo_name and wrapper_name == repo_name:
            remotes = remote_names_for_root(root)
            wt_map = g.get("wt_map", {})
            for wt_path, rec in wt_map.items():
                derived = branch_from_wrapper_path(root, wt_path, remotes)
                if derived:
                    rec["branch"] = derived

def scan_root_order_key(root):
    for i, scan_root in enumerate(scan_roots):
        if root == scan_root or root.startswith(scan_root + os.sep):
            return (0, i, root)
    if root == home or root.startswith(home + os.sep):
        return (1, 0, root)
    return (2, 0, root)

def group_order_key(root):
    has_sessions = 1 if groups[root]["sessions_by_wt"] else 0
    current_rank = 0 if (current_root_resolved and root == current_root_resolved) else (0 if (cwd_root_resolved and root == cwd_root_resolved) else 1)
    return (0 if has_sessions else 1, current_rank, *scan_root_order_key(root), groups[root]["repo"])

def wt_sort_key(path, root):
    br = groups[root]["wt_map"].get(path, {}).get("branch", "")
    return (0 if path == root else 1, br, path)

exclude_exact = set()
exclude_worktree_roots = set()

roots_sorted = sorted(groups.keys(), key=group_order_key)
roots_with_sessions = [ r for r in roots_sorted if groups[r]["sessions_by_wt"] ]
roots_without_sessions = [ r for r in roots_sorted if not groups[r]["sessions_by_wt"] ]

for root in roots_with_sessions:
    repo = groups[root]["repo"]
    wt_map = groups[root]["wt_map"]
    sessions_by_wt = groups[root]["sessions_by_wt"]

    for wt_path in sorted(sessions_by_wt.keys(), key=lambda p: wt_sort_key(p, root)):
        br = wt_map.get(wt_path, {}).get("branch", "")
        sess_names = sorted(set(sessions_by_wt.get(wt_path, [])))
        expected_raw = f"{repo}|{br}" if br else ""
        expected = tmux_sanitize_session_name(expected_raw) if expected_raw else ""
        chosen = expected if expected and expected in sess_names else sess_names[0]
        # Display the expected/canonical name for truly misnamed sessions, but
        # keep disambiguated names visible (e.g. `kibana|main@backport`) so
        # multiple checkouts don't look like duplicates.
        label = chosen
        if expected and chosen and chosen != expected and not chosen.startswith(expected + "@"):
            label = expected
        meta_base = f"sess_root:{br}" if wt_path == root else f"sess_wt:{br}"
        # If an existing session is "misnamed" (historical naming), keep the
        # display as the expected name, but include the expectation in metadata
        # so the picker can rename on selection.
        meta = meta_base
        if expected and chosen != expected:
            meta = f"{meta_base}|expected={expected}"
        disp = display_session_entry(label, tildefy(wt_path))
        mk = match_key(chosen, expected_raw, expected, repo, br, Path(wt_path).name, tildefy(wt_path), wt_path)
        print(f"{disp}\tsession\t{wt_path}\t{meta}\t{chosen}\t{mk}")
        exclude_worktree_roots.add(wt_path)

    for wt_path in sorted(wt_map.keys(), key=lambda p: wt_sort_key(p, root)):
        # Keep worktree rows even when a session exists for that path.
        # The picker output de-duplicates (session wins), but having the worktree
        # row in the cache allows immediate demotion after a session is killed,
        # without waiting for a background re-index.
        br = wt_map[wt_path].get("branch", "")
        meta = f"wt_root:{br}" if wt_path == root else f"wt:{br}"
        wt_name_raw = f"{repo}|{br}" if br else repo
        wt_name = tmux_sanitize_session_name(wt_name_raw) if wt_name_raw else ""
        mk = match_key(wt_name_raw, wt_name, Path(wt_path).name, tildefy(wt_path), wt_path)
        disp = f"{display_worktree_entry(tildefy(wt_path))}"
        print(f"{disp}\tworktree\t{wt_path}\t{meta}\t{root}\t{mk}")
        exclude_worktree_roots.add(wt_path)

for root in roots_without_sessions:
    wt_map = groups[root]["wt_map"]
    repo = groups[root]["repo"]
    for wt_path in sorted(wt_map.keys(), key=lambda p: wt_sort_key(p, root)):
        br = wt_map[wt_path].get("branch", "")
        meta = f"wt_root:{br}" if wt_path == root else f"wt:{br}"
        wt_name_raw = f"{repo}|{br}" if br else repo
        wt_name = tmux_sanitize_session_name(wt_name_raw) if wt_name_raw else ""
        mk = match_key(wt_name_raw, wt_name, Path(wt_path).name, tildefy(wt_path), wt_path)
        disp = f"{display_worktree_entry(tildefy(wt_path))}"
        print(f"{disp}\tworktree\t{wt_path}\t{meta}\t{root}\t{mk}")
        exclude_worktree_roots.add(wt_path)

for s in sorted(sessions, key=lambda x: x.get("name", "")):
    name = s.get("name") or ""
    if not name:
        continue
    if name in worktree_backed_sessions:
        continue
    path = s.get("path") or ""
    rpath = s.get("rpath") or path
    disp_path = tildefy(rpath) if rpath else ""
    mk = match_key(name, Path(rpath).name if rpath else "", disp_path, rpath)
    disp = f"{display_session_entry(name, disp_path)}"
    print(f"{disp}\tsession\t{rpath}\t\t{name}\t{mk}")
    if rpath:
        exclude_exact.add(rpath)

if current_session_path:
    exclude_exact.add(resolve_path(current_session_path))

if exclude_file:
    try:
        with open(exclude_file, "w", encoding="utf-8") as f:
            for p in sorted(exclude_exact | exclude_worktree_roots):
                if p:
                    f.write("EX\t" + p + "\n")
            for p in sorted(exclude_worktree_roots):
                if p:
                    f.write("WT\t" + p + "\n")
    except Exception:
        pass
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

exclude_file="$(mktemp -t pick_session_exclude.XXXXXX)"
cleanup() { rm -f "$exclude_file" 2>/dev/null || true; }
trap cleanup EXIT

PICK_SESSION_EXCLUDE_FILE="$exclude_file" PICK_SESSION_QUICK="$quick_mode" emit_sessions_and_worktrees || true
if [ "$sessions_only" -eq 1 ]; then
  exit 0
fi
if [ "$quick_mode" -eq 1 ]; then
  emit_home_dirs_seeded "$exclude_file" || true
else
  emit_home_dirs "$exclude_file" || true
fi
