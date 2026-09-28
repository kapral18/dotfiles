"""Prove-audit: a secondary forbidden-token scan of every ``*.lean`` file under the unit dir,
plus the load-bearing check -- a compiled FormalKit executable (``formalcheck``, see
``lean/FormalKit/FormalKit/Check.lean``) that loads the unit's own already-built modules at
runtime and checks every constant in them semantically.

Round 5's design decision (four rounds of findings): a character-level Python token scanner can
never lex Lean (context-dependent interpolation such as ``throwError "{..}"``, ``'\x41'``,
``«x»``), and the *previous* design's generated ``.lake/formal/Axioms.lean`` -- a Lean program
containing ``import Unit.Proofs``, elaborated together with the unit -- let a unit's own
``macro_rules``/``elab_rules`` rewrite what that generated program's own ``run_cmd`` syntax even
meant, since macro expansion is a property of *elaboration*, and the generated program was
elaborated in the very same process as the unit's (untrusted) source. Moving the load-bearing
check into a *separately compiled* executable removes that vector entirely: `formalcheck`'s own
source is elaborated once, when the kit itself is built, and never again -- a unit's own macros
never run during `formalcheck`'s own compilation, and `formalcheck` never elaborates the unit's
syntax at all, only `Lean.importModules`s its already-compiled ``.olean``s at runtime, with
``loadExts := false`` and `enableInitializersExecution` never called (so a hostile module's own
``initialize``/``builtin_initialize`` block -- real, arbitrary compiled IO -- never runs either;
confirmed against a real Lean 4.34.1 toolchain that the constant map and every attribute this
tool reads, `Lean.Compiler.getImplementedBy?`/`Lean.isExtern`/`ConstantInfo.isUnsafe`, are all
still populated correctly without it). See `lean/FormalKit/FormalKit/Check.lean`'s module
docstring for the full mechanism.

``compute_module_scope`` (below) lists every root module whose ``.lean`` source lives under the
unit dir -- ``Unit.*``, ``Main``, and any *other* root a unit's own ``lakefile.toml`` adds. Those
roots are passed to `formalcheck`; for each root, the checker inspects every declaration in its
transitive import environment except modules established by a separate import of the actual
pinned toolchain and `FormalKit` roots. Trust is exact module membership, not a namespace prefix.
Ordinary Lake dependencies are therefore checked even though their source lives outside the unit
directory. The root list is also passed to `leanchecker` for the
independent kernel replay described below. Across the non-trusted closure, `formalcheck` fails
on an axiom from `Lean.collectAxioms` outside `propext`/`Quot.sound`/`Classical.choice`
(covers `sorry`/`admit` -> `sorryAx`, `native_decide` -> `ofReduceBool`/`ofReduceNat`); a user
`axiom` declaration; `ConstantInfo.isUnsafe`; `implemented_by` (`Lean.Compiler.getImplementedBy?`);
and `extern` (`Lean.isExtern`). `ConstantInfo.isPartial` is deliberately *not* one of these checks
(round 5's threat-model amendment, see `lean/FormalKit/FormalKit/Check.lean`'s `violationsFor`
docstring): a `partial def`'s logical declaration is a genuinely opaque constant that cannot make
a proof unsound, and its compiled code is its own body, so there is nothing else it could
substitute in -- confirmed against a real Lean 4.34.1 toolchain that its compiler-generated
``<name>._unsafe_rec`` sibling (the real recursive body, only visible by enumerating every
constant in scope rather than only user-named ones) trips neither `isUnsafe`, `Lean.isExtern`,
nor `implemented_by` either, so no separate exemption is needed for those checks. These are
``scope_violations`` on the receipt (a new key -- every existing key below keeps its old
meaning).

Separately, and unchanged from the previous design, ``Unit.Proofs``'s own theorem-kind constants
(and only those) still feed the F3 vacuity guard: ``theorems``/``user_written_count`` on the
receipt. A declaration counts as user-written only when `Lean.findDeclarationRanges?` returns a
source position **and**, after stripping every comment and string-literal content from the
source text between that range's full ``range`` start and its ``selectionRange`` start (Lean-side,
`FormalKit.Check.stripPreText` -- comment-*and*-string aware, and fixes a doc comment's own
closing-token handling that the *old* generated program's comment stripper mishandled, see that
function's docstring), the remaining text contains ``theorem`` as its own whole token -- split on
non-identifier characters, never a substring match. This tells a real `theorem`/`private
theorem`/`@[simp] theorem`/`open X in theorem`-one-liner/underscore-named declaration apart from
an `@[ext] structure`'s generated `.ext`/`.ext_iff` theorems, a `deriving ReflBEq, LawfulBEq`
instance theorem, and a doc comment or string attribute argument that merely mentions the word
"theorem" (e.g. ``@[deprecated "use --x instead" ...] theorem t1`` still counts `t1`, since the
string's content is stripped before the whole-token check, not because the word inside it would
otherwise match). Zero *user-written* theorems still fails closed rather than passing vacuously,
even when `Unit/Proofs.lean` defines only `structure`/`inductive` declarations whose
compiler-generated lemmas make the *checked* count nonzero.

A token denylist and a semantic per-constant check can still both miss a bypass that never adds a
new declaration to the module the axiom check inspects, but instead makes an *already-elaborated*
declaration's own kernel entry wrong -- confirmed with a real Lean 4.34.1 toolchain: a
`set_option debug.skipKernelTC true in run_cmd ... Lean.addDecl` that adds an ill-typed proof of
`False` reports zero axioms from `collectAxioms` (the term itself contains no axiom node, and the
kernel was simply never asked to check it), and referencing that bad declaration from a *new*,
normally-elaborated theorem elsewhere (even in a different, non-`Unit`-prefixed `lean_lib`, or
directly in `Main.lean`) elaborates and axiom-checks clean too, because elaboration trusts an
already-recorded type rather than re-deriving it. After every check above has already passed,
``run_prove`` therefore also runs an independent kernel re-check: the toolchain's real
``leanchecker``, resolved by *absolute path* (never a bare ``leanchecker`` on `PATH` -- a unit's
own `lean_exe` named `leanchecker` shadows the real one there, confirmed live), invoked with the
same explicit module list `formalcheck` used (never leanchecker's own default "current package
name" heuristic, which never includes `Main` or a non-`Unit`-prefixed root at all -- confirmed
live that this exact gap let a `Main.lean`- or a separate-`lean_lib`-based bypass through the old
design's bare, no-argument `lake env leanchecker`). Passing the explicit list makes leanchecker
replay every one of those modules' own newly-defined declarations through the real kernel,
independent of any elaboration-time debug option -- confirmed live: it rejects both bypasses above
(and every mutant/proof-injection route the tests below exercise), and still passes a clean unit
in under a second (measured against a real 5-module unit).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import manifest as manifest_mod
from . import paths
from .util import is_environment_failure, run

FORBIDDEN_TOKENS = (
    "sorry",
    "admit",
    "axiom",
    "native_decide",
    "implemented_by",
    "extern",
    "unsafe",
    # Kernel-bypass routes that leave no axiom trace for `collectAxioms` to see at all (confirmed
    # against a real Lean 4.34.1 toolchain, source at ~/.elan/toolchains/leanprover--lean4---
    # v4.34.1/src/lean/Lean/Environment.lean): `set_option debug.skipKernelTC true in run_cmd ...
    # Lean.addDecl decl` adds a theorem whose proof term the kernel never type-checks (an
    # ill-typed proof of `False` was added and reported zero axioms); calling `Lean.Environment.
    # addDeclCore` directly with its `doCheck` argument (the real parameter name -- not
    # `useSlowCheck`, defaulting to `true`) set to `false` bypasses the kernel check the same way
    # even without `debug.skipKernelTC` set at all, so the `addDeclCore` token below blocks a
    # real, live bypass route, not just a hypothetical one. `Lean.Kernel.Environment.
    # addDeclWithoutChecking` also exists as a real, public identifier in this toolchain version
    # (same file, `namespace Kernel.Environment`) -- the token below blocks calling it directly
    # too.
    "skipKernelTC",
    "addDeclCore",
    "addDeclWithoutChecking",
)
ALLOWED_AXIOMS = {"propext", "Quot.sound", "Classical.choice"}
_TOKEN_RE = re.compile(r"\b(" + "|".join(re.escape(token) for token in FORBIDDEN_TOKENS) + r")\b")


def _is_ident_continuation_char(char: str) -> bool:
    """True for a character that can appear *inside* a Lean identifier -- used only to check the
    character immediately before a candidate ``r``/``s``/``f``/``m`` string-prefix letter, so an
    identifier that merely *ends* in that letter (``myVarr"..."``, ``xs!"..."``) is never mistaken
    for a raw/interpolated string prefix."""
    return char.isalnum() or char in "_'"


def strip_comments(text: str) -> str:
    """Strip ``/- ... -/`` block comments (Lean nests them, e.g. ``/- /- -/ -/``, and
    ``/-- doc -/`` is just a block comment whose body happens to start with an extra ``-``) and
    ``-- ...`` line comments, so the forbidden-token scan ignores documentation text. Comment
    text is replaced with the same number of newlines it contained (never simply dropped) so a
    forbidden-token hit *after* a multi-line block comment still reports the correct source line
    number.

    Before checking for a comment opener, every Lean string/char form is copied through
    verbatim so a literal ``"/-"`` or ``"--"`` inside any of them never opens a comment (confirmed
    against a real Lean 4.34.1 toolchain for every form below):

    - A plain ``"..."`` string, with ``\\`` escapes (Lean string literals may contain a raw
      newline).
    - A char literal (``'x'``, ``'\\n'``). A bare ``'`` that is not immediately followed by a
      closing ``'`` within one (or one escaped) character -- e.g. the prime in an identifier like
      ``reset_from_done'`` -- is not a char literal and falls through to normal scanning instead
      of swallowing the rest of the file looking for a close that never comes.
    - A raw string, ``r"..."`` or ``r#"..."#`` (any number of ``#``, matched on both sides): no
      escapes at all -- a ``\\`` right before the closing quote does not extend the string, and
      the body is copied through exactly as written, so e.g. ``r#"a"/-"#`` keeps its literal
      ``"/-"`` and closes at the matching ``"#``.
    - An interpolated string, ``s!"...{expr}..."`` (also ``f!"..."``, ``m!"..."``): the literal
      text between ``{...}`` groups is a plain escaped string, but each ``{expr}`` is real Lean
      code -- it can contain its own nested strings (of any form above, including another
      interpolated string) and even a real ``/- ... -/`` comment, and none of that leaks past the
      ``}`` that closes it. ``s!"{"/-"}"`` is real, compiling Lean: the ``"/-"`` is a nested plain
      string inside the ``{...}``, never a comment opener, and the whole token round-trips
      unchanged.

    A raw/interpolated-string prefix letter (``r``, ``s``, ``f``, ``m``) is only recognized when
    the character right before it is not itself an identifier character, so ``myVarr"..."``/
    ``xs!"..."`` (an ordinary identifier that merely ends in that letter, applied to a string) is
    never misread as one. Every string/char form above degrades to "copy the rest of the text
    through unchanged" (never raises) when it is unterminated at EOF -- a lone ``"abc``, a
    trailing ``"\\``, a raw ``r"abc`` with no closing quote, or an interpolated ``s!"{abc`` with no
    closing ``}``/``"``."""
    out: list[str] = []
    depth = 0  # block-comment nesting depth; shared across the whole scan, including recursion
    n = len(text)

    def prev_is_ident(i: int) -> bool:
        return i > 0 and _is_ident_continuation_char(text[i - 1])

    def raw_hash_count(i: int) -> int | None:
        """``text[i] == 'r'``; returns the hash count when immediately followed by zero or more
        ``#``s and then a ``"`` -- with nothing else in between -- else ``None``."""
        j = i + 1
        hashes = 0
        while j < n and text[j] == "#":
            hashes += 1
            j += 1
        return hashes if j < n and text[j] == '"' else None

    def is_interp_prefix(i: int) -> bool:
        """``text[i]`` is ``'s'``/``'f'``/``'m'``; true when immediately followed by ``!"``."""
        return text[i + 1 : i + 3] == '!"'

    def consume_plain_string(i: int) -> int:
        """``text[i] == '"'``; copies an escaped string through to its matching ``"``, or to EOF
        if unterminated (never raises)."""
        out.append('"')
        i += 1
        while i < n and text[i] != '"':
            if text[i] == "\\" and i + 1 < n:
                out.append(text[i])
                out.append(text[i + 1])
                i += 2
                continue
            out.append(text[i])
            i += 1
        if i < n:
            out.append('"')
            i += 1
        return i

    def consume_raw_string(i: int, hashes: int) -> int:
        """``text[i] == 'r'``; copies the ``r``/``#``s marker and the raw string body -- no
        escapes -- through to the matching ``"`` + ``hashes`` ``#``s, or to EOF if unterminated."""
        marker_len = 1 + hashes
        out.append(text[i : i + marker_len])
        i += marker_len
        out.append('"')
        i += 1
        closer = '"' + "#" * hashes
        end = text.find(closer, i)
        if end == -1:
            out.append(text[i:])
            return n
        out.append(text[i:end])
        out.append(closer)
        return end + len(closer)

    def consume_char_literal(i: int) -> int | None:
        """``text[i] == "'"``; returns the index past a real char literal, or ``None`` when this
        ``'`` is not one (e.g. the prime in an identifier)."""
        j = i + 1
        if j < n and text[j] == "\\" and j + 1 < n:
            j += 2
        elif j < n:
            j += 1
        if j < n and text[j] == "'":
            out.append(text[i : j + 1])
            return j + 1
        return None

    def consume_interp_string(i: int) -> int:
        """``text[i]`` is the ``s``/``f``/``m`` prefix letter of an ``s!"..."``-style
        interpolated string (already confirmed followed by ``!"``); the literal portions are a
        plain escaped string, and each ``{...}`` is scanned as real code via ``scan_region`` so a
        nested string/comment/brace never leaks into the surrounding literal text. Returns the
        index past the closing ``"``, or to EOF if unterminated."""
        out.append(text[i : i + 3])
        i += 3
        while i < n:
            ch = text[i]
            if ch == '"':
                out.append('"')
                return i + 1
            if ch == "\\" and i + 1 < n:
                out.append(ch)
                out.append(text[i + 1])
                i += 2
                continue
            if ch == "{":
                out.append(ch)
                i = scan_region(i + 1, stop_on_close_brace=True)
                continue
            out.append(ch)
            i += 1
        return i

    def scan_region(i: int, stop_on_close_brace: bool) -> int:
        """Scans ordinary Lean code -- comments, and every string/char form above -- exactly like
        the top-level scan. When ``stop_on_close_brace`` is set (used for an interpolated string's
        ``{expr}``), also tracks ``{``/``}`` nesting local to this call and returns the index past
        the ``}`` that matches the ``{`` the caller already consumed (or to EOF if unterminated);
        a ``{``/``}`` that is itself inside a comment or string here never affects that nesting, and
        a nested interpolated string's own braces are scoped to its own recursive call, never this
        one's counter. When unset (the real top level), ``{``/``}`` have no special meaning and are
        copied through like any other character -- Lean code uses plain ``{...}`` for reasons
        unrelated to string interpolation (e.g. ``{ st with phase := .running }``)."""
        nonlocal depth
        local_depth = 0
        while i < n:
            ch = text[i]
            if depth == 0 and ch == '"':
                i = consume_plain_string(i)
                continue
            if depth == 0 and ch == "'":
                new_i = consume_char_literal(i)
                if new_i is not None:
                    i = new_i
                    continue
            if depth == 0 and ch == "r" and not prev_is_ident(i):
                hashes = raw_hash_count(i)
                if hashes is not None:
                    i = consume_raw_string(i, hashes)
                    continue
            if depth == 0 and ch in "sfm" and not prev_is_ident(i) and is_interp_prefix(i):
                i = consume_interp_string(i)
                continue
            if depth == 0 and text.startswith("--", i):
                end = text.find("\n", i)
                i = n if end == -1 else end
                continue
            if text.startswith("/-", i):
                depth += 1
                i += 2
                continue
            if depth > 0 and text.startswith("-/", i):
                depth -= 1
                i += 2
                continue
            if stop_on_close_brace and depth == 0 and ch == "{":
                out.append(ch)
                local_depth += 1
                i += 1
                continue
            if stop_on_close_brace and depth == 0 and ch == "}":
                out.append(ch)
                i += 1
                if local_depth == 0:
                    return i
                local_depth -= 1
                continue
            if depth > 0:
                if ch == "\n":
                    out.append("\n")
            else:
                out.append(ch)
            i += 1
        return i

    scan_region(0, stop_on_close_brace=False)
    return "".join(out)


