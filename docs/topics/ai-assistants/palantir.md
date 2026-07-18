---
title: Palantír orchestrator
---

# Palantír orchestrator

`,palantir` is the tmux-native long-work orchestrator. It treats one effort as one **legion**: a disposable `,w` worktree, a dedicated tmux session, a deterministic supervisor, and interactive role panes that do the judgment-heavy work under normal SOP and skill governance.

The name is literal: the dashboard is the seeing stone for long-running work. It shows what each legion is doing, which stage is active, whether the run is waiting on a human, and whether the machine checks are green enough for a human to take over.

![Actual Palantír Textual dashboard in the ecosystem Catppuccin Frappé theme showing a cleared legion and a holding legion with semantic stage colors and Nerd Font stage glyphs, stage age, attention state, criteria count, attempts, goal, session, and worktree](./assets/palantir-dashboard-full.png)

_Rendered from the current dashboard source against a sanitized two-legion fixture; no UI or text was generated._

## Model

| Unit             | Meaning                                                                                                                                             |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Legion           | One effort. It owns one tmux session, one manifest, one worktree unless `--no-worktree` is used, and one stage timeline.                            |
| Session          | The tmux container for the effort. Window 0 is `command`: coordinator agent pane plus deterministic supervisor pane.                                |
| Role window      | A tmux window dedicated to an interactive role stage such as `implement` or `adversarial_review`; machine-run `verify` stays in the supervisor.     |
| Coordinator pane | A persistent agent harness that receives structured `[palantir]` events and makes judgment calls that the deterministic supervisor must not invent. |
| Supervisor pane  | The Python control loop. It owns lifecycle, state transitions, retries, wake dedupe, and safety guards without putting an LLM in the control path.  |

The implementation follows the repo's thin-launcher pattern: `~/bin/,palantir` dispatches into `~/lib/,palantir/`. The chezmoi source lives at `home/exact_bin/executable_,palantir`, `home/exact_lib/exact_,palantir/`, and the Fish completion lives at `home/dot_config/fish/completions/readonly_,palantir.fish`.

## Using it

The main CLI surface:

| Command                                                                          | Purpose                                                                                                                                   |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `,palantir`                                                                      | Open the dashboard.                                                                                                                       |
| `,palantir summon "<goal>" [--criteria '<json>'] [--base <ref>] [--no-worktree]` | Summon a new legion.                                                                                                                      |
| `,palantir farsee`                                                               | Survey every legion.                                                                                                                      |
| `,palantir behold <id>`                                                          | Behold manifest-derived status for one legion.                                                                                            |
| `,palantir send-word <id> [--window W] "<msg>"`                                  | Send structured word into a legion window.                                                                                                |
| `,palantir answer <id> "<msg>"`                                                  | Answer a parked condition and resume its stored stage.                                                                                    |
| `,palantir grant <id>`                                                           | Grant the human clearance gate, persist closeout memory instructions, tear down the legion, and print the packet path + routing reminder. |
| `,palantir routed <id>`                                                          | Mark a closed legion's memory-routing packet as executed, clearing the `U:n` attention flag.                                              |
| `,palantir banish <id> [--force]`                                                | Banish and tear down a legion. On a lock-only debris dir with no manifest, it removes the dir fail-closed.                                |
| `,palantir keep-watch <id> [--stop]`                                             | Keep or stop the deterministic supervisor watch.                                                                                          |
| `,palantir trial <id>`                                                           | Put the acceptance criteria to machine trial again.                                                                                       |
| `,palantir statusline`                                                           | Print the compact tmux status segment.                                                                                                    |
| `,palantir doctor`                                                               | Check local wiring and configuration.                                                                                                     |
| `,palantir composer <sub>`                                                       | Access composer helpers.                                                                                                                  |
| `,palantir state <sub>`                                                          | Inspect or adjust state internals.                                                                                                        |

Palantír is strictly opt-in in ordinary chat sessions (SOP §8.0). The agent must not propose, summon, or hand work to a legion unless the user explicitly asks to use Palantír in the current conversation.

After that request, the agent presents the goal packet, acceptance criteria, and base ref and waits for explicit approval. `--no-worktree` requires the user to have asked for it by name.

Direct human CLI use may omit `--criteria`, but `verify` then runs zero acceptance commands. A goal-only summon remains supervised and adversarially reviewed; it does not provide machine-tested acceptance.

## Stage machine

A normal legion advances left to right:

```text
summon → triage → diagnose → investigate → implement → adversarial_review → verify → cleared_for_human
```

`diagnose` and `investigate` are used when the goal needs them. Straightforward implementation work can move from `triage` to `implement`.

