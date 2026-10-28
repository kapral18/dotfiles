---
sidebar_position: 6
---

# Staying on the Goal

Every session keeps an intent card and checks its work against it on each iteration, so the user steers less.
Nothing needs invoking: the agent writes the card (`~/AGENTS.md` §3 step 0), and the intent-guard hooks in each harness do the rest.

## The intent card

Before the task's first edit, the agent writes the card with `,task card set`:

```text
Goal: Add CSV export to the report page
Reading: The user wants a download button next to Print; PDF stays as is.
Done when:
- D1: the button downloads a CSV of the visible rows
- D2: tests cover the export
Scope: src/report/, tests/report/*.py
Not doing: PDF export, column picker
```

`,task` numbers the `Done when` items (`D1`, `D2`, …) and stores session-keyed cards in `cards.json` per worktree under `~/.local/share/agent-tasks/<worktree>-<hash>/` (override with `AGENT_TASK_DIR`).
Each session retains its own card and turn state, even when several sessions share a worktree. Storage updates hold a worktree lock across reading and writing.
Card commands, `claim`, `stance`, `finding`, `check`, `block`, `reopen`, `status`, `scope`, and `correct` select `--session <id>`, then `AGENT_TASK_SESSION`, then the only recently active session. With several active sessions they require an explicit selection; hooks name the id in their notes. `card clear` removes only the selected card and turn state.
Subagents are left alone: OMP subagents and advisors, OpenCode child sessions, and Claude subagent tool calls never touch the card.
Rewriting the card under the same goal keeps the status of items whose text did not change; a new goal reopens every item, records the old goal, and the card shows only the latest earlier goal.
Hooks inject the latest five scope changes and count the rest; `card show` and scope checks use them all.
A new goal archives the old goal's scope changes as a record (`card show --json`); `card set` lists the archived paths so the agent re-adds the ones the new goal still needs.
`card set` warns when the agent-written part (Goal, Reading, Done when, Scope, Not doing) passes 2048 bytes; the card is saved anyway, and evidence notes and history lines do not count.
Scope entries preserve spaces and resolve symlinks. Use one path per line when a path contains a comma or semicolon.
The agent marks items with `,task check D1 --claim C1` or `,task block D2 --reason "..."`, and records a path the goal or a defect in the change's impact needs beyond the scope with `,task scope add <path> --reason "..."`.

## Evidence and decisions

Each card keeps claims (`C<n>`), stance history (`S<n>`) and review findings (`F<n>`). Card rewrites retain these records, including when the goal changes. Clearing the card removes them.

### Review acceptance

Before each independent review round, run:

```sh
,task review --session <id>
```

The command prints JSON containing versioned acceptance snapshots: goal, reading, criteria, scope and its extensions, exclusions, and user corrections. The first call records version 1. Completion statuses, claims, and review verdicts do not create acceptance versions.

When those acceptance fields change, the command refuses to checkpoint until the caller supplies `--reason "<user change or source evidence>"`. The card edit remains saved; the previous review snapshot stays intact. Inspect `,task card show --json`, then supply the reason to append a new version. Repeating an unchanged checkpoint reuses its version.

Reviewers cite criteria as `v1/D1`, so reordering or replacing a `D1` in a later card cannot silently change an earlier review's meaning. Card rewrites retain review history, including across goal changes; `card clear` removes it for that session. The command records the justification; it does not establish that the justification is true or authorize scope expansion.

