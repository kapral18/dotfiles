---
sidebar_position: 5
---

# MCP Servers

A single canonical registry defines every MCP (Model Context Protocol) server once; per-tool configs for Cursor, Claude Code, Gemini, Pi, Codex, and OpenCode are generated from it at `chezmoi apply` time. This avoids hand-maintaining the same server list in six different config formats.

Use when adding, removing, or debugging an MCP server, or understanding how a server reaches a given assistant.

## Registry: `mcp_servers.yaml`

Source of truth: [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml).

Each entry is one of two shapes:

- **Command server** — `name`, `work_only`, `command`, `args` (list). Example: `sequentialthinking` runs a docker image; `scsi-local` runs `bash -lc '...'` with secrets resolved from `pass`.
- **HTTP server** — `name`, `work_only`, `type: http`, `url`, and optionally `oauth_by_tool` (per-tool OAuth client metadata, since tools expect different OAuth field shapes). Example: `slack` and `scsi-main` both use `oauth_by_tool`. `scsi-main`'s OAuth2 (Elastic SSO, Okta authz server `elastic.okta.com/oauth2/default`, scopes `openid email offline_access`) is handled per-client with the pre-registered public client `0oa1aviou3pe7dITS1t8`. Cursor, Claude, Gemini, and Pi each have a tool block under `oauth_by_tool` because they expect different OAuth field shapes and redirect URIs (Pi derives both the advertised redirect URI and its local callback listener from `redirectUri: http://localhost:12345/callback`). This hosted `scsi-main` replaces the former self-hosted stdio server of the same name. `slack` (`https://mcp.slack.com/mcp`) likewise has per-tool `oauth_by_tool` blocks; Cursor and Gemini use the confidential client from `pass slack/mcp/*`, but Pi reuses Claude's public Slack client `1601185624273.8899143856786` (no secret) because that confidential client is not authorized for this user; Pi's `redirectUri` is `http://localhost:3118/callback`, with Slack's authorize/token endpoints auto-discovered from the server's protected-resource metadata.

`work_only: true` servers are emitted only when the `isWork` chezmoi variable is set. The default work set is `sequentialthinking`, `scsi-main`, `scsi-local`, `slack`; the personal set is `sequentialthinking`.

## Generation pipeline

[`scripts/mcp_registry.py`](../../../scripts/mcp_registry.py) reads and normalizes the registry (resolving `$(command)` strings via a login shell). [`scripts/generate_mcp_configs.py`](../../../scripts/generate_mcp_configs.py) turns the normalized servers into a tool-specific `{ "mcpServers": { ... } }` document, applying per-tool transforms (e.g. Cursor's `auth.CLIENT_ID` vs the standard `oauth` shape). For Pi only it also emits a top-level `"settings": { "autoAuth": true }` so pi-mcp-adapter runs the OAuth + reconnect flow automatically on the first tool call to a `needs-auth` server (still opens the browser in an interactive session; it is not headless auth). Other tools have their own config schemas and do not get this block.

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

LetsFG is intentionally not exposed through the shared MCP registry because its tools are irrelevant to most sessions; agents load its skill on demand instead. See [Tool configs](tool-configs.md) for details.

## Add or change a server

1. Edit [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) (set `work_only` appropriately).
2. `chezmoi diff` to preview the rendered per-tool configs.
3. `chezmoi apply` to regenerate them.

Verification:

```bash
chezmoi apply
python3 -m json.tool < ~/.cursor/mcp.json
python3 -c "import json; print(list(json.load(open('$HOME/.claude.json')).get('mcpServers', {})))"
```

## Related

- [Tool configs](tool-configs.md) — per-assistant settings and profile merging
- [Model registry & routing](model-registry.md) — the parallel registry for model definitions
- [The Agentic Operating System](index.md) — governance layer
