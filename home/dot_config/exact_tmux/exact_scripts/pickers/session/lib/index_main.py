#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

# If the consumer (fzf) exits early, don't spam tracebacks.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

threads_env = os.environ.get("PICK_SESSION_THREADS")
if threads_env and threads_env.isdigit():
    WORKER_THREADS = max(1, int(threads_env))
else:
    WORKER_THREADS = max(1, (os.cpu_count() or 2) // 2)
WORKER_THREADS_STR = str(WORKER_THREADS)


def parse_ignore_file_to_excludes(ignore_file: str) -> list[str]:
    """Read a .gitignore-style ignore file and return fd --exclude patterns.

    fd's --ignore-file silently drops multi-component patterns (e.g.
    `.local/share/mise/installs/`). Converting every pattern to an --exclude flag
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


ICON_SESSION = ""
ICON_WORKTREE = ""
ICON_DIR = ""


def display_session_entry(name):
    return f"{color('38;5;42', ICON_SESSION)}  {color('1;38;5;81', name)}"


def display_dir_session_entry(path_display):
    return f"{color('38;5;42', ICON_SESSION)}  {color('1;38;5;81', path_display)}"


def display_worktree_entry(path_display):
    return f"{color('38;5;214', ICON_WORKTREE)}  {color('38;5;221', path_display)}"


def display_dir_entry(path_display):
    return f"{color('38;5;75', ICON_DIR)}  {color('38;5;110', path_display)}"


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


def canonical_dir_session_name(path: str) -> str:
    if not path:
        return ""
    home_path = resolve_path(os.path.expanduser("~"))
    rp = resolve_path(path)
    if rp == home_path:
        return "home"
    return tmux_sanitize_session_name(Path(rp).name or rp)


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

    # Fallback: get all refs once and check candidates
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "show-ref"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout
        refs = {line.split()[1] for line in out.splitlines() if line.strip()}
    except Exception:
        refs = set()

    for cand in DEFAULT_BRANCH_DIRS_ORDER:
        for ref in (f"refs/heads/{cand}", f"refs/remotes/origin/{cand}", f"refs/remotes/upstream/{cand}"):
            if ref in refs:
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
        "--threads",
        WORKER_THREADS_STR,
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
    fd_args = [
        "fd",
        "--type",
        "d",
        "--max-depth",
        str(HOME_DIR_SCAN_DEPTH),
        "--absolute-path",
        "--threads",
        WORKER_THREADS_STR,
    ]
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
BADGE_DIRTY = color("1;38;5;214", " *")

BADGE_PR_OPEN = color("38;5;42", " ")
BADGE_PR_MERGED = color("38;5;141", " ")
BADGE_PR_CLOSED = color("38;5;196", " ")
BADGE_ISSUE_OPEN = color("38;5;42", " ")
BADGE_ISSUE_CLOSED = color("38;5;141", " ")

BADGE_REVIEW_APPROVED = color("38;5;42", " \u2713")
BADGE_REVIEW_CHANGES = color("38;5;196", " \u2717")
BADGE_REVIEW_PENDING = color("38;5;214", " \u25cb")

BADGE_CI_SUCCESS = color("38;5;42", "\u25cf")
BADGE_CI_FAILURE = color("38;5;196", "\u25cf")
BADGE_CI_PENDING = color("38;5;220", "\u25cf")

GH_CACHE_FILE = Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))) / "tmux" / "pick_session_gh.json"
GH_PICKER_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))) / "tmux"
GH_TTL_OPEN = 600
GH_TTL_TERMINAL = 86400
GH_TTL_MISS = 3600
GH_PICKER_TTL = 300


def _load_gh_picker_ci_index() -> dict[str, dict[int, tuple[str, str]]]:
    """Read CI + review status from the gh picker TSV caches (work + home).

    Returns {nwo: {pr_number: (review, ci)}} from the metadata column (col 7).
    TSV format: display\\tkind\\trepo\\tnumber\\turl\\tmatchkey\\treview,ci
    """
    index: dict[str, dict[int, tuple[str, str]]] = {}
    now = time.time()
    for mode in ("work", "home"):
        cache = GH_PICKER_CACHE_DIR / f"gh_picker_{mode}.tsv"
        if not cache.is_file():
            continue
        try:
            age = now - cache.stat().st_mtime
            if age < 0 or age > GH_PICKER_TTL:
                continue
        except Exception:
            continue
        try:
            for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.split("\t")
                if len(parts) < 5:
                    continue
                kind = parts[1]
                if kind != "pr":
                    continue
                repo = parts[2]
                try:
                    num = int(parts[3])
                except (ValueError, IndexError):
                    continue
                review = ""
                ci = ""
                if len(parts) >= 7 and parts[6]:
                    meta_parts = parts[6].split(",", 1)
                    review = meta_parts[0] if meta_parts else ""
                    ci = meta_parts[1] if len(meta_parts) > 1 else ""
                index.setdefault(repo, {})[num] = (review, ci)
        except Exception:
            continue
    return index


_gh_picker_ci_index: dict[str, dict[int, tuple[str, str]]] | None = None


def _get_gh_picker_meta(nwo: str, pr_number: int) -> tuple[str, str]:
    """Look up (review, ci) for a PR from the gh picker cache. Zero-cost local read."""
    global _gh_picker_ci_index
    if _gh_picker_ci_index is None:
        _gh_picker_ci_index = _load_gh_picker_ci_index()
    return _gh_picker_ci_index.get(nwo, {}).get(pr_number, ("", ""))


def _gh_cache_load() -> dict[str, Any]:
    try:
        if GH_CACHE_FILE.is_file():
            return json.loads(GH_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _gh_cache_save(data: dict[str, Any]) -> None:
    """Atomic write: temp file + os.replace so a crash never corrupts the cache."""
    try:
        GH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=GH_CACHE_FILE.parent, suffix=".tmp")
        closed = False
        try:
            os.write(fd, json.dumps(data, separators=(",", ":")).encode("utf-8"))
            os.close(fd)
            closed = True
            os.replace(tmp, GH_CACHE_FILE)
        except BaseException:
            if not closed:
                os.close(fd)
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception:
        pass


_TERMINAL_PR = frozenset({"MERGED", "CLOSED"})
_TERMINAL_ISSUE = frozenset({"CLOSED", "COMPLETED", "NOT_PLANNED"})


def _gh_cache_fresh(entry: dict[str, Any], branch: str, nwo: str, now: float) -> bool:
    """Return True if a cache entry is still valid."""
    if not entry or entry.get("branch") != branch or entry.get("nwo") != nwo:
        return False
    age = now - entry.get("ts", 0)
    pr = entry.get("pr")
    issue = entry.get("issue")
    if not pr and not issue:
        return age < GH_TTL_MISS
    all_settled = (not pr or (pr.get("state") or "").upper() in _TERMINAL_PR) and (
        not issue or (issue.get("state") or "").upper() in _TERMINAL_ISSUE
    )
    return age < (GH_TTL_TERMINAL if all_settled else GH_TTL_OPEN)


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


def _gh_pr_for_wt(wt_path: str, nwo: str) -> dict[str, Any] | None:
    """Query gh for the PR associated with the current branch at wt_path.

    Uses `gh pr view` (no args) which infers the branch from git context.
    This is the same fast-path that ,gh-prw uses and handles forks correctly.
    The -R flag is intentionally omitted: it requires an explicit branch
    argument and breaks the automatic branch inference that gh performs
    from the local git checkout.

    Also fetches closingIssuesReferences so callers can resolve linked
    issues without an extra network call.
    """
    if not shutil.which("gh"):
        return None
    try:
        r = subprocess.run(
            ["gh", "pr", "view", "--json", "number,state,url,reviewDecision,closingIssuesReferences"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
            cwd=wt_path,
        )
        if r.returncode != 0 or not (r.stdout or "").strip():
            return None
        return json.loads(r.stdout)
    except Exception:
        pass
    return None


def _gh_issue_state(wt_path: str, issue_num: str, repo_override: str = "") -> dict[str, Any] | None:
    """Query gh for an issue by number. Returns {number, state, url} or None.

    Uses cwd to let gh resolve the repo from git context (handles forks
    correctly).  Only passes -R when an explicit repo override is provided
    (e.g. from comma.w.issue.repo worktree config).
    """
    if not shutil.which("gh"):
        return None
    try:
        args = ["gh", "issue", "view", issue_num, "--json", "number,state,url"]
        if repo_override:
            args.extend(["-R", repo_override])
        r = subprocess.run(
            args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
            cwd=wt_path,
        )
        if r.returncode != 0 or not (r.stdout or "").strip():
            return None
        return json.loads(r.stdout)
    except Exception:
        pass
    return None


def _closing_issue_from_pr(pr_data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract the first closing issue from a PR's closingIssuesReferences.

    Returns {number, url, nwo} or None.  ``nwo`` is the ``owner/repo`` of the
    issue's repository (extracted from the response) so callers can pass it as
    an explicit ``-R`` override to ``gh issue view`` — this handles cross-repo
    closing issues and fork workflows where cwd would resolve to the wrong repo.
    """
    if not pr_data:
        return None
    refs = pr_data.get("closingIssuesReferences") or []
    for ref in refs:
        num = ref.get("number")
        url = ref.get("url", "")
        if num:
            repo = ref.get("repository") or {}
            owner = (repo.get("owner") or {}).get("login", "")
            name = repo.get("name", "")
            nwo = f"{owner}/{name}" if owner and name else ""
            return {"number": num, "url": url, "nwo": nwo}
    return None


_TRIVIAL_STATUS_RE = re.compile(
    r"^(CLA|prbot:|renovate/|license/|security/|buildkite/docs)",
    re.IGNORECASE,
)
_TRIVIAL_CHECK_RE = re.compile(
    r"^(Analyze new dependencies|docs-preview)",
    re.IGNORECASE,
)


def _extract_ci_state(commit_node: dict[str, Any], repo_name: str) -> str:
    """Extract meaningful CI state from status check contexts.

    Priority:
    1. StatusContext named '{repo_name}-ci' (e.g. 'kibana-ci')
    2. Buildkite StatusContext for the repo (excluding docs)
    3. CheckRun whose name contains the repo name (excluding docs)
    4. Aggregate state of non-trivial checks (excludes bots/CLA/docs/snyk)
    5. Empty string if only trivial contexts exist (no real CI ran)
    """
    try:
        rollup = commit_node["statusCheckRollup"]
    except (KeyError, TypeError):
        return ""
    if rollup is None:
        return ""

    # Never show green when the rollup is failing. This prevents a single
    # "canonical" success context (e.g. kibana-ci) from masking other failing
    # required checks.
    overall_state = (rollup.get("state") or "").upper()
    if overall_state in ("FAILURE", "ERROR"):
        return "FAILURE"

    contexts = []
    try:
        contexts = (rollup.get("contexts") or {}).get("nodes") or []
    except (AttributeError, TypeError):
        pass

    if not contexts:
        return rollup.get("state", "")

    canonical = f"{repo_name}-ci"
    for ctx in contexts:
        if ctx.get("__typename") == "StatusContext" and ctx.get("context") == canonical:
            return ctx.get("state", "")

    for ctx in contexts:
        if ctx.get("__typename") != "StatusContext":
            continue
        name = ctx.get("context", "")
        if name.startswith("buildkite/") and repo_name in name and "docs" not in name:
            return ctx.get("state", "")

    for ctx in contexts:
        if ctx.get("__typename") != "CheckRun":
            continue
        name = ctx.get("name", "")
        if repo_name in name.lower() and "docs" not in name.lower():
            conclusion = ctx.get("conclusion", "")
            status = ctx.get("status", "")
            if conclusion == "SUCCESS":
                return "SUCCESS"
            if conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED"):
                return "FAILURE"
            if status in ("IN_PROGRESS", "QUEUED", "WAITING"):
                return "PENDING"

    has_failure = False
    has_pending = False
    has_success = False
    real_count = 0
    for ctx in contexts:
        typename = ctx.get("__typename", "")
        name = ctx.get("context", "") or ctx.get("name", "")
        if typename == "StatusContext" and _TRIVIAL_STATUS_RE.search(name):
            continue
        if typename == "CheckRun" and _TRIVIAL_CHECK_RE.search(name):
            continue
        real_count += 1
        if typename == "StatusContext":
            st = (ctx.get("state") or "").upper()
            if st == "FAILURE":
                has_failure = True
            elif st == "PENDING":
                has_pending = True
            elif st == "SUCCESS":
                has_success = True
        elif typename == "CheckRun":
            conclusion = (ctx.get("conclusion") or "").upper()
            status = (ctx.get("status") or "").upper()
            if conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED"):
                has_failure = True
            elif conclusion == "SUCCESS":
                has_success = True
            elif status in ("IN_PROGRESS", "QUEUED", "WAITING"):
                has_pending = True

    if real_count == 0:
        return ""
    if has_failure:
        return "FAILURE"
    if has_pending:
        return "PENDING"
    if has_success:
        return "SUCCESS"
    return ""


def _batch_ci_graphql(pr_numbers: dict[str, set[int]]) -> dict[str, dict[int, tuple[str, str]]]:
    """Single batched GraphQL call for reviewDecision + CI status.

    Returns {nwo: {number: (review, ci), ...}}.
    """
    aliases: list[str] = []
    alias_map: dict[str, tuple[str, int]] = {}
    for nwo, nums in pr_numbers.items():
        owner, name = nwo.split("/", 1) if "/" in nwo else ("", nwo)
        if not owner:
            continue
        for n in nums:
            alias = f"_p{owner}_{name}_{n}".replace("-", "_")
            aliases.append(
                f'{alias}: repository(owner: "{owner}", name: "{name}") '
                f"{{ pullRequest(number: {n}) {{ number reviewDecision "
                f"commits(last:1) {{ nodes {{ commit {{ statusCheckRollup {{ state "
                f"contexts(first:100) {{ nodes {{ "
                f"... on CheckRun {{ __typename name conclusion status }} "
                f"... on StatusContext {{ __typename context state }} "
                f"}} }} }} }} }} }} }} }}"
            )
            alias_map[alias] = (nwo, n)
    if not aliases:
        return {}
    query = "query { " + " ".join(aliases) + " }"
    try:
        result = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if not result.stdout.strip():
            return {}
        data = json.loads(result.stdout).get("data", {})
    except Exception:
        return {}
    out: dict[str, dict[int, tuple[str, str]]] = {}
    for alias, (nwo, num) in alias_map.items():
        node = (data.get(alias) or {}).get("pullRequest")
        if not node:
            continue
        review = node.get("reviewDecision", "")
        repo_name = nwo.split("/", 1)[-1] if "/" in nwo else nwo
        ci_state = ""
        try:
            commit = node["commits"]["nodes"][0]["commit"]
            ci_state = _extract_ci_state(commit, repo_name)
        except (KeyError, IndexError, TypeError):
            pass
        out.setdefault(nwo, {})[num] = (review, ci_state)
    return out


def _lookup_gh_info(wt_path: str, branch: str, nwo: str) -> dict[str, Any]:
    """Return {"pr": {...} | None, "issue": {...} | None} for a worktree.

    Issue number resolution order:
      1. comma.w.issue.number worktree metadata (set by ,w / gh-dash)
      2. Branch name suffix heuristic (-NNN or /NNN)
      3. PR closingIssuesReferences (linked via "Closes #N" in PR body)
    PR resolution: gh pr view (single network call, infers branch from cwd).
    Issue state: gh issue view (single network call, only if number found).
    """
    result: dict[str, Any] = {"pr": None, "issue": None}
    if not branch:
        return result
    pr_data = _gh_pr_for_wt(wt_path, nwo)
    if pr_data:
        pr_num = pr_data["number"]
        picker_review, picker_ci = _get_gh_picker_meta(nwo, pr_num) if nwo else ("", "")
        result["pr"] = {
            "number": pr_num,
            "state": pr_data.get("state", ""),
            "url": pr_data.get("url", ""),
            "review": pr_data.get("reviewDecision", "") or picker_review,
            "ci": picker_ci,
        }
    issue_num = _wt_issue_number(wt_path) or extract_issue_number(branch)
    issue_repo_override = _wt_issue_repo(wt_path)
    if not issue_num:
        closing = _closing_issue_from_pr(pr_data)
        if closing:
            issue_num = str(closing["number"])
            if not issue_repo_override and closing.get("nwo"):
                issue_repo_override = closing["nwo"]
    if issue_num:
        result["issue"] = _gh_issue_state(wt_path, issue_num, issue_repo_override)
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


def review_badge(decision: str) -> str:
    s = (decision or "").upper()
    if s == "APPROVED":
        return BADGE_REVIEW_APPROVED
    if s == "CHANGES_REQUESTED":
        return BADGE_REVIEW_CHANGES
    if s == "REVIEW_REQUIRED":
        return BADGE_REVIEW_PENDING
    return ""


def issue_badge(state: str) -> str:
    s = (state or "").upper()
    if s == "OPEN":
        return BADGE_ISSUE_OPEN
    if s in ("CLOSED", "COMPLETED", "NOT_PLANNED", "MERGED"):
        return BADGE_ISSUE_CLOSED
    return ""


def ci_badge(state: str) -> str:
    s = (state or "").upper()
    if s == "SUCCESS":
        return BADGE_CI_SUCCESS
    if s in ("FAILURE", "ERROR"):
        return BADGE_CI_FAILURE
    if s in ("PENDING", "EXPECTED"):
        return BADGE_CI_PENDING
    return ""


def gh_badges(gh_info: dict[str, Any] | None) -> str:
    if not gh_info:
        return ""
    out = ""
    pr = gh_info.get("pr")
    if pr:
        out += pr_badge(pr.get("state", ""))
        out += review_badge(pr.get("review", ""))
        ci_state = pr.get("ci", "")
        if ci_state:
            out += ci_badge(ci_state)
    issue = gh_info.get("issue")
    if issue:
        out += issue_badge(issue.get("state", ""))
    return out


def gh_meta(gh_info: dict[str, Any] | None) -> str:
    """Encode GH info into the TSV meta column.

    PR format: pr=NUMBER:STATE:REVIEW:CI:URL  (URL is always last because it
    contains colons).
    """
    if not gh_info:
        return ""
    parts = []
    pr = gh_info.get("pr")
    if pr and pr.get("number"):
        parts.append(
            f"pr={pr['number']}:{pr.get('state', '')}:{pr.get('review', '')}:{pr.get('ci', '')}:{pr.get('url', '')}"
        )
    issue = gh_info.get("issue")
    if issue and issue.get("number"):
        parts.append(f"issue={issue['number']}:{issue.get('state', '')}:{issue.get('url', '')}")
    return "|".join(parts)


def _check_dirty(wt_path: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-c", "core.threads=1", "-C", wt_path, "status", "--porcelain", "--untracked-files=no"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return bool((r.stdout or "").strip())
    except Exception:
        return False


def status_badge(flags: set[str]) -> str:
    if "gone" in flags:
        return BADGE_GONE
    if "stale" in flags:
        return BADGE_STALE
    if "dirty" in flags:
        return BADGE_DIRTY
    return ""


def status_meta_flags(flags: set[str]) -> str:
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


wt_status: dict[str, set[str]] = {}

# 1. Discover worktrees
if not quick and not sessions_only and shutil.which("fd"):
    for wt_dir in scan_for_git_repos(scan_roots, int(os.environ.get("PICK_SESSION_SCAN_DEPTH", 6)), ignore_file):
        info = worktree_info(wt_dir)
        if info:
            rid = str(info.get("repo_id", ""))
            ensure_group(rid, str(info.get("root", "")), str(info.get("repo_path", "")))
            groups[rid]["wt_map"][info["path"]] = {"branch": str(info.get("branch", "")), "repo_id": rid}
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKER_THREADS) as pool:
        _futures = {pool.submit(_check_dirty, p): p for p in _dirty_candidates}
        for fut in concurrent.futures.as_completed(_futures):
            p = _futures[fut]
            try:
                if fut.result():
                    wt_status.setdefault(p, set[str]()).add("dirty")
            except Exception:
                pass

# 1c. Parallel GitHub PR/issue lookup for non-default branches.
# Uses a persistent file cache to avoid redundant API calls across refreshes.
# Skips stale/gone worktrees (no valid git context).
wt_gh_info: dict[str, dict[str, Any]] = {}
_gh_pruned: dict[str, dict[str, Any]] = {}
_gh_save_pending = False
_gh_all: list[tuple[str, str, str]] = []
_nwo_cache: dict[str, str] = {}
for rid in groups:
    root_checkout = groups[rid].get("root_checkout", "")
    if root_checkout and root_checkout not in _nwo_cache:
        url = origin_url_for_root(root_checkout)
        _nwo_cache[root_checkout] = nwo_from_url(url)
    nwo = _nwo_cache.get(root_checkout, "")
    for wt_path, wt_data in groups[rid]["wt_map"].items():
        br = wt_data.get("branch", "")
        flags = wt_status.get(wt_path, set[str]())
        if br and br not in DEFAULT_BRANCH_DIRS and not (flags & {"gone", "stale"}):
            _gh_all.append((wt_path, br, nwo))

if _gh_all:
    _gh_disk_cache = _gh_cache_load()
    _raw_entries = _gh_disk_cache.get("entries")
    _gh_entries: dict[str, dict[str, Any]] = _raw_entries if isinstance(_raw_entries, dict) else {}
    _now = time.time()
    _gh_need_fetch: list[tuple[str, str, str]] = []
    for p, br, nwo in _gh_all:
        cached = _gh_entries.get(p)
        if cached and _gh_cache_fresh(cached, br, nwo, _now):
            if cached.get("pr") or cached.get("issue"):
                wt_gh_info[p] = {"pr": cached.get("pr"), "issue": cached.get("issue")}
        else:
            _gh_need_fetch.append((p, br, nwo))

    if _gh_need_fetch and shutil.which("gh"):
        _fetch_meta = {p: (br, nwo) for p, br, nwo in _gh_need_fetch}
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKER_THREADS) as pool:
            _gh_futures = {pool.submit(_lookup_gh_info, p, br, nwo): p for p, br, nwo in _gh_need_fetch}
            for fut in concurrent.futures.as_completed(_gh_futures):
                p = _gh_futures[fut]
                br, nwo = _fetch_meta[p]
                try:
                    info = fut.result()
                    _gh_entries[p] = {
                        "pr": info.get("pr"),
                        "issue": info.get("issue"),
                        "branch": br,
                        "nwo": nwo,
                        "ts": _now,
                    }
                    if info.get("pr") or info.get("issue"):
                        wt_gh_info[p] = info
                except Exception:
                    _gh_entries[p] = {"pr": None, "issue": None, "branch": br, "nwo": nwo, "ts": _now}

    _live_paths = {p for p, _, _ in _gh_all}
    _gh_pruned = {k: v for k, v in _gh_entries.items() if k in _live_paths}
    _gh_save_pending = True

