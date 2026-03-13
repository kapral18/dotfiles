#!/usr/bin/env bash
# Re-exec under a modern bash when macOS ships bash 3.2 as /bin/bash.
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  _b="$(brew --prefix bash 2> /dev/null)/bin/bash"
  [ -x "$_b" ] && exec "$_b" "$0" "$@"
  exit 1
fi
set -euo pipefail

need_cmd() {
  local cmd="$1"
  command -v "${cmd}" > /dev/null 2>&1
}

tmux_opt() {
  local key="$1"
  local default_value="$2"
  local value=""
  value="$(tmux show-option -gqv "${key}" 2> /dev/null || true)"
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

DIR_ICON_COLORED=$'\033[38;5;75m\033[0m'
DIR_PATH_COLOR_PREFIX=$'\033[38;5;110m'
ANSI_RESET=$'\033[0m'
DEFAULT_PICK_SESSION_DIR_EXCLUDE_FILE="$HOME/.config/tmux/pick_session_dir_exclude.txt"

normalize_path_opt() {
  local p="${1:-}"
  case "$p" in
    "~") printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s\n' "$HOME/${p#"~/"}" ;;
    *) printf '%s\n' "$p" ;;
  esac
}

pick_session_ignore_file() {
  local file_opt
  file_opt="$(tmux_opt '@pick_session_dir_exclude_file' "$DEFAULT_PICK_SESSION_DIR_EXCLUDE_FILE")"
  file_opt="$(normalize_path_opt "$file_opt")"
  [ -f "$file_opt" ] && printf '%s\n' "$file_opt"
}

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
  git rev-parse --is-inside-work-tree > /dev/null 2>&1
}

