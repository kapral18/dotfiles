---
sidebar_position: 4
title: Pi coding agent
---

# Pi coding agent settings

Pi runs from pnpm-managed packages plus readonly chezmoi sources under `home/dot_pi/agent/`.
Settings and models are set directly in the files below; extensions provide the task and context policy.

## Sources

| Piece             | Source                                                                                                                                                                 | Target                                                                                     |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Packages          | [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs) (`@earendil-works/pi-coding-agent`, `@earendil-works/pi-tui`, `pi-subagents`) | pnpm globals                                                                               |
| Settings          | [`readonly_settings.json`](../../../../home/dot_pi/agent/readonly_settings.json)                                                                                       | merged into `~/.pi/agent/settings.json` by `run_onchange_after_07-merge-pi-config.sh.tmpl` |
| Models            | [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json)                                                                                           | merged into `~/.pi/agent/models.json`                                                      |
| MCP servers       | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml)                                                                                 | `~/.pi/agent/mcp.json`                                                                     |
| Instructions      | `symlink_AGENTS.md` → `~/AGENTS.md`                                                                                                                                    | Pi project context                                                                         |
| Operating layer   | [`readonly_APPEND_SYSTEM.md`](../../../../home/dot_pi/agent/readonly_APPEND_SYSTEM.md)                                                                                 | appended to Pi's default prompt                                                            |
| Subagent profiles | `exact_agents/k-agent-reviewer.md.tmpl`, `exact_agents/k-agent-scout.md`                                                                                               | `~/.pi/agent/agents/`                                                                      |
| Extensions        | `exact_extensions/`                                                                                                                                                    | `~/.pi/agent/extensions/`                                                                  |

## Settings

