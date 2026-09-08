# PR Snapshot, Drift, and File Truth

Loaded by `pr_common.md` for every PR mode. The controller runs this; workers read the resulting pack per `context-pack.md`.

## Snapshot (the context pack; one fetch per object)

The PR snapshot is the review context pack owned by `~/.agents/skills/k-review/references/context-pack.md`:
one producer, one layout, read by the controller and by every lane.
Fetch each PR object once into the pack and read from it; a second API shape for the same object is a duplicate fetch, not more evidence.

Pack root: `/tmp/deep-review/<owner>-<repo>-pr<number>/` (the layout, `manifest.json` fields, and file inventory are in `context-pack.md`).

- Metadata and body: `gh pr view <n> --repo <owner/repo> --json number,url,title,body,author,state,isDraft,baseRefName,baseRefOid,headRefName,headRefOid,mergeable,mergeStateStatus,files,labels,closingIssuesReferences` → `pr.json` (body also as `body.md`).
- Discussion: one GraphQL query → `threads.json`, paginated to completion, holding `reviews` (state, body, `submittedAt`, `updatedAt`, author `login` + `__typename`), `reviewThreads` (`isResolved`, `isOutdated`, `path`, `line`, and every comment with `databaseId`, `body`, `createdAt`, `updatedAt`, `isMinimized`, `minimizedReason`, author `login` + `__typename`), and issue `comments` (same fields).
  This is the only fetch for review and comment content; do not also call REST `pulls/<n>/reviews`, `pulls/<n>/comments`, or `issues/<n>/comments` for the same PR.
  Fetch the timeline only when an event (label, force-push, review request, close/reopen) is itself the question.
- Checks: `gh pr checks <n> --json name,state,bucket,workflow,link` → `checks.json` (owned by the CI Coverage Gate).
- Diff and files: `diff.patch`, `files/<path>`, `base/<path>` per `context-pack.md`, scoped as in Diff scope below.
- Media and references: every attachment and every linked PR/issue the intake gate reads goes into the pack too (`media/`, `refs/`), per the two subsections below.
- Write `manifest.json` with `head_sha`, `base_sha`, `snapshot_at`, and `discussion_at`;
  record the same four values plus `pack: <root>` in the review spec (`shared_rules.md`, Review Persistence).
- Read the pack with targeted reads.
  The complete raw artifact is on disk, which satisfies the intake gate below without dumping JSON into context twice.

### Media

- Download every image, GIF, video, or file attachment referenced by the PR body, a comment, or a linked reference into `media/<sha256-prefix>.<ext>` and add a row to `media/manifest.json`: `url`, `path`, `source` (comment `databaseId`, `body`, or `refs/<file>`), `sha256`, `bytes`, `content_type`, `fetched_at`.
- Public-repo `user-attachments` URLs serve the file to a plain unauthenticated GET; use that, with no `Authorization` header.
  A token is not a browser session. Inspect the payload; do not treat an org sign-in page as the requested attachment.
- Private-repo assets return 404 to an unauthenticated GET and need a logged-in browser session:
  fetch them through `~/.agents/skills/k-playwriter/SKILL.md` (open the asset URL in the authenticated browser and save the response), or ask the user to attach the file.
- After every download, check the payload before trusting it: `file <path>` must report an image, video, or the expected document type, and `content_type` must not be `text/html`.
  A 200 with an HTML body is a failed download, not evidence; record it as `download_failed` in the manifest and do not "read" it as media.
- An attachment URL is immutable per upload: never re-download a URL already in the manifest.
  When a comment edit changes the URL, the new URL is a new media row; the old row stays until the pack is rebuilt.
- Inspect media only from the pack path, view each file once, record its `media:` line in the review spec, and cite the manifest row when a finding depends on it.

### References

- Every linked or closing issue and PR the intake gate reads is fetched once into `refs/<pr|issue>-<owner>-<repo>-<number>.json` with its full body, comments, state, and `updatedAt`.
- Fetch a newer reference only when the user asks or the final check plan names its current state as material;
  otherwise read the stored file.

### Diff scope and file truth

- The review scope is `git diff <base_sha>...<head_sha>` and nothing else.
  Never diff `main...HEAD` or `<base-branch>...HEAD`: local `main` and local `HEAD` both drift from the PR, and the stat then carries unrelated commits.
- Verify both SHAs exist locally before diffing: `git cat-file -e <sha>^{commit}`.
  - `head_sha` missing: working-tree files are stale for this review.
    Read head content from `gh api repos/<o>/<r>/pulls/<n>/files` patches or `gh pr diff <n>`, or ask the user to fetch the PR head (`git fetch origin pull/<n>/head`); say which you used.
  - `base_sha` missing: use `gh api repos/<o>/<r>/compare/<base_sha>...<head_sha>` for the file list and patches, or ask to fetch base.
- Local checkout state, checked once with `git rev-parse HEAD` and `git status --porcelain`:
  - `HEAD == head_sha` and clean: working-tree reads are head reads.
  - `HEAD != head_sha` (unpushed local commits, another branch, a stale checkout) or a dirty tree:
    every cited `file:line` and every quoted line comes from `git show <head_sha>:<path>` or `files/<path>`, never from the working tree.
    Say so once in `Base context:`.
  - Local commits ahead of `head_sha`: the review target is still the remote head; note that the unpushed work is not under review.
- Generated paths stay out of unified diffs: apply the File-Type Awareness skip list as a pathspec exclusion (`-- .
':(exclude)<glob>'`), list those files from `git diff --stat` only, and open one only when a finding depends on it.
  A verified domain overlay may add repo-specific generated globs.

### Drift (one final freshness check)

The pack records truth at `snapshot_at`, not a continuously refreshed view.
In final Verify, the root checks head and discussion once against the frozen pack:

1. Head: compare `gh pr view <n> --json headRefOid` with `manifest.head_sha`.
2. Discussion: fetch the complete paginated discussion into a separate final evidence artifact.
   Compare comment IDs, `updatedAt`, content, review state, and thread resolution/outdated state with `threads.json`.
   Include new, edited, deleted, and minimized comments and replies.

Report `Drift: head=<same|old..new> discussion=<none|changed ids>`. If either changed, report stale evidence and the affected criteria.
Do not certify the new snapshot. Do not rebuild the pack, repeat intake, re-anchor findings, or restart review automatically.
A new attempt requires user authorization; retain unchanged evidence with its original snapshot identity.

Immediately before an authorized anchored publication, check the exact target head and anchor preconditions required by `k-github`.
This is a transaction safety check, not another semantic review. If they changed, withhold the write and report stale anchors.
Do not use publication checks to reopen final Verify.

### Lifetime

The pack is a best-effort `/tmp` cache, not a durable record; task decisions and receipts stay in the topic spec.
On continuation, resume the recorded stage and snapshot. Do not repeat completed freshness checks merely because a turn or session changed.
A missing pack is a concrete blocker. A new user-authorized attempt may build a new snapshot without overwriting the prior evidence.
