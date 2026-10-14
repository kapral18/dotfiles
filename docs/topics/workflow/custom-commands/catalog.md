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

## AI / agent helpers

| Command               | Description                                                                                                                                                                                                                                                                                                                                                                              |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `,artifact`           | Create cache-only local HTML artifacts and live-page feedback overlays with hidden-by-default feedback capture (click pins one anchor, Cmd-click pins multiple targets for a single prompt); tagged artifacts can return generic semantic entity IDs, ancestors, and relations from `data-artifact-id` plus an embedded manifest; per-session feedback pollers stay outside the worktree |
| `,q`                  | One-shot OpenRouter Pi agent (`deepseek/deepseek-v4.1-flash`) at high effort with native full context, tools on, a short system prompt, and skills/context/extensions/APPEND_SYSTEM off                                                                                                                                                                                                  |
| `,ai-kb`              | Search and write the local agent knowledge base (`~/lib/,ai-kb/`): hybrid BM25 + vector search, `remember` with duplicate refusal, `curate` for dedupe and decay; on demand only                                                                                                                                                                                                         |
| `,behavior-map`       | Keep a per-repo map of critical behaviors under `~/.local/share/k-ai-behavior-map/<repo>/`: a base map shared by all worktrees plus per-branch overlays, with stale/drift checks, changed-since-read write refusal, and three-way promote after merge                                                                                                                                    |
| `,handoff`            | Save, show, and list short task-handoff notes under `~/.local/share/agent-handoffs/<repo>/` so a task can continue in another session or harness                                                                                                                                                                                                                                         |
| `,task`               | Keep each session's intent card per worktree (goal, reading, `Done when` items, scope) under `~/.local/share/agent-tasks/`; the intent-guard hooks in every harness call `,task hook` to show it, flag edits outside its scope, and send a stop back while an item is open                                                                                                               |
| `,doctor ai`          | Report the ownership-aware effective state of generated AI configs; `--json` is scriptable and `--live` adds deduplicated local consumer probes without applying or refreshing anything                                                                                                                                                                                                  |
| `,llama-cpp`          | Manage the local llama.cpp endpoint, including shared leases that auto-start a loopback router, configurable last-consumer grace, and an ownership-safe explicit stop that treats zombie owners as already stopped                                                                                                                                                                       |
| `,codex`              | Launch Codex with local llama.cpp model catalog metadata injected when a local model is selected                                                                                                                                                                                                                                                                                         |
| `,claude-llama-cpp`   | Launch Claude Code with a shared auto-managed llama.cpp router lease                                                                                                                                                                                                                                                                                                                     |
| `,claude-openrouter`  | Launch Claude Code against OpenRouter's Anthropic Messages endpoint, defaulting to `xiaomi/mimo-v2.6-pro` at `high` effort; every Claude alias maps to the selected wire id                                                                                                                                                                                                              |
| `,codex-llama-cpp`    | Launch Codex with a shared auto-managed llama.cpp router lease                                                                                                                                                                                                                                                                                                                           |
| `,codex-openrouter`   | Launch Codex against OpenRouter's OpenAI Responses endpoint, defaulting to `xiaomi/mimo-v2.6-pro` at `high` effort                                                                                                                                                                                                                                                                       |
| `,opencode-llama-cpp` | Launch OpenCode with a shared auto-managed llama.cpp router lease; context/output limits come from `opencode.jsonc`                                                                                                                                                                                                                                                                      |
| `,letsfg-docker`      | Run LetsFG in a headless Docker/Podman container with Xvfb for browser-based flight connectors                                                                                                                                                                                                                                                                                           |

Provider wrappers with model choices accept `--model <id>` / `-m <id>`. The OpenRouter wrappers also take `--effort <level>` (aliases `--reasoning-effort`, `--thinking`; `--no-thinking` = `minimal`) and `--context short|long`; see [Other harnesses](../../ai-assistants/tool-configs/other-harnesses.md#provider-wrappers).

Plain interactive `claude` stays native. Plain interactive `codex` routes through the managed `,codex` wrapper. Local/provider-specific wrappers (`*,llama-cpp`, `,codex-openrouter`, `,claude-openrouter`) select their own upstreams.

### One-shot pi agent: `,q`

```bash
,q "What is 2+2?"
,q --dry-run "ping"
printf '%s' "$prompt" | ,q
```

`~/bin/,q` is a thin launcher for `~/lib/,q/main.py`. It execs `pi` against OpenRouter `deepseek/deepseek-v4.1-flash` with `--thinking high` and no context-limiting extension, so Pi uses the model's native full context. It also passes `--no-session`, `--offline`, a short `--system-prompt`, empty `--append-system-prompt` (skips `~/.pi/agent/APPEND_SYSTEM.md`), and the `--no-skills` / `--no-themes` / `--no-context-files` / `--no-prompt-templates` / `--no-extensions` discovery flags. Tools stay enabled. The short prompt replaces Pi's coding-assistant default; Pi still appends the cwd. AGENTS.md, skills, and extensions stay off. Prompt words are the user message; with no words, stdin is the prompt. The explicitly loaded `q_literal.md` template passes one quoted argument through as literal text, preserving leading flags, `@`, quotes, and whitespace; default template discovery remains off. `--dry-run` emits the pi argv JSON.

## Utility helpers

| Command             | Description                                                                             |
| ------------------- | --------------------------------------------------------------------------------------- |
| `,cp-files-for-llm` | Copy a directory tree's text contents to the clipboard with file headers                |
| `,appid`            | Print the macOS bundle identifier for an app name/path                                  |
| `,dumputi`          | Dump the system's registered Uniform Type Identifiers                                   |
| `,to-gif`           | Convert a video to an optimized GIF                                                     |
| `,vid-ipad`         | Re-encode a video for iPad playback                                                     |
| `,pdf-diff`         | Visual diff two PDFs by compositing pages                                               |
| `,nano-banana`      | Cloud Gemini generate/edit/compose/inpaint (uploads to Google)                          |
| `,image-local`      | On-device FLUX.2 klein 9B generate (512 default) and `-i` edit at input size            |
| `,image-openrouter` | OpenRouter generate/edit; Seedream 5 Pro; strips input metadata; ZDR routing            |
| `,image-codex`      | Codex subscription GPT Image 2 generate/edit; automatic settings; strips inputs         |
| `,image-openai`     | Native GPT Image 2 generate/edit/mask with quality, size, and format controls           |
| `,set-default-mic`  | Select the preferred external microphone, falling back to the MacBook microphone        |
| `,update`           | Reconcile dotfiles and package-manager updates with a native dekit TUI                  |
| `,parallel`         | Forward to GNU Parallel when both GNU Parallel and semantic-git are installed           |
| `,sem`              | Forward to Ataraxy semantic-git's entity-level CLI (telemetry, update check, cloud off) |
| `,format-md`        | Wrap AI prose around complete inline code; leave ordinary Markdown unchanged            |

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
