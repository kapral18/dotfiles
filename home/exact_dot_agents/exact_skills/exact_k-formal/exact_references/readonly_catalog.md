# Catalog

Owner: `~/.agents/skills/k-formal/SKILL.md`. Load this reference for catalog layout, staleness/inheritance
rules, or the Scope-time `,formal` commands.

## Purpose

The catalog is a persistent, per-machine store of unit versions. Anchor validity permits reuse of extraction and saved model content
across branches, worktrees, and squash merges. It does not make an audit receipt current: delivery always requires the exact current
snapshot and inputs, while matching stage receipts may be reused only within that identity.

## State root and repo identity

- Root: `$AGENT_FORMAL_HOME`, else `$XDG_STATE_HOME/agent-formal`, else `~/.local/state/agent-formal`.
- The resolved root and every selected repository, work, and unit/version destination must remain under that trusted root and outside
  the current git workspace; pre-existing ancestor symlinks that cross either boundary are refused (exit 2) before workspace writes.
- Repo id: the first 16 hex characters of `sha256(realpath(git rev-parse --git-common-dir))`. This is shared
  across worktrees of the same repo (unlike a per-toplevel key), which is what makes inheritance across worktrees work.
- `<root>/<repo-id>/repo.json` records the repo id, `git remote get-url origin` (when one exists), and the common-dir path.

## Layout

```text
<root>/_kit/<kit-hash>/                     copy of the FormalKit Lean library; Lake builds here, never under ~/lib
<root>/<repo-id>/repo.json
<root>/<repo-id>/index.json                 {units: {<unit>: {versions: [{branches: {<branch-key>: <last-save-seq>, ...}, seq: <global-seq>, ...}], work: [<branch-key>...]}}}
<root>/<repo-id>/work/<branch-key>/<unit>/  editable unit for the current branch
<root>/<repo-id>/units/<unit>/versions/<version-id>/   saved copy: no .lake, no receipts/tmp
```

- Unit and version identifiers reject absolute paths, separators, parent traversal, and any resolved destination outside the trusted
  catalog root or inside the workspace, including escapes through pre-existing repository, work, units, or leaf symlinks.
  Selected work and version paths must also remain in their own storage subtree; mutable work cannot alias an immutable saved version.
  Hashing rejects symlinked unit directories rather than omitting their contents before a copy.

- `branch-key`: a collision-resistant storage key derived from the full branch ref; detached-HEAD keys occupy a distinct namespace.
  Treat it as opaque and use command-returned `unit_dir` paths instead of reconstructing it.
- `version-id`: the first 16 hex characters of `sha256` over the sorted `(relative path, file sha256)` pairs
  of the saved unit's files, excluding the top-level working dirs `tmp/`, `traces/`, `receipts/`, `.lake/`,
  every `lake-manifest.json` file at any depth (`manifest.EXCLUDED_FILES`; Lake's own lockfile, never unit
  content), and, within `MANIFEST.json`, the `branch` and `source_commit` fields (the two fields
  `checkout`/`init --from-version` overwrite on every checkout) — content-addressed, not branch- or
  commit-addressed, so identical unit content saved from different branches/commits still shares one version id.
- Materialization encodes branch and state-path values according to the target file format (JSON or TOML); quoted names and
  backslashes are data, never template syntax.

## Anchors

- Anchor snippets preserve the exact selected source text for hashing and comparison: tabs, indentation, internal and trailing
  whitespace, and blank lines are significant. Any change to that text stales the anchor.
- Anchor check states: `unchanged` (the exact snippet is found at its recorded range, or relocated when identity is unambiguous),
  `edited` (the file exists but the original occurrence cannot be established, including ambiguous relocation), or `missing`
  (the file itself is gone).
- Unique snippets may relocate when exactly one current occurrence matches. A nonunique snippet also records a conservative source-file
  digest as origin identity; coordinates alone never prove identity. It remains `unchanged` at the recorded range only while that
  identity still matches, and any source change that prevents proving the same occurrence resolves `edited` with `reason: "ambiguous"`.
- `--write` persists only an identity-proven `unchanged` relocation and never relocates an ambiguous anchor.
- `,formal anchors check <unit>` reports one of these per anchor and exits 1 unless every anchor is `unchanged`.
  `,formal anchors check <unit> --write` additionally persists a relocated `unchanged` anchor's new start/end back into `ANCHORS.json`.
