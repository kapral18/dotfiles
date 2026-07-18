---
sidebar_position: 1
---

# The Agentic Operating System (AI & Assistants)

This setup treats assistant behavior as strict, version-controlled configuration installed alongside the rest of the dotfiles. The goal is deterministic, verifiable behavior instead of relying on unpredictable LLM defaults.

Start with [Choose your flow](scenarios.md) when you are asking "how do I do X?" It routes build, check, understand, and communicate scenarios to the right flow, then shows how to pivot between flows mid-work.

![Abstract layered AI operating system: dotfiles base, terminal tools, and coordinated agent workers](./assets/agentic-os-orchestration.jpg)

At a high level, the AI layer is a set of governed routes, not a pile of prompts:

![Agentic operating system governance route: request, SOP, skill, gates, optional subagent, evidence, and gated action](./assets/agentic-governance-flow.svg)

## Mental model

| Layer      | What it owns                                                               | Where to read next                                                                                                                                            |
| ---------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Governance | Always-on SOP entrypoints installed into `$HOME`                           | [System Prompt (SOP)](system-prompt/index.md)                                                                                                                 |
| Routing    | Skills under `~/.agents/skills/` that load by intent                       | [Skills](skills/index.md)                                                                                                                                     |
| Execution  | Subagents, reviews, `/k-build`, and Palantír legions                       | [Cross-harness subagents](subagents.md), [Review workflow](reviews/index.md), [Creation workflow](creation-workflow.md), [Palantír orchestrator](palantir.md) |
| Memory     | Hook memory plus durable AI KB                                             | [Agent memory](knowledge-base/index.md)                                                                                                                       |
| Tooling    | MCP servers, model routing, per-tool config rendering, and local inference | [MCP servers](mcp.md), [Model registry & routing](model-registry.md), [Tool configs](tool-configs/index.md), [llama.cpp local inference](llama-cpp/index.md)  |

## Using this section

Use the scenario router first when you know the job but not the subsystem:

- [Choose your flow](scenarios.md) — scenario rows for build, check, understand, and communicate work.
- [Reviewing agent diffs](reviewing-diffs.md) — staged-diff reading discipline when an agent produced the change and you are the reviewer.

Use the subsystem pages when you already know the layer you are changing or debugging:

| Subsystem                              | Page                                            |
| -------------------------------------- | ----------------------------------------------- |
| Scenario router (start here)           | [Choose your flow](scenarios.md)                |
| System prompt / SOP                    | [System Prompt (SOP)](system-prompt/index.md)   |
| Skills list and routing contract       | [Skills](skills/index.md)                       |
| Subagent runtime profiles              | [Cross-harness subagents](subagents.md)         |
| Review skill and agent-review topology | [Review workflow](reviews/index.md)             |
| Spec packets and hands-free builds     | [Creation workflow](creation-workflow.md)       |
| Hook memory + durable AI KB            | [Agent memory](knowledge-base/index.md)         |
| Palantír detached orchestration        | [Palantír orchestrator](palantir.md)            |
| Canonical MCP registry                 | [MCP servers](mcp.md)                           |
| Model registry and routing             | [Model registry & routing](model-registry.md)   |
| Per-tool config rendering              | [Tool configs](tool-configs/index.md)           |
| Local llama.cpp inference              | [llama.cpp local inference](llama-cpp/index.md) |
| Reviewing agent diffs                  | [Reviewing agent diffs](reviewing-diffs.md)     |

## Governance layer

Entrypoints installed into `$HOME`:

| Source                                                                                                                          | Target                               | Notes                    |
| ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------ |
| [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md)                                                                   | `~/AGENTS.md`                        | Single SOP source        |
| [`home/symlink_CLAUDE.md`](../../../home/symlink_CLAUDE.md)                                                                     | `~/CLAUDE.md`                        | Symlink to `~/AGENTS.md` |
| [`home/dot_gemini/symlink_GEMINI.md`](../../../home/dot_gemini/symlink_GEMINI.md)                                               | `~/.gemini/GEMINI.md`                | Symlink to `~/AGENTS.md` |
| [`home/dot_cursor/symlink_AGENTS.md`](../../../home/dot_cursor/symlink_AGENTS.md)                                               | `~/.cursor/AGENTS.md`                | Symlink to `~/AGENTS.md` |
| [`home/dot_codex/symlink_AGENTS.md`](../../../home/dot_codex/symlink_AGENTS.md)                                                 | `~/.codex/AGENTS.md`                 | Symlink to `~/AGENTS.md` |
| [`home/dot_config/opencode/symlink_AGENTS.md`](../../../home/dot_config/opencode/symlink_AGENTS.md)                             | `~/.config/opencode/AGENTS.md`       | Symlink to `~/AGENTS.md` |
| [`home/private_dot_copilot/symlink_copilot-instructions.md`](../../../home/private_dot_copilot/symlink_copilot-instructions.md) | `~/.copilot/copilot-instructions.md` | Symlink to `~/AGENTS.md` |

There is one real SOP file. The harness entrypoints above are symlinked to it, so the always-on instruction layer stays identical across harnesses.

Skills live under `~/.agents/skills/`; the chezmoi source is [`home/exact_dot_agents/exact_skills/`](../../../home/exact_dot_agents/exact_skills/).

## Core workflow: change a skill

1. Edit files under:

   ```text
   home/exact_dot_agents/exact_skills/
   ```

2. Apply and verify:

   ```bash
   chezmoi diff
   chezmoi apply
   ls -la ~/.agents/skills
   ```

## Safety boundaries

- Keep assistant instructions declarative and repo-local.
- Keep generic AI workflows, setup, skills, hooks, and subagent profiles domain-neutral.
- Repo/org/product specifics live in verified domain overlays or dedicated domain skills.
- Keep secrets in `pass` or local private config, not tracked markdown.
- Validate generated automation commands before state-changing actions.

## Verification and troubleshooting

High-signal checks:

```bash
chezmoi diff
chezmoi apply
ls -la ~/.agents/skills
```

If behavior is not picking up expected instructions:

- verify the correct entrypoint exists in `$HOME`;
- verify skill files exist under `~/.agents/skills/`;
- verify runtime secrets expected from `pass` are present.

## Related

- [Switching work/personal identity](../workflow/git-identity/switch-identity.md)
- [Security and secrets](../security/security-and-secrets.md)
- [Reference map](../../reference/reference-map.md)
