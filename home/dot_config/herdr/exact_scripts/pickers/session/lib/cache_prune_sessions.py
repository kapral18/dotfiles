#!/usr/bin/env python3
import os
import tempfile

cache_file = os.environ["CACHE_FILE"]
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

        if kind == "dir" and path in dirs:
            continue

        out.append(line)

fd, tmp = tempfile.mkstemp(dir=os.path.dirname(cache_file) or ".", prefix=".cache_prune.")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.writelines(out)
os.replace(tmp, cache_file)
