---
sidebar_position: 4
---

# Ralph Orchestrator (`,ralph go`)

One entry point, `,ralph go`, drives an opinionated `planner -> executor -> reviewer -> re_reviewer` loop with persistent state, self-healing (replans on `RALPH_REPLAN`), and full tmux observability. Both reviewer and re_reviewer run on every iteration, in sequence, so two different model families always cover each other's gaps. After a passing run, an optional `reflector` role distills durable lessons into the [AI knowledge base](knowledge-base.md) so subsequent runs benefit from the learnings.

Use when spawning agents, kicking off a run, verifying a run, replanning, or interacting with the tmux Ralph control plane.

| Component         | Source                                                                                                                            |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| CLI entry         | [`home/exact_bin/executable_,ralph`](../../../home/exact_bin/executable_,ralph) + [`scripts/ralph.py`](../../../scripts/ralph.py) |
| Roles + diversity | [`home/dot_config/ralph/roles.json`](../../../home/dot_config/ralph/roles.json)                                                   |
| Role prompts      | [`home/dot_config/ralph/prompts/`](../../../home/dot_config/ralph/prompts/)                                                       |
| Dashboard (TUI)   | [`tools/ralph-tui/`](../../../tools/ralph-tui/)                                                                                   |
| Skill             | [`home/exact_dot_agents/exact_skills/exact_ralph`](../../../home/exact_dot_agents/exact_skills/exact_ralph)                       |

## Roles and the diversity gate

Roles are configured in [`~/.config/ralph/roles.json`](../../../home/dot_config/ralph/roles.json):

| Role          | Default harness | Default model                  | Mode flag     |
| ------------- | --------------- | ------------------------------ | ------------- |
| `planner`     | `cursor`        | `claude-opus-4-7-thinking-max` | `--mode plan` |
| `executor`    | `cursor`        | `composer-2`                   | `--force`     |
| `reviewer`    | `cursor`        | `claude-opus-4-7-thinking-max` | `--mode ask`  |
| `re_reviewer` | `cursor`        | `gpt-5.5-extra-high`           | `--mode ask`  |
| `reflector`   | `cursor`        | `claude-opus-4-7-thinking-max` | `--mode ask`  |

Defaults are cursor-first because cursor's frontier models give the strongest output and judgement on this user's setup; pi stays fully supported and is required for non-cursor providers (anthropic/openai/google direct, openrouter, llama-cpp). The orchestrator enforces `family_of(re_reviewer.model) != family_of(reviewer.model)` (substring match on `claude|gpt|gemini|llama|mistral|deepseek`) so the mandatory second opinion never comes from the same family. `--mode plan` (planner) and `--mode ask` (reviewer/re_reviewer) are read-only — they prevent role hijacking (small models with full tools tend to skip JSON and just execute the goal) while still allowing read access for verification probes. `--force` on the executor auto-approves shell commands so the orchestrator can drive non-interactively. On pi the equivalent role-scoping is `--no-tools` for planner/reviewer/re_reviewer. Per-role prompts live at [`home/dot_config/ralph/prompts/`](../../../home/dot_config/ralph/prompts/).

Local models (llama-cpp / qwen3.6) are opt-in only; defaults never depend on `,llama-cpp serve` being up. Swap them in by editing `roles.json` (e.g. point `executor.harness=pi`, `executor.model=llama-cpp/local`). See [llama.cpp local inference](llama-cpp.md).

### Elastic-gated `/review` skill invocation

For elastic-belonging codebases — operator's day job — the reviewer and re-reviewer roles invoke the operator's [`review` skill](reviews.md) directly. The skill's verification disciplines become the primary instruction; Ralph's existing JSON output contract is preserved as the wire format. Non-elastic workspaces are unchanged.