def scan_forbidden_tokens(unit_dir: Path) -> list[dict[str, Any]]:
    """Scans every ``*.lean`` file anywhere under the unit dir, excluding every top-level dir
    ``manifest.EXCLUDED_DIRS`` excludes from the snapshot/version hash (``receipts``, ``traces``,
    ``.lake``, ``tmp`` -- the exact same rule ``manifest._excluded_top_level`` applies, reused
    here rather than re-implemented, so a scratch file under one of these dirs can never diverge
    between what gets hashed and what gets scanned) -- not just ``Unit/*.lean``: a bypass placed
    directly in ``Main.lean``, or in a separate, non-`Unit`-prefixed `lean_lib`/`lean_exe` a
    unit's own ``lakefile.toml`` adds (e.g. ``Evil.lean``), used to go completely unscanned here
    (round 5 finding). This text scan stays secondary: the semantic per-constant check below
    (``formalcheck``, invoked over the identical file-derived module scope via
    ``compute_module_scope``) is the load-bearing one -- see the module docstring for why a token
    denylist can never be complete on its own (a runtime-built option name, or a bypass that
    never adds a literal forbidden token to the source at all)."""
    hits = []
    for path in sorted(unit_dir.rglob("*.lean")):
        rel = path.relative_to(unit_dir)
        if manifest_mod._excluded_top_level(rel):
            continue
        # V1.2 (round 6): `errors="replace"` -- never raise `UnicodeDecodeError` on an
        # undecodable byte (e.g. a stray latin-1 byte in a comment): the scan degrades to
        # scanning the replacement character in its place rather than crashing `,formal prove`.
        stripped = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        for lineno, line in enumerate(stripped.splitlines(), start=1):
            for match in _TOKEN_RE.finditer(line):
                hits.append({"file": str(rel), "line": lineno, "token": match.group(1)})
    return hits


