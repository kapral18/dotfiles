---
name: ralph
description: Drive the Ralph orchestrator (planner -> executor -> reviewer -> re-reviewer with self-healing) via the chezmoi-managed `,ralph go` CLI and tmux dashboard. Use when the user asks to spawn agents, kick off a run, verify a run, attach to a role, replan, or interact with the tmux Ralph control plane.
---

# Ralph orchestrator

Ralph is the local, durable AI orchestrator built into this dotfiles setup. One entry point — `,ralph go` — runs a `planner -> executor -> reviewer -> re_reviewer` loop with self-healing, persistent state, and full tmux observability. Backend lives at `scripts/ralph.py` (wrapped by `,ralph`); the multi-Ralph dashboard is a Bubble Tea TUI at `tools/ralph-tui/` (deployed to `~/.local/bin/ralph-tui`). State is per-user under `${XDG_STATE_HOME}/ralph/`. Knowledge capsules persist via `,ai-kb`.

## When to use

- the user wants to run an autonomous task with verification (just use `,ralph go`)
- the user wants to spawn or inspect background AI agents inside their current tmux flow
- the user mentions "ralph", "orchestrator", "planner / executor / reviewer / re-reviewer", "manifest", "validation", "control plane", "replan", "resume"
- the user reaches the tmux dashboard (`prefix+A`) or palette entries prefixed `Ralph ...`

## Entry points

- `,ralph go --goal "..." [--workspace PATH] [--foreground|--detach|--subprocess] [--plan-only] [--workflow {auto|feature|bugfix|review|research}] [--<role>-model X --<role>-harness {cursor|pi|command} --<role>-args "STR"]` — create a new run. Planner picks complexity, the loop self-heals (replans on `RALPH_REPLAN`, escalates split-verdicts to a re-reviewer). Per-role overrides (`--planner-model`, `--planner-harness`, `--planner-args`, …, `--re-reviewer-model`, `--re-reviewer-harness`, `--re-reviewer-args`) are applied on top of `~/.config/ralph/roles.json` and re-trigger the diversity gate at parse time. `--<role>-args` accepts a single shell-style string that is `shlex.split` server-side into `extra_args`; an empty string clears any roles.json default, omitting the flag carries the default through unchanged. For `command` harness this IS the command; for `cursor` / `pi` it is appended as flag tail (e.g. `--mode plan`). The `command` harness is a CLI/runtime escape hatch (used by tests via `mock_role.sh` and by power users wiring custom agents like `aider`, `claude`, `gemini`, `,llama-cpp run ...` persistently in `roles.json`). The dashboard's new-run picker intentionally hides it.
  - default in tmux: detaches the runner so your terminal returns immediately; observe via the dashboard or `,ralph runs`
  - `--foreground`: drive the state machine inline; blocks until the run is terminal
  - `--subprocess`: skip tmux entirely (tests/CI); implies foreground
  - `--plan-only`: stop after the planner emits the spec (operator review). Drive the run later with `,ralph runner RUN_ID` or `,ralph resume RUN_ID`.
  - `--workflow`: hint the planner toward a specific workflow shape. `auto` (default) lets the planner pick; `feature`/`bugfix` use the full planner→executor→reviewer→re-reviewer loop; `review` runs reviewer-only; `research` plans + iterates research notes without an executor edit pass. The picker in the TUI's new-run form forwards this same flag.
- `,ralph answer RUN_ID --json -` — post answers to a run parked at `awaiting_human`. Stdin is a JSON object mapping question id (or "all") to the answer text. The orchestrator clears `status=awaiting_human` and resumes the loop. The TUI's `A` modal pipes its answers through this command.
- `,ralph runner RUN_ID` — internal: drive the resumable state-machine loop for a run. Idempotent: if a runner is already alive on the run, raises and exits non-zero
- `,ralph resume RUN_ID [--foreground]` — re-launch the runner if it died (PID-file flock detects liveness). No-op when the run is already terminal or a runner currently holds the lock
- `,ralph replan RUN_ID [--no-resume]` — queue a replan; the running runner consumes it at the next loop tick. Auto-resumes the runner unless `--no-resume`
- `,ralph supervisor [--loop] [--interval N] [--json]` — resume dead non-terminal runners that are safe to automate. Skips runs parked for manual control. **Scheduling**: there is no built-in scheduler. Pick one of:
  - tmux pane: `,ralph supervisor --loop --interval 60` (in a dedicated background pane / detached session — survives until tmux dies). Quickest setup; what the palette's `Ralph supervisor` entry runs (one-shot).
  - `launchd` user agent: drop a `~/Library/LaunchAgents/dev.kapral18.ralph-supervisor.plist` with a `StartInterval` of 60 (or `KeepAlive` + the `--loop` form). Survives reboots.
  - cron (`*/1 * * * * ,ralph supervisor`): one-shot every minute. Cheapest, but loses the `--loop`'s shared kb / process cache between ticks.
  - The supervisor only resumes runs whose runner has died (PID flock released) and that aren't parked for manual control, so re-running it is always safe.
