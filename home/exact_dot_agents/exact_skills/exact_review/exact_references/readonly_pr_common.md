# PR Common Setup

All PR review modes load this file. Do not duplicate these rules in mode files.

## Resolve the PR Target (Avoid Searching)

- If the user provided a PR URL/number, use that.
- Otherwise:
  - Set `GH_PAGER=cat` for all `gh` calls (prevents interactive pager hangs).
  - Resolve PR number via `,gh-prw`:
    - `,gh-prw --number`
  - If `,gh-prw` fails once, stop and ask the user for the PR URL/number.

## Merge-Conflict Check (Do After PR Resolution)

- Run: `gh pr view <number> --json mergeable,mergeStateStatus --jq '{mergeable, mergeStateStatus}'`
- If `mergeable` is `CONFLICTING` or `mergeStateStatus` is `DIRTY`:
  - Flag at the top of the review output: "This PR has merge conflicts with base. Findings may be invalidated once conflicts are resolved."
  - Continue the review (conflicts do not block review), but note any findings in conflict-affected files as potentially stale.
  - If the user asks to resolve conflicts, load and follow `~/.agents/skills/weave/SKILL.md` (entity-level semantic merge driver).

## Large-PR Triage

- After reading `git diff --stat`, assess the PR size:
  - If the diff touches more than 20 files or exceeds ~1000 changed lines:
    - Prioritize files containing business logic, security-sensitive code, and API surface changes.
    - Deprioritize generated files (lockfiles, snapshots, auto-generated code, vendored deps).
    - State the triage order at the start of the review so the user knows what was prioritized and what was deferred.
  - For smaller PRs: review everything; no triage needed.

## File-Type Awareness

Adjust review depth by file type:

- **Skip or skim** (unless the user explicitly asks): lockfiles (`package-lock.json`, `yarn.lock`, `Cargo.lock`), generated code, snapshots, `.min.js`, vendored dependencies.
- **Full depth**: business logic, API routes, auth/authz, data models, migrations, configuration that affects runtime behavior.
- **Medium depth**: test files (check coverage and correctness, but do not nitpick style), documentation, CI config.
- If a finding exists only in a skimmed file, still report it — but note the file type context.

## CI Coverage Gate (scoping — complete before drafting findings)

PR review otherwise re-checks everything, including classes the PR's own CI already catches.

Avoid redundant findings:

- Drop findings CI will inevitably flag.
- First verify the relevant check actually exists.
- First verify the check covers that finding class.
- Do not assume usual CI exists on every branch.
- Backports may loosen or narrow CI.

1. Enumerate the PR's checks (read-only). Set `GH_PAGER=cat`, then `gh pr checks <number> --json name,state,bucket,workflow,link`.
2. Map each present check to the Coverage-Checklist classes it actually catches.
   - lint -> style/format nits
   - typecheck -> type errors
   - a test job -> the behavior it exercises
   - SAST -> the vuln classes it scans
   - A check covers only what it actually runs.
   - Do not credit a check from its name alone.
   - Buildkite job whose coverage is unclear: load and follow `~/.agents/skills/buildkite/SKILL.md` (`bk` CLI) to see what it runs before crediting it with a class.
     For Elastic repos, route through `elastic-domain` first when available, but do not skip the Buildkite check solely because the overlay cannot be loaded.
     If Buildkite access is unavailable, keep the coverage class in scope instead of crediting the check.
3. Exempt a finding-class from review only when a present check genuinely covers it —
   CI will flag those, so do not build findings or draft comments for them.
4. Keep every other class in scope, including ones whose check is absent or loosened on this branch.
   Do not assume a class is covered just because CI usually covers it elsewhere.
5. State one line before drafting: `CI coverage: covered=[...] -> exempt; in-scope=[...]`.

## GitHub Context Intake + Reference Resolution (blocking — complete before diff analysis)

Use this gate for the primary PR and every recursively discovered item that could inform the review:

- PR
- issue
- comment
- thread
- asset
- URL
- reference

Do not rely on:

- summaries
- previews
- truncated terminal output
- compacted output

