---
title: Ralph Orchestrator
---

# Ralph Orchestrator (`,ralph go`)

`planner -> executor -> reviewer -> re_reviewer` is the core loop. Ralph adds persistent manifests, tmux observability, model-family diversity, and optional durable learning.

![Ralph dashboard popup over the tmux workbench, showing multiple runs, an awaiting-human question, iterations, role validation, and role log tail](../assets/ralph-dashboard-full.png)

| Navigation slice                                        | Owns                                                                         |
| ------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [Roles and diversity](roles-and-diversity.md)           | role defaults, model-family gate, domain-gated review preamble               |
| [State and runtime](state-and-runtime.md)               | run data paths, CLI workflow, tmux mode, resumability phases                 |
| [Dashboard and tmux integration](dashboard-and-tmux.md) | Bubble Tea dashboard, keybindings, run isolation, picker/status integrations |
| [Verification](verification.md)                         | Python/TUI suites and smoke-test commands                                    |

## Component map

| Component         | Source                                                                                                                                  |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| CLI entry         | [`home/exact_bin/executable_,ralph`](../../../../home/exact_bin/executable_,ralph) + [`scripts/ralph.py`](../../../../scripts/ralph.py) |
| Roles + diversity | [`home/dot_config/ralph/roles.json`](../../../../home/dot_config/ralph/roles.json)                                                      |
| Role prompts      | [`home/dot_config/ralph/prompts/`](../../../../home/dot_config/ralph/prompts/)                                                          |
| Dashboard         | [`tools/ralph-tui/`](../../../../tools/ralph-tui/)                                                                                      |
| Skill             | [`home/exact_dot_agents/exact_skills/exact_ralph`](../../../../home/exact_dot_agents/exact_skills/exact_ralph)                          |

The dashboard is the operator view. It reads manifests/logs and dispatches control actions back through `,ralph`; it does not own the state machine.

## Related

- [Agent memory](../knowledge-base/index.md) — the AI KB that Ralph reads from and writes to
- [Review workflow](../reviews/index.md) — reviewer/re-reviewer skill policy on domain repos
- [llama.cpp local inference](../llama-cpp/index.md) — opt-in local models for roles
- [The Agentic Operating System](../index.md) — governance layer