Two non-success states matter:

| State      | Meaning                                                                                                              |
| ---------- | -------------------------------------------------------------------------------------------------------------------- |
| `holding`  | The legion is parked because a role asked a question, a premise needs human input, or the retry budget is exhausted. |
| `banished` | Terminal lifecycle stage entered when closure is accepted; teardown status records whether cleanup completed.        |

The supervisor enforces the hard guards:

- `adversarial_review` cannot clear the same model family that implemented the change.
- `verify` is machine-run acceptance criteria only: command exit 0 is green and nonzero is red with evidence.
- `cleared_for_human` is reachable only after green verify and zero review blockers.
- A verify failure or an adversarial review with open blockers wakes `implement` with bounded evidence.
- Every return to `implement` spends the shared `max_implement_attempts` budget, then parks the legion in `holding`.
- Repeated identical wake states are deduped, so the coordinator sees one actionable event instead of log spam.
- State transitions persist their runtime actions before execution; a supervisor restart retries an unacknowledged pane launch, verify, wake, or closeout packet instead of losing it.
- Coordinator events are durably queued while its pane is busy and removed only after composer-authorized delivery.
- Pane input is fail-closed: only composer `empty` authorizes injection; `pending`, `busy`, and `unknown` wait and retry without advancing the stage.
- Role harnesses carry `PALANTIR_AGENT_ROLE`; the dispatcher and supervisor refuse agent-originated `grant` and `banish` events, and `summon` refuses legion panes outright (no recursive legions), keeping clearance, teardown, and legion creation human-controlled.

## Hybrid control

Palantír splits control and judgment deliberately.

| Owner                    | Responsibilities                                                                                                                                                                                                              |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Deterministic supervisor | Manifest reads/writes, tmux pane/window creation, stage transitions, retry counters, wake dedupe, verify execution, statusline data, and terminal state.                                                                      |
| Coordinator agent        | Reacts to supervisor events: decides how to respond to blockers, how to interpret review feedback, when to send word to a role, and what to tell the human. It does not poll, monitor, restart, or directly drive role panes. |
| Role panes               | Run interactive harness CLIs such as Copilot by default, with role-specific settings from `~/.config/palantir/config.toml`.                                                                                                   |

The deterministic loop never asks an LLM to decide whether a state transition is safe. It emits structured `[palantir]` event lines into the coordinator pane when human-like judgment is needed, and it waits for role result files for stage completion.

## Role harnesses and family diversity

Role configuration lives in `~/.config/palantir/config.toml`. It selects the harness command and model for each role while keeping the control loop harness-agnostic.

The shipped route uses Copilot CLI with GPT-5.6 Sol for the coordinator, triage, diagnosis, investigation, and implementation roles. Adversarial review also uses Copilot CLI, but with Claude Fable 5.

Family diversity is a summon-time requirement. The `adversarial_review` role must use a different model family than `implement`; if the configured families match, summon refuses to start the legion.

The point is not variety for its own sake: a model family may not be the only judge of the work it just produced.

## Role-supervisor handshake

Each role reports completion by writing a JSON file under the legion state directory:

```text
stages/<stage>.result.json
```

Successful stage shape:

```json
{
  "kind": "stage_result",
  "stage": "implement",
  "verdict": "done",
  "summary": "Implemented the accepted criteria and ran the targeted checks.",
  "blockers": []
}
```

Question shape:

```json
{
  "kind": "question",
  "text": "Which migration path should this use?"
}
```

The supervisor treats the file as the stage boundary. A `question` parks the legion in `holding`; a stage result with blockers cannot clear the review/verify gates until those blockers are resolved.

An `adversarial_review` result must state `blockers` explicitly. A clean review writes `"blockers": []`, and a result that omits the field is refused fail-closed.

Every dispatched stage records before/after dirty-path identities under `stages/`. The successor receives the resulting changed-path packet, so an adversarial reviewer can distinguish the implementation stage from pre-existing changes in an intentionally dirty `--no-worktree` run.

## Criteria discipline

Specs should hand Palantír criteria that have already been proven red. The `k-spec` flow produces criteria JSON from acceptance checks that were run before implementation and observed failing for the right reason. `,palantir summon --criteria '<json>'` consumes that criteria block for detached execution.

During `verify`, Palantír runs criteria with configured commands as machine checks. A green status means the command exited 0 under the legion worktree. A red status returns evidence to implementation; it does not become a coordinator judgment call.

Judgment-only criteria without a `check` remain for the human and do not block machine verification.

Implementation roles may run focused development checks, but the supervisor owns the full acceptance run. Adversarial review audits both the implementation and criterion observability; a command that exits 0 without exercising the stated behavior is a blocker, not a passing criterion.

