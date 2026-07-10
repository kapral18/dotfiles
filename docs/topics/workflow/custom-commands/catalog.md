---
sidebar_position: 2
---

# Command catalog

This is the grouped lookup for commands that are useful but not always front-and-center.

## GitHub / PR helpers

| Command                    | Description                                                                                                            |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `,view-my-issues`          | Browse your GitHub issues with fzf preview                                                                             |
| `,remove-comment`          | Delete a comment from the current PR via fzf picker                                                                    |
| `,gh-subissues-create`     | Draft multiple sub-issues in your editor, create them, and attach to a parent issue via GitHub's sub-issue GraphQL API |
| `,check-backport-progress` | Find PRs missing backports or required labels across target branches                                                   |
| `,disable-auto-merge`      | Disable auto-merge for all open PRs targeting a base branch                                                            |
| `,enable-auto-merge`       | Enable auto-merge for all open PRs targeting a base branch                                                             |
| `,trace-string-pr`         | Locate the PR that introduced a matching string and open it in the browser                                             |
| `,hey-branch`              | Quick "am I in sync with upstream?" status: ahead/behind plus missing remote                                           |
| `,codeowners`              | List matching owners, owned paths, or the last CODEOWNERS owner for a path                                             |

## Search / discovery helpers

| Command              | Description                                                                                |
| -------------------- | ------------------------------------------------------------------------------------------ |
| `,grepo`             | Grep for a pattern across files and open the selected match in `$EDITOR` at the right line |
| `,search-brew-desc`  | Search installed Homebrew formula descriptions as JSON                                     |
| `,fuzzy-brew-search` | Fuzzy search Homebrew descriptions, then drive an "add this to Brewfile" workflow          |
| `,search-gh-topic`   | Search GitHub repos by topic with preview, then open the selected repo                     |
| `,youtube-search`    | Search YouTube from an fzf TUI with filters, preview, browser open, and mpv playback       |

## Testing / analysis helpers

| Command                   | Description                                                          |
| ------------------------- | -------------------------------------------------------------------- |
| `,jest-test-title-report` | Compare Jest test titles between two worktrees and emit a CSV report |
| `,get-risky-tests`        | Run Jest and report tests whose runtime exceeds a threshold          |
| `,get-age-buckets`        | Compute file age buckets from git history to spot stale areas        |
| `,generate-git-sandbox`   | Create a throwaway git repo for testing rebases, merges, and scripts |

## Kibana development helpers

| Command      | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `,kbn-stack` | Spin up an isolated ES + Kibana stack for the current worktree: auto-allocates a slot (unique port, cookie name, encryption key) so many worktrees run in parallel without `/etc/hosts`; before allocating a snapshot slot it reclaims stale slots by probing Kibana/ES ports and cleaning up any surviving half, then chooses the lowest free slot, but keeps a slot reserved while a recorded launcher or stack PID is alive so a bootstrapping stack with no bound ports is not mistaken for dead; `--es snapshot` (default, fully parallel) or `--es serverless` (single-instance: kbn-es runs fixed `es01`/`es02` containers, so serverless pins to slot 0, auto-stops agent-owned serverless stacks first, refuses to auto-stop user-owned serverless stacks from agent mode, and refuses to start over a snapshot stack on the conflicting low ports); keeps `--data`/`-E` flexibility and adds `-K key=value` (repeatable) to start Kibana with extra settings such as a dev/feature flag (`-K xpack.index_management.dev.enableSemanticField=true`) in one shot, recorded in the registry entry's `kbn_flags`. Interactive default runs ES in the current tmux pane and auto-launches Kibana in a second pane once ES is ready (splits the window if only one pane exists, reuses an existing 2-pane layout otherwise). `--detach` is the agent mode: starts ES + Kibana headless in the background, waits until Kibana answers `/api/status`, marks the stack `ready` with `started_by: "agent"` and `start_mode: "agent-detach"` in the registry, then returns. `--stop` tears down the current worktree's registered stack and drops its registry entry: it kills recorded detached/serverless processes when present, and otherwise (interactive tmux stacks with no recorded pids) kills whatever still listens on the slot's Kibana/ES ports, dropping the entry even when nothing is left running; `--stop-all` tears down registered detached/serverless stacks and still leaves pid-less interactive tmux entries in the registry (stop those from their own worktree with `--stop`) |