# 2. Add sessions
_tmux_session = subprocess.run(["tmux", "display-message", "-p", "#S"], check=False, stdout=subprocess.PIPE, text=True)
current_session = (_tmux_session.stdout or "").strip()
_tmux_sessions = subprocess.run(
    ["tmux", "list-sessions", "-F", "#{session_name}\t#{session_path}"], check=False, stdout=subprocess.PIPE, text=True
)
sess_out = _tmux_sessions.stdout or ""
sessions = []
home = os.path.expanduser("~")
for row in sess_out.splitlines():
    if not row:
        continue
    name, _, path = row.partition("\t")
    name, path = name.strip(), path.strip()
    rp = resolve_path(path)
    # Skip sessions rooted in "bag" locations (archived leftovers from picker
    # removals). These are almost always stale and can mask a newly recreated
    # worktree with the same intended session name.
    if "/.bag/worktree_remove/" in rp or "/.bag/pickers/session/" in rp:
        continue
    sessions.append({"name": name, "path": path, "rpath": rp, "is_current": (name == current_session)})
    wt_root = find_worktree_root_for_path(rp, home)
    if wt_root:
        info = worktree_info(wt_root)
        if info:
            rid = str(info.get("repo_id", ""))
            ensure_group(rid, str(info.get("root", "")), str(info.get("repo_path", "")))
            groups[rid]["wt_map"].setdefault(info["path"], {"branch": str(info.get("branch", "")), "repo_id": rid})
            groups[rid]["sessions_by_wt"].setdefault(info["path"], []).append(name)

