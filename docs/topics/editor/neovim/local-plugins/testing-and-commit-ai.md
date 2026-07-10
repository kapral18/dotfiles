---
sidebar_position: 1
title: Testing and commit AI
---

# Testing and commit AI

## Testing: Jest In A Split (Local Plugin)

This is one of the most valuable "hidden" workflows.

- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_run-jest-in-split.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_run-jest-in-split.lua)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_run-jest-in-split.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_run-jest-in-split.lua)

Keymaps:

- `leader-tt` run nearest test
- `leader-tT` run entire file
- `leader-td` debug nearest test
- `leader-tD` debug entire file
- `leader-tu` update snapshots (nearest)
- `leader-tU` update snapshots (file)
- `leader-tq` close the test terminal

Close semantics: `q` in normal mode closes a terminal buffer only inside the Jest split created by this plugin (`util.terminal.run_in_split` sets that mapping locally on its own terminal buffer). Opening any other terminal (`:terminal`, a different plugin's terminal, etc.) never gets `q` rebound — there is no global `TermOpen` mapping, so unrelated terminal jobs are never closed as a side effect.

## Git: Commit Message Summarizer (Local Plugin)

In a `gitcommit` buffer, generate a Conventional Commit message from the staged diff (`git diff --cached`).

- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_summarize-commit.lua.tmpl`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_summarize-commit.lua.tmpl)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_summarize-commit.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_summarize-commit.lua)

Keymaps:

- `leader-aisc` summarize via Cloudflare Workers AI
- `leader-aiso` summarize via OpenRouter

Output format notes:

- Header: `type(scope?): summary`
- Type selection: prefer behavior/functionality, then bug fixes, then chores/maintenance; use `docs` only for docs-only diffs.
- Runtime guard: if a provider still returns `docs(...)` for a staged diff that includes non-doc paths, the plugin rewrites the header to a non-doc fallback type.
- Bullet points: one bullet per changed functionality (or per distinct logical change)

Environment variables:

| Provider   | Required                                                            | Optional                                                                                                                                                                                                                                                                      |
| ---------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cloudflare | `CLOUDFLARE_WORKERS_AI_ACCOUNT_ID`, `CLOUDFLARE_WORKERS_AI_API_KEY` | `CLOUDFLARE_WORKERS_AI_MODEL` (default `@cf/zai-org/glm-5.2`, 262,144-token hosted context; use `minimax/m3` for 1,000,000-token context when the account has Cloudflare AI third-party balance/BYOK), `CLOUDFLARE_THINKING` (default `false`), `CLOUDFLARE_REASONING_EFFORT` |
| OpenRouter | `OPENROUTER_API_KEY`                                                | `OPENROUTER_MODEL` (default `z-ai/glm-5.2`, 1,048,576-token context), `OPENROUTER_NITRO` (default `true`, applies only to Kimi/Moonshot models), `OPENROUTER_THINKING` (default `false`), `OPENROUTER_REASONING_EFFORT`                                                       |
| Gemini     | `GEMINI_API_KEY`                                                    | `GEMINI_MODEL` (default `gemini-flash-latest`, 1,048,576-token input limit), `GEMINI_MAX_OUTPUT_TOKENS` (default `2048`)                                                                                                                                                      |

OpenRouter requests always enable the `context-compression` plugin, so oversized staged diffs are compressed by OpenRouter instead of failing at the model context boundary.

Transport failures are reported directly in the Neovim notification. For example, `curl exit 28` means the provider request reached the configured timeout; inspect `:messages` for the captured curl stderr/body preview.
