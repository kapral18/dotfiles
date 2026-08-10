---
sidebar_position: 6
---

# GitHub picker mechanics

This page holds the detailed behavior behind the [GitHub picker](github-picker.md) overview.

## Entry source

Items come from standalone YAML configs:

- `~/.config/tmux/scripts/pickers/github/gh-picker-work.yml`
- `~/.config/tmux/scripts/pickers/github/gh-picker-home.yml`

Each file defines PR and issue sections using GitHub Search syntax. `lib/gh_items_main.py` parses the config, uses GraphQL review-request actors for direct and selected-team review queues, and formats rows as fzf TSV.

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

## Multi-select across reloads

`gh_picker.sh` enables fzf `--multi` and identifies rows with `--id-nth=2,3,4` (`kind`, `repo`, `num`). Background fetch and row-loader spinner updates `reload-sync` the list and mutate the visible marker cell in field 1; without stable identity fields, fzf clears marks on each reload. The session picker uses the same pattern (`--id-nth=2,3`).

## Worktree detection

Local worktree markers come from git worktree state plus branch/metadata heuristics. Issue markers can also be inferred from the session picker cache when a worktree is already linked to an issue.

## Actions

| Key      | Action                                              |
| -------- | --------------------------------------------------- |
| `enter`  | Checkout worktree and focus it; batches marked rows |
| `ctrl-t` | Batch worktree creation                             |
| `alt-b`  | Checkout and open Octo review                       |
| `alt-o`  | Open in browser                                     |
| `alt-y`  | Copy URLs                                           |
| `alt-c`  | New comment                                         |
| `alt-r`  | Quote-reply                                         |
| `alt-d`  | Edit your own comment                               |
| `alt-x`  | Command palette for PR/issue actions                |

Mutating actions are delegated to helper scripts and use the standard GitHub side-effect gates outside the read-only dashboard view.

Batch worktree creation (`ctrl-t`) captures the launching picker's mode, scope, port, cache file, and tmux socket into an immutable dispatch packet, then detaches a `nohup` background job (not `tmux run-shell -b`) so closing the dashboard popup cannot cancel in-flight clones. Selected worktrees are created one at a time across detached batches because one Git checkout can already use every configured worker; a shared BSD `lockf` lock prevents overlapping full-repo checkouts from starving tmux or racing marker updates. Lock wait counts against the same total deadline as creation. An item failure before the batch deadline does not cancel later items or poison the next batch; once the hard deadline expires, unstarted items are not launched. Issue creation invokes the read-only `~/lib/,w/add.sh` and `open.sh` command libraries through `bash`, and detached creates carry the captured socket as `OUTER_TMUX_SOCKET` after `TMUX` is intentionally removed. Worktree session existence and focus use tmux's `=` exact-target form, so a longer session with the requested name as its prefix cannot suppress creation or receive the switch. Completion markers still target the popup that started the batch, even if another popup rewrites the shared mode/scope globals before the background work finishes.

Detached survival is bounded so hung clones cannot linger as rogue processes with stuck amber spinners: each `,gh-worktree` call runs under `timeout --kill-after=10s` (`GH_BATCH_ITEM_TIMEOUT_SECS`, default 600), the batch waits with a hard deadline (`GH_BATCH_TOTAL_TIMEOUT_SECS`, default 1800) that TERM/KILL-reaps remaining create trees, and a per-batch job ledger under `~/.cache/tmux/gh_batch_worktree_jobs/<batch-pid>.tsv` records create/spinner PIDs, process-start identities, and `(kind,repo,num)`. A create child retains the cross-batch lock through ledger publication and EXIT cleanup, while spinner, curl, and `,gh-worktree` descendants close that descriptor; the next batch therefore cannot pass an unrecorded orphan or reap a ledger during an active drop. On batch exit, unsettled ledger rows are killed and their loading markers cleared. A later lock holder treats every remaining ledger as stale, removes ledger-less lock directories left by an interrupted reap before a batch PID can reuse them, and signals a recorded process only when both its start identity and detached `gh_batch_worktree.sh --background` argv still match; reused ledger filenames and row PIDs cannot suppress cleanup or target unrelated processes. Ledger append, drop, and reap remain mkdir-lock serialized so cleanup cannot race publication or lose a row before finalization. Spinner subshells are started as direct children of their create subshell (no `$(...)` capture), so the tree kill reaps them even when a create is SIGKILLed before its EXIT trap.

Row-loader spinner frames are ephemeral full-list renders POSTed fire-and-forget, and fzf applies whatever arrives last. Each spinner carries a token file named by its pid (`gh_row_loader_spin_<pid>.tok`): the loop re-checks it after every slow render and aborts before POSTing once `stop_spinner` has removed it, while the spinner tracks and waits for its direct curl children before the authoritative re-render. Direct comment/palette callers also stop and join their spinner from EXIT cleanup, so interruption cannot orphan the infinite frame loop. Without this, a stale loading frame could clobber the final render, leaving rows stuck on amber spinners after the work finished.

