# Judging Change Gates

Loaded through `judging_core.md` when a listed gate matches the reviewed path, plan claim, or assigned check.
Before using this file directly, load `~/.agents/skills/k-review/references/judging_core.md` for the authoritative triggers.
Apply matching gates in full; loading this group does not activate an unrelated gate.

## Deletion-Safety Audit (Run On Any Removal)

Signals include: `git diff --diff-filter=D --stat`, removed `export`s, deleted functions/branches.

Before calling a deletion safe, verify each item and report a one-line deletion ledger:

- **No live references:** `rg` the deleted symbol/file/path across the repo and public barrels/index files;
  confirm zero live importers/callers.
- **Public surface:** deleted exports are removed from barrels and not part of a published package entry point still consumed downstream.
- **Behavior parity:**
  - every deleted behavior is intentionally dropped (user-approved per SOP `2.1`) or demonstrably replaced; name each replacement
- **Tests:** deleted tests were migrated, or removed only because the code they covered is gone;
  coverage still exists for behavior that remains after the diff.
- **Base comparison:**
  - for branch-heavy/stateful deletions, compare against base behavior buckets, see State-Machine Verification Gate, and classify each difference as intended/unexpected
- **Disclosure:** meaningful deleted infrastructure is reflected in the PR description (Summary/Fix), not silently dropped.

## Replacement/Migration Parity Gate (Run On Replacements And Test Migrations)

Definitions:

- **Old implementation:** the base-branch code/test/helper that the diff deletes, unregisters, or stops calling.
- **Replacement:** the head-branch code/test/helper now covering the same behavior.
- **Candidate:** a possible review finding before this gate classifies it.

Before a candidate can become review feedback:

1. **Map old to replacement:** identify old and replacement entry points, helper side effects, assertions/checkpoints, setup/cleanup, permissions, wiring, and runtime assumptions.
   - For every explicitly set behavior/style/spacing/layout property, name where the replacement re-establishes it (component, prop, or default) or prove it is intentionally dropped.
     "I did not observe a regression" is not evidence the property is preserved;
     absence-of-observation never substitutes for naming the replacement's contract.
   - A migration handing a property to the target component (e.g. local CSS replaced by a shared component default) is only `preserved_limitation`/`scope_expansion`/intended-replacement after citing the target's contract (static source proof) or verifying it live.
     Until then the candidate stays unclassified, not dropped.
2. **Assign exactly one classification:**
   - `parity_gap`: old behavior or coverage existed and the replacement omits or weakens it.
   - `new_regression`: the replacement adds a failure mode the old implementation did not have.
   - `preserved_limitation`: the old implementation had the same limitation and the replacement does not worsen it.
   - `scope_expansion`: the PR body, linked issue, user request, or reviewer request explicitly requires stronger behavior/coverage than the old implementation provided.
   - `prose_drift`: only prose, counts, or docs disagree; implementation behavior and coverage remain equivalent.
3. **Keep/drop rule:**
   - Keep `parity_gap`, `new_regression`, and `scope_expansion` as review findings when evidence supports them.
   - Drop `preserved_limitation` from review feedback. Do not ask the author to fix it in this PR.
   - Drop `prose_drift` from code-review feedback.
     If it matters to reviewers, handle it as PR-level prose feedback, not as an implementation finding.
4. **Verification rule:** run live UI, heavy runtime probes, or delegated findings audit only for a kept candidate when source-level evidence cannot decide keep/drop; skip them for `preserved_limitation` or `prose_drift`.
   - The live-UI skip only applies once step 1's evidence bar is met.
     Never drop a UI-visual candidate (spacing, alignment, layout, visual styling) on an unproven classification and then cite that drop as why live UI was unnecessary — that inverts cause/effect.
     If classification rests on a UI-visual property you have neither traced to the replacement's contract nor verified live, the candidate is unproven: settle with static proof or live UI before classifying; do not skip because it was dropped.

## Historical Archaeology Gate (Code Provenance & Evolution)

Code encodes history; static search sees current syntax, not past bugs, CVEs, or edge cases that shaped it.
In large repos, keep probes targeted and line-bounded rather than running whole-file blame:

- **Targeted line archaeology:** probe only high-uncertainty or non-obvious modified logic; always bound line ranges and depth:
  `git blame -L <start>,<end> <base> -- <path>` or `git log -n 5 -L <start>,<end>:<path>` to find introducing commit and PR context (`gh pr view`, `gh issue view`).
  Never run unbounded whole-file blame in massive repos.
- **Unwritten invariant check:** discover whether a modified guard/fallback was introduced to fix a subtle bug, race condition, backward-compatibility requirement, or upstream quirk.
- **Regression reintroduction:** verify whether the diff inadvertently removes or weakens a guard previously added to fix a past defect.
- **Classify & act:**
  - _intentional obsolescence:_ past reason no longer applies; document why in review/PR.
  - _accidental regression:_ re-opens a historical bug or breaks a hard-won invariant; classify as HIGH.
  - _historical drift:_ refactor preserves past invariant under cleaner architecture.

## Semantic-Projection & Sibling-Consumer Gate

Audit co-located consumers that project, compare, or transform that same concept:

- **Projection symmetry:** when one projection changes, verify parallel projections reflect the same semantic mapping.
- **Bi-directional consistency:** verify read vs write, serialize vs deserialize, and encode vs decode paths handle all known variants and edge cases symmetrically.
- **Delta divergence:** classify any case where sibling consumers apply diverging semantic deltas to the same input space as HIGH (broken invariant / silent behavioral split).
