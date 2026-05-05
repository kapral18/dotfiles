"""Embedding service abstraction for Ralph's KB.

Stdlib-only consumer surface. The orchestrator (`ralph.py`) and the
knowledge base (`ai_kb.py`) talk to this module; this module talks to
the isolated `embed_runner.py` via subprocess. The runner declares its
own deps (fastembed) via PEP 723 inline-script metadata, so no ML
package leaks into the orchestrator's import graph.

Protocol with the runner is defined in `embed_runner.py`:

    request:  {"model": str, "texts": list[str]}
    response: {"model": str, "dim": int, "vectors": list[list[float]]}
              | {"error": str}

The default model is `BAAI/bge-small-en-v1.5` (33M params, 384-dim,
MTEB ~62.2 on English retrieval — a good balance of size vs quality
for natural-language and code-related capsules). Override via the
`RALPH_EMBED_MODEL` environment variable or the `model` keyword.

Failure mode is intentionally soft: if the runner is unreachable or
errors, callers receive an empty list (or `None` per call) and decide
whether to skip embeddings or fall back to FTS5-only retrieval. We do
not raise into the orchestrator hot path because graceful degradation
is the explicit BIG-tier requirement.
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_DIM = 384  # used when a placeholder zero-vector is needed (no embedder available)
DEFAULT_TIMEOUT_SECONDS = 120


def runner_path() -> Path:
    """Absolute path to the colocated embed_runner.py script."""
    return Path(__file__).resolve().parent / "embed_runner.py"


def uv_binary() -> str | None:
    """`uv` is required to drive the PEP 723 inline-script invocation."""
    return shutil.which("uv")


@dataclass
class EmbedResult:
    """Single embed response payload."""

    model: str
    dim: int
    vectors: list[list[float]]


class EmbedderUnavailable(RuntimeError):
    """Raised by `Embedder.embed_strict` when no embedder is reachable.

    The standard `embed()` API never raises — it returns an empty list —
    so callers that care about strict failure modes must opt in. The
    orchestrator never opts in; tests do.
    """


class Embedder:
    """Coordinator for embedding requests.

    Holds configuration (model id, runner path, timeout) and dispatches
    to the runner subprocess on each call. Stateless across calls; safe
    to construct per-orchestrator-process and reuse.

    Cold-start cost is paid by the runner subprocess on first invocation
    (model files load from HuggingFace cache, ~200-500ms). Subsequent
    calls in a long-lived runner would amortize, but Ralph's call
    frequency at role-spawn time is low enough that subprocess-per-call
    keeps the design simple. A pooled long-lived runner can be added
    later if profiling shows it's needed.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        runner: Path | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model or os.environ.get("RALPH_EMBED_MODEL") or DEFAULT_MODEL
        self.runner = runner or runner_path()
        self.timeout = timeout

    def is_available(self) -> bool:
        """`uv` plus the runner script must both be present.

        We do NOT probe the runner here (subprocess spawn is expensive
        and the model download might happen on first call). Callers can
        rely on `embed()` returning an empty list if the runner errors
        at runtime.
        """
        return uv_binary() is not None and self.runner.is_file()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns [] on any failure.

        This is the orchestrator's hot path so we swallow all exceptions
        and degrade silently. Callers that need strict failure semantics
        use `embed_strict`. Empty input returns [] without spawning.
        """
        if not texts:
            return []
        try:
            return self.embed_strict(texts).vectors
        except Exception:
            return []

    def embed_one(self, text: str) -> list[float]:
        """Embed a single text. Returns [] on any failure."""
        if not text:
            return []
        vectors = self.embed([text])
        return vectors[0] if vectors else []

    def embed_strict(self, texts: list[str]) -> EmbedResult:
        """Like `embed`, but raises `EmbedderUnavailable` on failure.

        Useful for tests and tooling (e.g. `,ralph kb-doctor`) that
        want to surface configuration errors loudly.
        """
        if not self.is_available():
            raise EmbedderUnavailable(f"embedder not available: uv={uv_binary()!r} runner={self.runner!s}")
        if not texts:
            return EmbedResult(model=self.model, dim=0, vectors=[])
        request = {"model": self.model, "texts": texts}
        cmd = [
            uv_binary() or "uv",
            "run",
            "--quiet",
            "--no-project",
            "--script",
            str(self.runner),
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(request),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as err:
            raise EmbedderUnavailable(f"runner spawn failed: {err}") from err

        if proc.returncode != 0:
            raise EmbedderUnavailable(
                f"runner exited {proc.returncode}: stderr={proc.stderr.strip()!r} stdout={proc.stdout.strip()!r}"
            )
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as err:
            raise EmbedderUnavailable(f"runner emitted unparseable stdout: {err} stdout={proc.stdout!r}") from err
        if "error" in payload:
            raise EmbedderUnavailable(f"runner error: {payload['error']}")
        return EmbedResult(
            model=str(payload.get("model", self.model)),
            dim=int(payload.get("dim", 0)),
            vectors=[[float(x) for x in v] for v in payload.get("vectors", [])],
        )


# --- Vector packing helpers ------------------------------------------------


def pack_vector(vector: list[float]) -> bytes:
    """Pack a float vector into a compact little-endian float32 BLOB.

    Stored alongside each capsule. Float32 is precise enough for cosine
    similarity ranking and halves the size vs float64.
    """
    return struct.pack(f"<{len(vector)}f", *vector)


def unpack_vector(blob: bytes | None) -> list[float]:
    """Inverse of `pack_vector`. Returns [] for None/empty BLOBs."""
    if not blob:
        return []
    n = len(blob) // 4
    if n == 0:
        return []
    return list(struct.unpack(f"<{n}f", blob[: n * 4]))


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors.

    Returns 0.0 if either side is empty or lengths differ. We never
    raise here because retrieval is best-effort.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / ((na**0.5) * (nb**0.5))