## AI / agent helpers

| Command                | Description                                                                                                                                                                                                                                                                                                 |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `,agent-memory`        | Inspect `/tmp/specs` hook memory, bind one agent session to a shared topic bucket, or wipe selected topic files                                                                                                                                                                                             |
| `,artifact`            | Create cache-only local HTML artifacts, inject live-page feedback overlays, and manage per-session feedback pollers without writing into the worktree                                                                                                                                                       |
| `,ai-kb`               | Manage the durable local agent knowledge base and harvest candidates from a session-bound topic worklog                                                                                                                                                                                                     |
| `,proof`               | Maintain a repo-external criteria/evidence/review ledger for ordinary freeform agent completion claims                                                                                                                                                                                                      |
| `,ralph`               | Start, resume, inspect, and control Ralph multi-agent orchestration runs                                                                                                                                                                                                                                    |
| `,llama-cpp`           | Serve/manage the local llama.cpp-compatible inference endpoint                                                                                                                                                                                                                                              |
| `,codex`               | Launch Codex with hosted-MCP bearer-token env vars refreshed and local llama.cpp model catalog metadata injected when a local model is selected                                                                                                                                                             |
| `,claude-llama-cpp`    | Launch Claude Code against the local llama.cpp-compatible endpoint                                                                                                                                                                                                                                          |
| `,codex-llama-cpp`     | Launch Codex against the local llama.cpp-compatible endpoint                                                                                                                                                                                                                                                |
| `,opencode-llama-cpp`  | Launch OpenCode against the local llama.cpp-compatible endpoint                                                                                                                                                                                                                                             |
| `,codex-cloudflare`    | Launch Codex directly against Cloudflare AI Gateway's OpenAI Responses endpoint                                                                                                                                                                                                                             |
| `,copilot`             | Launch GitHub Copilot CLI natively, refreshing each header-auth MCP token and re-baking (or first-run generating) `~/.copilot/mcp-config.json` first; refreshes unless a help/version/admin invocation and stops if token refresh or config bake fails                                                      |
| `,copilot-cloudflare`  | Launch GitHub Copilot CLI against Cloudflare's OpenAI-compatible endpoint                                                                                                                                                                                                                                   |
| `,copilot-litellm`     | Launch GitHub Copilot CLI against the LiteLLM gateway's OpenAI-compatible endpoint                                                                                                                                                                                                                          |
| `,copilot-openrouter`  | Launch GitHub Copilot CLI against OpenRouter's OpenAI-compatible endpoint                                                                                                                                                                                                                                   |
| `,cursor`              | Launch cursor-agent natively, refreshing each OAuth MCP token declared in `~/.cursor/mcp.json` via `,mcp-token <server> --login` first (no-op when valid; skipped for admin subcommands); stops if a token refresh fails                                                                                    |
| `,opencode-cloudflare` | Launch OpenCode against the personal Cloudflare Workers AI provider                                                                                                                                                                                                                                         |
| `,pi-cloudflare`       | Launch Pi against the personal Cloudflare Workers AI provider                                                                                                                                                                                                                                               |
| `,mcp-token`           | Print a valid MCP token for `slack`/`scsi-main` from cursor's OAuth cache; `--login` verifies the opaque token's liveness with an MCP `initialize` probe (server URL from `~/.cursor/mcp.json`), adopts a live cached alternative or runs cursor login only when needed, and `--quiet` suppresses auth logs |
| `,letsfg-docker`       | Run LetsFG in a headless Docker/Podman container with Xvfb for browser-based flight connectors                                                                                                                                                                                                              |

Provider wrappers with model choices accept either `--model <id>` / `-m <id>` when the underlying CLI supports it, or a model ID as the first argument. Fish completions list supported model IDs at the bare command prompt and after the model flag. The completion cache is refreshed from OpenRouter's public model API or Cloudflare's authenticated model-search API and falls back to configured defaults when remote lookup is unavailable.

The same wrappers expose `--effort <level>`, `--thinking <level>`, and `--no-thinking` when the harness has an equivalent control. Pi maps to `--thinking`; OpenCode maps effort to `run --variant`; Codex maps to `model_reasoning_effort`; Copilot maps `--thinking` to `--effort`.

