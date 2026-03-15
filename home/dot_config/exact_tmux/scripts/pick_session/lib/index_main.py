#!/usr/bin/env python3
import concurrent.futures
import json
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path

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
    return f"{color('38;5;42', '')}  {color('1;38;5;81', name)}"


def display_worktree_entry(path_display):
    return f"{color('38;5;214', '')}  {color('38;5;221', path_display)}"


def display_dir_entry(path_display):
    return f"{color('38;5;75', '')}  {color('38;5;110', path_display)}"


def tildefy(p):
    home = os.path.expanduser("~")
    if p == home:
        return "~"
    if p.startswith(home + "/"):
        return "~/" + p[len(home) + 1 :]
    return p


def home_rel(p: str) -> str:
    """Return a stable home-relative identifier without the leading '~/'."""
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
    return " ".join([(p or "").strip() for p in parts if (p or "").strip()])


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


def nwo_from_url(url: str) -> str:
    """Extract owner/repo (name-with-owner) from a git remote URL."""
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith(".git"):
        url = url[: -len(".git")]

    path = ""
    if url.startswith("git@") and ":" in url:
        path = url.split(":", 1)[1]
    elif url.startswith("ssh://git@"):
        parts = url.split("/", 3)
        if len(parts) >= 4:
            path = parts[3]
    elif url.startswith("https://") or url.startswith("http://"):
        parts = url.split("/", 3)
        if len(parts) >= 4:
            path = parts[3]

    if "/" not in path:
        return ""
    segments = path.split("/")
    if len(segments) >= 2:
        return f"{segments[0]}/{segments[1]}"
    return ""


DEFAULT_BRANCH_DIRS = {"main", "master", "trunk", "develop", "dev"}
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
            if not first.startswith("gitdir:"):
                return None
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
        except Exception:
            pass
    return None


def find_worktree_root_for_path(p, stop_at):
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


def scan_for_git_repos(roots, depth, ignore_file):
    candidates = set()
    fd_args = [
        "fd",
        "--hidden",
        "--no-ignore",
        "--absolute-path",
        "--type",
        "f",
        "--type",
        "d",
        "--max-depth",
        str(depth),
        "--glob",
        ".git",
    ]
    for pat in parse_ignore_file_to_excludes(ignore_file):
        fd_args.extend(["--exclude", pat])

    for r in roots:
        out = subprocess.run(
            fd_args + [r], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        ).stdout
        for gitp in out.splitlines():
            p = gitp.strip()
            if p:
                candidates.add(resolve_path(str(Path(p).parent)))

    accepted = []
    for wt_dir in sorted(candidates, key=lambda p: (len(p), p)):
        if not any(wt_dir == a or wt_dir.startswith(a + os.sep) for a in accepted):
            accepted.append(wt_dir)
    return accepted


HOME_DIR_SCAN_DEPTH = 6


def get_home_dirs(root, ignore_file, include_hidden, stop_prefixes=None):
    fd_args = ["fd", "--type", "d", "--max-depth", str(HOME_DIR_SCAN_DEPTH), "--absolute-path"]
    if include_hidden in ("1", "true", "yes", "on"):
        fd_args.append("--hidden")
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

    out = subprocess.run(
        fd_args + [".", root], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    ).stdout
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

BADGE_STALE = color("2;38;5;214", " stale")
BADGE_GONE = color("2;38;5;196", " gone")
BADGE_DIRTY = color("2;38;5;214", " *")

BADGE_PR_OPEN = color("38;5;42", " \uf407")
BADGE_PR_MERGED = color("38;5;141", " \uf407")
BADGE_PR_CLOSED = color("38;5;196", " \uf4dc")
BADGE_ISSUE_OPEN = color("38;5;42", " \uf41b")
BADGE_ISSUE_CLOSED = color("38;5;141", " \uf41d")

_ISSUE_SUFFIX_RE = re.compile(r"[-/](\d+)$")


