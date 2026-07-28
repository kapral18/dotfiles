---
sidebar_position: 1
title: Source of truth
---

# Source of truth

`home/readonly_AGENTS.md` is the generated always-loaded core SOP. Rules with an accepted ablation/evaluation record (`passed` or current no-live `mechanical-only`) may live in point-of-use consumers such as skills, with ownership recorded in the policy manifest and disposition files.

This page is the maintenance map for changing the prompt without editing rendered `$HOME` outputs directly.

The core SOP owns the default response style: lead with the answer or next action, use bounded actionable steps, show current state and errors, cut filler and tangents, and keep prose direct and specific without weakening evidence or uncertainty. It synthesizes the applicable guidance from [Stop Slop](https://github.com/hardikpandya/stop-slop) and [i-have-adhd](https://github.com/ayghri/i-have-adhd): their core skills, linked style references, examples, evaluation cases/rubric, and always-on implementation patterns.

## Mental model

| Rule                                               | Why it matters                                                   |
| -------------------------------------------------- | ---------------------------------------------------------------- |
| Platform/system/developer rules stay authoritative | keeps harness contracts above user-level policy                  |
| Global SOP beats weaker project-local SOPs         | prevents repo-local instructions from erasing safety gates       |
| Load matching skills                               | moves intent-specific rules out of the global prompt             |
| Do not pause mid-task                              | keeps execution aligned with the user's requested stopping point |

## Using it

Update the source and then verify the rendered effect.

| Step          | Command / check                                                                                                   |
| ------------- | ----------------------------------------------------------------------------------------------------------------- |
| Edit source   | core rules in `home/readonly_AGENTS.md`; moved rules in their declared consumer plus disposition/ablation records |
| Generate      | `python3 scripts/compile_ai_policy.py generate`                                                                   |
| Review render | `chezmoi diff`                                                                                                    |
| Apply         | `chezmoi apply`                                                                                                   |
| Verify effect | `make verify-agent-policy` plus the runtime/content check for the changed consumer                                |

## Reference: do not edit these directly

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

## Compiled ownership (policy compiler)

`scripts/compile_ai_policy.py` compiles `home/readonly_AGENTS.md` from a versioned policy IR (`scripts/ai_policy_ir.py`) instead of treating the file as hand-authored prose. Stage 1 established byte-for-byte compilation from one IR rule per numbered SOP heading. Stage 2 moves ablated rules out of the always-loaded core by changing their disposition and consumer while freezing their original text for provenance.

| Artifact                                                    | Role                                                                                                                                                                                                         |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `scripts/ai_policy_ir.py`                                   | rule schema + legacy-file splitter/renderer                                                                                                                                                                  |
| `scripts/ai_harness_capabilities.py`                        | fails closed when a rule claims a capability (`hook`, pinned-model overlay) the snapshot doesn't prove                                                                                                       |
| `home/dot_config/ai/readonly_harness-capabilities.v1.json`  | per-harness evidence: instruction entrypoint, hook support level, model mutability                                                                                                                           |
| `scripts/compile_ai_policy.py`                              | `generate` / `verify` / `verify-budgets` / `audit-coverage` / `explain` / `measure`                                                                                                                          |
| `home/dot_config/ai/readonly_policy-manifest.v1.json`       | committed provenance: per-rule hash, disposition, consumer, risk tier, eval ref                                                                                                                              |
| `home/dot_config/ai/readonly_policy-dispositions.v1.json`   | Stage 2 disposition overrides for moved rules, including frozen original text                                                                                                                                |
| `home/dot_config/ai/readonly_policy-ablations.v1.json`      | accepted ablation/evaluation records (`passed` or current no-live `mechanical-only`) before any rule leaves `core`                                                                                           |
| `home/dot_config/ai/readonly_policy-rule-inventory.v1.json` | permanent rule inventory so split rules cannot disappear after core shrinks                                                                                                                                  |
| `scripts/eval_ai_policy.py`                                 | `plan` emits the cross-product cell count/cost estimate; `verify-routing`/`verify-behavior` report every cell `blocked` — live eval execution is a separate, explicitly user-approved spend, never automatic |