## Dashboard and tmux surface

| Surface          | Behavior                                                                                                                                                                                                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Bare `,palantir` | Opens the Textual dashboard via `uv run` from the deployed PEP 723 entrypoint.                                                                                                                                                                                                                   |
| `prefix+A`       | Opens the same dashboard in a tmux popup.                                                                                                                                                                                                                                                        |
| Status-right     | Calls `,palantir statusline`: `P:n H:n C:n` for progressing/holding/cleared, `T:n` for erroring coordinator transport, `O:n` for incomplete teardown, `U:n` for closed legions whose memory packet is still unrouted, and `E:n` for corrupt state. Clean closed-and-routed history stays silent. |
| Tmux config      | `home/dot_config/exact_tmux/exact_conf.d/readonly_45-palantir.conf`.                                                                                                                                                                                                                             |

Nothing is invisible to the stone. Legion dirs without a readable manifest, including lock-only debris, surface as `corrupt` rows in `farsee`, the dashboard, and the `E:n` statusline count.

Locking a nonexistent legion is refused rather than creating such a dir, and `banish` removes a manifest-less dir fail-closed, never while its supervisor lock is live.

The dashboard is Vim-first:

| Key                                    | Action                                                                                                                           |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `j` / `k`                              | Move by row.                                                                                                                     |
| `Ctrl-D` / `Ctrl-U`                    | Move by page.                                                                                                                    |
| `g` / `G`                              | Jump to the first/last legion.                                                                                                   |
| `l` or Enter                           | Attach through the popup's owning tmux server. Popup jobs inherit `$TMUX`; `OUTER_TMUX_SOCKET` remains a nested-server override. |
| Arrow, Page Up/Down, Home, End         | Equivalent accessibility aliases.                                                                                                |
| `s`, `e`, `y`, `w`, `b`, `r`, `x`, `q` | Summon, answer, grant, send word, banish, refresh, toggle successfully closed history, and quit.                                 |

Orphaned/failed teardowns remain visible even when history is hidden. Grant and banish require a typed legion-id confirmation; force-banish requires `FORCE <id>`.

The detail panel shows stage age, supervisor/coordinator transport health, queued wakes, criteria, blockers, close reason, and teardown status.

The dashboard uses Textual's built-in `catppuccin-frappe` theme (Textual ≥ 8), matching the tmux `@catppuccin_flavor 'frappe'` theme the rest of the terminal ecosystem runs.

Stages carry semantic color and a single-width Nerd Font glyph: `holding` in warning yellow (question circle), `cleared_for_human` in success green (check circle), `banished`/`corrupt` in error red (ban circle / warning triangle). Fully green criteria render in success green, and detail-panel transport errors, blockers, and holding conditions use the same theme roles.

Color emoji are deliberately avoided because they ignore theming and their double-width cells drift tmux table alignment.

## State layout

State lives outside the repo by default:

```text
${PALANTIR_STATE_HOME:-~/.local/state/palantir}/legions/<id>/manifest.json
${PALANTIR_STATE_HOME:-~/.local/state/palantir}/legions/<id>/stages/<stage>.result.json
```

`manifest.json` is the supervisor's source of truth for the legion id, goal, worktree, active stage, retry counters, role assignments, blocker state, and verify results.

## Memory routing on close

When a legion closes, Palantír atomically persists a `memory-routing.json` closeout packet before teardown. The human-facing workflow routes its contents by lifetime and ownership:

| Memory                                                  | Destination                                                |
| ------------------------------------------------------- | ---------------------------------------------------------- |
| Durable reusable learning                               | `,ai-kb remember` with deliberate metadata.                |
| Task-scoped worklog or intent notes                     | `/tmp/specs`.                                              |
| Repo-intrinsic conventions discovered during the effort | The target repo's `AGENTS.md` through the legion worktree. |

Routing is human-executed and tracked. `grant` prints the packet path and a reminder, and the legion keeps a `U` (unrouted) attention flag in `farsee`, the dashboard, and the statusline until `,palantir routed <id>` records that the packet's contents were routed.

Do not store secrets, guesses, or one-off observations in durable memory.

## Where to go deeper

- SOP §8 in `~/AGENTS.md` defines the chat agent's Palantír operating boundary.
- Skill source: `home/exact_dot_agents/exact_skills/exact_k-palantir/readonly_SKILL.md`.
- State-machine map: `.mermaids/04-palantir-state-machine.mmd`.
- Governed agent runtime flow: `.mermaids/S2-flow-agent-runtime.mmd`.