- `,ralph runs [--json] [--limit N] [--workspace PATH] [--session NAME]` — list runs
- `,ralph role RUN_ID ROLE [--json]` — inspect one role pane / output / manifest
- `,ralph preview RUN_ID [ROLE] [--mode summary|tail]` — formatted summary or tail
- `,ralph attach RUN_ID [--role ROLE]` — switch tmux client to the run/role pane
- `,ralph tail RUN_ID [--role ROLE] [--lines N]` — capture pane output or output.log
- `,ralph verify RUN_ID [--json]` — re-run validation chain (artifact + role status)
- `,ralph control RUN_ID --role ROLE --action takeover|dirty|resume|auto` — change role state
- `,ralph kill RUN_ID [--role ROLE]` — Ctrl-C the pane(s) and mark killed
- `,ralph kill --all` — bulk-kill every non-terminal run (mutually exclusive with `RUN_ID` / `--role`); useful when a runaway swarm needs the panic button
- `,ralph rm RUN_ID|--all-completed [--keep-learnings]` — archive a run and drop ai-kb capsules. The cached `latest-run.txt` pointer self-heals (next argless command picks the newest live manifest) so `,ralph rm` doesn't strand the dashboard.
- `,ralph dashboard` — thin alias for `prefix+A`: `exec`s `~/.local/bin/ralph-tui` directly. Falls back to a clear "ralph-tui not installed" error rather than printing a one-shot text snapshot. For a text view of one run use `,ralph preview RID`.
- `,ralph statusline` — tmux status segment (running / needs verification counts) with a trailing dim `(^A)` hint pointing at the dashboard binding
- `,ralph doctor` — env, ai-kb, runtimes health check

## Roles + diversity gate

Roles are defined in `~/.config/ralph/roles.json`. Defaults are cursor-first because cursor's frontier models give the best output/judgement quality; pi remains fully supported and is required for non-cursor providers (anthropic direct, openai direct, openrouter, llama-cpp).