def _wt_issue_number(wt_path: str) -> str:
    """Read issue number from worktree-local git config (comma.w.issue.number).

    This is set by ,w when creating worktrees linked to issues via gh-dash.
    Zero-cost local lookup — no network call.
    """
    try:
        r = subprocess.run(
            ["git", "-C", wt_path, "config", "--worktree", "--get", "comma.w.issue.number"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        num = (r.stdout or "").strip()
        if num and num.isdigit():
            return num
    except Exception:
        pass
    return ""


def _wt_issue_repo(wt_path: str) -> str:
    """Read repo NWO from worktree-local git config (comma.w.issue.repo)."""
    try:
        r = subprocess.run(
            ["git", "-C", wt_path, "config", "--worktree", "--get", "comma.w.issue.repo"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def extract_issue_number(branch: str) -> str:
    """Extract a GitHub issue number from a branch name suffix.

    Matches -NNN or /NNN at the end of the branch name, consistent with
    ,gh-issuew heuristics.
    """
    m = _ISSUE_SUFFIX_RE.search(branch or "")
    return m.group(1) if m else ""


def _gh_pr_for_wt(wt_path: str, nwo: str) -> dict | None:
    """Query gh for the PR associated with the current branch at wt_path.

    Uses `gh pr view` (no args) which infers the branch from git context.
    This is the same fast-path that ,gh-prw uses and handles forks correctly.
    """
    if not shutil.which("gh"):
        return None
    try:
        args = ["gh", "pr", "view", "--json", "number,state,url"]
        if nwo:
            args.extend(["-R", nwo])
        r = subprocess.run(
            args, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=15, cwd=wt_path
        )
        if r.returncode != 0 or not (r.stdout or "").strip():
            return None
        return json.loads(r.stdout)
    except Exception:
        pass
    return None


def _gh_issue_state(wt_path: str, issue_num: str, nwo: str) -> dict | None:
    """Query gh for an issue by number. Returns {number, state, url} or None."""
    if not shutil.which("gh"):
        return None
    try:
        args = ["gh", "issue", "view", issue_num, "--json", "number,state,url"]
        if nwo:
            args.extend(["-R", nwo])
        r = subprocess.run(
            args, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=15, cwd=wt_path
        )
        if r.returncode != 0 or not (r.stdout or "").strip():
            return None
        return json.loads(r.stdout)
    except Exception:
        pass
    return None


def _lookup_gh_info(wt_path: str, branch: str, nwo: str) -> dict:
    """Return {"pr": {...} | None, "issue": {...} | None} for a worktree.

    Issue number resolution (all local, zero network cost):
      1. comma.w.issue.number worktree metadata (set by ,w / gh-dash)
      2. Branch name suffix heuristic (-NNN or /NNN)
    PR resolution: gh pr view (single network call, infers branch from cwd).
    Issue state: gh issue view (single network call, only if number found).
    """
    result: dict = {"pr": None, "issue": None}
    if not branch:
        return result
    result["pr"] = _gh_pr_for_wt(wt_path, nwo)
    issue_num = _wt_issue_number(wt_path) or extract_issue_number(branch)
    if issue_num:
        issue_nwo = _wt_issue_repo(wt_path) or nwo
        result["issue"] = _gh_issue_state(wt_path, issue_num, issue_nwo)
    return result


def pr_badge(state: str) -> str:
    s = (state or "").upper()
    if s == "OPEN":
        return BADGE_PR_OPEN
    if s == "MERGED":
        return BADGE_PR_MERGED
    if s == "CLOSED":
        return BADGE_PR_CLOSED
    return ""


def issue_badge(state: str) -> str:
    s = (state or "").upper()
    if s == "OPEN":
        return BADGE_ISSUE_OPEN
    if s in ("CLOSED", "COMPLETED", "NOT_PLANNED"):
        return BADGE_ISSUE_CLOSED
    return ""


def gh_badges(gh_info: dict | None) -> str:
    if not gh_info:
        return ""
    out = ""
    pr = gh_info.get("pr")
    if pr:
        out += pr_badge(pr.get("state", ""))
    issue = gh_info.get("issue")
    if issue:
        out += issue_badge(issue.get("state", ""))
    return out


def gh_meta(gh_info: dict | None) -> str:
    if not gh_info:
        return ""
    parts = []
    pr = gh_info.get("pr")
    if pr and pr.get("number"):
        parts.append(f"pr={pr['number']}:{pr.get('state', '')}:{pr.get('url', '')}")
    issue = gh_info.get("issue")
    if issue and issue.get("number"):
        parts.append(f"issue={issue['number']}:{issue.get('state', '')}:{issue.get('url', '')}")
    return "|".join(parts)


def _check_dirty(wt_path: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", wt_path, "status", "--porcelain", "--untracked-files=no"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
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
        groups[rid] = {
            "repo_id": rid,
            "root_checkout": root_checkout,
            "repo_path": repo_path,
            "wt_map": {},
            "sessions_by_wt": {},
        }


wt_status: dict[str, set] = {}

# 1. Discover worktrees
if not quick and not sessions_only and shutil.which("fd"):
    for wt_dir in scan_for_git_repos(scan_roots, int(os.environ.get("PICK_SESSION_SCAN_DEPTH", 6)), ignore_file):
        info = worktree_info(wt_dir)
        if info:
            rid = info.get("repo_id", "")
            ensure_group(rid, info.get("root", ""), info.get("repo_path", ""))
            groups[rid]["wt_map"][info["path"]] = {"branch": info.get("branch", ""), "repo_id": rid}
            flags: set[str] = set()
            if not os.path.isdir(info["path"]):
                flags.add("gone")
            elif info.get("stale"):
                flags.add("stale")
            if flags:
                wt_status[info["path"]] = flags

# 1b. Parallel dirty scan for worktrees that aren't already stale/gone.
_dirty_candidates = [p for rid in groups for p in groups[rid]["wt_map"] if p not in wt_status]
if _dirty_candidates:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        _futures = {pool.submit(_check_dirty, p): p for p in _dirty_candidates}
        for fut in concurrent.futures.as_completed(_futures):
            p = _futures[fut]
            try:
                if fut.result():
                    wt_status.setdefault(p, set()).add("dirty")
            except Exception:
                pass

# 1c. Parallel GitHub PR/issue lookup for non-default branches.
# Skips stale/gone worktrees (no valid git context).
wt_gh_info: dict[str, dict] = {}
_gh_candidates: list[tuple[str, str, str]] = []
_nwo_cache: dict[str, str] = {}
for rid in groups:
    root_checkout = groups[rid].get("root_checkout", "")
    if root_checkout and root_checkout not in _nwo_cache:
        url = origin_url_for_root(root_checkout)
        _nwo_cache[root_checkout] = nwo_from_url(url)
    nwo = _nwo_cache.get(root_checkout, "")
    for wt_path, wt_data in groups[rid]["wt_map"].items():
        br = wt_data.get("branch", "")
        flags = wt_status.get(wt_path, set())
        if br and br not in DEFAULT_BRANCH_DIRS and not (flags & {"gone", "stale"}):
            _gh_candidates.append((wt_path, br, nwo))
if _gh_candidates and shutil.which("gh"):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        _gh_futures = {pool.submit(_lookup_gh_info, p, br, nwo): p for p, br, nwo in _gh_candidates}
        for fut in concurrent.futures.as_completed(_gh_futures):
            p = _gh_futures[fut]
            try:
                info = fut.result()
                if info and (info.get("pr") or info.get("issue")):
                    wt_gh_info[p] = info
            except Exception:
                pass

# 2. Add sessions
current_session = subprocess.run(
    ["tmux", "display-message", "-p", "#S"], check=False, stdout=subprocess.PIPE, text=True
).stdout.strip()
sess_out = subprocess.run(
    ["tmux", "list-sessions", "-F", "#{session_name}\t#{session_path}"], check=False, stdout=subprocess.PIPE, text=True
).stdout
sessions = []
home = os.path.expanduser("~")
for row in sess_out.splitlines():
    if not row:
        continue
    name, _, path = row.partition("\t")
    name, path = name.strip(), path.strip()
    rp = resolve_path(path)
    sessions.append({"name": name, "path": path, "rpath": rp, "is_current": (name == current_session)})
    wt_root = find_worktree_root_for_path(rp, home)
    if wt_root:
        info = worktree_info(wt_root)
        if info:
            rid = info.get("repo_id", "")
            ensure_group(rid, info.get("root", ""), info.get("repo_path", ""))
            groups[rid]["wt_map"].setdefault(info["path"], {"branch": info.get("branch", ""), "repo_id": rid})
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
                if expected and sess_name != expected:
                    meta += f"|expected={expected}"
                flags = wt_status.get(wt_path, set())
                sf = status_meta_flags(flags)
                if sf:
                    meta += f"|status={sf}"
                ghi = wt_gh_info.get(wt_path)
                gm = gh_meta(ghi)
                if gm:
                    meta += f"|{gm}"
                disp = display_session_entry(sess_name) + status_badge(flags) + gh_badges(ghi)
                mk = match_key(sess_name, expected, repo, br)
                print(f"{disp}\tsession\t{wt_path}\t{meta}\t{sess_name}\t{mk}")
                exclude_worktree_roots.add(wt_path)

        # Worktrees second (skip entirely in sessions-only mode).
        if not sessions_only:
            for wt_path in sorted(wt_map.keys()):
                if wt_path in sessions_by_wt:
                    continue
                br = wt_map[wt_path].get("branch", "")
                meta = f"wt_root:{br}" if wt_path == root_checkout else f"wt:{br}"
                meta += f"|repo={repo}"
                flags = wt_status.get(wt_path, set())
                sf = status_meta_flags(flags)
                if sf:
                    meta += f"|status={sf}"
                ghi = wt_gh_info.get(wt_path)
                gm = gh_meta(ghi)
                if gm:
                    meta += f"|{gm}"
                wt_name = f"{repo}|{br}" if br else repo
                mk = match_key(wt_name, Path(wt_path).name, tildefy(wt_path))
                print(
                    f"{display_worktree_entry(tildefy(wt_path))}{status_badge(flags)}{gh_badges(ghi)}\tworktree\t{wt_path}\t{meta}\t{root_checkout}\t{mk}"
                )
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
