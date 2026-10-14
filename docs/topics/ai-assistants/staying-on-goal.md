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
Card commands, `check`, `block`, `reopen`, `status`, `scope`, and `correct` select `--session <id>`, then `AGENT_TASK_SESSION`, then the only recently active session. With several active sessions they require an explicit selection; hooks name the id in their notes. `card clear` removes only the selected card and turn state.
Subagents are left alone: OMP subagents and advisors, OpenCode child sessions, and Claude subagent tool calls never touch the card.
Rewriting the card keeps the status of items whose text did not change and records the old goal.
Scope entries preserve spaces and resolve symlinks. Use one path per line when a path contains a comma or semicolon.
The agent marks items with `,task check D1 --evidence "<command and result>"` or `,task block D2 --reason "..."`, and records a path the goal needs beyond the scope with `,task scope add <path> --reason "..."`.

## When the user is wrong

The user can misword an ask, miss context, or pick a weaker option, so the card holds the goal behind the words, not the words.
What the user wants is theirs to say; facts and methods are settled by evidence (`~/AGENTS.md` §1).
When the ask misses its goal or conflicts with the evidence, the agent notes it in `Reading:` and says so with the evidence before it acts.
It takes a better path itself only when that is reversible, keeps the goal, and overrides no explicit choice; anything else becomes a question.
A correction of what the user wants updates the card; one of fact or method that the evidence contradicts gets one line with that evidence.
A zoom-out also asks whether the goal itself still looks right, and both reviewers count an answer that followed a flawed ask without saying so as a miss.

## What runs on each iteration

| When                              | What happens                                                                                                                                                                         | Catches                       |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| Each prompt                       | The card goes in with the prompt; the session's first prompt also gets saved preferences.                                                                                            | Lost intent after a long turn |
| A prompt that corrects            | The text is added to the card as a verbatim correction and logged; the agent updates the card, flags a factual or method error the evidence shows, and saves a lasting preference.   | The same misreading again     |
| First edit with no card           | Refused once per session, with the card format.                                                                                                                                      | Starting without a goal       |
| Each file edit                    | A note when the path is outside `Scope:`.                                                                                                                                            | Scope creep                   |
| Each shell or code execution call | The call's before/after snapshots detect created, changed, or deleted files, including existing untracked files, and flag paths outside `Scope:`. Read tools do not attribute edits. | Edits made through a shell    |
| Every 25 tool calls               | A zoom-out note with the card: say in one line whether the work still serves the Goal.                                                                                               | Drift on long runs            |
| Compaction                        | The summary keeps the card verbatim, with statuses and corrections; the next tool call zooms out.                                                                                    | Goal lost to the summary      |
| Stop                              | Sent back while a `Done when` item is open or a file this turn changed is outside `Scope:` (pre-existing dirt and user edits between tool calls do not count).                       | Stopping early, quiet creep   |

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
| Pi          | `~/.pi/agent/extensions/intent-guard.ts`                                 | `before_agent_start` message                                                             | `tool_call` block                             | `tool_result` content          | flag only; the next tool call shows the card | `agent_before_settle` continue                      |
| OMP         | `~/.omp/agent/extensions/intent-guard.ts`                                | `before_agent_start` message                                                             | `tool_call` block                             | `tool_result` context          | `session.compacting` context                 | `session_stop` continue                             |
| Codex       | `[[hooks.*]]` in `~/.codex/config.toml`, each running `,task hook codex` | `UserPromptSubmit`                                                                       | `PreToolUse` edit refusal and shell snapshots | `PostToolUse` context          | `SessionStart` (`compact`) context           | `Stop` `decision: block`                            |
| OpenCode    | `~/.config/opencode/plugins/intent-guard.ts` (2.x plugin API)            | `session` `prompt` hook; the card is pinned as a system part on each request of the turn | `tool` `execute.before` throws                | `execute.after` result content | `compaction` system part                     | a follow-up prompt on `session.execution.succeeded` |

Pi, OMP, and OpenCode share `~/lib/shared/intent_guard.ts`; `~/bin/,task` launches `~/lib/,task/main.py`. OMP passes normalized hashline header paths; the core also checks `MV` destinations. Shell snapshots pair by tool-call ID. Concurrent user edits during a shell call cannot be distinguished from that command's writes.
OMP background Bash/Eval snapshots survive prompts until a terminal `tool_execution_update` reports completion, failure, or cancellation. That update records the writes; ordinary read calls do not.
Claude background Bash snapshots record writes at handoff and survive until a terminal task notification or `GetTask` result. Running check-ins leave them pending; typed text cannot impersonate a completion notice. Headless commands marked to end at the final response are also sampled at Stop, since they send no completion notice; their snapshots expire at the next prompt.
OpenCode has no blocking stop hook, so its plugin sends one follow-up prompt when a run ends with an item open; that prompt skips the prompt hook, so the 3-send-back guard still holds.
Codex runs a config hook only after it is trusted once in `/hooks`; `inject_mcp_into_codex_toml.py` keeps the trust hashes across applies.
The model reviewers judge the answer against the card first: Claude's `stop-review` gets it from `,task card show --session <id>`, and OMP's `Gate` reads it from the prompt context the extension adds.

## Preferences and the steering log

`,task pref add "<rule in the user's words>"` saves a preference keyed by the resolved Git common directory (`--global` for every repo; outside Git, by the working directory); new sessions load it on their first prompt, and `,task pref list` prints what applies.
Each correction the prompt hook detects goes to `~/.local/share/agent-tasks/steering.jsonl` with the goal and the answer it corrected.
`,task steering --days 7` counts corrections per repo and harness and prints the recent ones: the place to look for a rule, a skill, or a card habit that keeps failing.