def compute_module_scope(unit_dir: Path) -> list[str]:
    """Every root module whose ``.lean`` source lives under the unit dir, excluding every
    top-level dir ``manifest.EXCLUDED_DIRS`` excludes from the snapshot/version hash
    (``receipts``, ``traces``, ``.lake``, ``tmp``). ``Unit/Proofs.lean`` -> ``Unit.Proofs``,
    ``Main.lean`` -> ``Main``, and a separate local library such as ``Evil.lean`` -> ``Evil``.

    This filesystem-derived list deliberately names build/check roots, not the complete import
    graph. ``build.lake_build`` explicitly compiles each listed root. At proof time,
    ``formalcheck`` imports each root and semantically checks every non-trusted module in the
    resulting transitive environment, including ordinary Lake dependencies outside ``unit_dir``;
    only the pinned toolchain and FormalKit are trusted. The real ``leanchecker`` independently
    kernel-replays these explicit roots, whose imports supply their dependency declarations.
    Reusing ``manifest._excluded_top_level`` keeps scratch/generated paths aligned with the
    snapshot hash and prevents excluded files from becoming bogus Lake targets."""
    modules = []
    for path in sorted(unit_dir.rglob("*.lean")):
        rel = path.relative_to(unit_dir)
        if manifest_mod._excluded_top_level(rel):
            continue
        modules.append(".".join(rel.with_suffix("").parts))
    return modules


