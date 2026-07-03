---
sidebar_position: 3
title: Dashboard and tmux integration
---

# Multi-Ralph dashboard

The dashboard is a Bubble Tea TUI:

| Surface          | Source / behavior                                                                                                                 |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Source           | [`tools/ralph-tui/`](../../../../tools/ralph-tui/)                                                                                |
| Binding          | `prefix + A`                                                                                                                      |
| Installed binary | `~/.local/bin/ralph-tui`                                                                                                          |
| Build hook       | [`run_onchange_after_06-build-ralph-tui.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_06-build-ralph-tui.sh.tmpl) |
| Read model       | manifests under `$RALPH_STATE_HOME`, watched with fsnotify                                                                        |
| Write model      | mutating actions shell out to `,ralph`; orchestrator remains sole writer                                                          |

Layout:

- Left pane: scrollable list of every run (newest first); each row carries the heartbeat marker described below. Status colors track validation/phase.
- Right top: selected run's header (id, goal, phase, status, runner) and a roles table with per-iteration history.
- Right bottom: live tail of the selected role's `output.log`.
- Modals: new-run form (`n`), control menu (`c`), help overlay (`?`).

Keybindings:

- Fleet view rows: heartbeat dot (bright violet `●` alive+fresh, amber `●` alive+stale, red `●` dead, `R` replan queued, blank never started), name, status badge, phase, `n/N` iterations vs `max_iterations`, and a verdict-colored sparkline (green=pass, red=fail, amber=replan, blue=in-flight, dim=pending). A `Q:N` badge surfaces open clarifying questions.
- `j/k` (or arrows) move within the focused pane; `tab` cycles `runs -> roles -> tail`; `enter` (or `3`) zooms the focused pane to fullscreen; `1`/`2`/`3` switch between detail / 2x2 role grid / zoom layouts.
- `s` cycles the runs list sort (`need` parks-on-questions+live-work first, `recent` newest first); `S` toggles the cross-run activity drawer (recent decisions + verdicts across all parent `kind=go` runs).
- `enter` (on a run) attaches via `tmux switch-client -t ralph-<short-rid>`; `enter` (on a role) attaches to that role's window. `p` opens a tmux capture-pane preview of the focused role's pane (read-only, refreshes every second + on `r`); inside the modal, capital `A` launches `tmux display-popup -E -- tmux attach-session -r -t TARGET` for a read-only popup attach without leaving the TUI.
- `n` opens the new-run form. Fields: goal, workspace, plan-only, **workflow** picker (`auto` / `feature` / `bugfix` / `review` / `research`), plus per-role harness AND model pickers for planner / executor / reviewer / re_reviewer. Pickers cycle with `h`/`l` or `←`/`→`; `j`/`k` (or `↓`/`↑`, or `tab`/`shift+tab`) move down/up between fields (gated so the goal/workspace text inputs still accept literal characters); `enter` advances harness → matching model → next role. Harness cycles `cursor → pi → command`; model lists curated per harness in [`tools/ralph-tui/internal/state/models.go`](../../../../tools/ralph-tui/internal/state/models.go); `auto` workflow lets the planner pick, otherwise `--workflow <name>` is forwarded to `,ralph go`.
- `A` (capital) opens the answer modal when the selected run is parked at `awaiting_human`. One text input per open question; `tab`/`j`/`k`/`shift+tab` move focus, `enter` advances or submits, `esc`/`ctrl+c` cancels (`q` cancels only when focus is not on a text input). Submission pipes JSON answers through `,ralph answer <rid> --json -` so the orchestrator can resume. The status bar shows `Q:Σ` aggregated across the fleet.
- `K` (capital) opens the AI KB browser modal. Type a query and `enter` to dispatch a hybrid search (lexical + dense, RRF + MMR, superseded capsules excluded); `↑/↓` move between hits to expand metadata (kind/scope/confidence/refs) on the right; `esc`/`q` closes. The status bar shows `KB:N` (total non-superseded capsules).
- `v` verify; `r` manual refresh; `R` resume runner; `P` replan; `x` kill; `X` rm. `x` and `X` open a confirmation modal before dispatching.
- `/` filter the runs list; `c` opens the control menu (verify, takeover, dirty, kill, rm, replan, resume); `?` toggles help; `q` quit.

Multi-Ralph isolation contract:

- Each `,ralph go` run owns a dedicated tmux session named `ralph-<short-rid>`. Multiple runs coexist without polluting the user's main session.
- The dashboard never holds tmux state; quitting (`q`) does not affect any running runners or sessions.
- `kill <rid>` and `rm <rid>` only touch their own dedicated session; concurrent runs are unaffected (covered by [`scripts/test_ralph.py::TestRalphMultiRunIsolation`](../../../../scripts/tests/test_scripts.py)).

Other tmux integrations:

- `prefix + A` opens the dashboard popup (only top-level prefix key Ralph claims). The popup runs `~/.local/bin/ralph-tui` directly; if the user picks a run + `enter`, the TUI exits cleanly and `tmux switch-client` jumps to that run's session.
- `prefix + R` is **untouched** (still reloads tmux config); start runs from the dashboard (`n`) or the palette.
- The command palette (`prefix + r`) lists Ralph entries (dashboard, `ralph:start-go` prompt, `ralph:plan-only` prompt, verify latest, attach prompt, doctor) that fire `tmux command-prompt` instead of dumping text.
- The session picker (`prefix + T`) tags Ralph-owned tmux sessions with a colored badge (`ralph✓` `ralph?` `ralph✗` `ralph●` `ralph⨯`) and shows the matching `,ralph runs --session …` block in the preview.
- The GitHub picker (`prefix + G`) `alt-A` on a PR/issue stages a Ralph handoff: closes the picker, resolves the matching worktree (or `$PWD`), and opens a `,ralph go` goal prompt seeded with the PR/issue title.
- A status-bar segment (appended after TPM/Catppuccin) shows `R:<running>` and `V:<needs_verification>` counts via `,ralph statusline`.

Dashboard / control-plane invariants:

- Source of truth: `~/.local/state/ralph/runs/<run-id>/manifest.json`. Mutate via the CLI only.
- Each `go` run records `phase` (`planning|executing|reviewing|rereviewing|replanning|done|failed|blocked`), `iterations[]` (each with its own `phase` (`pending|exec|review|rereview|decided`), `verdict`, `executor_id`, `reviewer_id`, `re_reviewer_id`, `task`, `next_task`, `spec_seq`), `roles{}` (pane handles for planner-N / executor-N / reviewer-N / re_reviewer-N), `spec`, `spec_seq`, `learned_ids`, and `runner` (pid + host + heartbeat + alive bit).
- `spec.target_artifact` is promoted to top-level `manifest.artifact`; on a passing verdict Ralph freezes `artifact_sha256`, and `verify` requires the artifact hash to match.
- `executor_count` must be `1` until real multi-executor orchestration exists. Planner output with a higher value fails fast instead of being silently ignored.
- Iteration records are appended at iteration START (phase=pending) and updated as phases progress; the runner is fully resumable from the manifest alone — see [Resumability](state-and-runtime.md#core-workflow).
- Human control: every role records pane handle, status, last output path, and `control_state` (`automated|manual_control|dirty_control|resume_requested`).
- Low-token observability: dashboards read manifests, logs, and tmux pane tails directly. No LLM is invoked for summarization unless the user explicitly requests a review/triage agent.
- Validation gates: a `go` run is `passed` only when the orchestrator loop exits with `status=completed`, the final verdict is `pass`, every role child is `automated`, every role child passed validation, and the artifact hash gate passes when `target_artifact` is declared.
- Manual takeover: `,ralph control <run-id> --role <role> --action takeover|dirty|resume|auto`. `resume` auto-runs `verify`.
- Isolation: workspace and ralph state stay separated by run ID; worktrees remain source-code context, not scratch storage.