- **Detection**: [`is_elastic_workspace(path)`](../../../scripts/ralph.py) parses `git remote -v` and matches `(github\.com[:/])elastic/` against any remote URL (HTTPS or SSH; `origin` or `upstream`). Best-effort — non-git directories, missing paths, or `git` failures all yield `False`.
- **Wiring**: [`elastic_review_preamble(role)`](../../../scripts/ralph.py) reads `~/.agents/skills/review/references/{shared_rules,local_changes}.md` and renders a `## REVIEW SKILL HEURISTICS (elastic)` block containing (a) "you are running the `/review` skill in local_changes mode", (b) the skill's `shared_rules.md` content verbatim, (c) the skill's `local_changes.md` content verbatim, and (d) a format-normalization note translating the skill's "fix in working tree" guidance into Ralph's `criteria_unmet` + `next_task` JSON fields. The block is prepended to the dynamic context BEFORE `## SPEC`, so the model reads the skill instruction first then applies it to the inputs.
- **Override**: `RALPH_REVIEW_SKILL_DIR=<path>` swaps in a different skill source directory (useful for testing alternate review heuristics without touching `~/.agents/`).
- **Graceful degradation**: when the skill files are missing the preamble silently degrades to empty (no crash) and the default review path runs unchanged. Operators without the skill installed see no behavior change.
- **Output contract**: unchanged. Reviewer still emits `{verdict, criteria_met, criteria_unmet, next_task, blocking_reason, notes}`; re-reviewer still emits `{agree_with_primary, final_verdict, ...}`. The orchestrator's verdict parser is not aware that the elastic preamble was injected.

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
,ralph go --goal "Refactor module" --workflow research            # workflow hint
,ralph go --goal "Refactor module" \
  --reviewer-model claude-sonnet-4-7 --re-reviewer-model gpt-5.5  # per-role overrides
,ralph answer <run-id> --json - <<< '{"q-1":"yes, the cache is ok"}' # post answers when parked at awaiting_human
,ralph runner <run-id>                                            # internal: drive the state machine
,ralph resume <run-id>                                            # re-launch runner if it died (no-op if alive/terminal)
,ralph replan <run-id>                                            # queue replan; runner consumes it next loop
,ralph supervisor --json                                          # resume dead non-terminal runners when safe
```

Tmux-native mode (default when `$TMUX` is set the runner detaches and your shell returns immediately; `--foreground` blocks inline; `--subprocess` skips tmux entirely):

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
```

Resumability: every iteration is a state machine driven by the manifest on disk. If the runner process dies (Ctrl-C, SSH drop, host reboot), `,ralph resume <run-id>` re-launches it and the loop picks up at the earliest pending phase: per-iteration phases are `pending -> exec -> review -> rereview -> decided`. Role spawns are idempotent at the parent-manifest level: a role with `status=completed` in the manifest cache is reused without re-spawning; if a tmux role pane is still alive after a runner crash, the runner reuses that pane and waits for its exit marker instead of spawning a duplicate. Runner liveness is detected via an exclusive `flock` on `<run_dir>/runner.pid`. `,ralph supervisor` can resume dead non-terminal runners and skips runs parked for manual control.

## Multi-Ralph dashboard

