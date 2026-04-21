#!/usr/bin/env python3
"""Preprocess captured pane text for URL extraction.

- Collapse each line at its last CR (terminal redraws/progress bars).
- Strip Unicode "format" characters (category Cf): zero-width space (U+200B),
  zero-width non-joiner / joiner (U+200C / U+200D), word joiner (U+2060),
  BOM / zero-width no-break space (U+FEFF), bidi marks (U+200E/U+200F,
  U+202A-U+202E), etc. These are invisible and never legal inside a URL,
  but the bash extractor uses `[^[:space:]]+` which would otherwise capture
  them and produce broken URLs (e.g. a ZWSP pasted after a github commit
  SHA turns the URL into a 404).
"""

import sys
import unicodedata

text = sys.stdin.read()
lines = text.split("\n")
cleaned = []
for ln in lines:
    ln = ln.split("\r")[-1]
    ln = "".join(ch for ch in ln if unicodedata.category(ch) != "Cf")
    cleaned.append(ln)
sys.stdout.write("\n".join(cleaned))
