#!/usr/bin/env python3

import os
import signal
import sys

signal.signal(signal.SIGPIPE, signal.SIG_DFL)
current = os.environ.get("CURRENT", "")
suffix = "\033[2;38;5;244m (current)\033[0m"
with open(sys.argv[1], "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 5:
            parts[0] = parts[0].replace(suffix, "")
            if parts[1] == "session" and parts[4] == current:
                parts[0] += suffix
        print("\t".join(parts))