# 2a. In quick/sessions-only mode, step 1b (dirty scan) was skipped because no
# worktrees were discovered yet. Now that step 2 found session worktree paths,
# run dirty checks for them so session entries keep their dirty badge.
if quick or sessions_only:
    _new_wt_paths = [p for rid in groups for p in groups[rid]["wt_map"] if p not in wt_status]
    if _new_wt_paths:
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKER_THREADS) as pool:
            _dirty_futs = {pool.submit(_check_dirty, p): p for p in _new_wt_paths}
            for fut in concurrent.futures.as_completed(_dirty_futs):
                p = _dirty_futs[fut]
                try:
                    if fut.result():
                        wt_status.setdefault(p, set[str]()).add("dirty")
                except Exception:
                    pass

# 2b. In quick/sessions-only mode, step 1c was skipped (no worktree discovery).
# Hydrate wt_gh_info from the persistent gh disk cache so session entries still
# get PR/issue badges. Zero-cost: just a local JSON read, no network calls.
if (quick or sessions_only) and not wt_gh_info:
    _gh_disk = _gh_cache_load().get("entries")
    if isinstance(_gh_disk, dict):
        for rid in groups:
            for wt_path in groups[rid]["wt_map"]:
                cached = _gh_disk.get(wt_path)
                if cached and (cached.get("pr") or cached.get("issue")):
                    wt_gh_info[wt_path] = {"pr": cached.get("pr"), "issue": cached.get("issue")}

