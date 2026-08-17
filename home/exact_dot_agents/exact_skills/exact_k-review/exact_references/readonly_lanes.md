# Expert Lane Registry

The single source for which review lenses exist, when each one is implicated, and what it checks.
Every review tier selects lanes from this file; angle lists live here only, never inline in a tier.

This is a selection menu, not a launch list. Availability is free; only launched lanes cost tokens.
The lane budget lives in the calling tier, not here.

## How the controller uses it

1. Build the roster from scope-level evidence only: mode, changed paths, `git diff --stat`, `git diff --diff-filter=D --stat`, and the context pack manifest.
   Roster selection is scope-level only — pick lanes from that evidence, leaving code bodies unread.
2. Always launch `correctness-regressions`.
3. Add another lane only when its Trigger matches on that scope-level evidence **and** its lens would be under-covered inside an already-selected lane.
4. Paste the selected lane's **Lens skill** line and **Checks** list verbatim into that worker's scope packet.
   Workers receive only the pasted entry; pasting it costs a few lines instead of the whole registry.
5. Fold implicated lanes that exceed the budget into the closest launched lane as named secondary emphases, and say which were folded.
6. Record each selection with the concrete evidence that triggered it, so an unproductive lane can be pruned from later runs.

A lens skill is loaded by the worker only when the lane entry names one.
When no skill exists for a lens, the Checks list is the whole contract.

## Lanes

### `correctness-regressions`

- Trigger: always.
- Lens skill: `~/.agents/skills/k-code-quality/SKILL.md`
- Checks: does the changed code do what the diff claims; off-by-one, null/undefined, boundary and empty-collection handling;
  inverted or short-circuited conditions; changed defaults; callers not updated alongside a changed signature;
  behavior that silently differs from base for existing inputs.

### `tests-validation`

- Trigger: test files touched, or risky logic changed with no test change.
- Lens skill: `~/.agents/skills/k-code-quality-tests/SKILL.md`
- Checks: does each new test fail without the fix; assertions that cannot distinguish pass from broken;
  over-mocking that removes the behavior under test; determinism (time, ordering, randomness, network);
  coverage claimed by the PR but not actually exercised; deleted tests whose coverage moved nowhere.

### `design-modularity`

- Trigger: large refactor, rename, file moves, new module/package, or structural churn in `git diff --stat`.
- Lens skill: `~/.agents/skills/k-codebase-design/SKILL.md`
- Checks: does the change deepen or shallow the module; interface surface grown for one caller's convenience; leaked implementation detail;
  new seam that is untestable; duplicated concept now expressed two ways; abstraction introduced with a single implementation.

### `api-contracts`

- Trigger: public API, exported types, schema, protobuf, OpenAPI, or type-surface paths.
- Checks: breaking change to an exported signature, type, or wire shape without a stated migration;
  widened input or narrowed output accepted silently; optional made required; enum extended where consumers exhaustively switch;
  version/compat guarantees stated in docs but not enforced in code.

### `security-authz`

- Trigger: auth, authz, permission, session, token, crypto, secret, input-parsing, deserialization, file-upload, or shell-invocation paths.
- Checks: authorization decided on client-supplied identity; missing or post-hoc permission check;
  injection through interpolated SQL/shell/HTML; secret written to logs, errors, or fixtures; unsafe deserialization; path traversal;
  permission check present on one entry point but absent on a sibling added by this diff.

### `data-persistence`

- Trigger: migration files, schema definitions, persisted-state paths, cache keys, or serialization formats.
- Checks: migration that is not reversible or not safe to run against live data; backfill that assumes a small table;
  write path changed without a read path that tolerates both shapes during rollout; cache key that no longer distinguishes what it must;
  data loss on partial application.

### `concurrency-state`

- Trigger: parser/tokenizer, routing/matching, retry/backoff, workflow/queue, permission-matrix, scheduler, or multi-flag control flow.
- Checks: run the State-Machine Verification Gate in `judging_core.md` in full; unreachable or newly-shadowed states;
  retry without idempotency; race between check and use; state mutated from two owners; a flag combination the diff never considers.