The [independent review procedure](reviewing-diffs.md#independent-agent-reviews) keeps finding discovery open within the authorized scope and impact. Acceptance snapshots are not a whitelist of reportable defects.

```sh
,task claim add "The source defines the export flag" --file src/export.py:12 --text 'EXPORT_ENABLED = True'
,task check D1 --claim C1
,task stance set export-format "Keep CSV" --because C1
,task finding resolve F1 --rejected C1
```

The example line is illustrative; use the exact current line.

- `--file <path>:<line> --text "<line>"` hashes the whole file. The claim fails once the file changes or disappears, so register a new claim after a change. Symlinks are read through the named path. File claims work in every harness.
- `--quote "<output>"` matches a Bash, Read, Grep or Glob result in the selected Claude session's local transcript under `CLAUDE_CONFIG_DIR/projects` (default `~/.claude/projects`). The match covers text beyond the judge's head/tail preview and evidence from before compaction, but not output the tool itself truncated. Rewound branches do not count. In a parallel tool batch every call and result counts, though only the result that finished last continues the ancestry. Other tools are excluded because they can return model reports or omit the operation behind them; use a file claim for their source content. A Bash call whose command text mentions `,task` is excluded too, even a plain source read; use a file claim or `--unknown` instead. Read and Grep inputs and Bash descriptions do not trigger that exclusion. An admitted result can still hold model-written or false text.
- `--unknown "<reason>"` records a gap. It cannot complete a Done-when item.

Changing a stance requires a verified claim whose source is newer than the previous stance, or newer verbatim user words (`--user`). Re-registering old output does not make it new. Claude words must come from a human-origin transcript row. Elsewhere only text a person typed counts: Codex's `UserPromptSubmit`, and in Pi and OMP an `input` event whose source is not `extension` (`,task hook user`). A synthetic prompt such as OMP's auto-continue after compaction, or an extension's `sendUserMessage`, never counts. OpenCode records no user words: its prompt hook also gets a command's expanded template, so `--user` has nothing to match there. Repeating the same key, value and valid reason returns the existing stance. A different verified reason appends a refresh even when the value stays the same; only a change of value requires newer evidence.

Claude's Stop hook rechecks cited sources and checked Done-when items. Each `Checked:` item needs `[C<n>]`; each `Assumptions:`, `Proposed:` and `Decision needed:` item needs its current `[S<n>]`. Quoted and fenced examples cannot stand in for a report. A bare report heading is incomplete; empty lists marked `none` need no citation. Free prose is outside this gate. Older checked items with only free-text evidence must be rechecked with a claim; `check --evidence` is removed.

The judge receives the card, claims and provenance results, stance history, stored findings, and the current turn. Earlier raw chat is omitted. Findings retain their exact anchor and concern: a different concern at the same line remains distinct. A fixed or rejected repeat is suppressed while its resolution claim is valid, unless it quotes tool evidence newer than that resolution. This is exact matching, not semantic deduplication; the judge is instructed to reuse the stored wording for the same issue.

Matching proves a quote or line exists, not that it supports the claim; the judge still decides that. The Stop hook still fails open and sends a turn back at most once per stretch, so the ledger is a provenance check and review aid, not a guarantee against pandering. Only Claude enforces answer citations; the CLI works in every harness.

## Pi context checkpoints

`,task hook checkpoint --harness pi --input '{"session":"<id>","cwd":"<repo>"}'` returns a current task/evidence projection without duplicating raw source bodies. It returns an empty context when that session has no card, so clearing a card cannot select another session's task.

Pi refreshes this checkpoint before provider calls and saves it at completed tool-turn boundaries. It includes saved preferences, review acceptance, decisions, finding resolutions and claim provenance results. A provenance match still does not prove a claim. Older bulky tool output may become retrievable references; the [Pi retention policy](tool-configs/pi.md#task-checkpoints-and-output-retention) documents its limits. Existing independent review discovery and the fix loop remain unchanged.

## When the user is wrong

The user can misword an ask, miss context, or pick a weaker option, so the card holds the goal behind the words, not the words.
What the user wants is theirs to say; facts and methods are settled by evidence (`~/AGENTS.md` §1).
When the ask misses its goal or conflicts with the evidence, the agent notes it in `Reading:` and says so with the evidence before it acts.
Whether it then acts, asks, or proposes follows §1.
A correction of what the user wants updates the card; one of fact or method that the evidence contradicts gets one line with that evidence.
A zoom-out also asks whether the goal itself still looks right, and both reviewers count an answer that followed a flawed ask without saying so as a miss.

## What runs on each iteration

| When                              | What happens                                                                                                                                                                                 | Catches                       |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Each prompt                       | The card goes in with the prompt; the session's first prompt also gets saved preferences.                                                                                                    | Lost intent after a long turn |
| A prompt that corrects            | The text is added to the card as a verbatim correction and logged; the agent updates the card, flags a factual or method error the evidence shows, and saves a lasting preference.           | The same misreading again     |
| First edit with no card           | Refused once per session, with the card format.                                                                                                                                              | Starting without a goal       |
| Each file edit                    | A note when the path is outside `Scope:`.                                                                                                                                                    | Scope creep                   |
| Each shell or code execution call | Before/after fingerprints detect file-state changes, including existing untracked files, and flag paths outside `Scope:`. Staging and timestamp-only changes to readable files do not count. | Edits made through a shell    |
| Every 25 tool calls               | A zoom-out note with the card: say in one line whether the work still serves the Goal.                                                                                                       | Drift on long runs            |
| Compaction                        | The summary keeps the card verbatim, with statuses and corrections; the next tool call zooms out.                                                                                            | Goal lost to the summary      |
| Stop                              | Sent back while a `Done when` item is open or an unresolved file change is outside `Scope:`. Restoring a path's pre-edit state clears it, including pre-existing dirty content.              | Stopping early, quiet creep   |

The stop check sends a turn back at most 3 times, and lets the stop through when the same items and files are still open after a send-back, so it cannot loop.
A turn whose tools write nothing (a question, a status check) is not held to the open items, even with a card.
While another session shares the worktree, the prompt note names this session's id for `,task card set --session <id>`.
In Claude Code, only prompts a person sent count: a task notice or a peer's message neither adds the card nor resets the stop check.
The card keeps the last 5 corrections; the steering log keeps them all.
Scratch paths (`/tmp`, `$TMPDIR`, `~/.claude/plans`, the agent-tasks store) outside the worktree need no card and are always in scope.
When `,task` is missing or fails, every hook lets the session go on unguarded.

## Per harness

| Harness     | Adapter                                                                  | Prompt                                                                                   | Edit                                          | Zoom-out                       | Compaction                                   | Stop                                                |
| ----------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------ | -------------------------------------------- | --------------------------------------------------- |
| Claude Code | `intent-guard` mod ([Claude Code](tool-configs/claude.md#mods))          | `prompt.submit` context                                                                  | `tool.call` deny or result context            | `tool.call` result context     | `session.compact` instructions               | `classic.Stop` block                                |
| Pi          | `~/.pi/agent/extensions/intent-guard.ts`                                 | `before_agent_start` message; `input` records the user's words                           | `tool_call` block                             | `tool_result` content          | flag only; the next tool call shows the card | `agent_before_settle` continue                      |
| OMP         | `~/.omp/agent/extensions/intent-guard.ts`                                | `before_agent_start` message; `input` records the user's words                           | `tool_call` block                             | `tool_result` context          | `session.compacting` context                 | `session_stop` continue                             |
| Codex       | `[[hooks.*]]` in `~/.codex/config.toml`, each running `,task hook codex` | `UserPromptSubmit`                                                                       | `PreToolUse` edit refusal and shell snapshots | `PostToolUse` context          | `SessionStart` (`compact`) context           | `Stop` `decision: block`                            |
| OpenCode    | `~/.config/opencode/plugins/intent-guard.ts` (2.x plugin API)            | `session` `prompt` hook; the card is pinned as a system part on each request of the turn | `tool` `execute.before` throws                | `execute.after` result content | `compaction` system part                     | a follow-up prompt on `session.execution.succeeded` |

Pi, OMP, and OpenCode share `~/lib/shared/intent_guard.ts`; `~/bin/,task` launches `~/lib/,task/main.py`. OMP passes normalized hashline header paths; the core also checks `MV` destinations. Snapshots pair by tool-call ID. Each call establishes or refines baselines only from its own after/completion sample; capture order chooses the earliest completed sample, including background handoffs. Unfinished attempts cannot override another call’s baseline. Claude and OpenCode also sample failed direct attempts. In-flight snapshots from older formats are discarded on upgrade; cards and completed checks remain intact. Fingerprints include content, file type, permissions and symlink target; Git status discovers shell candidates, including a rename’s deleted source. An omitted tracked path has an unknown baseline; an omitted untracked path within the capture’s discovery domain starts absent. Capture-time exclusions preserve direct-edit baselines for ignored files, Git metadata, nested repositories and paths hidden by index flags, even if Git visibility later changes. Paths from the starting snapshot are rechecked even if they become clean. Direct edits capture their named paths and symlink referents before writing; directory symlinks resolve before `..`. Read failures preserve available metadata as a conservative fingerprint, so an unreadable file does not discard the rest of a snapshot. Stop compares attributed paths with their first pre-edit state, so restored edits clear and unresolved deletions remain flagged. Concurrent user edits during a shell call cannot be distinguished from that command's writes.
OMP background Bash/Eval snapshots survive prompts until a terminal `tool_execution_update` reports completion, failure, or cancellation. That update records the writes; ordinary read calls do not.
Claude background Bash snapshots record writes at handoff and survive until a terminal task notification or `GetTask` result. Running check-ins leave them pending; typed text cannot impersonate a completion notice. Headless commands marked to end at the final response are also sampled at Stop, since they send no completion notice; their snapshots expire at the next prompt.
OpenCode has no blocking stop hook, so its plugin sends one follow-up prompt when a run ends with an item open; that prompt skips the prompt hook, so the 3-send-back guard still holds.
Codex runs a config hook only after it is trusted once in `/hooks`; `inject_mcp_into_codex_toml.py` keeps the trust hashes across applies.
The model reviewers judge the answer against the card first: Claude's `stop-review` gets it from `,task hook evidence`, and OMP's `Gate` reads it from the prompt context the extension adds.

## Preferences and the steering log

`,task pref add "<rule in the user's words>"` saves a preference keyed by the resolved Git common directory (`--global` for every repo; outside Git, by the working directory); new sessions load it on their first prompt, and `,task pref list` prints what applies.
Each correction the prompt hook detects goes to `~/.local/share/agent-tasks/steering.jsonl` with the goal and the answer it corrected.
`,task steering --days 7` counts corrections per repo and harness and prints the recent ones: the place to look for a rule, a skill, or a card habit that keeps failing.