# 2c. Enrich PR entries with CI + review from the gh picker cache first,
# then batch-fetch remaining PRs via a single GraphQL call.
_prs_needing_ci: dict[str, set[int]] = {}
if wt_gh_info:
    for wt_path, gh in wt_gh_info.items():
        pr = gh.get("pr")
        if not pr or not pr.get("number"):
            continue
        pr_url = pr.get("url", "")
        upstream_nwo = ""
        if "github.com/" in pr_url:
            url_parts = pr_url.split("github.com/", 1)[1].split("/")
            if len(url_parts) >= 2:
                upstream_nwo = f"{url_parts[0]}/{url_parts[1]}"
        if upstream_nwo:
            picker_review, picker_ci = _get_gh_picker_meta(upstream_nwo, pr["number"])
            if picker_ci and not pr.get("ci"):
                pr["ci"] = picker_ci
            if picker_review and not pr.get("review"):
                pr["review"] = picker_review
        if not pr.get("ci") and upstream_nwo and (pr.get("state", "").upper() == "OPEN"):
            _prs_needing_ci.setdefault(upstream_nwo, set[int]()).add(pr["number"])

# 2c-ii. Batch GraphQL for PRs still missing CI (not in gh picker cache).
if _prs_needing_ci and not quick and not sessions_only and shutil.which("gh"):
    _gql_ci = _batch_ci_graphql(_prs_needing_ci)
    if _gql_ci:
        for wt_path, gh in wt_gh_info.items():
            pr = gh.get("pr")
            if not pr or pr.get("ci") or not pr.get("number"):
                continue
            pr_url = pr.get("url", "")
            upstream_nwo = ""
            if "github.com/" in pr_url:
                url_parts = pr_url.split("github.com/", 1)[1].split("/")
                if len(url_parts) >= 2:
                    upstream_nwo = f"{url_parts[0]}/{url_parts[1]}"
            if upstream_nwo:
                meta = _gql_ci.get(upstream_nwo, {}).get(pr["number"])
                if meta:
                    review_gql, ci_gql = meta
                    if ci_gql:
                        pr["ci"] = ci_gql
                    if review_gql and not pr.get("review"):
                        pr["review"] = review_gql