- `planner` — emits a JSON spec (goal, target_artifact ABS, success_criteria, complexity, executor_count, max_iterations, max_minutes, iteration_task_seed). Defaults to `cursor + claude-opus-4-7-thinking-max --mode plan` (read-only planning; cannot edit). On pi, equivalent is `--no-tools`.
- `executor` — does one concrete step toward the spec, ends output with a `LEARNING:` line and `RALPH_DONE`. May emit `RALPH_REPLAN` to force a replan. Defaults to `cursor + composer-2 --force` (cursor's purpose-built agentic coder, auto-approves commands). Needs full tools either way.
- `reviewer` — judges the executor's last step against the spec, emits a JSON verdict (`pass|needs_iteration|fail|block`) followed by `RALPH_DONE`. Defaults to `cursor + claude-opus-4-7-thinking-max --mode ask` (read-only Q&A with shell read access for verification probes like `od -c` / `wc -c`). On pi, equivalent is `--no-tools`.
- `re_reviewer` — **mandatory** second-opinion gate; runs after every reviewer pass, in sequence. Emits its own `final_verdict` which the orchestrator uses (overrides the reviewer's). Defaults to `cursor + gpt-5.5-extra-high --mode ask`. **Must be a different model family** from the reviewer; orchestrator enforces `family_of(re_reviewer.model) != family_of(reviewer.model)` (substring match on `claude|gpt|gemini|llama|mistral|deepseek`) and aborts on config load otherwise.
- `reflector` — optional post-run distiller. After a passing run, emits a JSON list (0-5) of structured KB capsules (`title`, `body`, `kind`, `scope`, `domain_tags`, `confidence`, `refs`). Runs on the `feature` and `bugfix` workflows by default (`defaults.reflector_workflows` in `roles.json`); skipped when the run failed or `defaults.reflector_enabled=false`. Output is best-effort: invalid capsules are dropped, and reflector failures never block the overall run from being recorded as passed.

Prompt templates live at `~/.config/ralph/prompts/{planner,executor,reviewer,re_reviewer,reflector}.md`.

## Knowledge base wiring

Each role's prompt builder retrieves the top-K capsules from `,ai-kb` filtered by role-appropriate `kind` and injects them into a `## RECENT LEARNINGS` block. Filters: planner — no filter (broadest slice with workspace bias); executor — `fact / recipe / gotcha / anti_pattern / pattern`; reviewer — `gotcha / anti_pattern`; re_reviewer — `gotcha / anti_pattern / principle`. A compressed copy is persisted to `manifest.json::roles[*].retrieval_log` for TUI replay. Roles can also call `,ai-kb search` directly from inside their pane (the `Tool: on-demand KB search` block is in every prompt). `LEARNING:` lines emitted by roles are captured by `RalphRunner.capture_learnings` with `kind` inferred from the role and `scope=project` when a workspace is set.

Hybrid retrieval is BM25 + sqlite-vec (cosine) fused with RRF and diversified with MMR. The vector lane and curation pairs run inside `scripts/vec_runner.py` — a `uv run --script` subprocess with `sqlite-vec` declared via PEP 723 — so the orchestrator process stays stdlib-only. `RALPH_KB_DISABLE_VEC=1` is the test/offline escape hatch. See [`docs/categories/ai-and-assistants.md`](../../../../../docs/categories/ai-and-assistants.md) — section "AI knowledge base (`,ai-kb`)" — for capsule schema, hybrid retrieval semantics, and `,ai-kb` CLI usage.

## Elastic-gated `/review` skill

For workspaces whose `git remote -v` includes an `elastic/<repo>` URL, the reviewer and re-reviewer roles invoke the operator's [`review` skill](../exact_review) as the primary instruction (`shared_rules.md` + `local_changes.md` rendered into a `## REVIEW SKILL HEURISTICS (elastic)` preamble before `## SPEC`). The role's existing JSON output contract is preserved as the wire format — the skill drives _how_ to verify, the JSON dictates _what_ to emit. Detection lives in `is_elastic_workspace()` in `scripts/ralph.py`; non-elastic workspaces are unchanged. Override via `RALPH_REVIEW_SKILL_DIR=<path>`; degrades silently to the default review path when the skill files are missing.

Local models (llama-cpp/qwen) are opt-in only; defaults never depend on `,llama-cpp serve` being up. Swap them in by editing `roles.json`.

## Manifest invariants

- per-`go`-run: `id`, `kind="go"`, `phase` (`planning|executing|reviewing|rereviewing|replanning|done|failed|blocked`), `status`, `validation_status`, `iterations[]` (each with `n`, `phase` (`pending|exec|review|rereview|decided`), `executor_id`, `reviewer_id`, `re_reviewer_id`, `verdict`, `task`, `next_task`, `spec_seq`), `roles{}`, `spec`, `spec_seq`, `learned_ids`, `runner` (pid+host+started_at+heartbeat_at+alive)
- per-role-child: `kind="role"`, role name (`planner-N|executor-N|reviewer-N|re_reviewer-N`), `pane`, `output_log`, `control_state`
- iteration records are appended at iteration START (phase=pending) and updated as phases progress; the runner is fully resumable from the manifest alone
- a runner parks with `status=needs_human` when any role is `manual_control`, `dirty_control`, or `resume_requested`; it resumes only after role validation clears those states
- `spec.target_artifact` is promoted to top-level `manifest.artifact`; a passing run freezes `artifact_sha256` and validation requires the artifact hash to match
- `executor_count` must be exactly `1` until Ralph implements real parallel executor orchestration; higher values fail fast instead of being silently ignored
- runner liveness is the exclusive flock on `<run_dir>/runner.pid`; never edit `runner.*` fields by hand
- never edit manifests by hand; mutate via `control`, `verify`, `kill`, `rm`, `replan`, `resume`

## Multi-Ralph dashboard (`prefix + A`)

The dashboard is a Bubble Tea TUI binary built from `tools/ralph-tui/` and installed at `~/.local/bin/ralph-tui`. It reads run state via fsnotify so updates are live; mutations always shell out to `,ralph`. Default layout: runs list (left), run detail + roles table (top right), live tail of the selected role's output (bottom right). Optional layouts: 2x2 role grid for the selected run, or fullscreen zoom of the focused pane. An optional cross-run activity drawer aggregates recent decisions and verdicts.

Fleet view (left pane):

- Each row carries: a heartbeat dot (bright violet `●` = alive + fresh, amber `●` = alive + stale heartbeat, red `●` = explicitly dead, `R` = replan queued, blank = never started), name, status badge, phase, `n/N` iteration count vs the planner's `max_iterations`, and an iteration sparkline colored by verdict (green=pass, red=fail, amber=replan, blue=in-flight, dim=pending). A `Q:N` badge appears when a run has open clarifying questions.
- `s` cycles the sort mode: `need` (default — parked-on-questions and live work first) and `recent` (newest first by `created_at`). The current mode renders in the runs pane header.
- `/` filters runs by id/name/goal/status/validation; `esc` clears the filter. While typing in the filter, single-letter global shortcuts (`q`, `n`, `a`, `c`, `S`, ...) are shadowed and flow into the filter buffer instead — type `enter` to commit the filter and re-arm the global keys.

Layouts:

- `1` detail (default 3-pane), `2` role grid (2x2 of the latest iteration's role tails for the selected run), `3` zoom (focused pane fills the screen). The status bar shows the active layout name.
- In grid layout (`2`), `h/j/k/l` (or arrows) move the cell cursor between the four role tiles; `enter` drills the cursored cell into the detail layout focused on that role's tail. Switching the run selection resets the cell cursor to the top-left tile.

New-run form:

- `n` opens the new-run form. Fields: goal, workspace, plan-only, **workflow** (picker: `auto` / `feature` / `bugfix` / `review` / `research`), plus per-role harness AND model pickers for planner / executor / reviewer / re_reviewer. Pickers cycle with `h`/`l` or `←`/`→`; `j`/`k` (or `↓`/`↑`, or `tab`/`shift+tab`) move down/up between fields (gated so they still type literal characters into goal / workspace text inputs). `enter` advances harness → matching model → next role. Harness picker cycles `cursor → pi` (the `command` harness is a CLI/runtime escape hatch — see `,ralph go` flag docs above — and is intentionally hidden from the dashboard); the model list is curated per harness in `tools/ralph-tui/internal/state/models.go`. `auto` workflow lets the planner pick; selecting any other workflow forwards `--workflow <name>` to `,ralph go`. Per-role `extra_args` (e.g. `--mode plan`, `--force`) live in `~/.config/ralph/roles.json` because they are persistent configuration; per-run overrides go through `,ralph go --<role>-args` at the CLI.
- Pre-filled with the user's `roles.json` defaults. Submit fires `,ralph go --workflow ...` with the matching `--<role>-{model,harness}` flags.

Awaiting-human + answer flow:

- A run parks at `awaiting_human` when the planner (or any role) emits clarifying questions. The detail pane shows a prominent banner, the runs list adds a `Q:N` badge, and the status bar aggregates `Q:Σ` across the fleet.
- `A` (capital) opens the answer modal: one text input per open question, `tab`/`j`/`k`/`shift+tab` move focus, `enter` advances or submits, `esc`/`ctrl+c` cancel (`q` cancels only when focus is not on a text input). Submission posts answers via `,ralph answer <rid> --json -` so the orchestrator can resume.

Pane preview:

- `p` opens a tmux capture-pane preview of the focused role's pane (read-only, refreshes on a 1s tick and on `r`). Inside the modal, capital `A` launches `tmux display-popup -E -- tmux attach-session -r -t TARGET` so you can read the live pane in a tmux popup without leaving the TUI. `esc`/`q`/`ctrl+c` close the modal.

KB browser:

- `K` (capital) opens an AI KB search modal. Type a query and `enter` to fire a hybrid (lexical + dense, RRF + MMR) search; results are filtered to non-superseded capsules. `↑/↓` move the cursor; the right pane shows kind/scope/confidence/refs of the highlighted hit. `esc`/`q` close. The status bar shows `KB:N` for the total non-superseded capsule count, refreshed every ~30s so reflector-emitted capsules show up mid-session.

Activity drawer:

- `S` (capital) cycles the activity drawer above the status bar through three sizes: `off` → `small` (5 inner rows) → `large` (12 inner rows) → `off`. Each press emits a status toast naming the new size. The drawer aggregates recent `decisions.log` and `verdicts.jsonl` events across every parent (`kind=go`) run, sorted most recent first; `(no recent decisions or verdicts)` placeholder when empty.

Other navigation / actions:

- `j/k` (or arrows) move within the focused pane; `tab` cycles `runs -> roles -> tail`; `enter` zooms the focused pane to fullscreen (same as `3`, esc to return).
- `enter` (run row) attaches via `tmux switch-client` to `ralph-<short-rid>`; `enter` (role row) attaches to that role's window. (Use `p` instead when you only need a peek.)
- `c` opens the control menu (verify, takeover, dirty, kill, rm, replan, resume). Direct shortcuts: `v` verify, `r` manual refresh of runs, `R` resume runner, `P` replan, `x` kill, `X` rm. Destructive actions open a confirmation modal first.
- `?` toggles help overlay; `q` quits.

## Multi-Ralph isolation contract

- Each `,ralph go` invocation owns a dedicated tmux session named `ralph-<short-rid>`. Multiple runs coexist without polluting the user's main tmux session.
- `kill <rid>` and `rm <rid>` only touch their own dedicated session; the dashboard, palette, and other runs are unaffected.
- Concurrent runs in the same `$RALPH_STATE_HOME` are fully isolated by run id; covered by `scripts/tests/test_scripts.py::TestRalphMultiRunIsolation`.

## GH picker handoff

Inside `prefix+G` GitHub picker, `alt-A` on a PR/issue row stages a Ralph handoff: closes the picker, resolves the matching worktree (or `$PWD` fallback), and prompts for a `,ralph go` goal seeded with `<kind> <repo>#<num>: <title>`.

## Session picker badge

Sessions matching a Ralph `go` run get a colored `ralph<status>` badge in `prefix+T` (`ralph✓` passed, `ralph?` needs verification, `ralph✗` failed, `ralph●` running, `ralph⨯` killed). The session preview also surfaces the matching `,ralph runs --session NAME`.

## Status bar

`,ralph statusline` is appended to `status-right` (idempotently, after TPM/Catppuccin). Output: `R:<running> V:<needs_verification>` or `✓<n>` when only completed runs exist, with a trailing dim `(^A)` hint pointing at the dashboard popup binding; empty when nothing demands attention.

## Verification contract

A `go` run is `passed` only when:

- the orchestrator loop exits with `status=completed`,
- the final iteration verdict is `pass` (or `pass` upheld by the re-reviewer),
- every role child has `control_state=automated`,
- every role child passed validation,
- the artifact gate passes when `target_artifact` is declared.

Any `manual_control`, `dirty_control`, or `resume_requested` flips overall validation to `needs_verification`. `resume` auto-verifies. The orchestrator drives validation for `kind=go`; per-role `--expect` no longer applies.

`validation_status=passed_with_warnings` is the third success value: the iteration verdict reached `pass`, the artifact gate is intact, but at least one role's scaffolding gate (typically the `ANCHOR:` re-anchoring line) failed. The run still ships (`status=completed`, exit 0, reflector still distills) and the failing roles are listed in `manifest.validation.warnings` and a `## Warnings` section of `summary.md`. The status bar counts these toward `passed`. Treat the warnings as a quality smell to chase down (usually a model wrapping the anchor in markdown), not a blocker.

The `ANCHOR:` check tolerates leading markdown decorators (`**ANCHOR:**`, `*ANCHOR:*`, `` `ANCHOR:` ``, `# ANCHOR:`, `> ANCHOR:`) so models that default to markdown formatting don't trip the gate on cosmetics.

## Don't

- don't add `--runtime local` to `,ralph go` — the orchestrator picks runtimes from `roles.json`. `local` runtime still exists for `,ralph dry-run` smoke tests.
- don't write directly into `~/.local/state/ralph/runs/...`; mutate via the CLI
- don't commit anything under `~/.local/state/ralph/` or `~/.local/share/ai-kb/`
- don't put the same model family on both `reviewer` and `re_reviewer` in `roles.json` — the diversity gate rejects it