Recover the full raw content before marking an item read.

1. Maintain a visited set by canonical URL/object ID so recursion is exhaustive without looping.
2. Seed the queue from the primary PR:
   - raw PR description/body, read every line including template text, checkboxes, code blocks, quotes, collapsible sections, and footnotes
   - PR conversation/timeline comments, review bodies, review comments, review threads, and every reply in each thread, including resolved/outdated state when available
   - any `PENDING` review and draft comments authored by the current authenticated account, using `shared_rules.md` Existing Pending Review Awareness
   - linked/closing issues, linked PRs, commits, check/build links, URLs, and image/media/attachment links found anywhere above
3. For each queued item, read the complete artifact before extracting references from it:
   - PRs:
     - read raw description/body line-by-line
     - read state, author/base/head, labels/milestone when relevant
     - read all conversation/timeline comments
     - read all review bodies
     - read all review comments/threads/replies
     - read linked/closing issues and PRs
     - read check/build links
     - read diff summary
     - inspect the full diff or exact files when the referenced PR is cited as precedent, fix, regression, or evidence for a claim
   - Issues: read raw body line-by-line, state, labels/milestone when relevant, all comments/replies/timeline text, linked PRs/issues, and every attachment/media/reference.
   - Comments/threads: read the parent comment plus every reply end-to-end; include author, timestamp/order, resolved/outdated/minimized state, and any referenced code or links.
   - Images/screenshots: download to `/tmp` with `curl -sL -o /tmp/<name> <url>`, then inspect the local file, including visible text, UI state, annotations, and error messages.
   - GIFs/videos:
     - download to `/tmp`
     - inspect first/last frames
     - inspect every significant frame or scene/state transition
     - cover UI changes, overlays, terminal output changes, and before/after states
     - use available local tooling (`ffmpeg`/`ffprobe`, browser/player, image extraction, OCR/vision when available)
     - inspect audio, captions, or transcripts when present
   - Buildkite URLs (`buildkite.com/...`): **do not fetch directly** (authenticated pages commonly 403).
     Load and follow `~/.agents/skills/buildkite/SKILL.md` — use `bk` CLI to retrieve build/job info.
     For Elastic repos, route through `elastic-domain` first when available, but do not skip Buildkite solely because the overlay cannot be loaded.
   - Other URLs: fetch when they could inform the review, then read the full relevant content and extract references.
4. From every artifact just read, extract new URLs, PR/issue refs, comments, assets, media, commits, builds, and code references;
   enqueue any unvisited potentially relevant item.
5. Repeat until the queue is empty.
   - Do not proceed while a reachable, potentially relevant reference remains unread.
   - If an item is inaccessible, record the exact reason before excluding it.
   - If an item is unsupported by local tooling, record the exact reason before excluding it.
   - If an item is genuinely irrelevant, record the exact reason before excluding it.
6. State the full list of references visited, skipped-with-reason, and what you learned from each before proceeding to diff analysis.

If a claim depends on visuals and visuals are missing, inaccessible, or unclear, stop and ask for visuals or better access before making that claim.

## Ambient Topic Exploration (conditional — complete before judging contested context)

Run this second layer only when direct PR/issue context does not settle shared understanding:

- the PR/issue discussion shows disagreement, conflicting claims, or unclear ownership/requirements
- the user asks for deep context, history, "why", precedent, or whether a claim matches team/product understanding
- a candidate finding depends on product intent, team convention, prior incidents, or decisions not proven by the directly referenced artifacts
- direct references are sparse, contradictory, or appear to omit the rationale behind the current disagreement

Skip it for routine implementation reviews where the diff, base context, and direct references are enough.

Keep it bounded. Before using the results, write:

- topic
- queries
- sources searched
- hits read
- stop reason

