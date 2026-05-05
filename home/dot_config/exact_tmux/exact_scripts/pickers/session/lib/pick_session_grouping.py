"""Shared grouping/sorting logic for the tmux session picker.

Used by both filter.sh and items_hide_selected.sh to deduplicate, group,
and sort TSV rows produced by items.sh.
"""

import os

KIND_PRIO = {"session": 3, "worktree": 2, "dir": 1}
DEFAULT_BRANCHES = {"main", "master", "trunk", "develop", "dev"}


def simple_resolve(p):
    """Minimal path resolution without caching."""
    from pathlib import Path

    try:
        return str(Path(p).resolve())
    except Exception:
        return p


def cached_resolve(cache):
    """Return a resolve function that caches results and handles ~ expansion."""
    from pathlib import Path

    def _resolve(p):
        if not p:
            return ""
        cached_val = cache.get(p)
        if cached_val is not None:
            return cached_val
        try:
            rp = str(Path(p).expanduser().resolve())
        except Exception:
            try:
                rp = os.path.realpath(os.path.expanduser(p))
            except Exception:
                rp = p
        cache[p] = rp
        return rp

    return _resolve


def scan_root_rank_for_path(p, scan_roots, resolve_fn):
    rp = resolve_fn(p)
    if not rp:
        return 999
    for i, r in enumerate(scan_roots):
        if not r:
            continue
        if rp == r or rp.startswith(r + os.sep):
            return i
    return 999


def scan_root_prefix_for_path(p, scan_roots, resolve_fn, depth=2):
    rp = resolve_fn(p)
    if not rp:
        return ""
    for r in scan_roots:
        if not r:
            continue
        if rp == r:
            return ""
        if rp.startswith(r + os.sep):
            rel = rp[len(r) :].lstrip(os.sep)
            segs = [s for s in rel.split(os.sep) if s]
            return "/".join(segs[:depth])
    return ""


def dedup_best(rows, resolve_fn, scan_roots_set):
    best_by_path = {}
    scan_root_dir_idx = {}
    for i, line in enumerate(rows):
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        kind, path = parts[1], parts[2] or ""
        if not path:
            continue
        key = resolve_fn(path)
        if kind == "dir" and key in scan_roots_set and key not in scan_root_dir_idx:
            scan_root_dir_idx[key] = i
        pr = KIND_PRIO.get(kind, 0)
        prev = best_by_path.get(key)
        if prev is None or pr > prev[0]:
            best_by_path[key] = (pr, i)
    out = []
    seen = set()
    seen_scan_root_dirs = set()
    for i, line in enumerate(rows):
        parts = line.split("\t")
        if len(parts) < 5:
            out.append(line)
            continue
        kind = parts[1]
        path = parts[2] or ""
        if not path:
            out.append(line)
            continue
        key = resolve_fn(path)
        if kind == "dir" and key in scan_roots_set:
            if key in seen_scan_root_dirs:
                continue
            seen_scan_root_dirs.add(key)
            out.append(line)
            continue
        best = best_by_path.get(key)
        if best is None:
            out.append(line)
            continue
        if best[1] != i:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def wrapper_for_root(root):
    base = os.path.basename(root.rstrip("/"))
    if base in DEFAULT_BRANCHES:
        parent = os.path.dirname(root.rstrip("/"))
        return parent if parent else root
    return root


