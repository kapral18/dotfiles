---
sidebar_position: 1
title: Source of truth
---

# Source of truth

`home/readonly_AGENTS.md` is the one real SOP file. Other entrypoints are symlinks or generated surfaces that point back to it.

## Why it is first

| Rule                                               | Why it matters                                                   |
| -------------------------------------------------- | ---------------------------------------------------------------- |
| Platform/system/developer rules stay authoritative | keeps harness contracts above user-level policy                  |
| Global SOP beats weaker project-local SOPs         | prevents repo-local instructions from erasing safety gates       |
| Load matching skills                               | moves intent-specific rules out of the global prompt             |
| Do not pause mid-task                              | keeps execution aligned with the user's requested stopping point |

## Update path

| Step          | Command / check                                                 |
| ------------- | --------------------------------------------------------------- |
| Edit source   | `home/readonly_AGENTS.md`                                       |
| Review render | `chezmoi diff`                                                  |
| Apply         | `chezmoi apply`                                                 |
| Verify effect | check only the rendered content or runtime behavior you changed |

## Do not edit these directly

| Target                               | Reason                                              |
| ------------------------------------ | --------------------------------------------------- |
| `~/AGENTS.md`                        | rendered output from chezmoi                        |
| `~/CLAUDE.md`                        | symlink to `~/AGENTS.md`                            |
| `~/.gemini/GEMINI.md`                | symlink to `~/AGENTS.md`                            |
| `~/.cursor/AGENTS.md`                | symlink to `~/AGENTS.md`                            |
| `~/.codex/AGENTS.md`                 | symlink to `~/AGENTS.md`                            |
| `~/.config/opencode/AGENTS.md`       | symlink to `~/AGENTS.md`                            |
| `~/.copilot/copilot-instructions.md` | symlink to `~/AGENTS.md`                            |
| `~/.agents/skills/*/SKILL.md`        | rendered from `home/exact_dot_agents/exact_skills/` |
