---
sidebar_position: 1
title: Source of truth
---

# Source of truth

`home/readonly_AGENTS.md` is the generated always-loaded core SOP. Rules with an accepted ablation/evaluation record (`passed` or current no-live `mechanical-only`) may live in point-of-use consumers such as skills, with ownership recorded in the policy manifest and disposition files.

This page is the maintenance map for changing the prompt without editing rendered `$HOME` outputs directly.

Wording-only compression keeps each numbered rule and its existing core/consumer disposition. Review the full clause mapping for conditions, exceptions, examples, and prohibitions before accepting a shorter version. Invariant checks protect instruction presence; isolated model decision probes can find regressions, but passing probes do not establish universal equivalence or justify retiring a rule. The current evaluator scaffold does not execute those probes.

The core SOP owns the default user-response shape, and §5 keeps that contract compact: the user is dyslexic, so replies use the shortest complete shape that preserves evidence, uncertainty, paths, commands, and safety qualifiers. It keeps the per-class budgets (direct answer ≤80 words, comparison/audit ≤120 words plus one table or anchor list, multi-part investigation ≤200 words), response shape, and the substance floor in core. Time neutrality lives earlier in §1.1 because it is a planning axiom: assume available work time is unbounded and development speed is instant, then scope by correctness, evidence, risk, and explicit user constraints. §1 also owns the depth threshold: use deeper coverage by default for non-trivial work, and use the light path only after proving the work is local, reversible, observable, and semantically simple. Optional STE (ASD-STE100 Simplified Technical English) sentence habits apply only when they shrink text, and full STE applies only when the user asks for STE or docs compliance. The detailed reinforcement is intentionally carried by `prefix.txt`, not repeated in full here.

