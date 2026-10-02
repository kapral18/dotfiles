# Delegation Mechanics

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.

### 3.7a Delegation Mechanics

Categories select capability and responsibility, not workflows.
Resolve model and, where the harness accepts it, effort from `category_models` in the shared registry.
Keep research/orchestration/review/refutation strong; never a cheap model for unsettled judgment.
Do not silently raise effort, substitute a costlier model, or change family outside the resolved category.

- `orchestrate`: the root/main session itself, never a delegation target; `session_models.<harness>` declares its model/effort and generates every repo-owned root config; owns intent, decisions, packet dependencies, integration, stages, user conversation.
- `research`: strong isolated search, investigation, exploration, discovery, diagnosis, and impact mapping when meaning or cause is unresolved, even on known paths; returns locations, conclusions, evidence pointers, uncertainty, affected interfaces.
  Named paths never downgrade such work to mechanical.
  Use `k-agent-code-searcher` or the harness research-bound explorer; external sources via `k-agent-public-sources`.
- `implement`: implementation-band worker for a settled step whose acceptance the root can state but whose code it has not written;
  never the root/review model for routine implementation by default.
  Use the implement-bound worker with `~/.agents/skills/k-build/references/implement-worker.md`.
- `mechanical`: a settled procedure and specified return for known retrieval, execution, extraction, transformation, compression, or reporting over named targets.
  Use `k-agent-mechanical` or the native mechanical-bound type for substantial output-heavy work that benefits from isolation, even when the procedure is deterministic; tiny operations use tools directly.
- `review`: strong final assessment of the frozen artifact with selected risk lenses, including the light tier's `change-auditor` packet.
- `refute`: strong final challenge of named claims, criteria, or assumptions;
  prefer a different family at equal capability, never weaker for diversity;
  report reduced independence when same-family.
  Keep requested review and adversarial lenses together in final Verify; for deep or high-risk work give them distinct questions on the same frozen candidate and evidence.
  No reviewer-of-reviewer or reviewer-fed certification pass. Low-risk work needs only its applicable judgment.
- `memory`: staged recall admission via `k-agent-smol` (judge only); the root persists the final learning batch inline with `,ai-kb remember`; no per-turn scribe or leaf memory orchestration.

The root conducts substantial work through flat stage-sized packets classified by needed judgment and explicit return:
Scope, decisions, packet authoring, integration, course correction, Verify dispatch, user conversation.
Dispatch by stage-sized judgment, not counts:

| category     | dispatch when                                                              | root keeps inline                                                                        |
| ------------ | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `research`   | substantial interpretation, cause, discovery, or impact work is unresolved | bounded targeted reads and existing-evidence lookup                                      |
| `mechanical` | the procedure and return are settled and stated for the named targets      | tiny operations via direct tools                                                         |
| `implement`  | substantial acceptance is settled and code is not written                  | trivial single-site edits                                                                |
| `review`     | a nontrivial requested or skill-gated artifact assessment is due in Verify | eligibility routing and terminal synthesis                                               |
| `refute`     | a named claim, criterion, or assumption needs a substantial challenge      | questions resolved by existing evidence                                                  |
| `memory`     | the hook pointer (recall judgment)                                         | the final learning batch via `,ai-kb remember`; the documented unavailable-lane fallback |

Unsettled user intent and user-only decisions stay root Understand work, not a packet;
bounded factual or design unknowns may go as research packets.
"Bounded" is judged by the accumulated total, not per read: reads of skill references, third-party source, or logs that are not named by an active gate are packet work even when each read is small.
Named files count toward the same accumulated bound.
When inline reads keep accumulating without settling the question, stop reading, write the packet from what is already known, dispatch it, and consume its terminal result.
No agent per read, command, check result, or tiny edit.
No numeric file-count quota and no mandatory mechanical check agent.
Tiny deterministic operations, inline UI proof, and inline text comparison stay inline. Convergence stays explicit-only.
If the resolved lane is unavailable, surface it; do not silently implement inline unless the user explicitly requires inline work.
A packet names stage/category, scope and owned paths, ready inputs, intended/preserved differences, the applicable shared contract, project/safety constraints, role mechanics, output, forbidden effects, terminal condition, and the active topic plus session id for `,agent-memory note`.
Before parallel production, settle applicable shared runtime versions, canonical schema/identity/order examples, the compatibility decision, semantic dependencies, and one root-owned integration owner.
Materialize them as immutable shared input references in every dependent packet; file-disjoint ownership alone is insufficient.
Ready inputs are materialized state the child can open (a manifest, diff, path list, or artifact file), never prose that describes state the child must rediscover.
Keep the packet to those fields; the leaf profile already carries the leaf contract, so do not restate its prohibitions, and pass role-mechanics files as absolute paths, not pasted bodies (a lane's few-line Checks list is criteria, not a mechanics file, and travels inline).
Pass needed constraints explicitly, not the whole SOP, instruction tree, skill catalog, or parent transcript.
Use fresh worker context where supported; disclose runtime-injected instructions; a marker does not prove isolation.
Parallelize only work independent in semantics and ownership with all ready inputs;
sequence the rest instead of leaving workers waiting for siblings.
Ownership covers the path set and mutable shared state (git index, generated outputs, lockfiles);
one writer per worktree unless targets are proven independent.
Give each independent implementation task its own implement packet; do not chain unrelated tasks through one worker.
The root validates return structure, ownership, and artifact availability without repeating semantic review.
Workers return `produced` or `blocked` with artifact pointers; consume a child result once:
a file pointer means read the file once, an inline body means do not re-read the file.
Keep root context to requirements, decisions, dependencies, compact results, open questions;
raw source, search output, logs, and diffs stay in task-local artifacts with pointers; workers return no transcripts.
Persist a compact handoff in the topic: stage, snapshot, settled decisions, open work, active/terminal packet IDs, evidence pointers.
Write it as a block that starts with a line `HANDOFF:` and ends at the first blank line or `END HANDOFF`, at most 2500 characters;
the hooks inject that block when the spec itself is too large to inject.
On compaction or continuation resume from it; do not rediscover completed work or relaunch a packet.
Final reviewers read the actual relevant artifacts, not only compressed summaries.
Report token usage across root, children, and advisors from available harness/session telemetry, else unknown.
State missing coverage and the price/rate basis; distinguish available counts, scope, and rate estimates from recorded cost, and never claim bill equivalence.
Repo-owned agent IDs use `k-agent-<role>`; harness-native IDs stay unchanged.

### 3.7b Dispatch Cost, Timeouts, And Recovery

A packet costs a composing turn, child decode time, and a consuming turn; a strong child at high effort spends tens of seconds per turn.
Do not dispatch a question the root can settle in a few targeted reads, and do not dispatch work whose inputs the root has already read.
This does not lift the accumulated-read bound above: when inline reads keep accumulating without settling the question, dispatch.
Before writing a packet, confirm the resolved lane's capabilities (required tools, servers, output-mode requirements);
a rejected dispatch still costs the composing turn.
Size the child timeout at no less than 30 seconds per expected child turn, or omit it to keep the harness default;
NEVER set a limit below that figure.
Dispatch synchronously unless the root has independent work to continue; NEVER end a turn only to wait for an async child.
After a child timeout, read its partial transcript or output artifact inline once; MUST NOT dispatch a recovery agent to mine it.
