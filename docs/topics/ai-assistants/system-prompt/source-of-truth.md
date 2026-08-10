---
sidebar_position: 1
title: Source of truth
---

# Source of truth

`home/readonly_AGENTS.md` is the generated always-loaded core SOP. Rules with an accepted ablation/evaluation record (`passed` or current no-live `mechanical-only`) may live in point-of-use consumers such as skills, with ownership recorded in the policy manifest and disposition files.

This page is the maintenance map for changing the prompt without editing rendered `$HOME` outputs directly.

The core SOP owns the default response style, and §6 opens with an accessibility contract: the user is dyslexic, so brevity outranks structure and structure must earn its space by adding scannable information not present elsewhere (do not add sections, tables, or lists to fill a budget or restate a shorter form; compression cuts words first, not structure that carries new information). The remaining subsections are a debloat requirement built on per-class word budgets (direct answer ≤80, comparison/audit ≤120 + one table or anchor list, multi-part investigation ≤200 across skeleton slots), time neutrality (the model has no valid model of elapsed time, effort, or urgency, so it may never justify scope or shortcuts with them), response shape (reach for a density primitive — verdict line, delta table, anchor list, decision block — before prose; emit a 1-line skeleton first for any answer with ≥3 sections; a section may not restate an item already given in an earlier table/list), and a substance floor that protects evidence, precision, real uncertainty, and safety qualifiers from the compression rules. It synthesizes the applicable guidance from [Stop Slop](https://github.com/hardikpandya/stop-slop) and [i-have-adhd](https://github.com/ayghri/i-have-adhd): their core skills, linked style references, examples, evaluation cases/rubric, and always-on implementation patterns.

Instruction text alone decays across a long session, and no harness in [`harness-capabilities.v1.json`](../../../../home/dot_config/ai/exact_policy-ir/readonly_harness-capabilities.v1.json) exposes a hook that can rewrite outbound model text, so output style cannot be enforced by a hook. The per-turn reinforcement channel is [`prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt), whose `[OUTPUT DISCIPLINE]` block restates the compression, structure, and time-neutrality rules. One file fans out to the tmux prompt wrap, `session_context.py` at session start, `ai-kb-recall.ts` per turn (re-injected after a 20-point context-fill delta or a compaction), and every generated subagent profile across harnesses.

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

| Artifact                                                                    | Role                                                                                                                                                                                                         |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `scripts/ai_policy_ir.py`                                                   | rule schema + legacy-file splitter/renderer                                                                                                                                                                  |
| `scripts/ai_harness_capabilities.py`                                        | fails closed when a rule claims a capability (`hook`, pinned-model overlay) the snapshot doesn't prove                                                                                                       |
| `home/dot_config/ai/exact_policy-ir/readonly_harness-capabilities.v1.json`  | per-harness evidence: instruction entrypoint, hook support level, model mutability (under ignored `policy-ir/`; not deployed)                                                                                |
| `scripts/compile_ai_policy.py`                                              | `generate` / `verify` / `verify-budgets` / `audit-coverage` / `explain` / `measure`                                                                                                                          |
| `home/dot_config/ai/exact_policy-ir/readonly_policy-manifest.v1.json`       | committed provenance: per-rule hash, disposition, consumer, risk tier, eval ref (under ignored `policy-ir/`; not deployed)                                                                                   |
| `home/dot_config/ai/exact_policy-ir/readonly_policy-dispositions.v1.json`   | Stage 2 disposition overrides for moved rules, including frozen original text (under ignored `policy-ir/`; not deployed)                                                                                     |
| `home/dot_config/ai/exact_policy-ir/readonly_policy-ablations.v1.json`      | accepted ablation/evaluation records (`passed` or current no-live `mechanical-only`) before any rule leaves `core` (under ignored `policy-ir/`; not deployed)                                                |
| `home/dot_config/ai/exact_policy-ir/readonly_policy-rule-inventory.v1.json` | permanent rule inventory so split rules cannot disappear after core shrinks (under ignored `policy-ir/`; not deployed)                                                                                       |
| `scripts/eval_ai_policy.py`                                                 | `plan` emits the cross-product cell count/cost estimate; `verify-routing`/`verify-behavior` report every cell `blocked` — live eval execution is a separate, explicitly user-approved spend, never automatic |