def _kit_dir_for_unit(unit_dir: Path) -> Path | None:
    """The kit dir this unit's own ``MANIFEST.json``/``kit_hash`` names, under the resolved
    catalog state root (mirrors ``paths.Layout.kit_dir`` without needing a workspace/git repo,
    which this read-only lookup has no other reason to require). ``None`` when the manifest is
    missing or malformed -- callers report that as an environment error rather than raising,
    since ``run_prove`` never raises."""
    manifest_file = unit_dir / "MANIFEST.json"
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    kit_hash = manifest.get("kit_hash") if isinstance(manifest, dict) else None
    if not isinstance(kit_hash, str) or not kit_hash:
        return None
    return paths.state_root() / "_kit" / kit_hash


def ensure_formalcheck(kit_dir: Path, timeout: float | None = None) -> Path | dict[str, Any]:
    """Builds FormalKit's own ``formalcheck`` executable *in the kit* (``cwd=kit_dir``, never the
    unit dir): a Lake `path`-required local dependency builds in its own directory, not the
    dependent's (confirmed: a unit's plain ``lake build`` already writes FormalKit's own compiled
    ``.olean``s under ``kit_dir/.lake/build/...``, shared across every unit referencing that same
    kit hash) -- building ``formalcheck`` here, once per kit hash, gets that same sharing for
    free instead of rebuilding it inside every unit dir. Returns the built executable's absolute
    path (``<kit_dir>/.lake/build/bin/formalcheck``, Lake's own default `lean_exe` output
    location -- confirmed against a real build) on success, or an environment-error dict (never
    raises) on a nonzero/environment-failure exit."""
    result = run(["lake", "build", "formalcheck"], cwd=kit_dir, timeout=timeout)
    if is_environment_failure(result) or result.returncode != 0:
        return {
            "ok": False,
            "environment_error": True,
            "message": (
                f"building `formalcheck` in the kit failed (exit {result.returncode}): "
                f"{(result.stdout + result.stderr).strip()[-500:]}"
            ),
        }
    return kit_dir / ".lake" / "build" / "bin" / "formalcheck"


