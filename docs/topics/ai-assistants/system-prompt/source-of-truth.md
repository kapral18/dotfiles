---
sidebar_position: 1
title: Source of truth
---

# Source of truth

`home/readonly_AGENTS.md` is the generated always-loaded core SOP. Rules with an accepted ablation/evaluation record (`passed` or current no-live `mechanical-only`) may live in point-of-use consumers such as skills, with ownership recorded in the policy manifest and disposition files.

This page is the maintenance map for changing the prompt without editing rendered `$HOME` outputs directly.

The core SOP owns the default user-response shape, and §5 keeps that contract compact: the user is dyslexic, so replies use the shortest complete shape that preserves evidence, uncertainty, paths, commands, and safety qualifiers. It keeps the per-class budgets (direct answer ≤80 words, comparison/audit ≤120 words plus one table or anchor list, multi-part investigation ≤200 words), response shape, and the substance floor in core. Time neutrality lives earlier in §1.1 because it is a planning axiom: assume available work time is unbounded and development speed is instant, then scope by correctness, evidence, risk, and explicit user constraints. Optional STE (ASD-STE100 Simplified Technical English) sentence habits apply only when they shrink text, and full STE applies only when the user asks for STE or docs compliance. The detailed reinforcement is intentionally carried by `prefix.txt`, not repeated in full here.

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
| `~/.gemini/config/AGENTS.md`         | symlink to `~/AGENTS.md`                            |
| `~/.cursor/AGENTS.md`                | symlink to `~/AGENTS.md`                            |
| `~/.codex/AGENTS.md`                 | symlink to `~/AGENTS.md`                            |
| `~/.config/opencode/AGENTS.md`       | symlink to `~/AGENTS.md`                            |
| `~/.copilot/copilot-instructions.md` | symlink to `~/AGENTS.md`                            |
| `~/.agents/skills/*/SKILL.md`        | rendered from `home/exact_dot_agents/exact_skills/` |

## Compiled ownership (policy compiler)

`scripts/compile_ai_policy.py` compiles `home/readonly_AGENTS.md` from a versioned policy IR (`scripts/ai_policy_ir.py`) instead of treating the file as hand-authored prose. Stage 1 established byte-for-byte compilation from one IR rule per numbered SOP heading. Live rule IDs follow the current heading numbers. Stage 2 moves ablated rules out of the always-loaded core by changing their disposition and consumer while freezing their original text for provenance.

| Artifact                                                                    | Role                                                                                                                                                                                                         |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `scripts/ai_policy_ir.py`                                                   | rule schema + legacy-file splitter/renderer                                                                                                                                                                  |
| `scripts/ai_harness_capabilities.py`                                        | fails closed when a rule claims a capability (`hook`, pinned-model overlay) the snapshot doesn't prove                                                                                                       |
| `home/dot_config/ai/exact_policy-ir/readonly_harness-capabilities.v1.json`  | per-harness evidence: instruction entrypoint, hook support level, model mutability (under ignored `policy-ir/`; not deployed)                                                                                |
| `scripts/compile_ai_policy.py`                                              | `generate` / `verify` / `verify-budgets` / `audit-coverage` / `explain` / `measure`                                                                                                                          |
| `home/dot_config/ai/exact_policy-ir/readonly_policy-audit.v1.json`          | tracked audit state: Stage 2 disposition overrides plus accepted ablation/evaluation records for rules moved out of `core` (under ignored `policy-ir/`; not deployed)                                        |
| `home/dot_config/ai/exact_policy-ir/readonly_policy-manifest.v1.json`       | optional generated inspection output: per-rule hash, disposition, consumer, risk tier, and eval ref; ignored by git and recomputed by verification                                                           |
| `home/dot_config/ai/exact_policy-ir/readonly_policy-rule-inventory.v1.json` | current rule inventory plus removed-content hashes so split rules cannot disappear after core shrinks (under ignored `policy-ir/`; not deployed)                                                             |
| `scripts/eval_ai_policy.py`                                                 | `plan` emits the cross-product cell count/cost estimate; `verify-routing`/`verify-behavior` report every cell `blocked` — live eval execution is a separate, explicitly user-approved spend, never automatic |