# 2d. Save the GH disk cache (deferred from step 1c so CI enrichment is included).
if _gh_save_pending:
    for p, gh in wt_gh_info.items():
        if p in _gh_pruned and gh.get("pr"):
            cached_pr = _gh_pruned[p].get("pr") or {}
            if cached_pr and gh["pr"].get("ci") and not cached_pr.get("ci"):
                cached_pr["ci"] = gh["pr"]["ci"]
    _gh_cache_save({"version": 1, "entries": _gh_pruned})

# 3. Output results
exclude_exact = set()
exclude_worktree_roots = set()


def emit_sessions_and_worktrees():
    emitted_session_names = set()

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
                flags = wt_status.get(wt_path, set[str]())
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
                emitted_session_names.add(sess_name)
                exclude_exact.add(wt_path)
                exclude_worktree_roots.add(wt_path)

        # Worktrees second (skip entirely in sessions-only mode).
        if not sessions_only:
            for wt_path in sorted(wt_map.keys()):
                if wt_path in sessions_by_wt:
                    continue
                br = wt_map[wt_path].get("branch", "")
                meta = f"wt_root:{br}" if wt_path == root_checkout else f"wt:{br}"
                meta += f"|repo={repo}"
                flags = wt_status.get(wt_path, set[str]())
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

    # Plain directory sessions do not belong to a git worktree group, but they
    # should still take ownership of their path in the picker. Collapse multiple
    # tmux sessions rooted at the same directory and prefer the canonical name
    # (`~/code/` -> target `code`) so leaked/legacy names do not duplicate rows.
    plain_by_path: dict[str, list[dict[str, object]]] = {}
    for sess in sessions:
        sess_name = str(sess.get("name", "")).strip()
        if not sess_name or sess_name in emitted_session_names:
            continue
        rp = resolve_path(str(sess.get("rpath") or sess.get("path") or ""))
        if not rp or is_git_repo_dir(rp):
            continue
        plain_by_path.setdefault(rp, []).append(sess)

    def plain_session_sort_key(sess: dict[str, object]):
        rp = resolve_path(str(sess.get("rpath") or sess.get("path") or ""))
        name = str(sess.get("name", "")).strip()
        canonical = canonical_dir_session_name(rp)
        return (
            0 if canonical and name == canonical else 1,
            0 if bool(sess.get("is_current")) else 1,
            len(name),
            name.lower(),
        )

    for rp in sorted(plain_by_path.keys(), key=lambda p: p.lower()):
        sess = sorted(plain_by_path[rp], key=plain_session_sort_key)[0]
        sess_name = str(sess.get("name", "")).strip()
        tpath = tildefy(rp)
        label = (tpath + "/") if rp in scan_roots_set else tpath
        disp = display_dir_session_entry(label)
        mk = match_key(label, sess_name) if label == rp else match_key(label, sess_name, rp)
        print(f"{disp}\tsession\t{rp}\t\t{sess_name}\t{mk}")
        emitted_session_names.add(sess_name)
        exclude_exact.add(rp)


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
        if not p:
            continue
        # Hide directory rows that duplicate live session paths so a directory
        # selected as a tmux session consistently renders as a session later.
        if p in exclude_exact:
            continue
        # Normally we hide dir entries that duplicate a worktree root path. Scan
        # roots (e.g. ~/work, ~/code) stay reachable via path-ish queries unless
        # a live session owns the exact same path.
        if p in exclude_worktree_roots and p not in scan_roots_set:
            continue
        # Avoid spamming dirs that are already covered by explicit worktree roots,
        # but always keep configured scan roots visible (so `code/` can reach
        # `~/code/` even when a session is rooted at `~/code`).
        if p not in scan_roots_set and any(p == wt or p.startswith(wt + os.sep) for wt in home_worktree_prefixes):
            continue
        base = Path(p).name
        tpath = tildefy(p)
        if p in scan_roots_set:
            if tpath == "~":
                mk = match_key("~/", "~", p + "/", p)
            else:
                mk = match_key(base + "/", tpath + "/", tpath, base, p + "/", p)
            label = tpath + "/"
        else:
            mk = match_key(base, tpath, p)
            label = tpath
        print(f"{display_dir_entry(label)}\tdir\t{p}\t\t\t{mk}")
