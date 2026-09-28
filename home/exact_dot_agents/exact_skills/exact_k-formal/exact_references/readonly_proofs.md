# F3 proofs

Owner: `~/.agents/skills/k-formal/SKILL.md`. Load this reference only for an F3 unit: F2's anchors, model,
search, mutation, and replay stay as `references/lean-model.md` and `references/adapters.md` describe;
this reference adds `Unit/Proofs.lean` and the `,formal prove`/`audit` checks over it.

## When F3 applies

Add proofs only when behavior-relevant state is unbounded, `,formal explore` reports `bounded` (its state or
depth budget was hit before the search finished), or the user explicitly asks for a proof. F3 is additive: it
never substitutes for F2's exhaustive search, mutation, or trace replay, and a unit that stays F2 is complete without `Unit/Proofs.lean`.

## Invariant plus step-lemma pattern

- Define one invariant `Inv : St → Prop` per property (or one bundled invariant covering several related
  facts, see the bundling rule below).
- `inv_init : Inv init` for every state in `inits`.
- `inv_step : Inv st → Inv (step st e)` for every event `e`.
- Combine both by induction on reachability (a `Reachable` predicate closed under `step` from `inits`) to get `∀ st, Reachable st → Inv st`.
- State the property as a fact about every reachable state, quantifying over the full state and event space —
  never over a hand-picked subset of states or events.

## Per-case step lemmas

- `unfold Inv stepX; (repeat' split) <;> simp_all` is the recipe that worked across case-heavy `step`
  definitions: unfold the invariant and the step function, split every remaining case exhaustively, then
  close each goal with `simp_all`. Reach for `omega` or `decide` first on numeric/decidable side goals before writing a manual case proof.
- Prove the property theorem directly from `step`. Never introduce a second helper spec (e.g. a duplicate
  `stepFoo_eq` lemma the property proof actually goes through) — a mutant that only breaks the helper, not the
  named theorem, does not count as a kill, and `,formal mutate`/`audit` will not credit it.

## Bundling invariants

Bundle two facts into one invariant when one needs the other to stay inductive under `step` — for example "a
stub state implies session A or B" together with "a discard state implies subtree session C" — because proving
either fact alone can fail the induction step even though the conjunction is true at every reachable state.
Prove the bundle as one `Inv`, then derive each individual property from it.

## Ghost state

Add ghost state (a counter, an append-only log) only for history properties that the real observable state
cannot express on its own. Its search identity may omit a field only when equal keys preserve every property's
truth and equivalent successor behavior under the model step and every mutant. Keep a finite property-relevant
history summary in `key` when needed; if no sound finite abstraction exists, bound the search honestly rather
than silently merging states. Log the actual field the property inspects, not a substitute value chosen to make
the property trivially provable.

## One step spec

The real code's behavior lives in exactly one place: `Unit/Step.lean`'s `step` function. Every property proof
and every mutant compares against that same `step`. A second copy (a "spec" lemma restating what `step`
should do, proved once and then used by every property proof instead of `step` itself) hides bugs in `step`
from every property that goes through the spec instead — the property set stops testing the real function.

## Audit checks `,formal prove` enforces