Plain interactive `claude` stays native. Plain interactive `codex`, `copilot`, and `cursor-agent` route through the managed `,codex` / `,copilot` / `,cursor` wrappers so hosted MCP tokens are refreshed before launch (the `agent` alias also routes through `,cursor`). Local/provider-specific wrappers (`*,llama-cpp`, `,codex-cloudflare`, `,copilot-cloudflare`, `,copilot-litellm`, `,copilot-openrouter`) select their own upstreams.

## Utility helpers

| Command                | Description                                                                      |
| ---------------------- | -------------------------------------------------------------------------------- |
| `,cp-files-for-llm`    | Copy a directory tree's text contents to the clipboard with file headers         |
| `,appid`               | Print the macOS bundle identifier for an app name/path                           |
| `,dumputi`             | Dump the system's registered Uniform Type Identifiers                            |
| `,to-gif`              | Convert a video to an optimized GIF                                              |
| `,vid-ipad`            | Re-encode a video for iPad playback                                              |
| `,pdf-diff`            | Visual diff two PDFs by compositing pages                                        |
| `,nano-banana`         | Generate a Nano Banana/Gemini raster image from text                             |
| `,set-default-mic`     | Select the preferred external microphone, falling back to the MacBook microphone |
| `,update`              | Reconcile dotfiles and package-manager update categories                         |
| `,parallel`            | Forward to GNU Parallel when both GNU Parallel and semantic-git are installed    |
| `,sem`                 | Forward to Ataraxy semantic-git's entity-level CLI                               |
| `,unwrap-md`           | Unwrap Markdown prose; wrap AI-facing instruction files at sentence boundaries   |
| `,weave-setup-local`   | Configure weave merge driver in repo-local git config and `.git/info/attributes` |
| `,weave-unsetup-local` | Remove the local-only weave merge driver setup                                   |

## Fish history sync: `,history-sync`

- Source: [`home/exact_bin/executable_,history-sync`](../../../../home/exact_bin/executable_,history-sync)
- Merge logic: [`home/exact_lib/exact_,history-sync/fish-history-merge.py`](../../../../home/exact_lib/exact_,history-sync/fish-history-merge.py)
- Stores the synced history in the 1Password document `fish-history-sync`, which doubles as an off-machine backup.
- Merges by command text, keeping the most recent timestamp and writing entries chronologically.

Safety behavior:

- Before replacing local history, it writes `~/.local/share/fish/fish_history.bak`.
- It refuses to install/push a merged result with fewer entries than the remote copy.
- If remote pull fails but the `fish-history-sync` item exists, it aborts instead of overwriting good remote history with local-only history.

If you restore history out-of-band while fish is running, run `history merge` in active fish shells or restart them.

## Internal plumbing

These are used by scripts, fzf integrations, and Neovim; you rarely invoke them directly.

Large command internals live under `~/lib/,<command>/` while the public command stays in `~/bin`. Current library-backed commands are `,add-patch-to-prs`, `,artifact`, `,codex`, `,codeowners`, `,disable-auto-merge`, `,doctor`, `,enable-auto-merge`, `,get-age-buckets`, `,gh-prw`, `,gh-subissues-create`, `,gh-tfork`, `,gh-worktree`, `,hey-branch`, `,history-sync`, `,jest-test-title-report`, `,kbn-pr-audit`, `,kbn-stack`, `,llama-cpp`, `,mcp-token`, `,proof`, `,pull-rebase`, `,tmux-run-all`, `,update`, `,w`, and `,wh`. Cross-command shell helpers live under `~/lib/shared/`.

| Command                  | Description                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------- |
| `,bat-preview`           | Smart preview for fzf: images via chafa, binaries via hexyl, directories via ls, text via bat |
| `,fzf-git-changed-lines` | Emit changed lines as grep-like entries for fzf                                               |
| `,fzf-preview-follow`    | Center fzf preview around a match line                                                        |
| `,fzf-rg-multiline`      | Convert ripgrep output into NUL-delimited multi-line fzf entries                              |

## Verification

```bash
make verify-bin-surface
command -v ,w
command -v ,gh-prw
command -v ,tmux-run-all
```

If commands are missing after apply, verify the script exists under `home/exact_bin/`, has the correct `executable_` prefix, has a matching Fish completion under `home/dot_config/fish/completions/`, and that `~/bin` is on `PATH`.
