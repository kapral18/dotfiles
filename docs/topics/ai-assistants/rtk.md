---
sidebar_position: 11
---

# RTK token optimization

[RTK](https://github.com/rtk-ai/rtk) is a CLI proxy that compacts noisy command output from test runners, linters, builds, `git status`, `git log`, and similar commands. It can cut 60-90% of tokens from outputs that would otherwise dominate an agent context window.

Installed package:

- `brew "rtk"` in [`brews/shared/38-ai-large-language-models.brewfile`](../../../home/.chezmoitemplates/brews/shared/38-ai-large-language-models.brewfile)

## Agent wiring

Each agent's pre-execution shell hook calls the native `rtk hook <agent>` binary. RTK rewrites commands such as `git status` to `rtk git status` before execution, then filters the output.

| Agent    | Source                                                                                        | Mechanism                                                                      |
| -------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Cursor   | [`home/dot_cursor/hooks.json`](../../../home/dot_cursor/hooks.json)                           | `preToolUse` entry `rtk hook cursor` (`matcher: "Shell"`)                      |
| Claude   | [`home/dot_claude/settings.{work,personal}.json`](../../../home/dot_claude/)                  | `PreToolUse` block `rtk hook claude` (`matcher: "Bash"`)                       |
| Gemini   | [`home/dot_gemini/settings.json`](../../../home/dot_gemini/settings.json)                     | `BeforeTool` `run_shell_command`, `gemini-git-gate.sh`, then `rtk hook gemini` |
| OpenCode | [`home/dot_config/opencode/plugins/rtk.ts`](../../../home/dot_config/opencode/plugins/rtk.ts) | `tool.execute.before` plugin calling `rtk rewrite`                             |
| Pi       | [`home/dot_pi/agent/extensions/rtk.ts`](../../../home/dot_pi/agent/extensions/rtk.ts)         | `tool_call` extension calling `rtk rewrite`                                    |
| Copilot  | not wired                                                                                     | fail-closed `PreToolUse` hooks must not depend on RTK                          |

Cursor and Gemini keep the git commit/push gate in front of RTK. RTK does not hide mutating git commands from those gates: `git commit` / `git push` become `rtk git commit` / `rtk git push`, and the gates still match the `git ... commit|push` substring.

Copilot is intentionally not wired to RTK. Its `PreToolUse` hooks are fail-closed, and a failed output-compaction hook can block every bash call. Copilot git protection is instruction-owned instead.

## Config

Source and target:

```text
home/Library/Application Support/rtk/config.toml
~/Library/Application Support/rtk/config.toml
```

RTK reads `dirs::config_dir()/rtk/config.toml`; on macOS that is `~/Library/Application Support`, not XDG.

## Filter classification

Every filter was audited into one of three classes:

| Class             | Meaning                                                                | Default handling |
| ----------------- | ---------------------------------------------------------------------- | ---------------- |
| SAFE              | Strips only boilerplate; no semantic loss                              | rewrite          |
| LOSSY-RECOVERABLE | Drops content but signals it with `+N more` or `[full output: <path>]` | rewrite + tee    |
| LOSSY-SILENT      | Drops semantically relevant content without count/recovery path        | exclude          |

The config encodes that audit:

```toml
[hooks]
exclude_commands = ["gh pr view", "gh pr checks", "git diff", "git show", "git log", "find", "grep", "rg"]

[tee]
enabled = true
mode = "always"

[telemetry]
enabled = false
```

## Exclusions

| Command class                | Why excluded                                                                                |
| ---------------------------- | ------------------------------------------------------------------------------------------- |
| `gh pr view`, `gh pr checks` | Audited LOSSY-SILENT: field-subsets JSON with no overflow count                             |
| `git diff`, `git show`       | Recoverable in RTK, but truncated diffs are never useful for review or judgment             |
| `git log`                    | Audited LOSSY-SILENT: bare log silently capped at 50 commits unless explicit `-N` is passed |
| `find`                       | RTK models only `-name` / `-type` and silently drops important predicates                   |
| `grep`, `rg`                 | Rewritten semantics collide with normal `-l` / recursive search expectations                |

`gh ... --json/--jq/--template` and `gh api` already pass through raw. `git status` compacts recoverably and stays rewritten. `terraform plan` / `tofu plan` are not auto-rewritten by RTK TOML filters, so excluding them would be a no-op.

Audit notes from the live RTK 0.42.1 probes:

| Surface                 | Detail                                                                                                                    |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `git diff` exclusion    | Pattern matches `git diff --staged` / `git diff HEAD~1`, but not `git diff-tree` / `git difftool`                         |
| `git log` exclusion     | Bare `git log` / `git log --oneline` capped at 50 commits with no overflow marker; explicit `git log -N` overrides        |
| `find` exclusion        | RTK modeled only `-name` / `-type` and dropped `-mindepth`, `-maxdepth`, `-print`, `-quit`, `-prune`, and `-path`         |
| `grep` / `rg` exclusion | `-l` collided with RTK `--max-len`; `--files-with-matches .` fell back to non-recursive grep and errored `Is a directory` |
| Savings check           | `rtk gain` showed no measured token savings from `find`, `grep`, or `rg`; native Grep/Glob tools bypass RTK anyway        |

## Recovery contract

The SOP entrypoints instruct every agent to treat compacted output as an index, not the full truth.

When output shows any of these, fetch the full output before relying on it:

- `[full output: <path>]`
- `[see remaining: tail -n +N <path>]`
- `… +N more`

Recovery is mandatory for diff/PR review, debugging a failure, or enumerating issues. Bypass options:

```bash
RTK_DISABLED=1 <cmd>
RTK_NO_TOML=1 <cmd>
<tool> --no-compact
<tool> --json
```
