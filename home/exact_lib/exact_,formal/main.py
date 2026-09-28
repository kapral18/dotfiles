#!/usr/bin/env python3
"""Persistent, diff-aware formal model catalog for agents: anchored
extraction, an executable Lean model, exhaustive state search, model
mutation, trace-replay conformance on real code, and optional Lean proofs.

Entrypoint only: resolves ``sys.path`` to this directory (so tests can run
this file directly from the repo source, matching ``formal.paths.lib_dir``'s
``FORMAL_LIB_DIR`` override) and hands off to :mod:`formal.cli`. Usage:
``,formal --help``.
"""

from __future__ import annotations

import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from formal.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