| Area            | Value                                                                                                                            |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Default model   | `openai-codex` / `gpt-6-astra`, thinking `xhigh`                                                                                 |
| Extra providers | `openrouter` and `llama-cpp` in `models.json`; see [llama.cpp](../llama-cpp/index.md)                                            |
| Tools           | `defaultTools: ["+codemode", "+find", "+grep", "+ls"]`                                                                           |
| Compaction      | `reserveTokens` 16384, `keepRecentTokens` 80000 (raised from Pi's 20000 to keep more recent context verbatim)                    |
| Retries         | enabled, `maxRetries` 5                                                                                                          |
| Cache notices   | `showCacheMissNotices: true`; `/session` shows cached vs uncached tokens                                                         |
| Subagents       | `pi-subagents` loaded with empty `skills`/`prompts`; `disableBuiltins: true`, `defaultSubagentContext: "fresh"`, sync by default |
| Secrets         | API keys come from environment variables exported via `pass` in `config.fish.tmpl`                                               |

Pi loads packages from `~/.local/share/pnpm-global-links/node_modules/`, which `,install-pnpm-pkgs` rebuilds after each sync, because pnpm 11+ global paths are hashed.
Pi discovers `~/.agents/skills/` natively.

`models.json` explicitly registers OpenRouter `deepseek/deepseek-v4.1-flash-1017` so `,q` can select it when starting Pi with `--offline`, before Pi's built-in catalog includes it. The model keeps the DeepSeek routing floor and completion price cap.

Pi 1.1.0 loads context by path, not symlink identity. Inside `$HOME`, it includes both `~/.pi/agent/AGENTS.md` and `~/AGENTS.md`. The global link remains necessary for repositories outside `$HOME`.

## Extensions

| File                            | Purpose                                                                                                                                                                                                                                              |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `context-mode.ts.tmpl`          | `/context-mode short\|long\|status`: choose a smaller working window on eligible models. Policy lives in `~/lib/shared/context_mode.ts`; OMP uses its native context controls instead.                                                               |
| `intent-guard.ts.tmpl`          | Tracks the task through `,task hook`, maintains a current checkpoint, archives older text with raw-history retrieval, and preserves stop continuation. Policy: `~/lib/shared/task_context.ts`; shared event adapter: `~/lib/shared/intent_guard.ts`. |
| `model-pin.ts`                  | Re-pins the routed model after a turn whose echoed model id differs, so `pi -c` restores it. Workaround for [earendil-works/pi#9243](https://github.com/earendil-works/pi/issues/9243).                                                              |
| `subagent/readonly_config.json` | `modelResponseAliases` so `pi-subagents` accepts the `claude-fable-5-1` echo.                                                                                                                                                                        |

### Task checkpoints and output retention

Requires Pi 1.4.0. The existing runtime, TUI, session ID, compaction settings and review/fix procedure remain in use.

Before provider calls, the extension projects one task checkpoint, computed at the last completed tool turn or fetched fresh after a prompt: goal, criteria/status, scope, corrections, saved preferences, latest acceptance snapshot, decisions, findings and claim provenance/source pointers. Source bodies stay in the ledger. User prompts add only what the checkpoint lacks, such as correction notes. The latest assistant note is an unverified reference, not evidence of completion.

At completed tool-turn boundaries, older successful plain-text tool results can become short references. The checkpoint follows the conversation so routine refreshes preserve the earlier provider prefix. The policy preserves the most recent 32,000 text code units (JavaScript string length), errors, images, user messages and assistant messages. It writes a batch only when it saves at least 32,000 text code units. An older read with the same arguments as a later one is labelled identical or changed; a small changed read keeps only its label. Different ranges stay distinct. Archival runs with or without an intent card. The path-only `read-supersede.ts` extension is removed.

`task_context_read` retrieves original text by `entryId` from the active branch, including after compaction. Pages contain at most 12,000 Unicode code points; pass `nextOffset` as `offset` until it is null. Archival edits preserve tool-call/result metadata and append-only raw history. A result's preview and history are source data, not fresh verification.

The checkpoint persists in the branch as a non-context `custom` entry, written only when it changes, so extension reload and native compaction can recover it without a `context_edit` that would turn off Pi's usage-based overflow check. If the task backend fails, the extension labels a restored checkpoint as stored and skips archival. Aborted/error boundaries and queued user input also skip archival. Native compaction still summarizes conversation; this policy does not detect false beliefs or guarantee that every relevant detail stays in active context.

The shared Codex/Claude task ledger, acceptance snapshots and unbounded independent review/fix loop remain available. This extension does not dispatch additional reviewers.

### Working-context selection

GPT models default to short; other eligible families keep the native window until `/context-mode short`.
A model is eligible only when it has a short window below native capacity (from `cost.tiers[].inputTokensAbove`; GPT without tier data uses 272,000 tokens).
The choice is a session entry: it follows the branch and survives resume.
Switching to short is refused when history already exceeds the short window; run `/compact` first.
If the catalog exposes no larger capacity, `long` leaves the model unchanged; it does not infer an API limit.

## Subagents

Only the repo profiles exist; see [Subagents](../subagents.md).

| Profile            | Model                                                                   | Use                                                                                                                                |
| ------------------ | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `k-agent-scout`    | `openai-codex/gpt-6-luna`, thinking low, read-only tools, fresh context | broad read-only search                                                                                                             |
| `k-agent-reviewer` | `anthropic/claude-opus-5-5`, medium                                     | a finished change that `~/AGENTS.md` §3 step 5 lists (risky code or a rule edit) and its fix diffs, or a review the user asked for |

Both set `maxSubagentDepth: 0`, so they cannot start other agents.

## `APPEND_SYSTEM.md`

Pi's default prompt is minimal and has no verification defaults. `APPEND_SYSTEM.md` adds tone, tool-calling, codemode, edit, citation, and task-list rules; for autonomy, questions, and static verification it points to `AGENTS.md` §1 and §3.
Order: Pi default → `APPEND_SYSTEM.md` → project context (`AGENTS.md`). The system prompt and overlay stay authoritative; `AGENTS.md` §8 sets tone and format where they leave it open.
It is additive rather than `SYSTEM.md` so Pi keeps its default tool list and self-doc pointers.
`,q` skips it by passing a short `--system-prompt` and an empty `--append-system-prompt`.
