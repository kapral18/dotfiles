---
sidebar_position: 8
---

# MCP Servers

A single canonical registry defines every MCP server once.

At `chezmoi apply` time, generators render per-tool configs for:

- Cursor
- Claude Code
- Gemini
- Pi
- Codex
- OpenCode
- GitHub Copilot CLI

That avoids hand-maintaining the same server list in seven config formats.

Use when adding, removing, or debugging an MCP server, or understanding how a server reaches a given assistant.

## Registry: `mcp_servers.yaml`

Source of truth: [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml).

Each entry is one of two shapes:

- **Command server** — `name`, `work_only`, `command`, `args` (list). A command server may also carry `exclude_tools` (a list of tool names) to omit it for specific tools that cannot express per-tool membership via `oauth_by_tool`.
- **HTTP server** — `name`, `work_only`, `type: http`, `url`, and optionally `oauth_by_tool` (per-tool OAuth client metadata, since tools expect different OAuth field shapes).

The registry mechanics are generic; the current work-profile server set is Elastic-domain-specific:

- `scsi-main` is the hosted Semantic Code Search server using Elastic SSO/OAuth. Cursor, Claude, Gemini, and Pi each have tool-specific OAuth metadata because they expect different field shapes and redirect URIs.
- `scsi-local` is the local SCSI stdio backend and is excluded from Copilot once the hosted server is omitted there.
- `slack` is the Slack MCP server with per-tool OAuth metadata.
- Copilot is intentionally absent from the OAuth HTTP servers because it hardcodes its OAuth redirect to `http://127.0.0.1:{port}/`, which is not registered for either the SCSI Okta app or the public Slack client. With no `copilot` key under `oauth_by_tool`, `load_servers()` omits those servers for Copilot.

`work_only: true` servers are emitted only when the `isWork` chezmoi variable is set. The default work set is `scsi-main`, `scsi-local`, `slack`; the personal set is empty (no `work_only: false` servers remain). Per-tool exclusions narrow this further — e.g. Copilot gets none of these.

## Generation pipeline

The generation pipeline has two common stages:

| Stage                   | Script                                                                        | Purpose                                                   |
| ----------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------- |
| Normalize registry      | [`scripts/mcp_registry.py`](../../../scripts/mcp_registry.py)                 | Resolve `$(command)` strings through a login shell        |
| Generate per-tool shape | [`scripts/generate_mcp_configs.py`](../../../scripts/generate_mcp_configs.py) | Emit a tool-specific `{ "mcpServers": { ... } }` document |

Per-tool transforms handle schema differences, such as Cursor's `auth.CLIENT_ID` vs the standard `oauth` shape.

Pi gets one extra block:

```json
{ "settings": { "autoAuth": true } }
```

That lets `pi-mcp-adapter` run OAuth + reconnect automatically on the first tool call to a `needs-auth` server. It still opens the browser in an interactive session; it is not headless auth. Other tools have their own config schemas and do not get this block.

Tools whose config is not plain JSON get dedicated injectors that preserve the surrounding hand-curated file:

- [`scripts/inject_mcp_into_codex_toml.py`](../../../scripts/inject_mcp_into_codex_toml.py) — replaces a `# __MCP_SERVERS__` marker line in the Codex TOML with generated sections.
- [`scripts/inject_mcp_into_opencode_jsonc.py`](../../../scripts/inject_mcp_into_opencode_jsonc.py) — replaces a `"mcp": "__MCP_SERVERS__"` placeholder in the OpenCode JSONC.
- [`scripts/merge_claude_mcp.py`](../../../scripts/merge_claude_mcp.py) — surgically updates only the `mcpServers` key in `~/.claude.json`, which Claude Code also writes runtime state into.

## Per-tool targets

| Tool        | Target file (`mcpServers`)          | Rendered by hook                                                                                                                           |
| ----------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Cursor      | `~/.cursor/mcp.json`                | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| Claude Code | `~/.claude.json` (`mcpServers` key) | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| Pi          | `~/.pi/agent/mcp.json`              | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| Gemini      | `~/.gemini/settings.json`           | [`run_onchange_after_07-merge-gemini-settings.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-gemini-settings.sh.tmpl) |
| OpenCode    | `~/.config/opencode/opencode.jsonc` | [`run_onchange_after_07-merge-opencode-config.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-opencode-config.sh.tmpl) |
| Codex       | `~/.codex/config.toml`              | [`run_onchange_after_07-merge-codex-config.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-codex-config.sh.tmpl)       |
| Copilot     | `~/.copilot/mcp-config.json`        | [`run_onchange_after_07-merge-copilot-config.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-copilot-config.sh.tmpl)   |

Copilot transform behavior:

| Server class | Emitted shape                                                               |
| ------------ | --------------------------------------------------------------------------- |
| stdio        | `type: "local"` with `tools: ["*"]`                                         |
| OAuth HTTP   | `type: "http"` with `oauthClientId`, `auth.redirectPort`, and `oauthScopes` |

No HTTP server is currently wired for Copilot:

- `scsi-main` and `slack` are excluded by the redirect-URI mismatch above.
- `scsi-local` is excluded with `exclude_tools: [copilot]` because the hosted `scsi-main` it backs is gone.
- Copilot's generated `mcpServers` is empty and it relies on built-in servers.

The built-in `github-mcp-server` is provided by Copilot and is not emitted.

LetsFG is intentionally not exposed through the shared MCP registry because its tools are irrelevant to most sessions; agents load its skill on demand instead. See [Tool configs](tool-configs/index.md) for details.

## Add or change a server

1. Edit [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) (set `work_only` appropriately).
2. `chezmoi diff` to preview the rendered per-tool configs.
3. `chezmoi apply` to regenerate them.

Verification:

```bash
chezmoi apply
python3 -m json.tool < ~/.cursor/mcp.json
python3 -c "import json; print(list(json.load(open('$HOME/.claude.json')).get('mcpServers', {})))"
copilot mcp list   # lists the loaded Copilot servers and their transport types
```

## Related

- [Tool configs](tool-configs/index.md) — per-assistant settings and profile merging
- [Model registry & routing](model-registry.md) — the parallel registry for model definitions
- [The Agentic Operating System](index.md) — governance layer
