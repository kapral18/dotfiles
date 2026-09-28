# Kibana Formal-Verification Replay Adapters

Domain policy for the SOP `3.6` / `,formal replay <unit> --adapter '<cmd>'` adapter on `elastic/kibana`: which runner reaches a given
stateful surface. This overlay names the runner choice; `~/.agents/skills/k-formal/SKILL.md` owns the generic `,formal` mechanics.

## Runner choice per surface

Evidence comes only from `~/.agents/skills/k-elastic-domain/references/kibana-live-ui.md`,
`~/.agents/skills/k-kbn-stack/references/runtime-lifecycle.md`, `~/.agents/skills/k-elastic-domain/references/kibana-planning-forks.md`,
and `docs/topics/ai-assistants/skills/elastic-and-kibana.md`.

- **Server/API-reachable state** (Kibana route handlers, saved-object/task-manager transitions, anything the Data/setup ladder reaches
  through "local Kibana APIs" or "the registry-resolved Elasticsearch endpoints", `kibana-live-ui.md` Data/setup ladder step 4):
  the adapter calls the PR/head worktree's `kbn_url`/`es_url` resolved from the `,kbn-stack` registry (`~/.cache/kbn-stack/registry.json`),
  the same way `kibana-live-ui.md` Runtime targets resolves them — never a hardcoded port or `*.local` hostname.
  Load `~/.agents/skills/k-kbn-stack/SKILL.md` first for stack start/reuse and registry-entry liveness correlation.
- **UI-only-reachable state** (a transition observable only through the rendered app): the adapter drives Playwriter per
  `~/.agents/skills/k-playwriter/SKILL.md`'s Documentation contract and the readiness/evidence rules in
  `kibana-live-ui.md` Required preflight and `kibana-live-ui-evidence.md` — Playwriter is the required readiness check there;
  WebFetch/`curl` are excluded as readiness evidence.
- **Direct Elasticsearch indexing**: only when the UI cannot faithfully see the state otherwise (`kibana-live-ui.md` Data/setup ladder
  step 4's "use direct Elasticsearch indexing only when that is how the UI can faithfully see the state"), against the registry-resolved
  `es_url`, with temporary identifiers that are easy to find and clean up.
- **Unit/integration test-suite runner selection (jest vs. FTR/TestUtils vs. any other framework)**: Unknown because none of the
  evidenced sources name an invocation command for a specific runner. `kibana-planning-forks.md` names the test-pyramid categories
  ("unit, integration (FTR or TestUtils), functional/e2e?", "Existing FTR API integration tests for the touched area?") as planning
  questions, not adapter commands. Do not invent a `jest`/`FTR`/`Scout` command line; resolve the exact command with the task owner or a
  research packet before wiring an adapter at that level, and report the gap instead of guessing.

## Isolation and teardown

An adapter run is a live-target probe: it inherits `kibana-live-ui.md` Runtime targets' serverless single-instance constraint,
`runtime-lifecycle.md` Isolation Judgment (pass `--isolated-es` when the unit's transitions assert empty state, mutate cluster-wide
settings, or exercise alerting/task-manager runs), and Teardown ownership (stop only a stack this adapter run started, never `--stop-all`).

## Differential replay (`--against`) limits

`,formal replay <unit> --against <base-ref>` differentiates its two runs only by `cwd` and `FORMAL_REPO_ROOT`
(`~/.agents/skills/k-formal/references/adapters.md` `--against` differential mode). A server/API adapter that
only calls the PR/head worktree's live `kbn_url`/`es_url` never reads `FORMAL_REPO_ROOT`: the `<base-ref>`
export and the current-head run both reach the identical running deployment, so the comparison always shows
parity regardless of what changed between the two refs. Such an adapter is not differential and MUST NOT be
used with `replay --against`; keep its unit's MANIFEST `"replay": {"differential": false}` so `,formal` refuses `--against`.
Differential comparison on Kibana needs an adapter that runs the code under
`FORMAL_REPO_ROOT` itself (for example, a jest-level adapter that imports and executes source from that root)
— which exact jest/FTR invocation to use stays Unknown per the Runner choice section above; do not invent one.

## Boundary

This section adds Kibana runner/target policy to the generic `,formal replay` contract; it does not change `,formal` semantics,
evidence types, or the generic-surface prohibition on Kibana/Elastic text (chezmoi repo `AGENTS.md` "AI Setup Contribution Boundary").