def grouped_output(rows, scan_roots, resolve_fn, *, dir_sort_override=None):
    """Group, sort, and return ordered TSV lines.

    Args:
        rows: raw TSV lines from items.sh
        scan_roots: resolved scan root paths
        resolve_fn: path resolution function (cached or simple)
        dir_sort_override: optional callable(line) -> sort key for dir rows;
            when None, uses the default dir_sort_key

    Returns:
        list of ordered TSV lines
    """
    deduped = dedup_best(rows, resolve_fn, set(scan_roots))

    wt_path_to_root = {}
    for line in deduped:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        kind, path, target = parts[1], parts[2], parts[4]
        if kind == "worktree" and target:
            wt_path_to_root[path] = target

    candidate_roots = set()
    for line in deduped:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        kind, path, meta, target = parts[1], parts[2], parts[3], parts[4]
        if kind == "worktree" and target:
            candidate_roots.add(target)
        if kind == "session":
            meta_base = (meta or "").split("|")[0]
            if meta_base.startswith("sess_root:") and path:
                candidate_roots.add(path)

    wrapper_to_root = {}

    def prefer_root(a, b):
        abase = os.path.basename((a or "").rstrip("/"))
        bbase = os.path.basename((b or "").rstrip("/"))
        a_def = abase in DEFAULT_BRANCHES
        b_def = bbase in DEFAULT_BRANCHES
        if a_def and not b_def:
            return a
        if b_def and not a_def:
            return b
        return a if len(a) <= len(b) else b

    for r in candidate_roots:
        w = wrapper_for_root(r)
        prev = wrapper_to_root.get(w)
        wrapper_to_root[w] = r if prev is None else prefer_root(prev, r)

    wrapper_prefixes = sorted(wrapper_to_root.keys(), key=len, reverse=True)

    def root_for_path_by_wrapper(p):
        if not p:
            return None
        for w in wrapper_prefixes:
            if p == w or p.startswith(w + "/"):
                return wrapper_to_root.get(w)
        return None

    root_order = []
    root_groups = {}
    ungrouped_sessions = []
    dir_rows = []
    other_rows = []

    def ensure_group(root):
        if root not in root_groups:
            root_order.append(root)
            root_groups[root] = {"sessions": [], "worktrees": []}
        return root_groups[root]

    for line in deduped:
        parts = line.split("\t")
        if len(parts) < 5:
            other_rows.append(line)
            continue
        kind, path, meta, target = parts[1], parts[2], parts[3], parts[4]

        if kind == "worktree":
            root = target or path
            ensure_group(root)["worktrees"].append(line)
        elif kind == "session":
            root = None
            meta_base = (meta or "").split("|")[0]
            if meta_base.startswith("sess_root:"):
                root = path
            elif meta_base.startswith("sess_wt:"):
                root = wt_path_to_root.get(path)
            if not root:
                root = wt_path_to_root.get(path)
            if not root:
                root = root_for_path_by_wrapper(path)
            if root:
                ensure_group(root)["sessions"].append(line)
            else:
                ungrouped_sessions.append(line)
        elif kind == "dir":
            dir_rows.append(line)
        else:
            other_rows.append(line)

    session_wrappers = set()
    for root in root_order:
        if root_groups[root]["sessions"]:
            session_wrappers.add(wrapper_for_root(root))
    for line in ungrouped_sessions:
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2]:
            session_wrappers.add(wrapper_for_root(parts[2]))

    _wrapper_dirs = []
    other_dirs = []
    for line in dir_rows:
        parts = line.split("\t")
        path = parts[2] if len(parts) > 2 else ""
        if path and path in session_wrappers:
            _wrapper_dirs.append(line)
        else:
            other_dirs.append(line)

    def session_name_for_row(line):
        parts = line.split("\t")
        if len(parts) >= 5:
            return (parts[4] or "").strip().lower()
        return ""

    def is_current_session_row(line):
        parts = line.split("\t")
        if not parts:
            return False
        return " (current)" in parts[0]

    def session_sort_key(line):
        return (0 if is_current_session_row(line) else 1, session_name_for_row(line))

    def worktree_sort_key(line):
        parts = line.split("\t")
        if len(parts) < 5:
            return (999, "", 1, "", "")
        meta = parts[3] or ""
        path = parts[2] or ""
        is_root = 0 if meta.startswith("wt_root:") else 1
        branch = meta.split(":", 1)[1] if ":" in meta else meta
        return (
            scan_root_rank_for_path(path, scan_roots, resolve_fn),
            scan_root_prefix_for_path(path, scan_roots, resolve_fn),
            is_root,
            (branch or "").lower(),
            path.lower(),
        )

    def ungrouped_session_sort_key(line):
        parts = line.split("\t")
        p = parts[2] if len(parts) >= 3 else ""
        w = wrapper_for_root(p) if p else ""
        base = w or p
        return (
            scan_root_rank_for_path(base, scan_roots, resolve_fn),
            scan_root_prefix_for_path(base, scan_roots, resolve_fn),
            session_sort_key(line),
            (base or "").lower(),
        )

    def orphan_root_sort_key(r):
        gp = wrapper_for_root(r) if r else ""
        base = gp or r
        return (
            scan_root_rank_for_path(base, scan_roots, resolve_fn),
            scan_root_prefix_for_path(base, scan_roots, resolve_fn),
            (base or "").lower(),
            r,
        )

    def dir_sort_key(line):
        parts = line.split("\t")
        p = parts[2] if len(parts) >= 3 else ""
        return (
            scan_root_rank_for_path(p, scan_roots, resolve_fn),
            scan_root_prefix_for_path(p, scan_roots, resolve_fn),
            (p or "").lower(),
        )

    session_groups = []
    for root in root_order:
        data = root_groups[root]
        if not data["sessions"]:
            continue
        first_name = ""
        for s in data["sessions"]:
            n = session_name_for_row(s)
            if n and (not first_name or n < first_name):
                first_name = n
        group_path = wrapper_for_root(root) if root else ""
        session_groups.append(
            (
                scan_root_rank_for_path(group_path, scan_roots, resolve_fn),
                scan_root_prefix_for_path(group_path, scan_roots, resolve_fn),
                first_name,
                group_path.lower(),
                root,
            )
        )
    session_groups.sort()

    session_groups_by_rank = {}
    for rank, pref, first_name, gpath, root in session_groups:
        session_groups_by_rank.setdefault(rank, []).append((pref, first_name, gpath, root))
    for rank in session_groups_by_rank:
        session_groups_by_rank[rank].sort()

    ungrouped_sorted = sorted(ungrouped_sessions, key=ungrouped_session_sort_key)
    ungrouped_by_rank = {}
    for line in ungrouped_sorted:
        rank = ungrouped_session_sort_key(line)[0]
        ungrouped_by_rank.setdefault(rank, []).append(line)

    orphan_roots_sorted = sorted(
        [r for r in root_order if not root_groups[r]["sessions"]],
        key=orphan_root_sort_key,
    )
    orphan_by_rank = {}
    for r in orphan_roots_sorted:
        rank = orphan_root_sort_key(r)[0]
        orphan_by_rank.setdefault(rank, []).append(r)

    other_dirs_sorted = sorted(other_dirs, key=dir_sort_key)
    other_dirs_by_rank = {}
    for line in other_dirs_sorted:
        rank = dir_sort_key(line)[0]
        other_dirs_by_rank.setdefault(rank, []).append(line)

    emitted_worktree_roots = set()
    result = []

    def emit_rank(rank):
        for _pref, _first_name, _gpath, root in session_groups_by_rank.get(rank, []):
            data = root_groups[root]
            result.extend(sorted(data["sessions"], key=session_sort_key))
            if root not in emitted_worktree_roots:
                result.extend(sorted(data["worktrees"], key=worktree_sort_key))
                emitted_worktree_roots.add(root)

        result.extend(ungrouped_by_rank.get(rank, []))

        for root in orphan_by_rank.get(rank, []):
            if root in emitted_worktree_roots:
                continue
            result.extend(sorted(root_groups[root]["worktrees"], key=worktree_sort_key))
            emitted_worktree_roots.add(root)

    ranks_with_sessions = sorted(set(session_groups_by_rank.keys()).union(ungrouped_by_rank.keys()))
    for rank in ranks_with_sessions:
        emit_rank(rank)

    for rank in sorted(set(orphan_by_rank.keys()).difference(ranks_with_sessions)):
        emit_rank(rank)

    result.extend(other_rows)

    effective_dir_sort = dir_sort_override if dir_sort_override is not None else dir_sort_key
    result.extend(sorted(dir_rows, key=effective_dir_sort))
    return result