_LEANCHECKER_MISSING_MARKER = "could not execute external process"


def resolve_leanchecker(unit_dir: Path, timeout: float | None = None) -> Path | dict[str, Any]:
    """Absolute path to the toolchain's real ``leanchecker`` binary: ``lake env lean
    --print-prefix`` (run from the unit dir, so it reflects the unit's own pinned toolchain)
    prints the toolchain root, and ``<prefix>/bin/leanchecker`` is where the real binary lives
    (confirmed against a real Lean 4.34.1 toolchain). Never resolved via a bare ``leanchecker``
    looked up on ``PATH`` (i.e. never `lake env leanchecker` with no explicit binary path): a
    unit's own ``lakefile.toml`` can declare a `lean_exe` also named `leanchecker`, and `lake
    env` puts a unit's own built executables ahead of the toolchain's on `PATH` -- confirmed live
    that such a unit's bare `lake env leanchecker` silently runs the *fake* one and exits 0.
    Returns an environment-error dict (never raises) when the prefix lookup fails or the
    resolved binary does not exist."""
    prefix_result = run(["lake", "env", "lean", "--print-prefix"], cwd=unit_dir, timeout=timeout)
    if is_environment_failure(prefix_result) or prefix_result.returncode != 0:
        return {
            "ok": False,
            "environment_error": True,
            "message": (
                f"`lake env lean --print-prefix` failed (exit {prefix_result.returncode}): "
                f"{prefix_result.stderr.strip()[:500]}"
            ),
        }
    binary = Path(prefix_result.stdout.strip()) / "bin" / "leanchecker"
    if not binary.exists():
        return {"ok": False, "environment_error": True, "message": f"leanchecker binary not found at {binary}"}
    return binary


