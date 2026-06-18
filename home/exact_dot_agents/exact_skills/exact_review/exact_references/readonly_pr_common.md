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

PR review otherwise re-checks everything, including classes the PR's own CI already catches — redundant. Drop findings CI will inevitably flag, but verify the relevant check actually exists and covers that class first: some branches (backports especially) loosen CI, so a check you would expect may be absent or narrowed.

1. Enumerate the PR's checks (read-only). Set `GH_PAGER=cat`, then `gh pr checks <number> --json name,state,bucket,workflow,link`.
2. Map each present check to the Coverage-Checklist classes it actually catches (e.g. lint -> style/format nits, typecheck -> type errors, a test job -> the behavior it exercises, SAST -> the vuln classes it scans). A check covers only what it actually runs; do not credit it from its name alone.
   - Buildkite job whose coverage is unclear: load and follow `~/.agents/skills/buildkite/SKILL.md` (`bk` CLI) to see what it runs before crediting it with a class.
3. Exempt a finding-class from review only when a present check genuinely covers it — CI will flag those, so do not build findings or draft comments for them.
4. Keep every other class in scope, including ones whose check is absent or loosened on this branch. Do not assume a class is covered just because CI usually covers it elsewhere.
5. State one line before drafting: `CI coverage: covered=[...] -> exempt; in-scope=[...]`.

## GitHub Context Intake + Reference Resolution (blocking — complete before diff analysis)

Use this gate for the primary PR and every recursively discovered PR, issue, comment, thread, asset, URL, or reference that could inform the review. Do not rely on summaries, previews, truncated terminal output, or compacted output; recover the full raw content before marking an item read.

1. Maintain a visited set by canonical URL/object ID so recursion is exhaustive without looping.
2. Seed the queue from the primary PR:
   - raw PR description/body, read every line including template text, checkboxes, code blocks, quotes, collapsible sections, and footnotes
   - PR conversation/timeline comments, review bodies, review comments, review threads, and every reply in each thread, including resolved/outdated state when available
   - linked/closing issues, linked PRs, commits, check/build links, URLs, and image/media/attachment links found anywhere above
3. For each queued item, read the complete artifact before extracting references from it:
   - PRs: read raw description/body line-by-line, state, author/base/head, labels/milestone when relevant, all conversation/timeline comments, all review bodies, all review comments/threads/replies, linked/closing issues and PRs, check/build links, and diff summary. Inspect the full diff or exact files when the referenced PR is cited as precedent, fix, regression, or evidence for a claim.
   - Issues: read raw body line-by-line, state, labels/milestone when relevant, all comments/replies/timeline text, linked PRs/issues, and every attachment/media/reference.
   - Comments/threads: read the parent comment plus every reply end-to-end; include author, timestamp/order, resolved/outdated/minimized state, and any referenced code or links.
   - Images/screenshots: download to `/tmp` with `curl -sL -o /tmp/<name> <url>`, then inspect the local file, including visible text, UI state, annotations, and error messages.
   - GIFs/videos: download to `/tmp`; inspect first/last frames plus every significant frame or scene/state transition (UI changes, overlays, terminal output changes, before/after states). Use available local tooling (`ffmpeg`/`ffprobe`, browser/player, image extraction, OCR/vision when available). Inspect audio, captions, or transcripts when present.
   - Buildkite URLs (`buildkite.com/...`): **do not fetch directly** (will 403). Load and follow `~/.agents/skills/buildkite/SKILL.md` — use `bk` CLI to retrieve build/job info.
   - Other URLs: fetch when they could inform the review, then read the full relevant content and extract references.
4. From every artifact just read, extract new URLs, PR/issue refs, comments, assets, media, commits, builds, and code references; enqueue any unvisited potentially relevant item.
5. Repeat until the queue is empty. Do not proceed while a reachable, potentially relevant reference remains unread. If an item is inaccessible, unsupported by local tooling, or genuinely irrelevant, record the exact reason before excluding it.
6. State the full list of references visited, skipped-with-reason, and what you learned from each before proceeding to diff analysis.

