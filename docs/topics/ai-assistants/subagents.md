---
sidebar_position: 4
---

# Staged agent workflows

Centralize control, not raw context or execution.

## Session lifecycle

`Scope → Understand → Produce → Verify → Deliver`

The active root owns this sequence. Skills contribute task mechanics and acceptance criteria; they do not add nested workflows. Empty stages need no ceremony. Verification occurs once on the integrated, formatted candidate. SOP §3.5 lets the root diagnose and repair failed checks within existing authority, freeze the repaired candidate, and rerun failed and affected checks. SOP §3.4 stops repeated attempts without new evidence or progress; workers never own recovery loops. Convergence is explicit-only and follows its declared dry exit and correctness filter; it is not ordinary failure recovery.

## Context and model responsibilities

| Category       | Responsibility                                                                                                                    | Context                                                                                                  |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| session (root) | Strong root: intent, decisions, dependencies, integration, stage transitions                                                      | Compact task handoff, not all source/logs                                                                |
| research       | Strong bounded search, investigation, exploration, discovery, impact mapping                                                      | Task-specific source; return locations, conclusions, evidence pointers, uncertainty, affected interfaces |
| implement      | Cheaper implementation band: a settled step with stated acceptance and unwritten code                                             | Owned targets and ready design inputs; return unverified artifacts                                       |
| mechanical     | Settled retrieval, execution, extraction, transformations, compression and reporting; isolate substantial output-heavy procedures | Exact procedure, targets, return and full-artifact pointers                                              |
| review         | Strong assessment of the frozen artifact                                                                                          | Actual source and shared check receipts                                                                  |
| refute         | Strong challenge of named claims, criteria or assumptions                                                                         | The claim, counterexamples and shared evidence                                                           |
| memory         | Automatic staged recall admission and final batched learning                                                                      | Compact admitted lines; no per-turn memory agents                                                        |

`home/.chezmoidata/ai_models/tiering.yaml` remains the model/effort authority. This change preserves model selections. Substantial routine implementation must not default to the expensive root/review model. A user-requested inline session is the explicit exception.

## Dispatch triggers

SOP §3.7 routes by stage-sized judgment and explicit return, not counts: `research` for unresolved interpretation, cause, or impact even on known paths; `mechanical` for a settled procedure with a stated rule and specified return (retrieval, execution, extraction, transformation, compression, or reporting); `implement` once acceptance is settled and code is not written; `review` for a nontrivial requested or skill-gated artifact assessment; `refute` for a named claim, criterion, or assumption challenge; `memory` on the hook pointer or final learning batch.
The root keeps bounded targeted reads and tiny deterministic operations. Known filenames do not make an interpretive investigation mechanical or require it to stay inline; a deterministic but output-heavy procedure can still benefit from an isolated mechanical packet.
A prose question or challenge answerable from existing evidence is answered, not launched; a nontrivial requested or skill-gated artifact assessment receives strong final judgment in an isolated worker, with the light tier using the change-auditor packet.
No numeric file-count quota and no mandatory mechanical check agent apply.

All review tiers require root-dispatched isolated review execution before the final judgment. The root MUST NOT substitute its own inline review absent an explicit user no-delegation instruction; an unavailable lane or tool is a reported blocker, not a silent inline fallback.

| Tier     | Required isolated packet                                                                                                                                                                                 |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| light    | one `change-auditor` review worker that loads `judging_core` + `judging_pipeline` by path for the packet's named gates                                                                                   |
| standard | one `reviewer-worker` review worker with the copied selected criteria and mode lens, in every mode                                                                                                       |
| deep     | distinct `reviewer-worker` and `adversarial-verifier` packets with distinct questions against the same frozen candidate; one adversarial packet per candidate unless a distinct named risk needs another |

