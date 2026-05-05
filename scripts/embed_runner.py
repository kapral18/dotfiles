#!/usr/bin/env -S uv run --quiet --no-project --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastembed>=0.3,<1.0",
# ]
# ///
"""Embedding runner — isolated subprocess that loads a fastembed model
and embeds a batch of texts.

Protocol (request/response over stdio, single round-trip):

    stdin  (one JSON object):
        {"model": "<model-id>", "texts": ["t1", "t2", ...]}

    stdout (one JSON object on success):
        {"model": "<model-id>", "dim": <int>, "vectors": [[...], [...], ...]}

    stdout (one JSON object on failure):
        {"error": "<message>"}

Exit code: 0 on success, 1 on failure.

This script intentionally lives outside the orchestrator's stdlib-only
boundary: it declares its own deps via PEP 723 inline-script metadata
and is invoked via `uv run --script embed_runner.py`. The orchestrator
(scripts/ralph.py, scripts/ai_kb.py) only knows how to spawn a
subprocess and parse JSON, keeping its own import surface stdlib-only.
"""

from __future__ import annotations

import json
import sys


def _eprint_and_exit(message: str) -> None:
    print(json.dumps({"error": message}))
    sys.exit(1)


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        _eprint_and_exit("empty stdin; expected one JSON object")

    try:
        req = json.loads(raw)
    except json.JSONDecodeError as err:
        _eprint_and_exit(f"stdin not valid JSON: {err}")

    if not isinstance(req, dict):
        _eprint_and_exit("request must be a JSON object")

    model_id = req.get("model") or "BAAI/bge-small-en-v1.5"
    texts = req.get("texts") or []
    if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
        _eprint_and_exit("'texts' must be a list of strings")
    if not texts:
        # No-op call still returns a valid empty payload so callers can
        # safely batch zero items without special-casing.
        print(json.dumps({"model": model_id, "dim": 0, "vectors": []}))
        return

    try:
        # Imported lazily so a malformed request still produces a
        # parseable error JSON before paying fastembed's import cost.
        from fastembed import TextEmbedding
    except Exception as err:
        _eprint_and_exit(f"failed to import fastembed: {err}")

    try:
        model = TextEmbedding(model_name=model_id)
        # fastembed.embed yields one numpy vector per input text.
        vectors = [list(map(float, v)) for v in model.embed(texts)]
    except Exception as err:
        _eprint_and_exit(f"embed failed: {err}")

    dim = len(vectors[0]) if vectors and vectors[0] else 0
    print(json.dumps({"model": model_id, "dim": dim, "vectors": vectors}))


if __name__ == "__main__":
    main()