The [`harness-capabilities.v1.json`](../../../../home/dot_config/ai/exact_policy-ir/readonly_harness-capabilities.v1.json) snapshot records specific tool-hook and model-binding evidence; it does not establish outbound-text style enforcement. The reinforcement channel is [`prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt), whose `[OUTPUT DISCIPLINE]` block restates the compression, structure, and time-neutrality rules. One file fans out to the tmux prompt wrap, `session_context.py` at session start, Pi/OMP `ai-kb-recall.ts` (re-injected after a 20-point context-fill delta or a compaction), and every generated subagent profile across harnesses. Every bounded consumer must retain the complete prefix; parity and runtime tail tests pin the shared cap so growth cannot silently drop its final rules.

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

| Target                                       | Reason                                                               |
| -------------------------------------------- | -------------------------------------------------------------------- |
| `~/AGENTS.md`                                | rendered output from chezmoi                                         |
| `~/CLAUDE.md`                                | native Claude `@AGENTS.md` import                                    |
| `~/.claude/CLAUDE.md`                        | native global entrypoint linking `~/AGENTS.md`                       |
| `~/.gemini/config/AGENTS.md`                 | symlink to `~/AGENTS.md`                                             |
| `~/.cursor/AGENTS.md`                        | symlink to `~/AGENTS.md`                                             |
| `~/.cursor/plugins/local/k-sop/rules/sop.md` | full SOP rendered from the canonical source with `alwaysApply: true` |
| `~/.codex/AGENTS.md`                         | symlink to `~/AGENTS.md`                                             |
| `~/.config/opencode/AGENTS.md`               | symlink to `~/AGENTS.md`                                             |
| `~/.copilot/copilot-instructions.md`         | symlink to `~/AGENTS.md`                                             |
| `~/.agents/skills/*/SKILL.md`                | rendered from `home/exact_dot_agents/exact_skills/`                  |

Claude resolves `@AGENTS.md` imports natively and deduplicates canonical paths. Its global `~/.claude/CLAUDE.md` symlink supplies the home SOP outside `$HOME` too; this repository’s `CLAUDE.md` imports its project `AGENTS.md`. The home import removes the second full body from Cursor’s ancestor-rule list.

Cursor’s contained `k-sop` user-local plugin renders the complete canonical SOP into an always-applied native rule. Hosted and authenticated-local profiles load it outside `$HOME`; explicit authless/Bedrock-local profiles disable user-local plugins and retain only their existing ancestor route. With the plugin enabled, Cursor loads 2 SOP bodies inside `$HOME` (ancestor plus plugin, matching the original 2-body baseline) and 1 outside. Native merging deduplicates paths, not equal bodies. No `.cursorignore` hides the readable home SOP, and `~/.cursor/AGENTS.md` alone is not a verified global scanner entrypoint.

Pi’s `runtime-parity.ts` appends the full canonical SOP through `before_agent_start` only when neither a realpath-equivalent native context file nor the complete SOP body is already present. It preserves the base prompt; explicit no-extension workflows bypass this extension. OMP already deduplicates canonical context aliases. Pi also has verified native `tool_call` blocking support; its model-band adapter remains unconfigured, so that blocking evidence does not establish per-call model clamping.

The deployed SOP carries a short managed-home reminder: dotfiles are chezmoi-managed on this machine.

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

`verify` recomputes the manifest when `--manifest` is omitted. An explicitly supplied missing or unreadable manifest fails verification; it cannot silently fall back to recomputation. Evaluation requires nonempty harness/model/role/scenario dimensions and positive repetitions. Empty or malformed matrices fail before a success report; valid scaffold cells remain honestly blocked.

`measure` counts UTF-8 source bytes for the core SOP and all declared skill descriptions. `verify-budgets` retains its declared non-manual description subset and reports the all-description total separately. `disable-model-invocation` does not prove native visibility across harnesses; these source counts are neither live prompt tokens nor skill-body load measurements.

## Runtime context ownership

Startup named-topic BM25 recall and per-turn retrieval stage complete candidates for `k-agent-smol` judgment. Only admitted judge results enter parent context or the seen-ID file. A pointer fires once per observed session-topic binding; later same-binding rows stage silently. The binding marker distinguishes a pending pointer from one already emitted, including transitions through an empty topic result. A topic-matched warm cache holds at most 3 startup rows so the next retrieval cannot overwrite that evidence before judgment; it does not accumulate previous prompt results.

Pi/OMP context-disable flags and workspace/topic sentinels suppress startup, correction, compaction and growth injections, while worklog capture stays independent. Missing `,ai-kb` disables optional recall for that extension load; the remaining lifecycle callbacks still register. Review clean-room filtering recognizes plain and Markdown ATX conclusion headings. Cursor startup uses a 10,000 UTF-16-unit carrier budget: omit whole optional worklog, then spec/bucket blocks with read pointers; retain the complete prefix, judgment pointer and reminder. Required-only overflow fails rather than truncating instructions.

Pi/OMP review-controller profiles retain native model/task notes and dispatch through canonical `k-review` or explicitly invoked `k-deep-review` owners. Every delegated invocation remains a bounded leaf; profile names grant no root authority. Plan review returns feedback only, standard review does not auto-promote to deep, and deep intake does not preload the full standard router. Narrow Claude/OMP workers load their required role contracts and conditional lenses instead of eager unrelated controller bodies.

The shared Git gate classifies `exec` utilities and executable substitutions in expandable heredocs. Quoted-delimiter data remains inert; shell-consuming heredocs still receive command classification. This is a bounded shell parser, not an exhaustive interpreter. The standalone `,agent-memory` launcher uses its deployed `~/lib/,agent-memory/` modules, rendered from canonical repository Python sources; it needs no checkout or `chezmoi` binary at runtime.

Topic selection emits bounded complete worklog rows and retains the full backing file. A live topic’s removed `.no_context` sentinel is removed from its mirror too; complete temporary-state loss still restores the saved topic. `wipe-current --reset-active` clears both live and mirrored active pointers so restoration cannot resurrect that explicit reset.