Pi profiles pin `tools:` (mechanical: `read, grep, find, ls, bash, edit`; implementer: `+ write`; code-searcher: `+ mcp:scsi-main, mcp:scsi-local`) so children do not receive ambient MCP schemas.
Claude Code profiles pin `tools:` as well, none of them lists `Agent`, and `home/dot_claude/settings.*.json` set `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in `env`, because Claude Code 2.1.219+ lets subagents nest three layers by default and a profile without `tools:` inherits every tool, `Agent` included (measured 2026-09-14: 52 KB of tool schemas on `k-agent-smol`, 16 KB of it the `Agent` schema).
Every skill entrypoint declares its dispatch class on one `Subagent dispatch:` line; see Skill dispatch classes below.

## Skill dispatch classes

- `inline`: the root runs the skill itself. Reasons: human-visible or authorization-gated effects, the user's live environment (browser/tmux/worktree/stack), a transaction the root must read back, or an intent loop with the user.
- `criteria`: not a workflow; loaded as criteria by whoever holds the current packet (root or leaf). Never dispatched by itself.
- `research|implement|mechanical|review|refute|memory`: the root launches a leaf of that SOP §3.7 category with the skill's role mechanics copied into the packet; the root keeps scope, decisions, synthesis and effects.

| Skill                           | Subagent dispatch                     |
| ------------------------------- | ------------------------------------- |
| `k-ai-kb`                       | `memory`                              |
| `k-artifact`                    | `inline`                              |
| `k-build`                       | `implement (research; review/refute)` |
| `k-buildkite`                   | `inline (mechanical)`                 |
| `k-cli-skills`                  | `inline (implement)`                  |
| `k-code-quality`                | `criteria`                            |
| `k-code-quality-react`          | `criteria`                            |
| `k-code-quality-tests`          | `criteria`                            |
| `k-code-quality-web`            | `criteria`                            |
| `k-codebase-design`             | `research`                            |
| `k-communication`               | `criteria`                            |
| `k-compose-issue`               | `inline`                              |
| `k-compose-pr`                  | `inline`                              |
| `k-converge`                    | `refute (implement)`                  |
| `k-deep-review`                 | `review (refute)`                     |
| `k-diagnosing-bugs`             | `research`                            |
| `k-elastic-domain`              | `criteria`                            |
| `k-elastic-slides`              | `inline`                              |
| `k-git`                         | `inline`                              |
| `k-github`                      | `inline (research)`                   |
| `k-google-workspace`            | `inline`                              |
| `k-improve-branch`              | `research`                            |
| `k-improve-codebase`            | `research`                            |
| `k-improve-local`               | `inline`                              |
| `k-improve-targeted`            | `research`                            |
| `k-instruction-boundaries`      | `criteria`                            |
| `k-interview-me`                | `inline`                              |
| `k-jscpd`                       | `inline (mechanical)`                 |
| `k-kbn-backport`                | `inline`                              |
| `k-kbn-stack`                   | `inline`                              |
| `k-kbn-standup`                 | `inline (mechanical)`                 |
| `k-kibana-console-monaco`       | `inline`                              |
| `k-kibana-labels-propose`       | `inline (research)`                   |
| `k-kibana-management-ownership` | `inline`                              |
| `k-knip`                        | `inline (mechanical)`                 |
| `k-letsfg`                      | `inline (mechanical)`                 |
| `k-libra-review`                | `inline`                              |
| `k-light-review`                | `review`                              |
| `k-live-ui-windows`             | `inline`                              |
| `k-nano-banana`                 | `inline`                              |
| `k-omp`                         | `criteria`                            |
| `k-playwriter`                  | `inline`                              |
| `k-pr-fix-loop`                 | `implement (review)`                  |
| `k-present-pr`                  | `inline (implement)`                  |
| `k-proof`                       | `inline`                              |
| `k-prototype`                   | `inline (implement)`                  |
| `k-public-sources`              | `research (refute)`                   |
| `k-review`                      | `review`                              |
| `k-sem`                         | `inline (mechanical)`                 |
| `k-semantic-code-search`        | `research`                            |
| `k-slack`                       | `inline`                              |
| `k-spec`                        | `inline (research)`                   |
| `k-text-tournament`             | `inline (implement)`                  |
| `k-tmux`                        | `inline`                              |
| `k-ui-capture`                  | `inline`                              |
| `k-walkthrough`                 | `research`                            |
| `k-worktrees`                   | `inline`                              |
| `k-writing-great-skills`        | `criteria`                            |

## Nesting stays flat

Children are flat: every `k-agent-*` profile is terminal (`MUST NOT launch` in the leaf contract, `maxSubagentDepth: 0`).
A nested `strong → mechanical` tier was designed and shelved: re-opening it would need sustained evidence, not a single small sample.
`scripts/subagent_child_stats.py` describes reported per-profile child session telemetry over `~/.pi/agent/sessions/*/*/*/run-*/session.jsonl`: run count, message median/p90, compaction count, and reported peak context median/p90/max. Reported usage plus a cutoff does not determine actual window exhaustion or savings.
Source declarations (profile files, registry rows, prompt contracts) state intent; only runtime evidence from the active harness establishes enforcement, cost, or quality. Text checks do not prove model compliance.

## Memory in a child

A child recalls for itself with `,ai-kb search` / `,ai-kb get` and records session-scoped insights with `,agent-memory note` using the packet's topic and session id; without packet-supplied ids it returns the insight in its terminal artifact.
Ordinary children MUST NOT run durable memory writes; only the root persists, with root-verified evidence and `,ai-kb remember`, and no child may invoke another memory agent.
The root harvests child notes with `,ai-kb harvest` into the final learning batch.

## Worker interface

A packet names stage/category, question/change, owned targets, ready evidence, applicable project/safety constraints, named role mechanics, intended/preserved differences, output, forbidden effects, and terminal condition. Pass the needed constraints explicitly, not the whole SOP, instruction tree, catalog, or parent transcript. Missing required constraints block the packet. Independent work may run concurrently; dependent work starts only when inputs exist. Each independent implementation task gets its own implement packet: in a 2026-09-25 A/B, three test-driven tasks run as three workers cost $10.99 on average against $17.12 as one chained worker, with every test passing in both arms. Workers never spawn models, message siblings, broaden scope, run private QA, or reopen after completion. Return `produced` or `blocked` with artifact pointers; production does not return green/approved verdicts. Final specialists return findings/evidence once and never verify one another. Keep the substantive terminal result immutable. Late events cannot replace it with status chatter.

## Long sessions

Keep raw source, diffs, search output, and logs outside root context. Persist a compact handoff in the existing active topic: stage, scope/snapshot, settled decisions, dependencies, active/completed packet IDs, open questions, and evidence pointers. After compaction, continue from it without rediscovery or relaunch. Final reviewers still inspect actual relevant source, not summaries alone. Known deterministic commands use tools directly; a separate agent per read/check wastes context without adding judgment. Write the handoff as a `HANDOFF:` block (ending at the first blank line or `END HANDOFF`, at most 2500 characters); `session_context.py` and `,agent-memory select` inject that block when the whole spec exceeds the 2500-character injection limit instead of omitting the spec.

## Preserved responsibilities, new owners

Removing child orchestration must not remove the work it used to carry. The migration from the pre-stage contracts (`bc9da0992f5f`) keeps these responsibilities at the following call sites. These are stage owners, not a mandatory agent roster.

| Previous responsibility                                                              | Current owner and reachable contract                                                                                                                     | Deliberately removed machinery                                                                                         |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Necessity, intent, forks and acceptance packet                                       | Root Understand: `k-spec` → `check-strength` / `packet-template`; verified overlays supply domain planning forks                                         | Automatic necessity/advisor/prototype ceremonies and red-check approval loops                                          |
| Large code/public-source investigation and design alternatives                       | Strong Understand packets: `code-searcher`, `public-sources`, `k-codebase-design` → `going-deeper`; root owns decisions                                  | Per-query/per-alternative orchestration; cheap research substitution                                                   |
| Settled implementation, tests, docs and generation                                   | Root Produce → implementation-band `implement-worker`; direct tools for deterministic transformations                                                    | Worker self-review, test-to-green and mechanical check-runner agents                                                   |
| Criterion truth, user-path reachability, clean-state durability and scope accounting | Root final Verify: `k-build` → `criteria-verifier` over actual source and shared receipts                                                                | A verifier per criterion, receipt re-execution and mandatory mutation of every branch                                  |
| Low-risk eligibility and complete judging rules                                      | Root-dispatched isolated `k-light-review` packet: predicate → `change-auditor` worker with `judging_core` + `judging_pipeline`                           | Treating a small diff as low risk; light finder/auditor chains; root-only inline light judgment                        |
| Expert criteria, complete assigned coverage and incidental real defects              | Root-dispatched `k-review` / deep `reviewer-roster` → `lanes`; final `reviewer-worker` receives selected checks and reports coverage/gaps                | Agent per heading; stopping at the first severe finding; leaves loading the roster; root-only inline standard judgment |
| Artifact review and adversarial challenge                                            | Distinct strong final questions against the same candidate; registry review/refute bands and `adversarial-verifier`                                      | Reviewing another review as independence; weaker-family substitution                                                   |
| Redundancy, verbosity, semantic duplication, missing consumers/docs/tests            | Integrated `judging_pipeline`, reached by standard/deep/light judging                                                                                    | Separate post-review/hygiene certification pass                                                                        |
| Finding conflicts, material missing evidence and blind clarity                       | Root-owned terminal synthesis in `judging_pipeline`; conditional `fresh-eyes` retains its blind packet                                                   | Model votes, silent blocker deletion, or PR narrative used to dismiss newcomer confusion                               |
| Public claims and exact numeric/source support                                       | Root `k-public-sources` → final batched `claim-verifier`; complete captured sources, exact quotes and URLs                                               | Per-claim verification and collect→verify→deepen cycles                                                                |
| PR necessity, current intent and correctly-open status                               | Root Understand: deep `pr-necessity` / standard `pr_common` → `pr_context_audits`                                                                        | Necessity controller ladder; spending on superseded work without an explicit reason                                    |
| Live UI applicability, branch/config/data truth and screenshots                      | Final `live-ui-validation` → `live-ui-review` → `live-ui-runtime`; verified overlays own target/setup policy; root views used images once                | Source fixes inside UI verification and automatic post-judgment fix tasks                                              |
| Snapshot, discussion, pending-review deduplication and publication                   | Root `pr_snapshot` / `pr_common` / `review_delivery` and publication skill                                                                               | Worker PR refetches; review authorship treated as edit or publish authority                                            |
| Diagnosis, cleanup and PR-fix batches                                                | Root authorizes known production through `k-diagnosing-bugs`, `k-knip`, `k-pr-fix-loop` / `pr_fix`; SOP owns integrated final checks and scoped recovery | Private check loops, unrequested class-wide cleanup and automatic new-comment drains                                   |
| Recall admission, corrections and durable learning                                   | Root `k-ai-kb` → `smol-operator` (judge) / `cli`; staged recall judge, root persists the final batch with `,ai-kb remember`; identical inline fallback   | Per-turn scribes, leaf memory orchestration and dropping learning when delegation is forbidden                         |
| Convergence and prose alternatives                                                   | Explicit `k-converge` invocation (declared exit + correctness filter) or requested `k-text-tournament`; root owns the enclosing lifecycle                | Automatic convergence and repeated evaluator tournaments                                                               |

Existing named profiles in Claude, Codex, Cursor, Pi and OMP point to the same leaf contracts. Dynamic or unsupported adapters remain subject to the capability boundaries below; a contract reference does not prove profile discovery or runtime enforcement. Contract tests check required load edges, profile bindings and retained obligations. Inline source/evidence judgment remains necessary: text tests do not prove model compliance, lower token use or large-project quality parity.

## Runtime controls and limits

### Coverage inventory

Coverage is the join of the launcher, managed configs, provider wrappers and installed application surfaces. `,ai` is not the harness inventory: it routes six native CLIs and omits OMP and Crush. A native CLI check does not certify a subscription wrapper, local provider, hosted frontend or desktop application.

| Surface                                                      | Configured scope and confidence boundary                                                                                                                                                                                          |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code, Codex, Cursor CLI                               | Native profiles/hooks plus the separately listed provider routes. Native child controls and model selection are distinct claims.                                                                                                  |
| Pi, OMP                                                      | Native packages/extensions and role profiles; see controls below.                                                                                                                                                                 |
| OpenCode                                                     | Existing work implementation workers; personal single-context. Strong category lanes are not configured.                                                                                                                          |
| Antigravity CLI (`agy`, category registry key `antigravity`) | Native dynamic tiers and shared hooks. The deployed model-mirror/review harness name remains `gemini`; this is not evidence for a separate Gemini CLI or the desktop application.                                                 |
| Crush                                                        | Managed `crushrc` loads the SOP. Installed v0.92.0 task defaults are read-only and share the large model; no managed category lanes or automatic memory hooks. Root-only native hooks do not certify child lifecycle enforcement. |
| OpenRouter wrappers                                          | Claude, Codex and Cursor wrappers select the Pi backend matrix. Claude and Codex project managed native profiles with exact selectors, including distinct refute effort; the gate denies missing or stale role maps.              |
| Codex subscription wrappers                                  | `,claude-codex`, `,cursor-codex`; use the Codex backend matrix, not the frontend's model catalog.                                                                                                                                 |
| llama.cpp wrappers                                           | Claude, Codex, Cursor and OpenCode launchers. A single local model is not a strong/cheap category ladder; native lifecycle controls still belong to the frontend.                                                                 |
| `,q`                                                         | Deliberately stripped Pi one-shot: no discovered extensions, skills, context or session persistence. It is not the staged coding workflow and does not inherit the Pi extension guards.                                           |
| Cursor / Antigravity desktop                                 | Separately installed application surfaces; CLI evidence does not establish desktop behavior.                                                                                                                                      |
| tuicr / lgtm                                                 | Review interfaces, not additional model orchestration harnesses.                                                                                                                                                                  |

Subscription adapters select child controls only through explicit `@lane-<effort>` selectors; a raw model ID never implies a worker role, even when it matches another registered lane. Raw root requests retain launch controls. Claude projects managed `--agents` definitions with exact registered pairs and preserves the profile body and skills. Selectors are stripped before the upstream request. The band hook removes call-level model overrides and denies missing/unavailable profiles, stale role maps, resume/fork requests, or conflicting controls. Projected tool lists exclude orchestration tools; root terminal-wakeup prevention remains a separate criterion.

The questioned subscription route has separate root, routing, admission, and lifecycle evidence:

| Route           | Root interoperability                                                        | Exact child role/model/effort routing                | Governed admission                                                                                   | Full leaf lifecycle                 |
| --------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------- |
| `,cursor-codex` | Prior live root shell smoke; authenticated native loopback exchange observed | Unverified; a root-model child ran without admission | Bypass observed: the local Task implementation disables its hooks despite the configured deny policy | Unsupported for governed delegation |

Cursor `2026.09.08-6caf4ff` has a native limitation. Its local-provider `nhe()` configuration explicitly sets `enableExecuteHookExec:false`; the Task hook path returns without calling the executor. Authenticated scripted-provider probes under the subscription launch environment returned child results without invoking either the deployed user band hook or an instrumented workspace copy. This establishes an admission bypass, not selector rejection. No vendor files were patched, and successful ungoverned child results do not establish role/effort routing.

Do not assign unattended child work to any route in this matrix until exact routing, effective admission, and full leaf lifecycle are certified for that route. Root sessions and native harness routes remain separate capabilities. Fake-provider translation checks alone do not establish frontend selector acceptance.

Native Claude alias overrides are clamped in both directions: a cheaper alias must not weaken a strong role. Generic Codex workers preserve a registered model/effort pair, not model membership alone. A model shared by multiple lane efforts requires an explicit matching effort. Cursor uses a model selector instead: its registered `auto` mechanical/memory rows intentionally omit effort. Backend-schema routes validate the backend contract, not the frontend's exception. Missing or malformed required lane data denies delegation on the configured mutating adapters.

### Native controls

- All profile templates include the shared leaf contract. Former controller profiles are final judgment leaves, not nested controllers. Pi/OMP reviewer and blind-clarity profiles name the active root as their dispatcher; reviewers must not reload an ambient catalog or treat a controller-named sibling as an orchestrator.
- Pi profiles set `defaultContext: fresh`, `inheritProjectContext: false`, `inheritGlobalContext: false`, `inheritSkills: false`, and child depth zero. This removes ambient instructions/catalog, not explicitly named role skills: pi-subagents 0.67.0 loads those separately in `runs/foreground/execution.ts`. The root supplies applicable project and safety constraints in the packet. The 13 read-only Pi profiles include `leaf-rules.txt`, as the Claude and Codex read-only leaves do. The writers (`k-agent-mechanical`, `k-agent-implementer`) do not. Pi's bash tool runs `/bin/bash`, not zsh, so the excerpt's zsh `NOMATCH` premise does not hold there; its quoting advice is still safe. Pi leaves have no web tool, so the excerpt's `ddgr --noua` fallback applies. Dispatch requires `agentScope:"user"` so project profiles cannot override managed models, tools, or inheritance. The source-owned `subagent-contract.ts` adapter publishes the sole `subagent` tool with a managed leaf-only schema and description, and its admission guard requires explicit `acceptance:false` while rejecting context/model/per-call skill overrides, composite workflows, host gates, scheduling and revival/recovery controls. Dispatch one ready packet per call; independent root packets may explicitly set `async:true`. Because the published contract never advertises the disabled paths, the package text and the guard no longer conflict at dispatch time. Defaults are fresh and foreground. Native child identity suppresses root memory/reinforcement injection and blocks the subagent tool.
- File-only output routing exists on Pi only; elsewhere the packet names the output path and the leaf writes it.
- Claude generic implementation profiles omit agent tools. Unrestricted shell remains a limitation, not a sandbox guarantee.
- Claude Code 2.1.282 attaches the user, project and local `CLAUDE.md` files (about 24k tokens of SOP and project instructions, measured 2026-09-25) to every custom subagent unless its frontmatter sets the native `omitClaudeMd: true`. Built-in Explore and Plan set it; the same-name profiles here override them. All 16 read-only leaf profiles set it. They start from their profile body, the packet, and `leaf-rules.txt`: a compiler-verified verbatim SOP excerpt covering evidence anchoring, truncated-output handling, search and shell tooling, the research order (`gh` first, harness web tools, never `curl`) and compact returns. Parent packets carried those rules rarely (memory 13%, zsh quoting 10%, `rg` narrowing 7%, web tools 1% of 348 packets over 14 days), and without them leaves used `curl` and returned 45% longer answers. The packet still carries every project constraint the leaf needs. An A/B on 2026-09-25 covered 26 tasks across 15 lanes, 3 repetitions per arm and 156 runs in total. Answer quality was equal in both arms (78/78 correct). `k-agent-live-ui-review` passed a headless-browser check of a seeded UI bug 3/3 in both arms. Mean cost per leaf fell on every lane (17–77%), and the leaf's starting context fell from about 28.8k to 5k tokens. Implementation profiles (`claude`, `general-purpose`, `k-agent-mechanical`) keep `CLAUDE.md` because they edit repositories with their own rules. A 2026-09-25 A/B on long test-driven tasks dropped it from `general-purpose` and saved only 6% (within noise), so they keep it.
- OMP retains native depth pruning and disables background advisors. Explicit root async and effort controls remain available; implicit Bash/Eval backgrounding is disabled because it also affects blocking workers. Managed profiles (including native-name `task`, `sonic`, and `scout` shims) use `blocking: true`, no `task` tool, and no `spawns` allowlist; independent task batches still run concurrently before returning. Native reviewer shortcuts are disabled in favor of managed review profiles.
- OMP's runtime extension latches the native `yield` capability as the leaf boundary and rejects leaf async, task, advisor and hub calls. This prevents those tool paths from creating work that outlives the return. Explicit-yield root sessions receive the same conservative restrictions. Ordinary roots retain named-process hub operations; peer sends remain blocked with native whitespace normalization. The native driver is not patched: an externally created pending job can still invalidate a yield. Do not confuse `blocking:true` with disabling background jobs or claim universal terminal enforcement.
- OMP 18.1.14 passes context files, skills, and native child/Coop instructions through `src/task/executor.ts`; its profile parser does not expose Pi's inheritance flags. The managed `before_agent_start` hook replaces the leaf model prompt with its role, explicit packet/context/plan, native worktree restriction, and yield protocol/schema. It removes the inherited SOP/catalog and native private-QA/peer-wakeup instructions; named skill autoload messages remain. The profile body stays in the kept `§ Role` frame, so the 14 read-only OMP profiles carry `leaf-rules.txt` in its place. The writers (`task`, `sonic`, `k-agent-mechanical`) do not. Unknown, ambiguous, or unmanaged prompt frames abort before provider dispatch instead of falling back to a controller prompt. This controls the model-facing prompt, not physical SDK discovery, native revival, or later third-party prompt rewrites. Do not use an adapter unattended when it cannot enforce the required no-orchestration/terminal boundary.
- Former controller leaves omit declared edit/write/agent/task tools where supported. Cursor retains `readonly: false` for its existing shell/MCP access caveat; prompt-level read-only instructions are not runtime write isolation.
- Shared startup/per-turn hooks skip Codex/Claude child payloads carrying `agent_id` before topic lookup or root-context injection. Root hooks retain filtered KB retrieval and staging; only the root owns admission and final learning. No per-turn scribe or automatic convergence. Topic binding, worklogs, context-disable sentinels, and reinforcement remain.
- Codex disables `features.multi_agent` in every managed child role, including native `default`, `worker`, and `explorer` overrides. Generic roles leave model selection to the existing band hook, preserving explicit registry-backed lane picks; dedicated roles retain their declared bands. Root collaboration remains enabled. This is CLI role configuration, not proof that a hosted frontend honors local role files.
- OpenCode work retains its existing implementation workers/models, now with the shared leaf prompt and native `permission.task: deny`. Only the work root may dispatch `worker_*`; personal remains single-context. The newly available built-in scout is disabled alongside existing built-ins. The memory plugin resolves native `parentID`: root recall/learning plumbing remains, children keep worklogs without root recall, and child/unknown-identity task calls fail closed. Existing worker-session resume requests are rejected. OpenCode still has no category-backed strong research/review/refutation adapter; do not substitute its implementation workers for those stages. OpenCode stays a documented implement-only exception rather than gaining a `category_models.opencode` row: its workers are hand-pinned to one model with no per-category lane to price, so a registry row would advertise strong lanes the plugin cannot select.
- Cursor retains its model-band adapter. Claude managed profile tool allowlists omit delegation. Cursor CLI does not discover user custom profiles, and Antigravity's native dynamic tiers are not leaf lifecycle enforcement. These surfaces still require the root's packet/no-resume discipline; do not run unattended isolated work where the runtime boundary is unavailable. Unrestricted shell/MCP is not an agent sandbox in any harness. Shell-reachable harness CLIs are an accepted prompt-only boundary on every harness.

OMP 18.1.14 dispatches blocking profiles through its synchronous fan-out path (`src/task/index.ts`); `src/discovery/helpers.ts` parses the flags. The root guard uses native `pi.pi.discoverAgents(cwd)` before dispatch. Task packets must name their profiles explicitly, including every batch item; implicit native defaults are rejected. Each selected definition must resolve to its enabled user-profile file under the canonical agent directory and carry blocking, explicit model/tool and leaf-boundary controls. Project, plugin-path and bundled replacements are rejected. Settings-level model overrides, worker advisors and prewalk handoffs are rejected too; explicit off values and final refute profiles using `@advisor` remain available. Eval can select profiles dynamically, so its admission checks every enabled definition. This can block non-agent Eval code when an enabled definition is unsafe; use ordinary root tools or correct the profile, not an unguarded dispatcher.

OMP CLI task/Eval dispatch also checks effective Bash/Eval foreground settings immediately before dispatch. Project/CLI overlays can override the managed file; unsafe or unavailable values block dispatch with the offending keys. The guard reads the CLI's bundled `pi.pi.Settings.instance` and reloads disk layers through the same native method as subagent preflight; it sets no values or overrides. A concurrent terminal-marker failure also blocks an admission awaiting discovery. Source/legacy-module imports can resolve a different singleton and silently return defaults in the shipped npm CLI. This is a CLI-root control, not certification of secondary roots created with isolated SDK settings. Those roots remain unsupported for unattended dispatch.

Eval has a separate native bypass. In OMP 18.1.14, `eval/js/tool-bridge.ts` routes `__agent__`, `__workpool__` and `__completion__` before ordinary tool lookup and wrapping; both Eval runtimes use that bridge. `agent()` registers background work with keep-alive execution in `eval/agent-bridge.ts`, irrespective of a profile's `blocking` flag. `workpool()` creates persistent pools; `completion()` resolves its own tier/effort and starts a model request without a managed profile. Passing the outer Eval admission guard does not enforce the inner helper's lifecycle or model lane. These helpers and their synthetic bridges are prohibited as managed dispatch routes; use explicit native task packets instead. Ordinary Eval is not disabled, and no runtime interception of these helper calls is claimed.

The `k-omp` adapter now puts task dispatch and named-process `hub` operations under its root-only section. A leaf skips that section rather than receiving a generic instruction to perform agent handoffs. The root-moves instruction scanner recognizes the quoted native `task` command as well as “Task tool”; its counterexamples retain prohibitions, ordinary task-state prose and root-gated dispatch.

Native OMP plan-mode dispatch is a confirmed unsupported path: `structured-subagent.ts` sets `restrictToolNames`, and `sdk.ts` loads an empty extension list for those children. That skips the managed leaf prompt/tool/terminal hooks. A per-call Eval-defined `tools` list alone does not set this restriction. The public extension context has no plan-mode getter, while ACP and plan-yolo can change mode without the TUI's transcript entries; transcript inspection would not close the gap. Do not dispatch unattended workers in native plan mode or restricted SDK sessions. This restriction does not change the strong `@plan` model role or prohibit root planning. Profile admission is not a fix for extension omission, concurrent external file edits, or altered files already inside the user profile directory.

A native yield while owned asynchronous jobs remain is provisional: the executor may collect results and request another yield before returning to the parent. A test observing two yields before the parent receives a result proves additional internal turns, not post-completion resurrection. Terminal tests must observe the parent-visible result and subsequent delivery separately; neither a one-yield fixture nor the foreground-settings guard proves every native revival path is sealed.

The OMP root also consumes the native `task:subagent:lifecycle` finalized event. Only `completed`, `failed`, or `aborted` creates an exclusive `<sessionFile>.k-leaf-terminal` marker beside that worker's native transcript. The native finalizer emits this after saving and classifying the result, not at a provisional yield. The marker leaves the transcript and result untouched. Managed leaves check it before prompts, provider requests and tool execution, including a cold reopen of the same session. This prevents guarded execution after the observed final event; it does not prevent native registry retention or session construction. Leaves without persisted session identity are blocked. A failed marker write makes the root task/Eval receipt an error and blocks further dispatch; other completed workers are still sealed.

Do not treat pre-existing workers without markers, removed/relocated markers, disabled/replaced extensions, or arbitrary shell/MCP as covered by that boundary. Do not resume a completed workpool batch as a new packet. The native-pipeline fixture uses a synthetic leaf identity and finalized event, so full task/revival confidence still requires a separately authorized native worker pilot.

OpenCode's task/no-resume guards register even when optional memory helper files are absent. Each available memory callback remains active independently; missing recall or worklog plumbing does not turn off lifecycle controls.

Prompt contracts do not prove native enforcement. Unsupported autonomous lifecycle controls require a visible capability limitation rather than a claimed guarantee. No universal spend cap is asserted; usage accounting must include children/advisors when the harness exposes it. The policy evaluation matrix includes every capability-snapshot harness, including OMP and Crush; runtime-only child bindings are reported unsupported for static-pinning scenarios, not silently omitted.

These controls prevent specific sources of extra work; they do not classify arbitrary shell commands as research, production or verification. The root still owns the single final check plan. A command allowlist broad enough for implementation is not proof that a worker cannot run private QA. Runtime boundary tests and a small worker pilot also do not establish better quality or speed on a matched Kibana-scale workload.

## Sources

Core: `home/readonly_AGENTS.md` §§3.5–3.7. Leaf: `home/dot_config/exact_tmux/agent_prompts/leaf-boundary.txt`. Recipes: `home/exact_dot_agents/exact_skills/`. Runtime: shared hooks plus Pi/OMP extensions and profile templates. See [model tiering](model-tiering.md), [spec/build](flows/spec-and-build.md), and [cross-agent memory](knowledge-base/cross-agent-memory.md).

Native configuration references: Codex [custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents) “loads these files as configuration layers for spawned sessions”; OpenCode [task permissions](https://opencode.ai/docs/agents/) “Control which subagents an agent can invoke via the Task tool with `permission.task`.” Installed source remains authoritative for the tested runtime version.

Crush source: [v0.92.0 hook scope](https://github.com/charmbracelet/crush/blob/v0.92.0/docs/hooks/README.md): “Sub-agents (the `agent` task tool, `agentic_fetch`, etc.) run without hook wrapping on their internal tools.”