### `error-failure-modes`

- Trigger: error handling, retry, timeout, fallback, rollback, or transaction-boundary changes.
- Checks: error swallowed or logged and continued; failure that leaves partial state committed; retry that amplifies an outage;
  timeout absent on a new remote call; fallback that silently serves wrong data; error surfaced to the user with an unactionable message.

### `performance-resource`

- Trigger: hot paths, loops over request/data volume, query construction, N+1 candidates, bundle-size-sensitive frontend paths, or added dependencies in a hot module.
- Checks: per-item work moved inside a loop; query added inside an iteration; unbounded memory growth or unbounded result set;
  synchronous work on a latency-critical path; new dependency pulled into a bundle-size-sensitive entry point.

### `deletion-replacement`

- Trigger: `git diff --diff-filter=D --stat` non-empty, removed exports, or an implementation/test/helper replaced by another.
- Checks: run the Deletion-Safety Audit and Replacement/Migration Parity Gate in `judging_core.md`;
  every behavior, assertion, and side effect of the removed code named in the replacement or proven intentionally dropped;
  remaining callers of the deleted symbol; historical rationale for long-lived code being removed.

### `product-flow`

- Trigger: UI components, routes, user-state, navigation, or API handlers serving a user-visible flow.
- Lens skill: `~/.agents/skills/k-code-quality-react/SKILL.md` when the diff is React/JSX/TSX.
- Checks: walk the user's path end to end, not the diff hunk; a state the user can reach that the change does not handle (empty, loading, error, unauthorized, stale); flow that now dead-ends; destructive action without confirmation or undo; changed copy that contradicts what the code does.

### `frontend-render`

- Trigger: JSX/TSX components, hooks, CSS, or template/markup files.
- Lens skill: `~/.agents/skills/k-code-quality-react/SKILL.md` plus `~/.agents/skills/k-code-quality-web/SKILL.md`
- Checks: hook dependency arrays that stale or over-fire; state derived in render that should be computed or memoized;
  effect that runs on every render; key instability across a list; layout or visual property dropped by a component swap;
  CSS specificity or cascade change that alters an unrelated surface.

### `accessibility`

- Trigger: interactive markup, focus management, ARIA attributes, forms, modals, or keyboard handlers.
- Lens skill: `~/.agents/skills/k-code-quality-web/SKILL.md`
- Checks: control reachable and operable by keyboard; focus moved and trapped correctly for overlays; accessible name present and accurate;
  state conveyed by more than color; ARIA that contradicts the native role; content order that breaks for screen readers.

### `observability-signal`

- Trigger: alerting, monitoring, threshold, metric, telemetry, logging, or query-generation paths.
- Checks: run the Signal-Quality Gate in `judging_core.md`; alert that cannot fire or fires on every sample; threshold with no stated basis;
  metric whose cardinality can explode; log line carrying user data; a failure mode the change introduces that emits no signal at all.

### `dependency-config`

- Trigger: lockfiles, manifests, build config, CI config, feature flags, or environment/runtime configuration.
- Checks: dependency added for a function the repo already has; version bump crossing a documented breaking change;
  config default that differs between environments; feature flag with no off-path or no removal plan;
  build/CI change that weakens an existing gate.

### `docs-contract-drift`

- Trigger: AI-facing instruction text, user-facing docs, README, or generated reference changed alongside behavior —
  or behavior changed while such text was not.
- Checks: documented behavior that the diff contradicts; instruction text whose cross-references, step numbers, or paths the diff invalidated; counts, examples, or defaults now stale; a rename applied to prose where it changed meaning rather than the identifier.

## Adding a lane

Add an entry only when a lens is genuinely under-covered by every existing one, and give it a scope-level Trigger that can be evaluated without reading code bodies.
Wire a `Lens skill` only when a matching skill already exists; the Checks list alone is a complete contract, so a slot needs no skill created for it.
