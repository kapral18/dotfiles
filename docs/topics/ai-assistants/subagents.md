---
sidebar_position: 4
---

# Staged agent workflows

Centralize control, not raw context or execution.

## Session lifecycle

`Scope → Understand → Produce → Verify → Deliver`

The active root owns this sequence. Skills contribute task mechanics and acceptance criteria; they do not add nested workflows. Empty stages need no ceremony. Verification occurs once on the integrated, formatted candidate. By default a failed final check ends the attempt with evidence. Convergence is explicit-only and requires a finite user-approved repair/check allowance before entry.

## Context and model responsibilities

| Category        | Responsibility                                                               | Context                                                                                       |
| --------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| orchestrate     | Strong root: intent, decisions, dependencies, integration, stage transitions | Compact task handoff, not all source/logs                                                     |
| research        | Strong bounded investigation                                                 | Task-specific source; return conclusions, evidence pointers, uncertainty, affected interfaces |
| implement       | Cheaper implementation band: substantial settled edits                       | Owned targets and ready design inputs; return unverified artifacts                            |
| mechanical      | Deterministic tools directly; cheap model only when needed                   | Exact rule and targets                                                                        |
| review / refute | Strong final judgment, selected framing and independent risk lenses          | Actual candidate source plus shared check receipts                                            |
| memory          | Automatic staged recall admission and final batched learning                 | Compact admitted lines; no per-turn memory agents                                             |

`home/.chezmoidata/ai_models/tiering.yaml` remains the model/effort authority. This change preserves model selections. Substantial routine implementation must not default to the expensive root/review model. A user-requested inline session is the explicit exception.

## Worker interface

A packet names stage/category, question/change, owned targets, ready evidence, applicable project/safety constraints, named role mechanics, intended/preserved differences, output, forbidden effects, and terminal condition. Pass the needed constraints explicitly, not the whole SOP, instruction tree, catalog, or parent transcript. Missing required constraints block the packet. Independent work may run concurrently; dependent work starts only when inputs exist. Workers never spawn models, message siblings, broaden scope, run private QA, or reopen after completion. Return `produced` or `blocked` with artifact pointers; production does not return green/approved verdicts. Final specialists return findings/evidence once and never verify one another. Keep the substantive terminal result immutable. Late events cannot replace it with status chatter.

## Long sessions

Keep raw source, diffs, search output, and logs outside root context. Persist a compact handoff in the existing active topic: stage, scope/snapshot, settled decisions, dependencies, active/completed packet IDs, open questions, and evidence pointers. After compaction, continue from it without rediscovery or relaunch. Final reviewers still inspect actual relevant source, not summaries alone. Known deterministic commands use tools directly; a separate agent per read/check wastes context without adding judgment.

## Runtime controls and limits

- All profile templates include the shared leaf contract. Former controller profiles are final judgment leaves, not nested controllers.
- Pi profiles set `defaultContext: fresh`, `inheritProjectContext: false`, `inheritGlobalContext: false`, `inheritSkills: false`, and child depth zero. This removes ambient instructions/catalog, not explicitly named role skills: pi-subagents 0.66.0 loads those separately in `runs/foreground/execution.ts`. The root supplies applicable project and safety constraints in the packet. Explicit native call overrides can change the context mode; inspect effective inputs, not just defaults. Native child identity suppresses root memory/reinforcement injection.
- Claude generic implementation profiles omit agent tools. Unrestricted shell remains a limitation, not a sandbox guarantee.
- OMP retains native depth pruning and disables background advisors. Async shell commands and explicit effort controls remain available. Managed profiles (including native-name `task`, `sonic`, and `scout` shims) use `blocking: true`, no `task` tool, and no `spawns` allowlist; independent task batches still run concurrently before returning. Native reviewer shortcuts are disabled in favor of managed review profiles.
- OMP's managed runtime extension blocks peer `hub send` while retaining named-process input. The guard trims `name` like the native router, so whitespace cannot bypass the peer boundary. Native parked-agent lifecycle is not rewritten.
- OMP 18.1.14 passes context files, skills, and native child/Coop instructions through `src/task/executor.ts`; its profile parser does not expose Pi's inheritance flags. Packet-only context is not established there. Do not use an adapter unattended when it cannot enforce the required no-orchestration/terminal boundary.
- Former controller leaves omit declared edit/write/agent/task tools where supported. Cursor retains `readonly: false` for its existing shell/MCP access caveat; prompt-level read-only instructions are not runtime write isolation.
- Shared startup/per-turn hooks retain filtered KB retrieval and staging; only the root owns admission and final learning. No per-turn scribe or automatic convergence. Topic binding, worklogs, context-disable sentinels, and reinforcement remain.
- Codex/Cursor/Copilot retain their existing model-band adapters. Antigravity uses native dynamic tiers. OpenCode/generic remain single-context where no category-backed adapter exists.

OMP 18.1.14 dispatches blocking profiles through its synchronous fan-out path (`src/task/index.ts`); `src/discovery/helpers.ts` parses the flags. Project/plugin agent overrides can replace user profiles: inspect the effective profile before use, and do not use an unguarded override unattended.

Prompt contracts do not prove native enforcement. Unsupported autonomous lifecycle controls require a visible capability limitation rather than a claimed guarantee. No universal spend cap is asserted; usage accounting must include children/advisors when the harness exposes it.

## Sources

Core: `home/readonly_AGENTS.md` §§3.5–3.7. Leaf: `home/dot_config/exact_tmux/agent_prompts/leaf-boundary.txt`. Recipes: `home/exact_dot_agents/exact_skills/`. Runtime: shared hooks plus Pi/OMP extensions and profile templates. See [model tiering](model-tiering.md), [spec/build](flows/spec-and-build.md), and [cross-agent memory](knowledge-base/cross-agent-memory.md).