- `ANCHORS.json` is never hand-edited. Create an anchor with `,formal anchors add <unit> <path>:<start>-<end>`; passing `--id <existing>`
  replaces that row in place (re-anchor) instead of erroring on a duplicate id. A non-`--design` unit needs at least one anchor.

## Audit and snapshot identity

- **Snapshot**: `,formal audit <unit>` and `,formal catalog save <unit>` compute the same snapshot id over the unit files, `HEAD`,
  the full workspace diff, every untracked file, and every anchored file plus files named directly by the adapter. Untracked records
  use unambiguous path-and-file-digest framing, so different path/content boundaries cannot collide. Any staged, unstaged, untracked,
  anchored, or direct adapter-input change produces a new snapshot and invalidates old receipts. A git command needed for this identity
  that cannot run fails closed with exit 2.
- `,formal audit <unit>` writes `<unit_dir>/receipts/<snapshot>/<stage>.json` per stage plus `<unit_dir>/receipts/<snapshot>/audit.json`
  (the aggregate verdict); a cached stage receipt for the current snapshot is reused instead of rerun -- except an `error` stage receipt
  (see below), which is never persisted and therefore never reused.
- **F2 stages** (default): `anchors, build, explore, mutate, replay`. **F3 adds** `prove`. `--require a,b,c` overrides the tier default with
  an explicit comma-separated stage list, except that a `--require` set containing `prove` without `build` still runs `build` first --
  `prove` needs a real, freshly-run build receipt (never a synthesized empty one) to know whether the code even compiles before
  running `formalcheck` against it. A design unit (`--design`) skips `replay`'s adapter requirement and reports that stage `n/a`
  (conformance `n/a-design`) instead of failing on a missing adapter. A stage excluded by `--require` (never attempted at all) reports
  conformance `not-run`, distinct from both `n/a-design` and an adapter-less `unverified` run.
- The `replay` stage generates its own `--mode cover` traces before running the adapter, capped at `MANIFEST.json`'s `budgets.max_traces`
  (default 500) and using its `budgets.max_states`/`max_depth`; a manual `,formal traces` run is only needed for `--mode failures`
  diagnosis or ad hoc inspection, never as a prerequisite to `,formal audit`.
- **Environment failures never cache, and exit 2.** `,formal audit` refuses immediately (exit 2, before any stage runs or any receipt is
  written) when `lake` is not on PATH at all. When a stage's own subprocess fails for an environment reason mid-audit instead (a timeout,
  a spawn failure, `lake exe`/the adapter/`lake env lean` exiting 124 or 127) that stage's status is `error` — distinct from `fail` — and
  its receipt is never written to disk, so fixing the environment and re-running never finds a stale cached `fail`/`error`. Any `error`
  stage makes `,formal audit` exit 2 (never 1); `audit.json` is still written. A `build` stage's own environment error still cascades the
  later required stages as `fail`/`"skipped: build failed"` exactly like an ordinary build failure, except that cascaded note is likewise
  never persisted (the skip itself was only caused by the environment problem, not a real finding).
- Adapter crashes, malformed or non-UTF-8 JSONL, duplicate trace ids, missing output rows, output-length mismatches, `lake exe`
  failures, and zero generated or compared traces are recorded as replay `fail` (or `error` under the environment rule), never uncaught
  exceptions or vacuous passes. Independent later required stages still run.
- `certifies` reports complete cover only from a successful explore result with valid state and `bounded` metadata, positive replay
  coverage, and no budget truncation. Missing, skipped, failed, or malformed exploration metadata makes cover unknown.
- `verdict: pass` requires every required stage `pass` or `n/a`; an `unverified` replay stage (no adapter) fails the verdict unless
  `--allow-unverified-conformance` is passed, and even then `certifies` still states conformance is unverified. Any `error` stage always
  fails the verdict, regardless of `--allow-unverified-conformance`.
