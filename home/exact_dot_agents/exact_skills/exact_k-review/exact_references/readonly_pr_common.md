# PR Common Setup

All PR review modes load this file; keep these rules defined here only, outside mode files.

## Resolve the PR Target (Avoid Searching)

- If the user provided a PR URL/number, use that.
- Otherwise:
  - Set `GH_PAGER=cat` for all `gh` calls (prevents interactive pager hangs).
  - Resolve PR number via `,gh-prw --number`.
  - If `,gh-prw` fails once, stop and ask the user for the PR URL/number.

## Merge-Conflict Check (Do After PR Resolution)

- Run: `gh pr view <number> --json mergeable,mergeStateStatus --jq '{mergeable, mergeStateStatus}'`
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

Avoid redundant findings:

- Drop findings CI will inevitably flag, but first verify the relevant check exists and covers that finding class.
- Verify CI per branch; backports may loosen or narrow CI, so a branch earns its usual-CI assumption only from its actual checks.

1. Enumerate PR checks (read-only). Set `GH_PAGER=cat`, then `gh pr checks <number> --json name,state,bucket,workflow,link`.
2. Map each present check to the Coverage-Checklist classes it actually catches.
   - lint -> style/format nits
   - typecheck -> type errors
   - a test job -> the behavior it exercises
   - SAST -> the vuln classes it scans
   - A check covers only what it actually runs.
   - Credit a check only from what it runs, never from its name alone.
   - Buildkite job whose coverage is unclear: load and follow `~/.agents/skills/k-buildkite/SKILL.md` (`bk` CLI) to see what runs before crediting it with a class.
     For Elastic repos, route through `k-elastic-domain` first when available, and keep the Buildkite step even when the overlay cannot be loaded.
     If Buildkite access is unavailable, keep the coverage class in scope instead of crediting the check.
3. Exempt a finding-class from review only when a present check genuinely covers it —
   CI will flag those, so leave them out of findings and draft comments.
4. Keep every other class in scope, including ones whose check is absent or loosened on this branch.
   Credit a class as covered only from this branch's actual checks, even when CI usually covers it elsewhere.
5. State one line before drafting: `CI coverage: covered=[...] -> exempt; in-scope=[...]`.

## Pending Review Intake (blocking before diff analysis)

Before PR diff analysis/dedup, seed the current-account review ledger from GitHub API truth:
resolve login, list reviews, select `PENDING` reviews by that login, read their draft comments, and mark submitted review/comment/reply content from normal PR intake that was authored by the same login.

## GitHub Context Intake + Reference Resolution (blocking — complete before diff analysis)

Use this gate for the primary PR and every recursively discovered item that could inform the review:

- PR
- issue
- comment
- thread
- asset
- URL
- reference

Rely only on full raw content: summaries, previews, truncated/compacted output, and sliced fields such as `body[0:N]`, `head`, preview scripts, or partial comment/reply lists are indexes, not truth.

Recover the full raw content before marking an item read. Limited output is allowed only for discovery/status.
Once an item can inform composition, review, labels, routing, or mutation, re-fetch the full raw artifact with pagination before using it.
For GitHub, prefer complete `--json` fields or API pagination over `jq` slices or preview commands.
Keep a short intake ledger for composition/review work: object read, full-body/comments status, linked objects followed, and reproduction/expected/actual sections found/absent.

1. Maintain a visited set by canonical URL/object ID so recursion is exhaustive without looping.
2. Seed the queue from the primary PR:
   - PR description/body, reading every line including template text, checkboxes, code blocks, quotes, collapsible sections, and footnotes
   - PR conversation/timeline comments, review bodies/comments/threads, and every reply, including resolved/outdated state when available
   - any `PENDING` review and draft comments authored by the current account, using Pending Review Intake above
   - linked/closing issues, linked PRs, commits, check/build links, URLs, and image/media/attachment links found anywhere above
