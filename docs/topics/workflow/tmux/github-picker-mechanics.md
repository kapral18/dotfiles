---
sidebar_position: 6
---

# GitHub picker mechanics

This page holds the detailed behavior behind the [GitHub picker](github-picker.md) overview.

## Entry source

Items come from standalone YAML configs:

- `~/.config/tmux/scripts/pickers/github/gh-picker-work.yml`
- `~/.config/tmux/scripts/pickers/github/gh-picker-home.yml`

Each file defines PR and issue sections using GitHub Search syntax. `lib/gh_items_main.py` parses the config, runs the GitHub API queries, and formats rows as fzf TSV.

## Scopes and sorting

The dashboard has two navigation axes:

| Axis  | Binding          | Values                    |
| ----- | ---------------- | ------------------------- |
| Mode  | `ctrl-s`         | `work`, `home`            |
| Scope | `alt-0`..`alt-2` | `all`, `focus`, `explore` |

Scopes are filtered views over the same cache:

- `all`: every configured section.
- `focus`: `Action:` + `Mine:` + `Maintenance:` sections.
- `explore`: `Watching:` sections.

`alt-S` cycles item sort within each section:

1. `created-desc`
2. `updated-desc`
3. `age-asc`
4. `repo-asc`

Headers stay anchored; only rows between headers move.

## Header navigation

`alt-n` and `alt-p` jump to next/previous section headers. The fetcher writes `~/.cache/tmux/gh_picker_offsets_{mode}_{scope}.json`; the bash jump helper reads that sidecar and emits fzf `pos(N)`.

The helper is intentionally pure bash in the hot path. An older `cat + python3` implementation cost enough per keypress that held `alt-n`/`alt-p` queued faster than they drained.

## Hierarchy and families

The picker nests related work without requiring you to open GitHub:

| Relationship         | How it appears                                                    |
| -------------------- | ----------------------------------------------------------------- |
| Issue epics          | Epic parent row with child issues                                 |
| PR backport families | Source PR parent plus target-branch children                      |
| PR ↔ issue links     | Inline `↳ #N`, `closes:N`, `closed-by:N`, and hidden match tokens |

Visual cues:

| Symbol                 | Meaning                  |
| ---------------------- | ------------------------ |
| `⬢`                    | Epic root                |
| `◇`                    | PR family root           |
| `├─` / `└─`            | Family child             |
| `↳ #N` / `↳ closes #N` | Cross-linked PR or issue |

The `Maintenance: Pending backports` section remains the source of truth for missing backports. It combines bot comments, current version labels, and title search for manually-created backports.

## Inline badges

Rows encode GitHub and local state inline:

- PR/issue state: open, merged, closed, not planned.
- review state: approved, changes requested, pending/review required.
- CI state: success, failure, pending.
- local state: matching worktree exists, conflict/mergeability state.
- relationship state: epic, backport family, linked issue/PR.

The hidden match key includes repo, author, assignee, labels, state, local worktree status, review status, CI status, conflict status, and relationship tokens so typed search can narrow by status without changing the visible row format.

## Worktree detection

Local worktree markers come from git worktree state plus branch/metadata heuristics. Issue markers can also be inferred from the session picker cache when a worktree is already linked to an issue.

## Actions

| Key      | Action                                              |
| -------- | --------------------------------------------------- |
| `enter`  | Checkout worktree and focus it; batches marked rows |
| `ctrl-t` | Batch worktree creation                             |
| `alt-b`  | Checkout and open Octo review                       |
| `alt-A`  | Stage selected PRs/issues for Ralph handoff         |
| `alt-o`  | Open in browser                                     |
| `alt-y`  | Copy URLs                                           |
| `alt-c`  | New comment                                         |
| `alt-r`  | Quote-reply                                         |
| `alt-d`  | Edit your own comment                               |
| `alt-x`  | Command palette for PR/issue actions                |

Mutating actions are delegated to helper scripts and use the standard GitHub side-effect gates outside the read-only dashboard view.

## Create issue / epic

`alt-i` opens `$EDITOR` to create a new issue. `alt-E` creates an epic: parent issue plus authored sub-issues. Both can optionally create a worktree and tmux session.

The creation helpers stage handoff files under the tmux cache dir so the popup can close and the next tool can consume the selection.

## Command palette (`alt-x`)

`alt-x` opens a per-item action palette for operations such as close/reopen, approve, request changes, merge, label add/remove, comment, and request review.

The palette applies to the cursor row or marked rows.

## Cache and refresh

Main cache:

```text
~/.cache/tmux/gh_picker_{work,home}.tsv
```

The picker paints cache immediately, starts a background fetch, and posts a reload to fzf's listen socket only when the fresh fetch succeeds. Failed refreshes leave the visible cache intact.

`ctrl-r` pre-empts any in-flight fetch, releases the fetch lock safely, and starts a fresh request.

## Preview pane

The preview uses `gh_preview.sh`, cached per repo/kind/number under:

```text
~/.cache/tmux/gh_preview/
```

Collapsed previews show summary/body/activity in bounded form. `alt-e` cycles collapsed → body expanded → all expanded.

## Popup dimensions

The GitHub picker opens at `95% × 95%` because the row list and preview are both dense. `alt-g` switches to the session picker by closing and reopening at the session picker's configured dimensions; tmux does not support resizing an existing popup.