1. Build a topic map from the current artifact and diff: product/feature names, code symbols, error text, labels, team names, user-visible phrases, and disputed terms.
2. Search GitHub beyond direct references:
   - Issues:
     - `gh search issues --repo OWNER/REPO "<terms>" --match title,body,comments --json number,title,state,commentsCount,updatedAt,url --limit 20`
     - omit `--state` to search both open and closed
   - PRs:
     - `gh search prs --repo OWNER/REPO "<terms>" --match title,body,comments --json number,title,state,commentsCount,updatedAt,url --limit 20`
     - omit `--state` to search both open and closed
   - Discussions when the repo uses them:
     - use GitHub GraphQL `search(query: "repo:OWNER/REPO <terms>", type: DISCUSSION, first: N)`
     - GraphQL exposes `DISCUSSION`, `Discussion.comments`, and `DiscussionComment.replies`
     - `gh search` has no discussion subcommand
3. If Slack MCP tools are available in the current runtime:
   - search relevant public/team channels for the topic terms
   - read full matching threads
   - examples in this setup:
     - `slack_search_public`
     - `slack_search_channels`
     - `slack_read_user_profile`
     - `slack_search_public_and_private` with explicit user consent
   - do not search private channels or DMs without explicit consent
4. For each promising ambient hit, read enough full context to decide whether it informs the disputed topic:
   - GitHub issues/PRs/discussions: body, comments/replies/threads, linked references, and relevant diffs/files using the GitHub Context Intake + Reference Resolution rules above
   - Slack: the complete thread/conversation around the hit, not just the matching message;
     preserve timestamps/order and distinguish decisions from speculation
5. Stop when:
   - searches produce no new decision-relevant facts
   - a small representative set of high-signal hits has been read
   - tools/access are exhausted
   - Record skipped sources with reasons (e.g. `Slack MCP unavailable`, `private channel requires consent`, `GitHub Discussions disabled/unavailable`).
6. Use ambient evidence only as context/precedent.
   The current PR diff and directly relevant artifacts remain the source of truth for what is actually changing.

## PR Necessity + Correctly-Open Audit (conditional)

Run this audit when reviewing a PR whose author is not the user (`authorship: other` or `unknown`).
It is part of other-authored PR review, not a separate user opt-in.

Skip it for local changes and routine self-review.

This audit does not approve, reject, close, or post. It produces evidence for draft feedback or controller judgment.

1. Reconstruct author intent:
   - Use the full GitHub Context Intake + Reference Resolution results.
   - Read the PR description, discussion, review threads, referenced issues/PRs, linked artifacts, and relevant changed files as one intent record.
   - Distinguish the author's stated goal from inferred goals, reviewer suggestions, and ambient precedent.
2. Check whether the PR is correctly open:
   - Verify state, draft/readiness signal, base/head refs, branch staleness, merge-conflict status, linked issue state, labels/milestone when relevant, and whether the described problem still exists on base.
   - Treat "open" as procedural correctness, not a merge verdict. A PR can be correctly open while still needing changes.
   - If the PR appears mis-targeted, stale, premature, missing a linked issue, or scoped differently from its stated intent, record the exact evidence.
3. Check whether the work is still needed:
   - Search for duplicate, overlapping, superseding, or recently merged work using the topic map from Ambient Topic Exploration.
   - Search GitHub issues/PRs/discussions beyond direct references with the existing Ambient Topic Exploration commands and rules.
   - For recent merged work, include query terms such as `is:pr is:merged merged:>=YYYY-MM-DD` in GitHub search queries instead of assuming closed PRs are relevant.
   - Compare any high-signal hit against the current PR's actual diff before calling it overlapping or superseding.
4. Inspect git history for touched files/symbols and topic terms:
   - Prefer bounded history such as `git log --all --since=<range> -- <paths>` for touched files.
   - Use `git log --all --grep=<terms>` for topic-level history.
   - Use blame or line history only when it can prove why the existing behavior exists or whether a prior fix already addressed the same issue.
   - Record the range and refs inspected.
5. Inspect Slack topic discussions when Slack tools are available:
   - Search relevant public/team channels for topic terms.
   - Read complete matching threads in timestamp order.
   - Distinguish decisions from speculation, proposals, and unresolved questions.
   - Do not search private channels or DMs without explicit user consent.
   - If Slack is unavailable, or private-channel consent would be required, record that as skipped-with-reason.
