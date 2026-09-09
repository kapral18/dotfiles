# PR Common Setup

All PR review modes load this file; do not duplicate these rules in mode files.

## Resolve the PR Target (Avoid Searching)

- If the user provided a PR URL/number, use that.
- Otherwise:
  - Set `GH_PAGER=cat` for all `gh` calls (prevents interactive pager hangs).
  - Resolve PR number via `,gh-prw --number`.
  - If `,gh-prw` fails, follow PR Detection in `~/.agents/skills/k-review/SKILL.md` before asking for the URL/number;
    this loads targeting rules only, not another review workflow.

## PR Snapshot (blocking before diff analysis)

Load and follow `~/.agents/skills/k-review/references/pr_snapshot.md`: it owns the one-fetch context pack production, media and reference capture, diff scope and file truth, the head + discussion Drift check, and the pack lifetime.
The root produces the pack during Understand and checks freshness once in final Verify. Workers do not refresh it.

## Merge-Conflict Check (Do After PR Resolution)

- Read `mergeable` and `mergeStateStatus` from the complete `pr.json` snapshot.
- If `mergeable` is `CONFLICTING` or `mergeStateStatus` is `DIRTY`:
  - Flag at the top: "This PR has merge conflicts with base. Findings may be invalidated once conflicts are resolved."
  - Continue the review (conflicts do not block), but note findings in conflict-affected files as potentially stale.
  - If the user asks to resolve conflicts, load and follow `~/.agents/skills/k-weave/SKILL.md` (entity-level semantic merge driver).

## Large-PR Triage

After `git diff --stat`, if the diff touches >20 files or ~1000 changed lines, prioritize business logic, security-sensitive code, and API changes; deprioritize generated/lock/snapshot/vendored files; state triage order.
For smaller PRs, review everything.

## File-Type Awareness

- **Skip/skim unless asked:** lockfiles, generated code, snapshots, `.min.js`, vendored dependencies.
- **Full depth:** business logic, API routes, auth/authz, data models, migrations, runtime-affecting config.
- **Medium depth:** tests, docs, CI config. Report real findings in skimmed files, with file-type context.

## CI Coverage Gate (scoping — complete before drafting findings)

PR review otherwise re-checks everything, including classes PR CI already catches.
This gate is the PR check-source instance of the Check-Coverage Exemption in `~/.agents/skills/k-review/references/judging_core.md`;
the exemption rules there apply here unchanged.

Avoid redundant findings:

- Drop findings CI will inevitably flag, but first verify the relevant check exists and covers that finding class.
- Do not assume usual CI exists on every branch; backports may loosen or narrow CI.

1. Read the complete `checks.json` snapshot. Fetch checks only if that artifact is missing during Understand.
2. Map each present check to the Coverage-Checklist classes it actually catches.
   - lint -> style/format nits
   - typecheck -> type errors
   - a test job -> the behavior it exercises
   - SAST -> the vuln classes it scans
   - A check covers only what it actually runs.
   - Do not credit a check from its name alone.
   - Buildkite job whose coverage is unclear: load and follow `~/.agents/skills/k-buildkite/SKILL.md` (`bk` CLI) to see what runs before crediting it with a class.
     For Elastic repos, route through `k-elastic-domain` first when available, but do not skip Buildkite solely because the overlay cannot be loaded.
     If Buildkite access is unavailable, keep the coverage class in scope instead of crediting the check.
3. Exempt a finding-class from review only when a present check genuinely covers it —
   CI will flag those, so do not build findings, draft comments, or withhold an approval for that exactly covered class.
4. Keep every other class in scope, including ones whose check is absent or loosened on this branch.
   Do not assume a class is covered just because CI usually covers it elsewhere.
5. State one line before drafting: `CI coverage: covered=[...] -> exempt; in-scope=[...]`.

An observed CI failure in an exactly excluded class is not a failed required acceptance criterion in this review attempt (§3.5).
It does not create a finding or block an approval; approval is a review verdict, NEVER CI certification.
The exclusion covers only the verified class, source, scope, and evidence above. It NEVER exempts all bugs or all CI failures.

## Verdict Gate (PR Mode Only)

Recommend a verdict only in final Verify after reading the complete primary discussion, enumerated CI coverage, and platform-backed author classifications from the shared pack.
Use GraphQL author `__typename` or API `user.type`; do not issue a second per-comment request when the pack already contains that evidence.
Unresolved material claims are blocked or retracted, not assumed true.

## Pending Review Intake (blocking before diff analysis)

