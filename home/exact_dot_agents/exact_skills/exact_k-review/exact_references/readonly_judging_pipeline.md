# Judging Pipeline (Findings Processing & Post-Review)

- Mode files and `shared_rules.md` reference this file; do not duplicate these sections elsewhere.
- Delivery-agnostic: no GitHub, SCSI, or delivery rules.
- Finding-generation gates, the Candidate Refutation Ladder, and the severity definitions live in `judging_core.md`.

Controller: before proposing/applying review fixes, load `~/.agents/skills/k-review/references/review_fixes.md` for fix scope and the verify-and-fix spine.
Before the Post-Review Stage, load `~/.agents/skills/k-review/references/review_post_stage.md`.
Read-only/no-fix paths do not load execution mechanics.

## Coverage Checklist (Do Not Skip)

On PR surfaces, first apply the CI Coverage Gate (`pr_common.md`).

A finding-class is exempt only when a present PR CI check genuinely catches it:

- First verify the check exists and covers the class; then CI will flag it — leave it to CI without re-checking or commenting on it.
- Keep in scope every class where CI is loosened or absent (e.g. a backport).

Non-PR surfaces have no PR CI to dedup against:

- local-changes
- k-light-review

Check every class below for non-PR surfaces: security; logic/correctness/invariants; data-loss risk; performance regressions;
test gaps (especially risky changes without tests, and expectations restating generated/spec-derived data instead of an independent oracle);
docs; maintainability/complexity; true nits.

## Post-Review Lens (The Four Dimensions)

Subject: the **fix diff** a review just produced (see Post-Review Stage).

These four dimensions are the only **canonical** ones: name them exactly; do not rename, merge, or reshape them.

1. **Redundancy** — the change repeats something existing:
   - re-implements an existing helper; re-states a rule already stated elsewhere; adds a path/branch/config that is already present
2. **Verbosity** — the change is bloated beyond the task: extra code/prose, comments that restate code, ceremony, or over-explanation.
3. **Semantic + logical duplication** — two places express the **same meaning or behavior** via different text (not literal copy-paste):
   - parallel branches that should be one; a rule stated two ways; divergent-but-equivalent logic;
     this is the subtle axis literal-clone detectors (`jscpd`) miss
4. **Gaps** — incomplete change:
   - dead code the change stranded; a co-edit-set member left unupdated (doc/diagram/census drift, or sibling sort/filter/persistence consumer left on old mapping); a half-applied rename; a referenced file/symbol that does not exist

For each dimension, anchor any finding in evidence: exact file + location, duplicate's other location, stranded symbol.

Do not assert a hygiene problem you have not pointed at.

## Findings-Set Audit (Run Before Final Refutation Or Acting)

Subject: candidate findings and proposed fixes — not the fix diff (Post-Review Stage) or original diff.
Owned by the deciding agent (k-light-review, the direct review modes, or a controller).
In deeper fan-out orchestration, keep this in the controller by default and delegate to `k-agent-findings-auditor` only for non-trivial sets.

Before final adversarial refutation, fixing, drafting, or presenting findings, run the four dimensions (Post-Review Lens) over the finding set:

- **Redundancy / semantic + logical duplication:** collapse two findings with the same root cause or anchor region into one;
  do not present the same issue twice under different wording.
- **Verbosity:** trim finding text and proposed fixes to the smallest form that still carries the evidence.
- **Gaps:** name any finding asserted without an exact anchor or without a decisive verification path, and either anchor it or drop it.

Also check each surviving finding for **actionability** (is the smallest fix concrete?) and **overengineering** (does the proposed fix exceed the proved problem?).
Merging duplicate findings is a deduplication task, never evidence that the underlying issue is unnecessary; keep the merged candidate.

When the final adversarial verifier returns bounded `new-candidate` miss-sweep items, run this Findings-Set Audit over them inline before judgment, drafting, or fixes.
Merge surviving items into the candidate set and report returned/surviving counts; do not relaunch the verifier over its own sweep items.
Existing evidence, parity, applicability, fix-scope, and publication gates still apply.

## Post-Review Stage (Run On Any Change-Producing Flow)

Before auditing a produced fix diff, load `review_post_stage.md` (matching heading).
Read-only roles report proposed fixes; they never gain edit permission.

## Verify-and-Fix Loop (Self-Authored Change-Producing Review)

For controller fix proposals/execution, load `review_fixes.md` (matching heading).
Read-only roles report proposed fixes; they never gain edit permission.