3. For each queued item, read the complete artifact before extracting references from it:
   - PRs:
     - read raw description/body line-by-line; state, author/base/head, labels/milestone when relevant; all conversation/timeline comments
     - read all review bodies, review comments/threads/replies, linked/closing issues and PRs, check/build links, and diff summary
     - inspect the full diff or exact files when the referenced PR is cited as precedent, fix, regression, or evidence for a claim
   - Issues: read raw body line-by-line, state, labels/milestone when relevant, all comments/replies/timeline text, linked PRs/issues, and every attachment/media/reference.
   - Comments/threads: read the parent comment plus every reply end-to-end; include author, timestamp/order, resolved/outdated/minimized state, and any referenced code or links.
   - Images/screenshots: download to `/tmp` with `curl -sL -o /tmp/<name> <url>`, then inspect the file, including visible text, UI state, annotations, and error messages.
   - GIFs/videos: download to `/tmp`; inspect first/last frames and every significant frame or scene/state transition;
     cover UI changes, overlays, terminal output changes, and before/after states;
     use local tooling (`ffmpeg`/`ffprobe`, browser/player, image extraction, OCR/vision when available);
     inspect audio/captions/transcripts when present
   - Buildkite URLs (`buildkite.com/...`): fetch only via the `bk` CLI (direct fetches of authenticated pages commonly 403).
     Load and follow `~/.agents/skills/k-buildkite/SKILL.md` — use `bk` CLI to retrieve build/job info.
     For Elastic repos, route through `k-elastic-domain` first when available, and keep the Buildkite step even when the overlay cannot load.
   - Other URLs: fetch when they could inform the review, then read the full relevant content and extract references.
4. From every artifact just read, extract new URLs, PR/issue refs, comments, assets, media, commits, builds, and code references;
   enqueue any unvisited potentially relevant item.
5. Repeat until the queue is empty.
   - Proceed only once every reachable, potentially relevant reference is read.
   - If an item is inaccessible, record the exact reason before excluding it.
   - If an item is unsupported by local tooling, record the exact reason before excluding it.
   - If an item is irrelevant, record the exact reason before excluding it.
6. State the full list of references visited, skipped-with-reason, and what you learned from each before proceeding to diff analysis.

If a claim depends on visuals and visuals are missing, inaccessible, or unclear, stop and ask for visuals or better access before making that claim.

## Ambient Topic Exploration (conditional — complete before judging contested context)

Run this second layer only when direct PR/issue context does not settle shared understanding:
the discussion shows disagreement, conflicting claims, or unclear ownership/requirements;
the user asks for deep context, history, "why", or precedent; a candidate finding depends on product intent, team convention, prior incidents, or decisions not proven by the directly referenced artifacts; or direct references are sparse, contradictory, or omit the rationale behind the current disagreement.
Skip it for routine implementation reviews where the diff, base context, and direct references are enough.

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
    - leave it without a new draft comment
  - `new`: not already covered and verified against the current implementation/diff; eligible for draft feedback.
    - For replacements and test migrations, apply the Replacement/Migration Parity Gate in `judging_core.md` first.
      Only `parity_gap`, `new_regression`, and `scope_expansion` can be `new`; `preserved_limitation` and `prose_drift` cannot be `new`.
  - `incorrect`: prior clarification/comment conflicts with the current implementation/diff;
    add one correction with evidence (state the correction itself, leaving the incorrect claim unquoted).

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
   - reuse it as the single pending review
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

Post or submit review feedback only after this reconciliation is known or proven non-verifiable locally/via API.

## Comment Placement (Draft Guidance)

Where to comment:

- Default: inline on a relevant diff line/range in the PR.
- File-scoped concerns: prefer a file-level comment (`subject_type=file`).
- If you are replying in an existing thread, use the reply mode of PR fix.
- Keep inline feedback inline; a PR-level summary body supplements it rather than replacing it.
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

- Run the smallest sufficient tests.
- If the concern is behavioral, reproduce/simulate it in `/tmp` or the worktree.
- UI repro hygiene (when verifying UI/editor behavior):
  - do one claim per repro run; reset state between runs (reload/new tab)
  - clear inputs deterministically before typing
  - for rich editors, verify what is actually rendered; the accessible textarea may lag the full editor model

## If Posting Is Requested

- Invoke the `k-github` skill via the Skill tool for exact anchoring and API constraints.