Before PR diff analysis/dedup, seed the current-account review ledger from GitHub API truth:
resolve login, list reviews, select `PENDING` reviews by that login, read their draft comments, and mark submitted review/comment/reply content from normal PR intake that was authored by the same login.

## GitHub Context Intake + Reference Resolution (blocking — complete before diff analysis)

During Understand, read the complete primary PR body, discussion/review threads and replies, current-account pending drafts, and diff metadata from the pack.
Do not rely on summaries, previews, truncated/compacted output, or sliced fields such as `body[0:N]`.
Retrieve complete raw artifacts with pagination before relying on them; do not re-fetch artifacts already in the pack.

Follow a reference only when it can settle a named material question about intent, changed behavior, a claimed precedent, or an acceptance condition.
Record that question before following further links. The presence of a URL is not an instruction to fetch it.
Do not recursively crawl every reachable or potentially relevant reference.

- Keep a visited set by canonical URL/object ID and reuse each complete artifact.
- For a selected issue/PR, read its full body and discussion before relying on it;
  inspect its diff/files only when the claim depends on code.
- For a selected comment/thread, read the complete thread with author, order, resolution, and outdated state.
- For selected media, use `~/.agents/skills/k-review/references/pr_snapshot.md` → Media, inspect the actual file, and retain the manifest evidence.
  For video/GIF claims, inspect the relevant transition plus surrounding states and audio/captions when material.
- For selected Buildkite evidence, use `k-buildkite`; verified overlays own repo-specific routing.
- Stop reference expansion when the named question is answered or the required source is inaccessible.
  Do not create new questions solely from incidental links. Report material unresolved questions as blocked.

Keep the intake ledger in the topic artifact: question, source, complete-content status, conclusion or access blocker.
User output contains only decision-relevant conclusions and evidence pointers, not a crawl transcript.

If a claim depends on visuals and visuals are missing, inaccessible, or unclear, stop and ask for visuals or better access before making that claim.

## Ambient Topic Exploration (conditional — complete before judging contested context)

Run this second layer only when direct PR/issue context does not settle shared understanding:
the discussion shows disagreement, conflicting claims, or unclear ownership/requirements;
the user asks for deep context, history, "why", or precedent; a candidate finding depends on product intent, team convention, prior incidents, or decisions not proven by the directly referenced artifacts; or direct references are sparse, contradictory, or omit the rationale behind the current disagreement.
Skip it for routine implementation reviews where the diff, base context, and direct references are enough.

Before running it, append `ambient: trigger=<condition> evidence=<thread id, claim, or user request>` to the review spec;
with no recordable trigger it does not run.
It never runs under a correctness-only constraint, and a self-authored PR with no review threads and no contested claim has no trigger.

When triggered, load and follow `~/.agents/skills/k-review/references/pr_context_audits.md` for the bounded search procedure, the required `topic / queries / sources searched / hits read / stop reason` ledger, and the stop conditions.

## PR Necessity + Correctly-Open Audit (conditional)

Run this audit when reviewing a PR whose author is not the user (`authorship: other` or `unknown`).
It is part of other-authored PR review, not a user opt-in, and it does not approve, reject, close, or post.
Skip it for local changes and routine self-review.

When triggered, load and follow `~/.agents/skills/k-review/references/pr_context_audits.md` for the intent/necessity procedure and the required `intent`, `correctly_open`, `needed`, `similar_or_recent_work`, and `recommended_review_action` classifications.

## Deduplication + Truth Filter (Required Before Drafting)

- Using artifacts from GitHub Context Intake + Reference Resolution, classify each candidate finding:
  - `covered`:
    - already addressed by accurate PR description clarifications or existing review threads/replies
    - already present in a valid existing pending review/draft comment from the current authenticated account
    - comment author does not matter
    - verify against the current implementation/diff
    - do not draft a new comment
  - `new`: not already covered and verified against the current implementation/diff; eligible for draft feedback.
    - For replacements and test migrations, apply the Replacement/Migration Parity Gate in `~/.agents/skills/k-review/references/judging_core.md` first.
      Only `parity_gap`, `new_regression`, and `scope_expansion` can be `new`; `preserved_limitation` and `prose_drift` cannot be `new`.
  - `incorrect`: prior clarification/comment conflicts with the current implementation/diff;
    add one correction with evidence (do not echo the incorrect claim).

## Existing Pending Review Reconciliation (Blocking Before Final Draft/Post)