- `certifies` is one semicolon-joined line: `model: <N> props hold[ within budget], <N> refuted as expected; mutants <killed>/<total>
killed; conformance: <passed>/<total> traces` (or `n/a-design` / `not-run` / `unverified`); `proofs: <user-written> theorems (<checked> constants axiom-checked), axioms clean` (or `axioms dirty:
<names>`, or `proofs: n/a` for an F2 unit). `axioms dirty: <names>` lists the disallowed axiom names (e.g. `sorryAx`, or the auxiliary axiom
  `decide +native` adds) that `Unit.Proofs`'s own theorem-kind constants used and takes priority over the two branches below, because `formalcheck` also records that same
  theorem as its own `disallowed_axiom` scope violation — printing "scope violation(s)" instead would hide the axiom names. Only once
  `Unit.Proofs`'s own axioms are clean does a `disallowed_axiom`/`axiom_declaration`/`unsafe`/`extern`/`implemented_by` violation on any
  _other_ constant across the unit's whole module scope instead print `scope violation(s): <name (kind)>, ...` (capped at 5), and a failure
  of the independent kernel re-check (`leanchecker`, run only after every check above already passed) prints `kernel re-check failed:
<message>` — neither of those two cases ever prints `axioms clean` despite `Unit.Proofs`'s own axioms being clean.
- `explore` fails when the unit has zero properties, and `mutate` fails for zero mutants, empty `killedBy`/`expected` declarations,
  or inconclusive required evidence. In particular, a bounded `.refuted` search with no counterexample is never a mutant kill or a
  successful control result; an observed `.holds` violation can remain a conclusive kill.
- `,formal catalog save <unit>` requires `receipts/<snapshot>/audit.json` for the _current_ snapshot with `verdict: pass` reached with a
  verified conformance stage; a `pass` reached only via `--allow-unverified-conformance` does not count. `--allow-unverified` on `save`
  itself bypasses that requirement and records the saved version as unverified, distinct from the audit-level allowance.

## Staleness and inheritance

- A saved version is **valid** for a working tree exactly when every one of its anchors resolves `unchanged` in that tree.
- `,formal catalog resolve <unit>` picks the newest valid version, preferring one saved on the current branch,
  then the newest valid version from any branch; it exits 1 when no version is valid.
- `,formal catalog checkout <unit>` materializes an explicitly resolved valid version into a branch with no work dir. This carries a
  unit across a branch switch, new worktree, or squash merge. Resolution depends on anchors, not commit ancestry. It exits 1 when no
  valid version resolves. It refuses with exit 2 when an existing work dir differs from the resolved version unless `--force` is passed,
  preventing silent loss of unsaved files; stale repair does not require checkout and keeps an existing work dir in place.
- `,formal catalog stale [--base REF]` and `,formal catalog uncovered --base REF` both resolve each unit's anchors
  from that unit's current branch work dir when one exists, else its newest saved version — never a stale mix of
  the two. `--base REF` accepts any git ref (branch, tag, or commit) that `git merge-base` accepts.
- `,formal catalog stale [--base REF]` lists units with at least one non-`unchanged` anchor. `--base REF` narrows
  the check to units anchoring a file that appears in `git diff --no-renames --name-only $(git merge-base REF HEAD)`
  plus the current working-tree diff — i.e. units actually touched by the change under review, not every unit in
  the catalog. `--no-renames` (not the default rename-following diff) so a unit still anchored to a file's _old_
  path is not missed when that file was renamed: a rename-following diff reports only the new path. Anchor paths
  are compared after `os.path.normpath` on both sides, so `./m.py` and `m.py` are always the same path.
- `,formal catalog uncovered --base REF` reports changed hunks (from the same diff, plus every untracked file in
  the workspace) that no anchor of any unit overlaps: `{path, start, end}` rows. This is the input for deciding
  whether a new unit is needed, not an automatic trigger — a changed hunk outside every unit's anchors may be
  irrelevant to any modeled lifecycle. A whole-file deletion (`+++ /dev/null`) is reported once, under the _old_
  path, with `"deleted_file": true`; it counts as covered iff some unit anchors that path at all (there is no
  surviving line range to overlap, so an anchor's own current status — even `missing`, now that the file is
  gone — does not matter). A pure-deletion hunk (removed lines with nothing added in their place, e.g. a dropped
  guard) after new-side line `s` is reported as `start = max(s, 1)`, `end = min(s + 1, len(file))` against the
  current file's own line count — the one or two lines that still exist immediately around the deletion point (a
  single line when the deletion sits at either file edge, two lines when it is interior); it counts as covered
  only when some anchor's range contains every one of those surviving neighbor lines.

