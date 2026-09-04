# Review Verify-And-Fix Loop

Before using this loop, load `~/.agents/skills/k-review/references/judging_pipeline.md` for coverage, findings audit, and the required Post-Review Stage pointer.
Read-only role boundaries remain authoritative.

## Verify-and-Fix Loop (Self-Authored Change-Producing Review)

Shared verify-and-fix spine for self-authored, fix-authorized review surfaces. Each surface sets scope and base-context stance first.
Read-only lanes report precise fixes for the parent to apply instead of editing.

1. **Build the findings queue.** Walk the whole diff against the Coverage Checklist, ordered by severity.
2. **Audit the set.** Run the Findings-Set Audit over candidate findings and proposed fixes.
3. **Final refutation.**
   Run the Candidate Refutation Ladder (`judging_core.md`) or the available `k-agent-adversarial-verifier` lane over the audited set;
   keep only survivors, record reachability, and drop refuted/unverified findings.
4. **Fix each finding** highest severity first: verify from evidence, apply the smallest correct change, and do not commit/push unless asked.
   For non-trivial or ambiguous fixes, state options and proceed with the recommended default unless the user intervenes.
   **Fix scope:** a fix stays inside the behavior the reviewed diff already changes.
   It becomes a proposal, reported with the smallest change and left unapplied, when it needs a new user-visible state (loading, error, retry), a new prop or export on a component outside the diff's package, a file outside the packages the diff touches, or new translated strings beyond the changed component.
   A review that finds a defect it cannot fix inside that scope reports the defect; it does not build the feature.
5. **Targeted checks.** Per fix, run the focused tests and lint for the touched files.
   The following once-only schedule applies to this bounded pass; an authorized convergence handoff uses `k-converge`'s per-round schedule.
   The repo-wide gate (full suite, type check, check script) runs once, after the last fix and before the report, launched in the background and collected on its completion signal; never block a turn on it and never re-run it per iteration.
6. **Post-Review Stage.** Run it over this pass's fix diff, then re-run the targeted checks if cleanup touched code.
7. **Bound.** One fix round, then one refutation round over the fix diff (Candidate Refutation Ladder or the verifier lane).
   Without an authorized convergence handoff, a finding the refuter raises against the fix goes to the user as a decision with the smallest proposed change; it is not redesigned in-review.
   After the round, append `round: <n> fixed=<files> gates=<result>` to the review spec and emit a one-line status to the user.
   `k-converge` is the only unbounded loop: enter by explicit user invocation or the caller's authorized handoff under `~/.agents/skills/k-converge/SKILL.md` and its workflow-handoff contract.