6. Classify the audit:
   - `intent`: clear / unclear / conflicting
   - `correctly_open`: yes / no / unclear
   - `needed`: yes / no / unclear
   - `similar_or_recent_work`: none found / open overlap / recently merged overlap / superseded / unknown
   - `recommended_review_action`: continue normal review / ask author a clarifying question / suggest narrowing / suggest closing as duplicate or superseded / block on missing evidence
7. Use the result conservatively:
   - Do not claim a PR is unnecessary from ambient evidence alone.
   - Do not claim overlap from matching terminology alone.
   - Draft feedback only when the classification is anchored in the current PR plus direct or high-signal ambient evidence.

## Deduplication + Truth Filter (Required Before Drafting)

- Using artifacts from GitHub Context Intake + Reference Resolution, classify each candidate finding:
  - `covered`:
    - already addressed by accurate PR description clarifications or existing review threads/replies
    - already present in a valid existing pending review/draft comment from the current authenticated account
    - comment author does not matter
    - verify against the current implementation/diff
    - do not draft a new comment
  - `new`: not already covered and verified against the current implementation/diff; eligible for draft feedback.
    - For replacements and test migrations, apply the Replacement/Migration Parity Gate in `judging_core.md` first.
      Only `parity_gap`, `new_regression`, and `scope_expansion` can be `new`; `preserved_limitation` and `prose_drift` cannot be `new`.
  - `incorrect`: prior clarification/comment conflicts with the current implementation/diff;
    add one correction with evidence (do not echo the incorrect claim).

## Existing Pending Review Reconciliation (Blocking Before Final Draft/Post)

Run this after the candidate queue is evidence-verified and before preparing any final PR-review draft, pending-review API payload, or review submission.

1. Build a ledger of current-account review content:
   - current authenticated login
   - pending review IDs, bodies, commit IDs, and draft comments
   - already-submitted review bodies, inline comments, thread replies, and PR-level comments authored by the same login
   - current PR head SHA
2. Compare every new candidate finding against that ledger and the current diff:
   - same root cause / same fix / same anchor region -> one merged finding
   - old pending anchor moved but finding remains valid -> re-anchor in the merged payload
   - old pending finding is now stale, fixed, duplicated by public context, or wrong -> drop it from the payload and record why
   - old pending finding is independent and still valid -> keep it once in the merged payload
   - new finding duplicates an existing valid pending finding -> suppress the new duplicate
   - new evidence contradicts existing pending content -> resolve from current head or stop as `blocked`
3. If a pending review already exists:
   - do not create another pending review
   - prepare a consolidated replacement payload that contains kept existing findings plus kept new findings exactly once
   - if posting is requested, the GitHub side-effect layer must delete/recreate the pending review only after explicit approval
4. Include this ledger in output:
   - `Pending review reconciliation: none found`
   - `Pending review reconciliation: reused existing <review_id> with no changes`
   - `Pending review reconciliation: merged replacement needed for <review_id> (kept=<n>, added=<n>, dropped=<n>)`
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
  - do not rely on full-file line numbers
  - do not rely on stale patches
  - do not rely on memory
- For API calls, do not assume a source-file line number is a valid anchor. Prefer:
  - `position` (diff-relative), computed from the PR's unified diff:
    - the `@@` hunk header line itself is **not counted** (position 0)
    - the first line after the `@@` header is position 1
    - counting continues sequentially across all subsequent hunks in the file
  - or `line` + `side` / `start_line` + `start_side` (still must resolve against the PR diff; GitHub will 422 if it cannot resolve)
- If the specific source line you care about is not shown in the diff context:
  - do NOT anchor the comment to an unrelated line
  - anchor on the nearest relevant diff line in the same file and include a deep link to the exact source location on the PR head SHA
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
  - for rich editors, do not assume the accessible textarea reflects the full editor model; verify what is actually rendered

## If Posting Is Requested

- Invoke the `github` skill via the Skill tool for exact anchoring and API constraints.