## Scope-time commands

Run these at Scope, before extraction or modeling work starts:

1. `,formal status [--json]` — every unit in the catalog for this repo, its work dirs on the current branch,
   the resolved valid version if any, and anchor state `valid`, `stale`, or `no-anchors` (no anchors recorded yet).
   `resolved_version` is null both when no saved version is currently valid and, unconditionally, whenever the
   unit already has a work dir on the current branch (`on_branch: true`) — resolution is skipped rather than
   attempted in that case, so a null value there says nothing about whether a valid saved version exists.
2. `,formal catalog stale --base <merge-base>` — units whose anchors moved relative to the change under review.
3. `,formal catalog uncovered --base <merge-base>` — changed hunks not covered by any unit's anchors, to decide
   whether a new unit is needed.
4. `,formal catalog checkout <unit>` — for each unit found valid but not yet materialized on this branch,
   before re-extracting anything already anchored.

To find a unit's on-disk work dir, use the `unit_dir` returned by `,formal init <unit> --json` or `,formal catalog checkout <unit> --json`.
`,formal status --json` does not include a path; branch keys are opaque, so do not reconstruct the path from the displayed branch.

## Stale-repair flow

`explore`, `mutate`, and `replay` operate on this branch's work dir. When `,formal catalog stale [--base REF]` reports a unit:

1. If its branch work dir already exists, retain it and repair it in place; do not require `checkout` to resolve a valid version first.
   If no work dir exists, use `catalog checkout` only for an explicitly resolved valid version, or
   `,formal init <unit> --from-version <id>` for an intentionally selected saved version from `catalog list`.
2. Repair each anchor by its exact `,formal anchors check <unit>` status: an identity-proven `unchanged` relocation needs only
   `,formal anchors check <unit> --write` to persist the new range; an `edited` anchor needs
   `,formal anchors add <unit> <path>:<start>-<end> --id <existing-id>` to record the intended exact source occurrence.
3. Update `Unit/Model.lean`/`Unit/Step.lean` for any row whose anchored behavior actually changed.
4. Then `,formal audit <unit>` and `,formal catalog save <unit>`.

## Save and garbage collection

- `,formal catalog save <unit> [--allow-unverified]` requires the current-snapshot `audit.json` described under
  Audit and snapshot identity above, unless `--allow-unverified` is passed and recorded in version metadata.
- Every version record requires a `branches` object mapping each opaque branch key to that branch's most recent save sequence for the
  content ID. The separate global `seq` records the latest save on any branch: same-branch resolution ranks by the matching
  `branches[branch-key]`, while cross-branch fallback and garbage collection rank by global `seq`. Thus another branch re-saving older
  content cannot roll back the current branch's preferred version. The separate `branch` field remains the latest save's human-readable
  branch name, or `detached@<commit>` for detached HEAD, and is display-only.
- Version-directory publication and the index mutation form one save/GC transaction under the shared lock. A complete copy is staged
  before publication, cleanup covers partial copying and metadata preparation, and an existing immutable same-id version is never
  destructively rebuilt.
- `,formal catalog gc [--keep N]` drops old versions beyond `N` per unit (default 5) and orphaned `_kit` directories. A kit lock's
  pending-owner state is either empty during first acquisition or a JSON object of the form `{"owners":[<positive-pid>,...]}`;
  malformed non-empty state is rejected. GC keeps a kit while any recorded owner remains alive and avoids lock-order inversion with
  provisioning.

## Squash-merge and branch behavior

Because resolution is purely anchor-text-based, a squash merge that lands the same code under a different
commit history still resolves the same unit version, and a rename or move of the anchored lines within the
same normalized text still resolves `unchanged` at the new line numbers when the relocation is unambiguous (the
snippet was `unique` at add time and has exactly one occurrence in the current file — see Anchors above); a move
that becomes ambiguous instead resolves `edited`. A unit only goes stale when the anchored text itself changes,
the anchored file disappears, or an unambiguous relocation is no longer possible — never merely because history was rewritten.
