#!/usr/bin/env python3
import os

cache_file = os.environ["CACHE_FILE"]
sel = os.environ["SESSIONS"].split("\n")
sel = {s for s in sel if s}
dirs = os.environ["DIRS"].split("\n")
dirs = {d for d in dirs if d}

out = []
with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        kind = parts[1]
        path = parts[2]
        target = parts[4]

        if kind == "dir" and path in dirs:
            continue

        out.append(line)

tmp = cache_file + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    f.writelines(out)
os.replace(tmp, cache_file)