emit_home_dirs() {
  local root="$HOME"
  local max_depth include_hidden ignore_file
  local exclude_file="${1:-}"
  max_depth="$(tmux_opt '@pick_session_dir_max_depth' '4')"
  include_hidden="$(tmux_opt '@pick_session_dir_include_hidden' 'on')"
  ignore_file="$(pick_session_ignore_file)"

  declare -A exclude_exact=()
  local -a wt_roots=()
  if [ -n "$exclude_file" ] && [ -f "$exclude_file" ]; then
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      if printf '%s' "$line" | grep -q $'\t'; then
        local tag p
        IFS=$'\t' read -r tag p <<< "$line"
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
    done < "$exclude_file"
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
  fd_args+=(--exclude .git)
  if [ -n "$ignore_file" ] && [ -f "$ignore_file" ]; then
    while IFS= read -r _pat; do
      _pat="${_pat%%#*}"
      _pat="$(printf '%s' "$_pat" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
      [ -n "$_pat" ] || continue
      _pat="${_pat%/}"
      [ -n "$_pat" ] || continue
      fd_args+=(--exclude "$_pat")
    done < "$ignore_file"
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
  fd "${fd_args[@]}" . "$root" 2> /dev/null | LC_ALL=C sort -u | while IFS= read -r p; do
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
  local include_hidden ignore_file
  local exclude_file="${1:-}"
  include_hidden="$(tmux_opt '@pick_session_dir_include_hidden' 'on')"
  ignore_file="$(pick_session_ignore_file)"

  declare -A exclude_exact=()
  if [ -n "$exclude_file" ] && [ -f "$exclude_file" ]; then
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      if printf '%s' "$line" | grep -q $'\t'; then
        local tag p
        IFS=$'\t' read -r tag p <<< "$line"
        [ -n "$p" ] || continue
        exclude_exact["$p"]=1
      else
        exclude_exact["$line"]=1
      fi
    done < "$exclude_file"
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
  fd_args+=(--exclude .git)
  if [ -n "$ignore_file" ] && [ -f "$ignore_file" ]; then
    while IFS= read -r _pat; do
      _pat="${_pat%%#*}"
      _pat="$(printf '%s' "$_pat" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
      [ -n "$_pat" ] || continue
      _pat="${_pat%/}"
      [ -n "$_pat" ] || continue
      fd_args+=(--exclude "$_pat")
    done < "$ignore_file"
  fi

  while IFS= read -r p; do
    [ -z "$p" ] && continue
    p="${p%/}"
    [ "$p" = "$root" ] && continue
    [ -n "${exclude_exact["$p"]+x}" ] && continue
    seeded["$p"]=1
  done < <(fd "${fd_args[@]}" . "$root" 2> /dev/null || true)

  # Seed configured worktree roots (and their home-relative ancestors) so
  # hidden hubs like ~/.local/share are matchable immediately on first refresh.
  local roots_raw wr cur
  roots_raw="$(tmux_opt '@pick_session_worktree_scan_roots' "$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share")"
  IFS=',' read -r -a wt_roots <<< "$roots_raw"
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
  export PICK_SESSION_IGNORE_FILE
  export PICK_SESSION_DIR_INCLUDE_HIDDEN
  export PICK_SESSION_GITHUB_LOGIN

  PICK_SESSION_SCAN_ROOTS="$(tmux_opt '@pick_session_worktree_scan_roots' "$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share")"
  PICK_SESSION_SCAN_DEPTH="$(tmux_opt '@pick_session_worktree_scan_depth' '6')"
  PICK_SESSION_IGNORE_FILE="$(pick_session_ignore_file)"
  PICK_SESSION_QUICK="$quick_mode"
  PICK_SESSION_SESSIONS_ONLY="$sessions_only"
  PICK_SESSION_DIR_INCLUDE_HIDDEN="$(tmux_opt '@pick_session_dir_include_hidden' 'on')"
  PICK_SESSION_GITHUB_LOGIN="$(tmux_opt '@pick_session_github_login' '')"

  python3 -u - << 'PY'
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

def parse_ignore_file_to_excludes(ignore_file: str) -> list[str]:
    """Read a .gitignore-style ignore file and return fd --exclude patterns.

    fd's --ignore-file silently drops multi-component patterns (e.g.
    `.asdf/installs/`).  Converting every pattern to an --exclude flag
    works reliably for both single- and multi-component patterns.
    """
    if not ignore_file or not os.path.isfile(ignore_file):
        return []
    excludes: list[str] = []
    try:
        with open(ignore_file, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                line = line.rstrip("/")
                if line:
                    excludes.append(line)
    except Exception:
        pass
    return excludes

RESET = "\033[0m"

def color(code, text):
    return f"\033[{code}m{text}{RESET}"

def display_session_entry(name):
    return f"{color('38;5;42', '')}  {color('1;38;5;81', name)}"

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

def home_rel(p: str) -> str:
    """Return a stable home-relative identifier without the leading '~/'. """
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

def resolve_path(p):
    try:
        return str(Path(p).resolve())
    except Exception:
        return p

def match_key(*parts):
    return " ".join([ (p or "").strip() for p in parts if (p or "").strip() ])

def normalize_branch_name(br: str) -> str:
    br = (br or "").strip()
    if not br:
        return ""
    if br.lower() in (".invalid", "invalid", "(invalid)"):
        return ""
    return br

def head_branch(gitdir):
    try:
        head = Path(gitdir, "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        if ref.startswith("refs/heads/"):
            return normalize_branch_name(ref[len("refs/heads/") :])
    return ""

def tmux_sanitize_session_name(s: str) -> str:
    s = (s or "").strip().lower()
    if not s:
        return ""
    s = re.sub(r"[^a-z0-9_@|/~-]+", "_", s)
    s = re.sub(r"[.:]+", "_", s)
    # Preserve leading underscores so dot-prefixed paths (e.g. `.backport`) keep
    # their identity as `_backport` instead of collapsing to `backport`.
    s = s.rstrip("_")
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
    # Last-resort fallback for narrow clones where only a topic branch exists
    # locally and remote HEAD is unavailable.
    return "main"

def repo_display_for_root(root: str) -> str:
    # `root` is the computed repo id (home-relative path).
    return (root or "").strip()

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

def parse_owner_from_remote_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith(".git"):
        url = url[: -len(".git")]

    path = ""
    if url.startswith("git@") and ":" in url:
        path = url.split(":", 1)[1]
    elif url.startswith("ssh://git@"):
        # ssh://git@<host>/owner/repo
        parts = url.split("/", 3)
        if len(parts) >= 4:
            path = parts[3]
    elif url.startswith("https://") or url.startswith("http://"):
        parts = url.split("/", 3)
        if len(parts) >= 4:
            path = parts[3]

    if "/" not in path:
        return ""

    return path.split("/", 1)[0].strip()

def remote_names_for_root(root: str) -> dict[str, str]:
    cfg = git_config_path_for_root(root)
    if cfg is None:
        return {}
    remotes = {}
    section = ""
    try:
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r'\[remote "(.+)"\]', line, flags=re.IGNORECASE)
            if m:
                section = m.group(1).strip()
                remotes.setdefault(section, "")
                continue
            if section:
                u = re.match(r"^\s*url\s*=\s*(.+)$", line)
                if u:
                    remotes[section] = parse_owner_from_remote_url(u.group(1).strip())
                    section = ""
    except Exception:
        pass
    return remotes

def branch_from_wrapper_path(root: str, wt_path: str, remotes: dict[str, str]) -> str:
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
                first_owner = (remotes.get(first) or "").strip()
                first_party_owner = (remotes.get("origin") or remotes.get("upstream") or "").strip()
                self_login = (
                    os.environ.get("PICK_SESSION_GITHUB_LOGIN")
                    or os.environ.get("GITHUB_USER")
                    or os.environ.get("USER")
                    or ""
                ).strip()
                if first_owner:
                    if first_party_owner and first_owner == first_party_owner:
                        return rest
                    if self_login and first_owner == self_login:
                        return rest
                return f"{first}__{rest}"
        return rel
    except Exception:
        return ""

def _gitdir_exists(gitdir: str) -> bool:
    try:
        return Path(gitdir).is_dir()
    except Exception:
        return False

def worktree_info(worktree_dir):
    wt = Path(worktree_dir)
    gitp = wt / ".git"
    if gitp.is_dir():
        gitdir = resolve_path(str(gitp))
        root_wt = resolve_path(str(wt))
        br = head_branch(gitdir)
        singular_checkout = not has_linked_worktrees(gitdir)
        if singular_checkout:
            default_br = default_branch_for_repo(root_wt)
            if default_br:
                br = default_br
        try:
            if wt.name in DEFAULT_BRANCH_DIRS:
                br = wt.name
        except Exception:
            pass
        wrapper_root_checkout = find_wrapper_root_checkout_for_path(root_wt, scan_roots_set)
        repo_path = root_wt
        if wrapper_root_checkout and is_git_repo_dir(wrapper_root_checkout):
            remotes = remote_names_for_root(wrapper_root_checkout)
            derived = branch_from_wrapper_path(wrapper_root_checkout, root_wt, remotes)
            if derived:
                br = derived
            repo_path = resolve_path(str(Path(wrapper_root_checkout).parent))
            root_wt = wrapper_root_checkout

        try:
            if wt.name in DEFAULT_BRANCH_DIRS:
                repo_path = resolve_path(str(wt.parent))
        except Exception:
            pass

        repo_id = home_rel(repo_path)
        return {
            "path": resolve_path(str(wt)),
            "root": root_wt,
            "repo_path": repo_path,
            "repo_id": repo_id,
            "gitdir": gitdir,
            "branch": br,
            "stale": False,
        }

    if gitp.is_file():
        try:
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if not first.startswith("gitdir:"): return None
            raw = first.split(":", 1)[1].strip()
            gitdir = resolve_path(str(wt / raw) if not os.path.isabs(raw) else raw)
            stale = not _gitdir_exists(gitdir)
            root_wt = resolve_path(str(wt))
            br = "" if stale else head_branch(gitdir)
            if not stale:
                wrapper_root_checkout = find_wrapper_root_checkout_for_path(root_wt, scan_roots_set)
                repo_path = root_wt
                if wrapper_root_checkout and is_git_repo_dir(wrapper_root_checkout):
                    remotes = remote_names_for_root(wrapper_root_checkout)
                    derived = branch_from_wrapper_path(wrapper_root_checkout, root_wt, remotes)
                    if derived:
                        br = derived
                    repo_path = resolve_path(str(Path(wrapper_root_checkout).parent))
                    root_wt = wrapper_root_checkout
            else:
                repo_path = root_wt
            repo_id = home_rel(repo_path)
            return {
                "path": resolve_path(str(wt)),
                "root": root_wt,
                "repo_path": repo_path,
                "repo_id": repo_id,
                "gitdir": gitdir,
                "branch": br,
                "stale": stale,
            }
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

def scan_for_git_repos(roots, depth, ignore_file):
    candidates = set()
    fd_args = ["fd", "--hidden", "--no-ignore", "--absolute-path", "--type", "f", "--type", "d", "--max-depth", str(depth), "--glob", ".git"]
    for pat in parse_ignore_file_to_excludes(ignore_file):
        fd_args.extend(["--exclude", pat])

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

HOME_DIR_SCAN_DEPTH = 6

def get_home_dirs(root, ignore_file, include_hidden, stop_prefixes=None):
    fd_args = ["fd", "--type", "d", "--max-depth", str(HOME_DIR_SCAN_DEPTH), "--absolute-path"]
    if include_hidden in ("1", "true", "yes", "on"): fd_args.append("--hidden")
    fd_args.extend(["--exclude", ".git"])
    for pat in parse_ignore_file_to_excludes(ignore_file):
        fd_args.extend(["--exclude", pat])
    if stop_prefixes:
        for sp in sorted(set(stop_prefixes)):
            if not sp:
                continue
            if sp == root or sp.startswith(root + os.sep):
                rel = os.path.relpath(sp, root).replace(os.sep, "/").strip("/")
                if rel and rel != ".":
                    fd_args.extend(["--exclude", rel])

    out = subprocess.run(fd_args + [".", root], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]

scan_roots_raw = os.environ.get("PICK_SESSION_SCAN_ROOTS", "").strip()
scan_roots = [resolve_path(os.path.expanduser(x.strip())) for x in scan_roots_raw.split(",") if x.strip()]
scan_roots = [r for r in scan_roots if os.path.isdir(r)]
home_scan_root = resolve_path(os.path.expanduser("~"))
if home_scan_root and os.path.isdir(home_scan_root) and home_scan_root not in scan_roots:
    scan_roots.append(home_scan_root)
scan_roots_set = set(scan_roots)
quick = os.environ.get("PICK_SESSION_QUICK", "").lower() in ("1", "true", "yes", "on")
sessions_only = os.environ.get("PICK_SESSION_SESSIONS_ONLY", "").lower() in ("1", "true", "yes", "on")
ignore_file = os.environ.get("PICK_SESSION_IGNORE_FILE", "").strip()

dir_include_hidden = os.environ.get("PICK_SESSION_DIR_INCLUDE_HIDDEN", "on").lower()

BADGE_STALE = color("2;38;5;214", " ⚠ stale")
BADGE_GONE  = color("2;38;5;196", " ✗ gone")
BADGE_DIRTY = color("2;38;5;214", " ∗")

def _check_dirty(wt_path: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", wt_path, "status", "--porcelain", "--untracked-files=no"],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=10,
        )
        return bool((r.stdout or "").strip())
    except Exception:
        return False

def status_badge(flags: set) -> str:
    if "gone" in flags:
        return BADGE_GONE
    if "stale" in flags:
        return BADGE_STALE
    if "dirty" in flags:
        return BADGE_DIRTY
    return ""

def status_meta_flags(flags: set) -> str:
    return ",".join(sorted(flags)) if flags else ""

groups = {}
def ensure_group(repo_id: str, root_checkout: str, repo_path: str):
    rid = (repo_id or "").strip()
    if rid not in groups:
        groups[rid] = { "repo_id": rid, "root_checkout": root_checkout, "repo_path": repo_path, "wt_map": {}, "sessions_by_wt": {} }

wt_status: dict[str, set] = {}

# 1. Discover worktrees
if not quick and not sessions_only and shutil.which("fd"):
    for wt_dir in scan_for_git_repos(scan_roots, int(os.environ.get("PICK_SESSION_SCAN_DEPTH", 6)), ignore_file):
        info = worktree_info(wt_dir)
        if info:
            rid = info.get("repo_id", "")
            ensure_group(rid, info.get("root", ""), info.get("repo_path", ""))
            groups[rid]["wt_map"][info["path"]] = { "branch": info.get("branch", ""), "repo_id": rid }
            flags: set[str] = set()
            if not os.path.isdir(info["path"]):
                flags.add("gone")
            elif info.get("stale"):
                flags.add("stale")
            if flags:
                wt_status[info["path"]] = flags

# 1b. Parallel dirty scan for worktrees that aren't already stale/gone.
_dirty_candidates = [
    p for rid in groups for p in groups[rid]["wt_map"]
    if p not in wt_status
]
if _dirty_candidates:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        _futures = { pool.submit(_check_dirty, p): p for p in _dirty_candidates }
        for fut in concurrent.futures.as_completed(_futures):
            p = _futures[fut]
            try:
                if fut.result():
                    wt_status.setdefault(p, set()).add("dirty")
            except Exception:
                pass

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
            rid = info.get("repo_id", "")
            ensure_group(rid, info.get("root", ""), info.get("repo_path", ""))
            groups[rid]["wt_map"].setdefault(info["path"], { "branch": info.get("branch", ""), "repo_id": rid })
            groups[rid]["sessions_by_wt"].setdefault(info["path"], []).append(name)

# 3. Output results
exclude_exact = set()
exclude_worktree_roots = set()

def emit_sessions_and_worktrees():
    for rid in sorted(groups.keys(), key=lambda r: repo_display_for_root(r).lower()):
        repo = repo_display_for_root(rid)
        root_checkout = groups[rid].get("root_checkout", "")
        wt_map = groups[rid]["wt_map"]
        sessions_by_wt = groups[rid]["sessions_by_wt"]

        # Sessions first
        for wt_path in sorted(wt_map.keys()):
            for sess_name in sorted(sessions_by_wt.get(wt_path, [])):
                br = wt_map.get(wt_path, {}).get("branch", "")
                expected = tmux_sanitize_session_name(f"{repo}|{br}" if br else repo)
                meta = f"sess_root:{br}" if wt_path == root_checkout else f"sess_wt:{br}"
                meta += f"|repo={repo}"
                if expected and sess_name != expected: meta += f"|expected={expected}"
                flags = wt_status.get(wt_path, set())
                sf = status_meta_flags(flags)
                if sf: meta += f"|status={sf}"
                disp = display_session_entry(sess_name) + status_badge(flags)
                mk = match_key(sess_name, expected, repo, br)
                print(f"{disp}\tsession\t{wt_path}\t{meta}\t{sess_name}\t{mk}")
                exclude_worktree_roots.add(wt_path)

        # Worktrees second (skip entirely in sessions-only mode).
        if not sessions_only:
            for wt_path in sorted(wt_map.keys()):
                if wt_path in sessions_by_wt: continue
                br = wt_map[wt_path].get("branch", "")
                meta = f"wt_root:{br}" if wt_path == root_checkout else f"wt:{br}"
                meta += f"|repo={repo}"
                flags = wt_status.get(wt_path, set())
                sf = status_meta_flags(flags)
                if sf: meta += f"|status={sf}"
                wt_name = f"{repo}|{br}" if br else repo
                mk = match_key(wt_name, Path(wt_path).name, tildefy(wt_path))
                print(f"{display_worktree_entry(tildefy(wt_path))}{status_badge(flags)}\tworktree\t{wt_path}\t{meta}\t{root_checkout}\t{mk}")
                exclude_worktree_roots.add(wt_path)

emit_sessions_and_worktrees()

# 5. Directories
if not sessions_only:
    # Directory output combines:
    # - configured scan roots (e.g. ~/work, ~/code)
    # - wrapper directories for detected repos
    # - depth-limited home directories (fd scan under $HOME)
    wrapper_dirs = set()
    for rid in groups.keys():
        rp = (groups.get(rid, {}) or {}).get("repo_path", "")
        if rp:
            wrapper_dirs.add(resolve_path(rp))
    for r in scan_roots:
        if r:
            wrapper_dirs.add(resolve_path(r))
    home_worktree_prefixes = []
    home_worktree_seen = set()
    for wt in exclude_worktree_roots:
        if not wt:
            continue
        rwt = resolve_path(wt)
        if not (rwt == home or rwt.startswith(home + os.sep)):
            continue
        if rwt in home_worktree_seen:
            continue
        home_worktree_seen.add(rwt)
        home_worktree_prefixes.append(rwt)
    home_worktree_prefixes.sort()
    if shutil.which("fd"):
        for p in get_home_dirs(home, ignore_file, dir_include_hidden, home_worktree_prefixes):
            rp = resolve_path(p)
            if rp:
                wrapper_dirs.add(rp)
    wrapper_dirs.add(resolve_path(home))
    ordered_dirs = []
    seen_dirs = set()
    for p in scan_roots:
        rp = resolve_path(p) if p else ""
        if rp and rp in wrapper_dirs and rp not in seen_dirs:
            ordered_dirs.append(rp)
            seen_dirs.add(rp)
    for p in sorted(wrapper_dirs):
        if p and p not in seen_dirs:
            ordered_dirs.append(p)
            seen_dirs.add(p)
    for p in ordered_dirs:
        if not p or p in exclude_worktree_roots:
            continue
        if any(p == wt or p.startswith(wt + os.sep) for wt in home_worktree_prefixes):
            continue
        base = Path(p).name
        if p in scan_roots_set:
            # Repeat the basename for scan roots so plain queries like `code` or
            # `work` rank the root above descendants under that tree.
            mk = match_key(base, base, base + "/", tildefy(p), p)
        else:
            mk = match_key(base, tildefy(p), p)
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
