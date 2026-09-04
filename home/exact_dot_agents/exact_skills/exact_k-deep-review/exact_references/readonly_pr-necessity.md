# Pr necessity

1. **Run conditional blocking PR necessity/intent audit.**
   - Run `k-agent-pr-necessity-auditor` before any implementation reviewer when:
     - mode is `pr_review.md` or `pr_fix.md`, and
     - `authorship` is `other` or `unknown`.
   - Also run it as a blocking PR intent audit when all of these hold:
     - mode is `local_changes.md`,
     - the local changes are attached to, assigned from, or adopted from a PR, and
     - PR intent/scope artifacts are needed to decide whether a local change is correct, stale, or fixable.
   - Invoking `/k-deep-review` is the request for this PR meta-audit; do not require a second user opt-in.
   - Skip it for local changes and self-authored PRs only when PR intent/scope is not needed for controller judgment.
   - This worker is read-only and evidence-only.
   - Give it the scope packet plus the PR URL/number, base/head refs, changed paths, directly referenced issues/PRs, and any already-known user constraints.
     Include linked Slack/design artifacts already known to the controller.
   - It must follow `~/.agents/skills/k-review/references/pr-necessity-auditor.md`.
   - It returns one of:
     - `Not applicable`
     - greenlight evidence that the PR is sensible enough to review further
     - blocker or stop status for inaccessible GitHub, Slack, history, unclear intent, not-needed/superseded work, or incorrectly-open status
   - Greenlight means there is no unresolved blocker and no supported classification that makes implementation review premature or unnecessary.
     For other-authored or unknown-author PRs, continue to reviewer fan-out only when the audit supports `needed: yes`.
     Also require no material correctly-open/intent concern blocking review.
   - Greenlight is not merge readiness.
     Failed/missing labels, outdated-branch checks, unknown mergeability, or other status blockers may be surfaced as `merge_readiness`/status uncertainty.
     These can still allow implementation review to continue.
   - Always treat `mergeable: UNKNOWN`, `mergeStateStatus: UNKNOWN`, or missing merge metadata as unknown, and record it as unknown;
     only affirmative merge metadata proves no conflicts.
   - If the audit returns blocked, unclear, not needed, superseded, incorrectly open, or leaves an intent dependency unresolved, stop the implementation review flow.
     Surface the supported blocker/PR-level draft feedback.
     Launch reviewer workers, live UI, or findings audit only when the user explicitly asks to continue anyway.
   - The controller judges and gates any draft feedback; the auditor's role is evidence, never decision or posting.