If a claim depends on visuals and visuals are missing, inaccessible, or unclear, stop and ask for visuals or better access before making that claim.

## Ambient Topic Exploration (conditional — complete before judging contested context)

Run this second layer only when direct PR/issue context does not settle shared understanding:

- the PR/issue discussion shows disagreement, conflicting claims, or unclear ownership/requirements
- the user asks for deep context, history, "why", precedent, or whether a claim matches team/product understanding
- a candidate finding depends on product intent, team convention, prior incidents, or decisions not proven by the directly referenced artifacts
- direct references are sparse, contradictory, or appear to omit the rationale behind the current disagreement

Skip it for routine implementation reviews where the diff, base context, and direct references are enough. Keep it bounded: write the topic, queries, sources searched, hits read, and stop reason before using the results.

1. Build a topic map from the current artifact and diff: product/feature names, code symbols, error text, labels, team names, user-visible phrases, and disputed terms.
2. Search GitHub beyond direct references:
   - Issues: `gh search issues --repo OWNER/REPO "<terms>" --match title,body,comments --json number,title,state,commentsCount,updatedAt,url --limit 20` (omit `--state` to search both open and closed)
   - PRs: `gh search prs --repo OWNER/REPO "<terms>" --match title,body,comments --json number,title,state,commentsCount,updatedAt,url --limit 20` (omit `--state` to search both open and closed)
   - Discussions when the repo uses them: GitHub GraphQL `search(query: "repo:OWNER/REPO <terms>", type: DISCUSSION, first: N)` (GraphQL exposes `DISCUSSION`, `Discussion.comments`, and `DiscussionComment.replies`; `gh search` has no discussion subcommand)
3. If Slack MCP tools are available in the current runtime, search relevant public/team channels for the topic terms and read full matching threads. Existing Slack MCP examples in this setup use `slack_search_public`, `slack_search_channels`, `slack_read_user_profile`, and, with explicit user consent, `slack_search_public_and_private`. Do not search private channels or DMs without explicit consent.
4. For each promising ambient hit, read enough full context to decide whether it informs the disputed topic:
   - GitHub issues/PRs/discussions: body, comments/replies/threads, linked references, and relevant diffs/files using the GitHub Context Intake + Reference Resolution rules above
   - Slack: the complete thread/conversation around the hit, not just the matching message; preserve timestamps/order and distinguish decisions from speculation
5. Stop when searches produce no new decision-relevant facts, after a small representative set of high-signal hits, or when tools/access are exhausted. Record skipped sources with reasons (`Slack MCP unavailable`, `private channel requires consent`, `GitHub Discussions disabled/unavailable`, etc.).
6. Use ambient evidence only as context/precedent. The current PR diff and directly relevant artifacts remain the source of truth for what is actually changing.

## Deduplication + Truth Filter (Required Before Drafting)

- Using artifacts from GitHub Context Intake + Reference Resolution, classify each candidate finding:
  - `covered`: already addressed by accurate PR description clarifications or existing review threads/replies (regardless of comment author) after verifying against the current implementation/diff; do not draft a new comment.
  - `new`: not already covered and verified against the current implementation/diff; eligible for draft feedback.
  - `incorrect`: prior clarification/comment conflicts with the current implementation/diff; add one correction with evidence (do not echo the incorrect claim).

## Comment Placement (Draft Guidance)

Where to comment:

- Default: inline on a relevant diff line/range in the PR.
- File-scoped concerns: prefer a file-level comment (`subject_type=file`).
- If you are replying in an existing thread, use the reply mode of PR fix.
- Do not replace inline feedback with a PR-level summary body.
- Only use file-level or PR-level placement when no reliable inline anchor exists, or when the user explicitly asks for non-inline placement.

## Anchoring Constraints (Only If Posting Is Requested)

- PR review comments are anchored to the PR's unified diff. The GitHub UI can sometimes let you comment on context lines by expanding the diff, but API calls still need a resolvable diff anchor.
- Before every API call that creates or submits anchored PR review comments, fetch the current PR diff/patch for the target head SHA and verify each anchor against the diff hunk you intend to comment on. Do not rely on full-file line numbers, stale patches, or memory.
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