The dashboard ([`tools/ralph-tui/`](../../../tools/ralph-tui/), `prefix + A` opens the popup) is a Bubble Tea TUI installed at `~/.local/bin/ralph-tui` by [`run_onchange_after_06-build-ralph-tui.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_06-build-ralph-tui.sh.tmpl). It reads run state directly from the manifest tree under `$RALPH_STATE_HOME` via fsnotify, so updates are live without polling. All mutating actions still shell out to `,ralph` so the orchestrator stays the only writer.

Layout:

- Left pane: scrollable list of every run (newest first). `*` = runner alive, `R` = replan queued. Status colors track validation/phase.
- Right top: selected run's header (id, goal, phase, status, runner) and a roles table with per-iteration history.
- Right bottom: live tail of the selected role's `output.log`.
- Modals: new-run form (`n`), control menu (`c`), help overlay (`?`).

Keybindings:

- Fleet view rows: heartbeat dot (bright violet `●` alive+fresh, amber `●` alive+stale, red `●` dead, `R` replan queued, blank never started), name, status badge, phase, `n/N` iterations vs `max_iterations`, and a verdict-colored sparkline (green=pass, red=fail, amber=replan, blue=in-flight, dim=pending). A `Q:N` badge surfaces open clarifying questions.
- `j/k` (or arrows) move within the focused pane; `tab` cycles `runs -> roles -> tail`; `enter` (or `3`) zooms the focused pane to fullscreen; `1`/`2`/`3` switch between detail / 2x2 role grid / zoom layouts.
- `s` cycles the runs list sort (`need` parks-on-questions+live-work first, `recent` newest first); `S` toggles the cross-run activity drawer (recent decisions + verdicts across all parent `kind=go` runs).
- `enter` (on a run) attaches via `tmux switch-client -t ralph-<short-rid>`; `enter` (on a role) attaches to that role's window. `p` opens a tmux capture-pane preview of the focused role's pane (read-only, refreshes every second + on `r`); inside the modal, capital `A` launches `tmux display-popup -E -- tmux attach-session -r -t TARGET` for a read-only popup attach without leaving the TUI.
- `n` opens the new-run form. Fields: goal, workspace, plan-only, **workflow** picker (`auto` / `feature` / `bugfix` / `review` / `research`), plus per-role harness AND model pickers for planner / executor / reviewer / re_reviewer. Pickers cycle with `h`/`l` or `←`/`→`; `j`/`k` (or `↓`/`↑`, or `tab`/`shift+tab`) move down/up between fields (gated so the goal/workspace text inputs still accept literal characters); `enter` advances harness → matching model → next role. Harness cycles `cursor → pi → command`; model lists curated per harness in [`tools/ralph-tui/internal/state/models.go`](../../../tools/ralph-tui/internal/state/models.go); `auto` workflow lets the planner pick, otherwise `--workflow <name>` is forwarded to `,ralph go`.
- `A` (capital) opens the answer modal when the selected run is parked at `awaiting_human`. One text input per open question; `tab`/`j`/`k`/`shift+tab` move focus, `enter` advances or submits, `esc`/`ctrl+c` cancels (`q` cancels only when focus is not on a text input). Submission pipes JSON answers through `,ralph answer <rid> --json -` so the orchestrator can resume. The status bar shows `Q:Σ` aggregated across the fleet.
- `K` (capital) opens the AI KB browser modal. Type a query and `enter` to dispatch a hybrid search (lexical + dense, RRF + MMR, superseded capsules excluded); `↑/↓` move between hits to expand metadata (kind/scope/confidence/refs) on the right; `esc`/`q` closes. The status bar shows `KB:N` (total non-superseded capsules).
- `v` verify; `r` manual refresh; `R` resume runner; `P` replan; `x` kill; `X` rm. `x` and `X` open a confirmation modal before dispatching.
- `/` filter the runs list; `c` opens the control menu (verify, takeover, dirty, kill, rm, replan, resume); `?` toggles help; `q` quit.

Multi-Ralph isolation contract:

- Each `,ralph go` run owns a dedicated tmux session named `ralph-<short-rid>`. Multiple runs coexist without polluting the user's main session.
- The dashboard never holds tmux state; quitting (`q`) does not affect any running runners or sessions.
- `kill <rid>` and `rm <rid>` only touch their own dedicated session; concurrent runs are unaffected (covered by [`scripts/tests/test_scripts.py::TestRalphMultiRunIsolation`](../../../scripts/tests/test_scripts.py)).

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
- Iteration records are appended at iteration START (phase=pending) and updated as phases progress; the runner is fully resumable from the manifest alone — see Resumability above.
- Human control: every role records pane handle, status, last output path, and `control_state` (`automated|manual_control|dirty_control|resume_requested`).
- Low-token observability: dashboards read manifests, logs, and tmux pane tails directly. No LLM is invoked for summarization unless the user explicitly requests a review/triage agent.
- Validation gates: a `go` run is `passed` only when the orchestrator loop exits with `status=completed`, the final verdict is `pass`, every role child is `automated`, every role child passed validation, and the artifact hash gate passes when `target_artifact` is declared.
- Manual takeover: `,ralph control <run-id> --role <role> --action takeover|dirty|resume|auto`. `resume` auto-runs `verify`.
- Isolation: workspace and ralph state stay separated by run ID; worktrees remain source-code context, not scratch storage.

## Verification

```bash
uvx pytest scripts/tests/                          # python suite (ralph + isolation + resumability + artifact/control gates + workflows + answer + KB schema/hybrid retrieval/reflector/doc-ingest/curation)
( cd tools/ralph-tui && go test ./... )            # TUI suite (state, cmds, forms, runs, detail, answer, preview, activity, kb, app/view)
AI_KB_HOME="$(mktemp -d)" RALPH_STATE_HOME="$(mktemp -d)" \
  ,ralph go --goal "create $(mktemp -d)/hello.txt with content 'hi'" \
            --workspace "$(mktemp -d)" --subprocess
```

`--runtime local` is deterministic and still exists for `,ralph dry-run` smoke tests; `,ralph go` itself reads runtimes from `roles.json` (Pi rich primary, Cursor Agent secondary).

## Related

- [Agent memory](knowledge-base.md) — the AI KB that Ralph reads from and writes to
- [Review workflow](reviews.md) — the skill reviewer/re-reviewer roles invoke on elastic repos
- [llama.cpp local inference](llama-cpp.md) — opt-in local models for roles
- [The Agentic Operating System](index.md) — governance layer
