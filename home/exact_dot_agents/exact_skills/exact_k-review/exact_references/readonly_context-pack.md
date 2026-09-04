# Deep Review Context Pack Contract

Shared intake contract for every review tier.
The controller produces the pack (`pr_snapshot.md` owns the fetch commands and the drift checks);
workers load this file when the parent scope packet names a pack and read it only.
The blind fresh-eyes lane is the one exception: its own contract restricts it to `diff.patch`, `files/`, and `base/` and forbids pack metadata and live fallbacks.

A context pack is an optimization and consistency boundary, not a new source of truth.
It lets stateless lanes consume the same complete PR snapshot without re-fetching identical GitHub and git data.

## Pack root

PR modes use:

```text
/tmp/deep-review/<owner>-<repo>-pr<number>/
```

Local modes use:

```text
/tmp/deep-review/local-<workspace-hash>-<base>..<head>/
```

Treat the pack as read-only.
Read from it only: leave it exactly as generated — no writes, in-place refreshes, deletions, or worker notes beside it.

## Contents

The pack may contain:

- `manifest.json` — `{pr, owner, repo, head_sha, base_sha, base_ref, mode, authorship, snapshot_at, discussion_at, files[]}`;
  each `files[]` entry names a changed path with status/additions/deletions.
  `snapshot_at` is when head-bound content was fetched; `discussion_at` is when `threads.json` was last fetched or refreshed.
- `pr.json` — the full `gh pr view --json` payload, present only when a PR exists.
- `body.md`
- `threads.json` — one paginated GraphQL snapshot of reviews, review threads with every comment and reply, and issue comments;
  each comment carries `databaseId`, `createdAt`, `updatedAt`, `isMinimized`, and author `login` + `__typename`.
  This is the only discussion artifact; there are no separate REST comment or review files.
- `checks.json`
- `diff.patch`
- `files/<path>` — head content for every changed file.
- `base/<path>` — base content for every changed file when available.
- `media/<sha256-prefix>.<ext>` plus `media/manifest.json` — every attachment referenced by the body, a comment, or a reference, downloaded once and `file`-verified (plain GET for public assets, browser session for private ones; on SAML-SSO orgs a token yields the sign-in page, not the file); manifest rows carry `url`, `path`, `source`, `sha256`, `bytes`, `content_type`, `fetched_at`.
- `refs/<pr|issue>-<owner>-<repo>-<number>.json` — every linked or closing PR/issue the intake gate read, with body, comments, state, and `updatedAt`.

The JSON snapshots are complete/paginated snapshots produced by the controller. Do not replace them with summaries or partial live queries.

## Lifetime

The pack is a cache of refetchable data under `/tmp`: not mirrored, not swept, rebuilt or refreshed by the controller's drift checks (head and discussion) and discarded rather than trusted when they find a change.
Durable review state lives in the review spec, never in the pack.

## Freshness gate

Before trusting any pack content:

1. Read `manifest.json`.
2. Verify `manifest.head_sha` equals the expected head in the parent scope packet.
3. If the head does not match, ignore the pack, fall back to live `gh`/`git` reads, and report `pack_stale` in your return block with both shas.
4. If the pack root or `manifest.json` is missing, fall back to live `gh`/`git` reads and report `pack_missing` in your return block.

Do not mix stale pack content with live content for the same PR snapshot.
After a stale or missing result, use live reads consistently for the affected artifact class.

## Consumption rules

- Read changed-file content, base changed-file content, PR metadata, discussions, reviews, checks, media, linked references, and the unified diff from the pack when the pack contains them.
- Never re-fetch with `gh pr view`, `gh api` comment/review pagination, attachment downloads, linked PR/issue reads, or `git show <head>:<changed-path>` for artifacts already present in the pack.
- Use live commands for material the pack does not contain: history/blame, symbol searches, files outside the changed set, base-repo context, external references, runtime checks, or follow-up evidence named by your role contract.
- If a single expected changed file is absent from `files/` or `base/`, fetch only that missing file live and report the missing path in the return block.
- Keep worker-local notes and disposable probes outside the pack.

Return `pack_used: <root>` when the pack passed the freshness gate and supplied any evidence.
Return `pack_missing` or `pack_stale` when you had to fall back.
