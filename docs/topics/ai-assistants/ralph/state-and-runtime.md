---
sidebar_position: 2
title: State and runtime
---

# State and runtime

## Runtime data

Runtime data stays outside chezmoi (per-session isolation, never under the project worktree):

| Data                | Default path                 | Override             |
| ------------------- | ---------------------------- | -------------------- |
| Knowledge capsules  | `~/.local/share/ai-kb/`      | `AI_KB_HOME`         |
| Ralph run manifests | `~/.local/state/ralph/runs/` | `RALPH_STATE_HOME`   |
| Ralph roles config  | `~/.config/ralph/roles.json` | `RALPH_ROLES_CONFIG` |

## Core workflow

```bash
,ai-kb remember --title "Project rule" --body "Keep generated state out of git."
,ralph dry-run --goal "Memory rehearsal"                          # render the prompt only
,ralph go --goal "Build a tiny CLI tool" --workspace "$(mktemp -d)"
,ralph go --goal "Refactor module" --plan-only                    # stop after planner
,ralph go --spec /tmp/specs/.../refactor.spec.json                # operator-authored spec; planner skipped
,ralph go --goal "Refactor module" --workflow research            # workflow hint
,ralph go --goal "Refactor module" \
  --reviewer-model claude-sonnet-4-7 --re-reviewer-model gpt-5.5  # per-role overrides
,ralph answer <run-id> --json - <<< '{"q1":"yes, the cache is ok"}' # post answers when parked at awaiting_human
,ralph runner <run-id>                                            # internal: drive the state machine
,ralph resume <run-id>                                            # re-launch runner if it died (no-op if alive/terminal)
,ralph replan <run-id>                                            # queue replan; runner consumes it next loop
,ralph supervisor --json                                          # resume dead non-terminal runners when safe
```

Tmux-native mode (default when `$TMUX` is set: the runner detaches and your shell returns immediately; `--foreground` blocks inline; `--subprocess` skips tmux entirely):

```bash
,ralph go --goal "Build a tiny artifact"               # detached runner; observe via dashboard
,ralph go --foreground --goal "Block until done"       # inline state-machine drive
,ralph runs --json --session "$(tmux display-message -p '#S')"
,ralph preview <run-id>      # rich summary; --mode tail for live tail
,ralph dashboard             # alias for prefix+A: execs ~/.local/bin/ralph-tui
,ralph attach <run-id> --role executor-1
,ralph verify <run-id>
,ralph kill  <run-id> [--role executor-1]              # SIGINT pane(s), mark killed
,ralph kill  --all                                     # bulk-kill every non-terminal run
,ralph rm    <run-id>                                  # archive + drop ai-kb capsules
,ralph statusline                                      # one-line tmux status segment + (^A) hint
,ralph doctor --live-models                            # opt-in complete Cursor catalog drift check
```

The live-model diagnostic uses the generated v1 mirror and is non-mutating: `ok` means every curated ID is still available, `drift` names curated IDs missing from the complete catalog, and command/auth/parse failures report `Unknown`. Newly available models are counted but never added automatically.

Resumability is manifest-driven:

| Case                   | Behavior                                                                                                                                                                                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| runner dies            | `,ralph resume <run-id>` relaunches from the earliest pending phase                                                                                                                                                                        |
| role already completed | manifest cache is reused; no duplicate role spawn                                                                                                                                                                                          |
| role pane still alive  | runner reuses the pane and waits for its exit marker                                                                                                                                                                                       |
| runner liveness check  | exclusive `flock` on `<run_dir>/runner.pid`                                                                                                                                                                                                |
| supervisor             | resumes dead runners in `running`/`needs_verification` only; skips every parked run (manual control, questions, reviewer BLOCK)                                                                                                            |
| reviewer BLOCK park    | `status=needs_human` + `phase=blocked` + `block_reason`, no role control; only `,ralph resume <run-id>` clears it and starts the next same-plan iteration (verify / direct runner / supervisor keep it parked; `,ralph replan` rejects it) |
| self-healing replan    | executor-emitted `RALPH_REPLAN` and manual `,ralph replan` queue replans                                                                                                                                                                   |

Per-iteration phases:

```text
pending -> exec -> review -> rereview -> decided
```

At review entry the orchestrator machine-runs every spec criterion `check` (a shell command, exit 0 = pass), injects the results into the prompts of whichever review roles the workflow runs, and stores them on the iteration record. At decide time a `pass` verdict over any failing check is demoted to `needs_iteration` — LLM verdicts cannot outvote a red check. Passing results freeze into `manifest.criteria_check_results` and render in `summary.md` under `## Criteria checks (machine-run)`.