When a batch includes issues, the foreground phase opens the branch-naming scratch buffer in `$EDITOR`. Each issue is a row in `<repo>#<number>|<branch>` form (e.g. `owner/repo#123|`), so the repo and issue are right in the fillable row rather than a bare number. When the editor is nvim, it also opens a vertical-split terminal to the right running an interactive `,cursor-openrouter` agent (DeepSeek preset, `--effort max`) with the fixed prompt from `gh_batch_branch_prompt.txt` (scratch path substituted at launch). That prompt tells the agent to fetch each issue title via `gh`, invent a conventional-commit branch name, write it after the pipe, and stop — no git/worktree side effects. The terminal auto-closes when the agent exits (`util.terminal.run_in_split` with `close_on_exit`); the scratch buffer remains the focused window and is still edited and saved directly. An empty branch skips that issue, and each created branch is `<branch>-<number>`.

## Create issue / epic

`alt-i` opens `$EDITOR` to create a new issue. `alt-E` creates an epic: parent issue plus authored sub-issues. Both can optionally create a worktree and tmux session.

The creation helpers stage a `gh_picker_create_pin` in the picker's handoff namespace (see [Handoff bus](#handoff-bus)) so the popup can close and `gh_picker` can consume the selection and check it out on exit.

## Handoff bus

Pickers cooperate through an owner-scoped file bus implemented by `pickers/lib/handoff_namespace.py` (verbs `begin`, `path`, `end`, `sweep`). It replaces the earlier top-level cache mailbox: there are no shared well-known files, and stray top-level legacy files are ignored and never written.

On launch, `gh_popup.sh` runs `begin --owner-role popup-loop --entry gh-popup`, which mints a random 32-hex token and publishes a private namespace at `${XDG_CACHE_HOME:-$HOME/.cache}/tmux/handoff-v1/<token>/`. The directory is created `0700` via an atomic `.new-<token>` staging rename, and its immutable `owner.json` (`0600`) fingerprints the owner `pid`, start time, and command. The token is exported as `TMUX_PICKER_HANDOFF_TOKEN` and explicitly injected into every child popup with `display-popup -e`; it is never passed in argv or inferred from a global mailbox. GitHub and session pickers resolve every slot inside that one namespace via `handoff_namespace path <slot>`.

Producers stage a selection and abort; the successor consumes and deletes it on launch:

| Slot                        | Producer → consumer                                                       |
| --------------------------- | ------------------------------------------------------------------------- |
| `pick_session_pin`          | GitHub picker `alt-g` → session picker startup seed (`pin_session_first`) |
| `gh_picker_pin`             | session picker `alt-g` → GitHub picker startup seed (`pin_gh_first`)      |
| `gh_picker_switch_sessions` | GitHub picker `alt-g` sentinel → popup loop relaunches the session picker |
| `pick_session_switch_gh`    | session picker `alt-g` sentinel → popup loop relaunches the GitHub picker |
| `gh_picker_create_pin`      | create flow → consumed on GitHub picker exit → checkout                   |

## Command palette (`alt-x`)

`alt-x` opens a per-item action palette for operations such as close/reopen, approve, request changes, merge, label add/remove, comment, and request review.

The palette applies to the cursor row or marked rows. After a mutation, it joins in-flight spinner posts, refreshes the cache, and posts the refreshed frame to the open picker.

## Cache and refresh

Main cache:

```text
~/.cache/tmux/gh_picker_{work,home}.tsv
```

The picker paints cache immediately, starts a background fetch, and posts a reload to fzf's listen socket only when the fresh fetch succeeds. Failed refreshes leave the visible cache intact.

The fetch lock is publication-safe: a waiter that loses the `mkdir` race never reaps an owner that has claimed the lock directory but not yet written its pid file. It backs off during a short publish grace instead, so two popups can never launch competing fetches for the same cache.

`ctrl-r` pre-empts any in-flight fetch, releases the fetch lock safely, and starts a fresh request.

## Preview pane

The preview uses `gh_preview.sh`, cached per repo/kind/number under:

```text
~/.cache/tmux/gh_preview/
```

Collapsed previews show summary/body/activity in bounded form. `alt-e` cycles collapsed → body expanded → all expanded.

## Popup dimensions

The GitHub picker opens at `95% × 95%` because the row list and preview are both dense. `alt-g` switches to the session picker by closing and reopening at the session picker's configured dimensions; tmux does not support resizing an existing popup.