Run this after the candidate queue is evidence-verified and before preparing any final PR-review draft, pending-review API payload, or review submission.

1. Build a ledger of current-account review content:
   - current authenticated login; pending review IDs, bodies, commit IDs, and draft comments;
     submitted review bodies, inline comments, thread replies, and PR-level comments by the same login; current PR head SHA
2. Compare every new candidate finding against that ledger and the current diff:
   - same root cause / same fix / same anchor region -> one merged finding
   - old pending anchor moved but finding remains valid -> re-anchor in the merged payload
   - old pending finding is now stale, fixed, duplicated by public context, or wrong -> drop it from the payload and record why
   - old pending finding is independent and still valid -> keep it once in the merged payload
   - new finding duplicates an existing valid pending finding -> suppress the new duplicate
   - new evidence contradicts existing pending content -> resolve from current head or stop as `blocked`
3. If a pending review already exists:
   - do not create another pending review
   - prepare a consolidated payload that contains kept existing findings plus kept new findings exactly once
   - purely additive payload -> append net-new threads via GraphQL `addPullRequestReviewThread`; no delete/recreate
   - any existing draft comment changes or drops -> delete/recreate, only after explicit approval
4. Include this ledger in output:
   - `Pending review reconciliation: none found`
   - `Pending review reconciliation: reused existing <review_id> with no changes`
   - `Pending review reconciliation: merged replacement needed for <review_id> (kept=<n>, added=<n>, dropped=<n>)`
   - `Pending review reconciliation: additive append to <review_id> (added=<n>)`
   - `Pending review reconciliation: stale pending dropped for <review_id> (<reason>)`
   - `Pending review reconciliation: blocked (<reason>)`

Never post or submit review feedback while this reconciliation is unknown and locally/API-verifiable.

## Comment Placement (Draft Guidance)

Where to comment:

- Default: inline on a relevant diff line/range in the PR.
- File-scoped concerns: prefer a file-level comment (`subject_type=file`).
- If you are replying in an existing thread, use the reply mode of PR fix.
- Do not replace inline feedback with a PR-level summary body.
- Only use file-level or PR-level placement when no reliable inline anchor exists, or when the user explicitly asks for non-inline placement.

## Anchoring Constraints (Only If Posting Is Requested)

- PR review comments are anchored to the PR's unified diff.
- The GitHub UI can sometimes let you comment on context lines by expanding the diff.
- API calls still need a resolvable diff anchor.
- Before every API call that creates or submits anchored PR review comments:
  - fetch the current PR diff/patch for the target head SHA
  - verify each anchor against the diff hunk you intend to comment on
  - compute anchors only from the current diff: full-file line numbers, stale patches, and memory are all invalid anchor sources
- For API calls, treat a source-file line number as a valid anchor only after it resolves against the PR diff. Prefer:
  - `position` (diff-relative), computed from the PR's unified diff:
    - the `@@` hunk header line itself is **not counted** (position 0)
    - the first line after the `@@` header is position 1
    - counting continues sequentially across all subsequent hunks in the file
  - or `line` + `side` / `start_line` + `start_side` (still must resolve against the PR diff; GitHub will 422 if it cannot resolve)
- If the specific source line you care about is not shown in the diff context:
  - anchor on the nearest relevant diff line in the same file (an unrelated line is an invalid anchor) and include a deep link to the exact source location on the PR head SHA
- If you cannot find a relevant diff anchor without confusing the author:
  - use a file-level comment (`subject_type=file`)
  - or a PR-level comment that links to the exact source lines

## Deep Links to Exact Source Lines (PR Head SHA)

- Prefer links of the form: `https://github.com/OWNER/REPO/blob/<head_sha>/<path>#L<start>-L<end>`
- If you cannot reliably compute line numbers from GitHub, fetch the PR head commit locally and use `git show <head_sha>:<path>` to compute them.

## Local Verification

- In the root-owned final Verify stage, consume existing check receipts and run only pending planned checks for the frozen candidate.
- Research and production workers must not run tests or reproduce claims as a completion check.
- Plan a minimal behavioral reproduction in `/tmp` or the worktree when existing evidence cannot settle the acceptance condition.
- UI repro hygiene (when verifying UI/editor behavior):
  - do one claim per repro run; reset state between runs (reload/new tab)
  - clear inputs deterministically before typing
  - for rich editors, do not assume the accessible textarea reflects the full editor model; verify what is actually rendered

## If Posting Is Requested

- Invoke the `k-github` skill via the Skill tool for exact anchoring and API constraints.