The semantic checks run in a **compiled** FormalKit executable (`formalcheck`, `lean/FormalKit/FormalKit/Check.lean`),
not in a generated Lean program elaborated beside the unit (the previous design, which a unit's own
`macro_rules`/`elab_rules` could rewrite). `formalcheck` is elaborated once, when the kit is built, and never
elaborates the unit's syntax: it `Lean.importModules`s the unit's already-compiled `.olean`s at runtime with
`loadExts := false` and never calls `enableInitializersExecution`, so a module's `initialize`/`builtin_initialize`
block never runs. `formalcheck` imports each module in scope in its **own**
`importModules` call, one module at a time, rather than combining every module into one shared environment:
two independently-compiled root modules that each declare their own unqualified `def main` (`Main.lean` and a
second `lean_exe`'s own root, the exact "leanchecker-shadow" scenario below) are ordinary, non-hostile Lean, and
combining them into one environment fails outright with `environment already contains 'main' from ...` —
confirmed against a real Lean 4.34.1 toolchain. Checking each module separately avoids that; a module that
references another module in scope (an `Evil.lean`-style bypass below) still sees it correctly, because that
reference resolves through the referencing module's own already-recorded `import` header, not through combining
separate top-level roots together.

**Threat model.** These checks assume an honest but fallible agent, not a user deliberately trying to fool the
checker. They catch accidental unsound or vacuous shortcuts — `sorry`/`admit`/`axiom`, `native_decide`,
`unsafe`/`implemented_by`/`extern` changing what actually executes, an unkilled mutant, model drift — never a
deliberate metaprogramming attempt aimed at defeating the checker itself (a `macro_rules` takeover, a
runtime-built kernel-bypass option, a fake tool binary, a lexer trick). The specific deliberate-bypass defenses
below (per-module `importModules` isolation, `loadExts := false`, absolute-path `leanchecker` resolution, the
explicit module list) stay because rounds 1-5 already found and tested them; no further deliberate-bypass
hardening is in scope going forward. A passing `,formal prove` certifies the model under honest authorship,
never a security boundary against a user determined to defeat the checker.

`,formal prove <unit>` runs, in order, and fails on the first violation:

1. `lake build`, then (only if that succeeds) a second `lake build` naming every module step 3's filesystem
   scan finds under the unit dir (round 6; previously only `Unit.Proofs`) — two sequential `lake build`
   invocations. `--proofs` is a `,formal build` CLI flag (`,formal build <unit> --proofs`) that selects this
   two-invocation sequence; `lake` itself never receives a `--proofs` flag.
2. A **secondary** forbidden-token scan of every `*.lean` file anywhere under the unit dir (not just
   `Unit/*.lean` — a bypass placed directly in `Main.lean`, or in a separate, non-`Unit`-prefixed `lean_lib`/
   `lean_exe` a unit's own `lakefile.toml` adds, used to go completely unscanned; this is a round-5 finding),
   excluding the same top-level `manifest.EXCLUDED_DIRS` dirs step 3 excludes (`receipts`, `traces`, `.lake`,
   `tmp`) and outside comments (never outside string/char literals — a forbidden word inside a
   plain, raw, or interpolated string or char literal is still scanned and still fails the audit; only a
   `/- ... -/`/`--` comment is stripped before the scan runs): `sorry`, `admit`, `axiom`, `native_decide`,
   `implemented_by`, `extern`, `unsafe`, `skipKernelTC`, `addDeclCore`, `addDeclWithoutChecking`. The last
   three catch kernel-bypass routes that leave no axiom trace for step 3's `collectAxioms` to see at all:
   `set_option debug.skipKernelTC true in run_cmd ... Lean.addDecl decl` and the lower-level
   `Environment.addDeclCore ... false` both add a declaration the kernel never type-checks (confirmed against
   a real Lean 4.34.1 toolchain: an ill-typed proof of `False` was added either way and reported zero axioms).
   Any hit outside a comment fails the audit; `sorry` in particular means an unfinished proof even when the
   file otherwise compiles. **This token denylist can never be complete on its own, and stays secondary to
   step 3's semantic check**: a runtime-built option name such as `Name.mkStr2 "debug" ("skipKernel" ++
"TC")` disables the same kernel checking the literal `debug.skipKernelTC` token would, without that literal
   token ever appearing in the source for this scan to catch, and a character-level Python token scanner can
   never fully lex Lean (context-dependent interpolation such as `throwError "{..}"`, `'\x41'`, `«x»`) — a
   `sorry`/`native_decide` hidden behind either trick still elaborates to a real `sorryAx`/native-decide axiom,
   so step 3's `collectAxioms` (never step 4) is what actually catches it either way. Step 4 below is a
   distinct, later safety net that only ever runs once steps 1-3 have already passed (`prove.py`'s
   `run_prove`); it specifically catches a bypass that leaves no axiom trace at all — an already-elaborated
   declaration's own kernel entry made wrong directly — which neither this scan nor step 3's semantic check
   can see (see step 4 below).
3. Computes the unit's local module scope and the imported dependency closure used by those modules. The pinned
   toolchain and the content-addressed FormalKit kit are explicit trusted roots; another Lake dependency is not
   trusted merely because its source sits outside the unit directory. Semantic validation includes every
   nontrusted imported dependency that can affect the executable model, including `implemented_by`, `extern`,
   unsafe declarations, user axioms, and disallowed collected axioms. An external module whose provenance or
   scope cannot be resolved fails closed instead of being silently treated as trusted.
   The unit's local scope still includes every buildable module under its declared roots, including additional
   `lean_lib`/`lean_exe` roots. Builds `formalcheck` once (shared per kit hash, in the kit's own dir, never the
   unit dir) and runs it over the resolved scope. The receipt retains `scope_violations` for every checked
   constant while preserving the separate user-written theorem classification and vacuity guard below.
   Separately, and unchanged from the previous design, `Unit.Proofs`'s own theorem-kind constants (and only
   those) still feed the F3 vacuity guard, via the same JSON contract `formalcheck` prints
   (`{"theorems": [{"name": ..., "axioms": [...]}, ...], "user_written": [name, ...], "scope_violations":
[{"name": ..., "kind": ...}, ...]}`):
   - Every printed axiom (for every checked theorem, including compiler-generated ones) is checked against
     `{propext, Quot.sound, Classical.choice}` (Lean's standard axioms) or the set is empty — anything else,
     most commonly `sorryAx` or a `decide +native` native-decide axiom, fails the audit; the JSON's per-theorem
     breakdown names exactly which theorem carried the disallowed axiom.
   - **A `private theorem` is checked, not refused.** `formalcheck` never elaborates the unit's own syntax at
     all (see the mechanism note above) — `Lean.collectAxioms` instead runs against the already-elaborated
     environment it `importModules`s at runtime, which already has the private declaration in scope from that
     import (`Lean.privateToUserName?` recovers the name the user
     wrote, for both the JSON `name` field and any error message; when it returns `none` for a compiler-private
     auxiliary rather than a user `private` declaration, the raw mangled name is used as-is) — confirmed
     against a real Lean 4.34.1 toolchain, including a `private theorem` using `sorry` correctly failing with `sorryAx` in its axiom list.
   - **Zero _user-written_ theorems is a failure, not a vacuous pass**, separately from the axiom check above.
     A declaration counts as user-written only when `Lean.findDeclarationRanges?` returns a source position
     **and**, after stripping every comment and string-literal content from the source text between that
     range's full `range` start and its `selectionRange` start, the remaining text contains `theorem` as its
     own whole token — split on non-identifier characters, never a bare substring match. A plain substring
     test over that same text is not enough on its own: a doc comment merely mentioning the word "theorem"
     (e.g. `/-- Nonempty witness for the theorem prover -/` right before an unrelated `instance`) would
     otherwise be miscounted as user-written even though no real `theorem` keyword follows it anywhere in that
     range; stripping string-literal content too (not just comments) means `@[deprecated "use --x instead"]
theorem t1` still correctly counts `t1`, since the string's own content never survives the strip in the
     first place. The declaration-range check alone is also not enough: an `@[ext] structure`'s generated
     `.ext`/`.ext_iff` theorems, the same two theorems from a standalone `attribute [ext]` command, and a
     `deriving ReflBEq, LawfulBEq`/`deriving ... Nonempty` instance theorem all return a source position too
     (each one's range points at the structure/attribute/deriving syntax that produced it, never at an actual
     `theorem` keyword) — the comment-and-string-stripped, whole-token check is what tells those apart from a
     real `theorem`/`private theorem`/`protected theorem`/`@[simp] theorem`/`set_option ... in theorem`/
     underscore-named (`_t`, `` `«_x»` ``)/`open X in theorem`-one-liner declaration, every one of which has
     its own `theorem` keyword, outside any comment or string, between those two positions. A theorem produced
     by a user-written macro is _checked_ like every other theorem-kind constant (the axiom check above never
     excludes it) but is never counted as user-written — its declaration range points at the macro invocation
     site, which never contains a literal `theorem` keyword; this fails closed rather than trusting a shape
     the check cannot see into. The receipt's `theorem_count` is the full checked count (every theorem-kind
     constant, which the axiom check above always covers), and `user_written_count` is the subset passing both
     checks. F3 exists specifically to add proofs; an F3 unit's `Unit/Proofs.lean` with zero user-written
     theorems fails `,formal prove`/the `prove` audit stage even when it defines `structure`/`inductive`
     declarations whose compiler-generated lemmas make the checked count nonzero.
   - A malformed or non-JSON stdout (an environment/toolchain problem, not a proof problem) fails the audit
     with an explicit message rather than crashing.
4. Only once steps 1-3 have all already passed, an independent kernel re-check with the toolchain's real
   `leanchecker`, resolved by **absolute path** (`lake env lean --print-prefix` from the unit dir, then
   `<prefix>/bin/leanchecker`) — never a bare `leanchecker` on `PATH`: a unit's own `lakefile.toml` can declare
   a `lean_exe` also named `leanchecker`, and `lake env` puts a unit's own built executables ahead of the
   toolchain's on `PATH` — confirmed live that such a unit's bare `lake env leanchecker` silently runs the
   _fake_ one and exits 0. It is invoked with the **same explicit module list** `formalcheck` used, never
   leanchecker's own default "current package name" heuristic (confirmed against a real Lean 4.34.1 toolchain,
   source: `LeanChecker.lean`'s `main`: with no args it reads only the current package's name from
   `lake-manifest.json` and matches modules by that name-prefix, which never includes `Main` or a
   separately-named `lean_lib`/`lean_exe` at all — confirmed live this exact gap let a `Main.lean`-only bypass
   or a separate non-`Unit`-prefixed `lean_lib` bypass through the old design's bare, no-argument
   `lake env leanchecker`). Passing the explicit list makes leanchecker replay every one of those modules' own
   newly-defined declarations through the real kernel, independent of any elaboration-time debug option — this
   is what step 2's token denylist and step 3's per-constant check can both miss: a bypass that never adds a
   new declaration to the module the checks above inspect, but instead makes an _already-elaborated_
   declaration's own kernel entry wrong (`set_option debug.skipKernelTC true in run_cmd ... Lean.addDecl` adds
   an ill-typed proof reporting zero axioms from `collectAxioms`, and referencing that bad declaration from a
   new, normally-elaborated theorem elsewhere — even in a different `lean_lib`, or directly in `Main.lean` —
   elaborates and axiom-checks clean too, since elaboration trusts an already-recorded type rather than
   re-deriving it). A nonzero exit or any reported problem fails `,formal prove`, with the checker's own output
   attached to the receipt's `kernel_check`; a clean unit still passes (confirmed: under a second against a
   real 5-module F3 unit). A missing `leanchecker` binary makes `lake env <name>` exit 255 with `could not
execute external process '<name>'` (neither exit code `is_environment_failure` already recognizes) — that
   is reported as an environment error, never a pass.

`,formal audit <unit>` for an F3 unit runs `anchors, build, explore, mutate, replay, prove` and only reports
`verdict: pass` when every stage passes. A design unit (`--design`) skips only the `replay` stage (recorded
`n/a`, driving the `conformance: n/a-design` wording) instead of failing on a missing adapter; the `anchors`
stage still runs for a design unit, it just does not fail solely for having zero anchors (`audit.py`'s
`run_stage_anchors`: `if not anchors and not design: ... "no anchors"` — any anchors a design unit does have are still checked).

## Stop after 2 repair rounds

When a proof or an audit stage fails, give the next attempt fresh context — do not carry a failed round's
build/error transcript forward. After two repair rounds on the same unit with no passing audit, stop and
report the remaining open theorems/properties honestly instead of continuing to iterate; a third round without
new evidence is a Requirements Reset case (SOP §3.4), not another attempt.
