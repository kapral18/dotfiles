"""Frecency store for the tmux session picker.

Tracks how often / how recently each path is opened so the picker can order
rows by usage once the user has started selecting things (zoxide-style: a
combined frequency + recency score). Pure stdlib; no external deps.

Storage: a small TSV at ``$XDG_CACHE_HOME/tmux/pick_session_frecency.tsv`` with
one row per resolved path:

    <resolved_path>\t<rank>\t<last_access_epoch>

``rank`` accumulates on each access; the live score decays ``rank`` by the age
of ``last_access`` so stale entries naturally sink. This mirrors zoxide's aging
buckets closely enough for ordering purposes.
"""

import os
import time
from pathlib import Path

_HOUR = 3600.0
_DAY = 86400.0
_WEEK = 7 * _DAY


def store_path():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return Path(base) / "tmux" / "pick_session_frecency.tsv"


def _resolve(p):
    if not p:
        return ""
    try:
        return str(Path(p).expanduser().resolve())
    except Exception:
        try:
            return os.path.realpath(os.path.expanduser(p))
        except Exception:
            return p


def _decay(age_seconds):
    """zoxide-style aging buckets applied as a multiplier on rank."""
    if age_seconds < _HOUR:
        return 4.0
    if age_seconds < _DAY:
        return 2.0
    if age_seconds < _WEEK:
        return 0.5
    return 0.25


def _read_rows(path):
    rows = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                p = parts[0]
                try:
                    rank = float(parts[1])
                    last = float(parts[2])
                except (ValueError, TypeError):
                    continue
                if p:
                    rows[p] = (rank, last)
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return rows


def _write_rows(path, rows):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for p, (rank, last) in rows.items():
                f.write(f"{p}\t{rank:g}\t{last:g}\n")
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def add(raw_path, weight=1.0):
    """Record an access to ``raw_path``, bumping its rank.

    Prunes entries whose resolved path no longer exists on disk so the store
    does not grow without bound across worktree churn.
    """
    rp = _resolve(raw_path)
    if not rp:
        return
    path = store_path()
    rows = _read_rows(path)
    now = time.time()
    rank, _last = rows.get(rp, (0.0, now))
    rows[rp] = (rank + weight, now)
    pruned = {}
    for p, val in rows.items():
        if p == rp or os.path.isdir(p):
            pruned[p] = val
    _write_rows(path, pruned)


def scores():
    """Return {resolved_path: decayed_score} for all known paths.

    Empty dict when the store is missing/empty — the caller treats that as
    "no frecency yet, keep structural order".
    """
    path = store_path()
    rows = _read_rows(path)
    if not rows:
        return {}
    now = time.time()
    out = {}
    for p, (rank, last) in rows.items():
        age = max(0.0, now - last)
        out[p] = rank * _decay(age)
    return out
