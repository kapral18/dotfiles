#!/usr/bin/env python3
"""Cache-only HTML artifact review loop for agents."""

from __future__ import annotations

import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from commands import main

if __name__ == "__main__":
    main()
