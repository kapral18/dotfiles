# Agent Review Context Pack Contract

Shared read-only intake contract for `/k-agent-review` workers. Load this file when the parent scope packet names a context pack.
The blind fresh-eyes lane is the one exception: its own contract restricts it to `diff.patch`, `files/`, and `base/` and forbids pack metadata and live fallbacks.

A context pack is an optimization and consistency boundary, not a new source of truth.
It lets stateless lanes consume the same complete PR snapshot without re-fetching identical GitHub and git data.

## Pack root

PR modes use:

```text
/tmp/agent-review/<owner>-<repo>-pr<number>/
```

Local modes use:

```text
/tmp/agent-review/local-<workspace-hash>-<base>..<head>/
```

Treat the pack as read-only. Never write into it, refresh it in place, delete files from it, or add worker notes beside it.

## Contents

The pack may contain:

- `manifest.json` — `{pr, owner, repo, head_sha, base_sha, base_ref, mode, authorship, generated_at, files[]}`;
  each `files[]` entry names a changed path with status/additions/deletions.
- `pr.json`
- `body.md`
- `comments.json`
- `reviews.json`
- `review_comments.json`
- `checks.json`
- `diff.patch`
- `files/<path>` — head content for every changed file.
- `base/<path>` — base content for every changed file when available.

The JSON snapshots are complete/paginated snapshots produced by the controller (`pr.json` is the full `gh pr view --json` payload, present only when a PR exists).
Do not replace them with summaries or partial live queries.

## Freshness gate

Before trusting any pack content:

1. Read `manifest.json`.
2. Verify `manifest.head_sha` equals the expected head in the parent scope packet.
3. If the head does not match, ignore the pack, fall back to live `gh`/`git` reads, and report `pack_stale` in your return block with both shas.
4. If the pack root or `manifest.json` is missing, fall back to live `gh`/`git` reads and report `pack_missing` in your return block.

Do not mix stale pack content with live content for the same PR snapshot.
After a stale or missing result, use live reads consistently for the affected artifact class.

## Consumption rules

- Read changed-file content, base changed-file content, PR metadata, discussions, reviews, checks, and the unified diff from the pack when the pack contains them.
- Never re-fetch with `gh pr view`, `gh api` comment/review pagination, or `git show <head>:<changed-path>` for artifacts already present in the pack.
- Use live commands for material the pack does not contain: history/blame, symbol searches, files outside the changed set, base-repo context, external references, runtime checks, or follow-up evidence named by your role contract.
- If a single expected changed file is absent from `files/` or `base/`, fetch only that missing file live and report the missing path in the return block.
- Keep worker-local notes and disposable probes outside the pack.

Return `pack_used: <root>` when the pack passed the freshness gate and supplied any evidence.
Return `pack_missing` or `pack_stale` when you had to fall back.
