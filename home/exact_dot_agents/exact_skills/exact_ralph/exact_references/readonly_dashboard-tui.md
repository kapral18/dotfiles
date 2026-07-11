# Ralph Multi-Ralph Dashboard (`prefix + A`)

Reference for the `ralph` skill. Load when steering, inspecting, or driving the Bubble Tea TUI dashboard rather than the CLI directly.

The dashboard is a Bubble Tea TUI binary built from `tools/ralph-tui/` and installed at `~/.local/bin/ralph-tui`.
It reads run state via fsnotify so updates are live; mutations always shell out to `,ralph`.
Default layout: runs list (left), run detail + roles table (top right), live tail of the selected role's output (bottom right).
Optional layouts: 2x2 role grid for the selected run, or fullscreen zoom of the focused pane.
An optional cross-run activity drawer aggregates recent decisions and verdicts.

## Fleet view (left pane)

- Each row carries: a heartbeat dot (bright violet `●` = alive + fresh, amber `●` = alive + stale heartbeat, red `●` = explicitly dead, `R` = replan queued, blank = never started), name, status badge, phase, `n/N` iteration count vs the planner's `max_iterations`, and an iteration sparkline colored by verdict (green=pass, red=fail, amber=replan, blue=in-flight, dim=pending).
  A `Q:N` badge appears when a run has open clarifying questions.
- `s` cycles the sort mode: `need` (default — parked-on-questions and live work first) and `recent` (newest first by `created_at`).
  The current mode renders in the runs pane header.
- `/` filters runs by id/name/goal/status/validation; `esc` clears the filter.
  While typing in the filter, single-letter global shortcuts (`q`, `n`, `a`, `c`, `S`, ...) are shadowed and flow into the filter buffer instead — type `enter` to commit the filter and re-arm the global keys.

## Layouts

- `1` detail (default 3-pane), `2` role grid (2x2 of the latest iteration's role tails for the selected run), `3` zoom (focused pane fills the screen).
  The status bar shows the active layout name.
- In grid layout (`2`), `h/j/k/l` (or arrows) move the cell cursor between the four role tiles;
  `enter` drills the cursored cell into the detail layout focused on that role's tail.
  Switching the run selection resets the cell cursor to the top-left tile.

## New-run form

- `n` opens the new-run form.
  Fields: goal, workspace, plan-only, **workflow** (picker: `auto` / `feature` / `bugfix` / `review` / `research`), plus per-role harness AND model pickers for planner / executor / reviewer / re_reviewer.
  Pickers cycle with `h`/`l` or `←`/`→`; `j`/`k` (or `↓`/`↑`, or `tab`/`shift+tab`) move down/up between fields (gated so they still type literal characters into goal / workspace text inputs).
  `enter` advances harness → matching model → next role.
  Harness picker cycles `cursor → pi` (the `command` harness is a CLI/runtime escape hatch — see `,ralph go` flag docs in the core skill —
  and is intentionally hidden from the dashboard); the picker consumes each harness's generated `recommended` set from the v1 model mirror.
  `auto` workflow lets the planner pick; selecting any other workflow forwards `--workflow <name>` to `,ralph go`.
  Per-role `extra_args` (e.g. `--mode plan`, `--force`) live in `~/.config/ralph/roles.json` because they are persistent configuration;
  per-run overrides go through `,ralph go --<role>-args` at the CLI.
- Pre-filled with the user's `roles.json` defaults.
  Submit fires `,ralph go --workflow ...` with the matching `--<role>-{model,harness}` flags.

## Awaiting-human + answer flow

- A run parks at `awaiting_human` when the planner (or any role) emits clarifying questions.
  The detail pane shows a prominent banner, the runs list adds a `Q:N` badge, and the status bar aggregates `Q:Σ` across the fleet.
- `A` (capital) opens the answer modal: one text input per open question, `tab`/`j`/`k`/`shift+tab` move focus, `enter` advances or submits, `esc`/`ctrl+c` cancel (`q` cancels only when focus is not on a text input).
  Submission posts answers via `,ralph answer <rid> --json -` so the orchestrator can resume.

## Pane preview

- `p` opens a tmux capture-pane preview of the focused role's pane (read-only, refreshes on a 1s tick and on `r`).
  Inside the modal, capital `A` launches `tmux display-popup -E -- tmux attach-session -r -t TARGET` so you can read the live pane in a tmux popup without leaving the TUI.
  `esc`/`q`/`ctrl+c` close the modal.

## KB browser

- `K` (capital) opens an AI KB search modal.
  Type a query and `enter` to fire a hybrid (lexical + dense, RRF + MMR) search; results are filtered to non-superseded capsules.
  `↑/↓` move the cursor; the right pane shows kind/scope/confidence/refs of the highlighted hit. `esc`/`q` close.
  The status bar shows `KB:N` for the total non-superseded capsule count, refreshed every ~30s so reflector-emitted capsules show up mid-session.

## Activity drawer

- `S` (capital) cycles the activity drawer above the status bar through three sizes:
  `off` → `small` (5 inner rows) → `large` (12 inner rows) → `off`. Each press emits a status toast naming the new size.
  The drawer aggregates recent `decisions.log` and `verdicts.jsonl` events across every parent (`kind=go`) run, sorted most recent first;
  `(no recent decisions or verdicts)` placeholder when empty.

## Other navigation / actions

- `j/k` (or arrows) move within the focused pane; `tab` cycles `runs -> roles -> tail`;
  `enter` zooms the focused pane to fullscreen (same as `3`, esc to return).
- `enter` (run row) attaches via `tmux switch-client` to `ralph-<short-rid>`; `enter` (role row) attaches to that role's window.
  (Use `p` instead when you only need a peek.)
- `c` opens the control menu (verify, takeover, dirty, kill, rm, replan, resume).
  Direct shortcuts: `v` verify, `r` manual refresh of runs, `R` resume runner, `P` replan, `x` kill, `X` rm.
  Destructive actions open a confirmation modal first.
- `?` toggles help overlay; `q` quits.