def parse_prove_json(stdout: str) -> dict[str, Any]:
    """Parse ``formalcheck``'s one-line JSON document (``{"theorems": [{"name": ..., "axioms":
    [...]}, ...], "user_written": [name, ...], "scope_violations": [{"name": ..., "kind": ...,
    ...}, ...]}``). ``theorems``/``user_written`` cover only ``Unit.Proofs``'s theorem-kind
    constants, unchanged from the previous design's own contract (see the module docstring's F3
    vacuity-guard paragraph); ``scope_violations`` is new -- one entry per semantic violation
    (``axiom_declaration``, ``unsafe``, ``extern``, ``implemented_by``, or ``disallowed_axiom``)
    found on any constant across the unit's whole module scope (never ``partial``: round 5's
    threat-model amendment drops it, see the module docstring above). Returns
    ``{"theorems": [...], "user_written": [...], "scope_violations": [...]}`` (each sorted, for a
    deterministic receipt) on success, or ``{"error": <message>}`` for anything else -- garbage
    stdout, valid JSON with the wrong shape, or a missing/malformed field -- so a caller can fail
    the stage with a message instead of raising."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {"error": f"formalcheck did not print valid JSON: {exc}"}
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("theorems"), list)
        or not isinstance(payload.get("user_written"), list)
        or not isinstance(payload.get("scope_violations"), list)
    ):
        return {
            "error": ("formalcheck's JSON output is missing a `theorems`, `user_written`, or `scope_violations` array.")
        }
    theorems: list[dict[str, Any]] = []
    for entry in payload["theorems"]:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("name"), str)
            or not isinstance(entry.get("axioms"), list)
            or not all(isinstance(a, str) for a in entry["axioms"])
        ):
            return {"error": f"formalcheck's JSON output has a malformed theorem entry: {entry!r}"}
        theorems.append({"name": entry["name"], "axioms": list(entry["axioms"])})
    if not all(isinstance(name, str) for name in payload["user_written"]):
        return {"error": f"formalcheck's JSON output has a malformed `user_written` entry: {payload['user_written']!r}"}
    violations_by_json: dict[str, dict[str, Any]] = {}
    for entry in payload["scope_violations"]:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("name"), str)
            or not isinstance(entry.get("kind"), str)
        ):
            return {"error": f"formalcheck's JSON output has a malformed `scope_violations` entry: {entry!r}"}
        # The checker imports each explicit root in a separate environment to avoid collisions
        # between unrelated `main` declarations. A shared dependency can therefore be observed
        # from several roots; collapse identical reports into one deterministic receipt entry.
        violations_by_json[json.dumps(entry, sort_keys=True, separators=(",", ":"))] = entry
    theorems.sort(key=lambda t: t["name"])
    user_written = sorted(payload["user_written"])
    violations = sorted(violations_by_json.values(), key=lambda v: (v["name"], v["kind"]))
    return {"theorems": theorems, "user_written": user_written, "scope_violations": violations}


def check_prove_theorems(theorems: list[dict[str, Any]]) -> dict[str, Any]:
    used_axioms: set[str] = set()
    for theorem in theorems:
        used_axioms.update(theorem["axioms"])
    disallowed = sorted(used_axioms - ALLOWED_AXIOMS)
    return {
        "theorem_count": len(theorems),
        "theorems": theorems,
        "axioms_used": sorted(used_axioms),
        "disallowed_axioms": disallowed,
        "ok": bool(theorems) and not disallowed,
    }


def run_kernel_recheck(unit_dir: Path, modules: list[str], timeout: float | None = None) -> dict[str, Any]:
    """Runs the toolchain's real ``leanchecker`` (resolved by absolute path, see
    ``resolve_leanchecker``) with the same explicit ``modules`` list ``formalcheck`` used, as an
    independent kernel re-check of every one of those already-built modules. Confirmed against a
    real Lean 4.34.1 toolchain (source read: ``LeanChecker.lean``'s ``main``): each positional
    arg is matched against every module on the search path by exact name or name-prefix, so an
    explicit list -- unlike leanchecker's own default "current package name" heuristic, which
    reads only the package name from ``lake-manifest.json`` and so never includes `Main` or a
    separately-named `lean_lib` (`Unit`/`Evil` would both need matching, and `Main` matches
    neither) -- makes it replay every named module's own newly-defined declarations through the
    real kernel, independent of any elaboration-time debug option (confirmed live: this is what
    catches both a `Main.lean`-only bypass and a separate non-`Unit`-prefixed `lean_lib` bypass
    that the *default*, no-argument ``lake env leanchecker`` lets through unnoticed). A clean F3
    unit's kernel re-check still exits 0 in under a second (measured against a real 5-module
    unit). A missing ``leanchecker`` binary makes ``lake env <name>`` print ``could not execute
    external process '<name>'`` and exit 255 -- neither exit code ``is_environment_failure``
    already recognizes (124/127), so that exact message is matched here too and reported as an
    environment error, never a pass."""
    leanchecker = resolve_leanchecker(unit_dir, timeout)
    if isinstance(leanchecker, dict):
        return {**leanchecker, "exit_code": None}
    result = run(["lake", "env", str(leanchecker), *modules], cwd=unit_dir, timeout=timeout)
    if is_environment_failure(result) or (result.returncode == 255 and _LEANCHECKER_MISSING_MARKER in result.stderr):
        return {
            "ok": False,
            "environment_error": True,
            "exit_code": result.returncode,
            "stderr": result.stderr[-2000:],
            "message": (f"leanchecker environment failure (exit {result.returncode}): {result.stderr.strip()[:500]}"),
        }
    if result.returncode != 0:
        return {
            "ok": False,
            "environment_error": False,
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
            "message": (
                f"kernel re-check (leanchecker) rejected the built modules "
                f"(exit {result.returncode}): {(result.stdout + result.stderr).strip()[-500:]}"
            ),
        }
    return {"ok": True, "environment_error": False, "exit_code": 0}


def run_prove(unit_dir: Path, build_receipt: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "kind": "prove",
        "build_ok": bool(build_receipt.get("ok")),
        "forbidden_tokens": [],
    }
    if not build_receipt.get("ok"):
        # V1.2 (round 6): check the build receipt *before* ever scanning -- a failed build can
        # leave a unit dir containing a broken/non-UTF-8 `.lean` file (e.g. a stray module the
        # build itself already rejected), and there is no reason to scan it at all once the build
        # has already failed. `forbidden_tokens` stays `[]` (never omitted): `cli.py`'s `cmd_prove`
        # human-output path indexes `receipt["forbidden_tokens"]` unconditionally whenever
        # `environment_error` is unset, which a non-environment build failure leaves unset here.
        receipt["ok"] = False
        receipt["axioms"] = None
        return receipt
    token_hits = scan_forbidden_tokens(unit_dir)
    receipt["forbidden_tokens"] = token_hits
    if token_hits:
        receipt["ok"] = False
        receipt["axioms"] = None
        return receipt
    kit_dir = _kit_dir_for_unit(unit_dir)
    if kit_dir is None:
        receipt["ok"] = False
        receipt["axioms"] = None
        receipt["environment_error"] = True
        receipt["message"] = f"no usable `kit_hash` in {unit_dir}/MANIFEST.json; run `,formal init` first."
        return receipt
    formalcheck = ensure_formalcheck(kit_dir, timeout)
    if isinstance(formalcheck, dict):
        receipt["ok"] = False
        receipt["axioms"] = None
        receipt.update(formalcheck)
        return receipt
    modules = compute_module_scope(unit_dir)
    result = run(["lake", "env", str(formalcheck), *modules], cwd=unit_dir, timeout=timeout)
    if is_environment_failure(result):
        receipt["ok"] = False
        receipt["axioms"] = None
        receipt["environment_error"] = True
        receipt["lean_exit_code"] = result.returncode
        receipt["lean_stderr"] = result.stderr[-2000:]
        receipt["message"] = (
            f"`formalcheck` environment failure (exit {result.returncode}): {result.stderr.strip()[:500]}"
        )
        return receipt
    parsed = parse_prove_json(result.stdout)
    receipt["lean_exit_code"] = result.returncode
    receipt["lean_stderr"] = result.stderr[-2000:]
    if "error" in parsed:
        # A real, non-environment-failure subprocess result (formalcheck ran and returned) whose
        # stdout still cannot be understood -- fail explicitly with a message rather than
        # crashing on a KeyError/JSONDecodeError the caller never expected.
        receipt["ok"] = False
        receipt["axioms"] = None
        receipt["error"] = parsed["error"]
        receipt["message"] = parsed["error"]
        return receipt
    theorems = parsed["theorems"]
    user_written = parsed["user_written"]
    scope_violations = parsed["scope_violations"]
    axioms_check = check_prove_theorems(theorems)
    # `theorem_count` is every *checked* theorem-kind constant in `Unit.Proofs` (no exclusion --
    # may include compiler-generated ones such as a structure's `mk.inj` or an inductive's
    # `sizeOf_spec`). `user_written_count`/`user_written_theorems` is the subset `formalcheck`
    # already filtered to code the user actually wrote (see the module docstring); the vacuity
    # guard below uses only that count, so a `Unit/Proofs.lean` containing nothing but
    # `structure`/`inductive` declarations (whose compiler-generated lemmas would otherwise make
    # `theorem_count` nonzero) still fails here.
    receipt["theorem_count"] = axioms_check["theorem_count"]
    receipt["user_written_count"] = len(user_written)
    receipt["user_written_theorems"] = user_written
    receipt["axioms"] = axioms_check
    # New: every semantic violation `formalcheck` found across the unit's *whole* module scope
    # (not only `Unit.Proofs`'s theorems) -- an `axiom` declaration, `unsafe`, `extern`,
    # `implemented_by`, or a disallowed axiom on any def/instance/opaque (never `partial`: round
    # 5's threat-model amendment drops it, see the module docstring). Existing receipt keys above
    # keep their exact previous meaning; this is additive.
    receipt["scope_violations"] = scope_violations
    if not user_written:
        receipt["ok"] = False
        receipt["error"] = (
            "no theorems found in Unit/Proofs.lean; F3 requires at least one proof "
            f"(collectAxioms checked {axioms_check['theorem_count']} theorem-kind constant(s), "
            "0 of them user-written)."
        )
        return receipt
    receipt["ok"] = result.returncode == 0 and axioms_check["ok"] and not scope_violations
    if not receipt["ok"]:
        if not receipt.get("error") and scope_violations:
            names = ", ".join(f"{v['name']} ({v['kind']})" for v in scope_violations[:5])
            receipt["error"] = f"{len(scope_violations)} constant(s) in scope failed a semantic check: {names}"
        return receipt
    # Every check above only ever sees what the token scan and the semantic per-constant check
    # can see; a bypass that leaves an already-elaborated declaration's own kernel entry wrong
    # (see the module docstring) leaves neither a literal token nor an axiom trace. Run the
    # kernel re-check only once every earlier check has already said "pass" -- it is a final,
    # independent safety net over the real kernel, not a replacement for any check above.
    kernel_check = run_kernel_recheck(unit_dir, modules, timeout)
    receipt["kernel_check"] = kernel_check
    if not kernel_check["ok"]:
        receipt["ok"] = False
        receipt["environment_error"] = kernel_check.get("environment_error", False)
        receipt["message"] = kernel_check["message"]
    return receipt
