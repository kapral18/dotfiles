# Kibana Planning Fork Checklist

Domain-seeded fork inventory for planning work targeting `elastic/kibana`.
Consult this list during the `spec` skill's fork-closing step (or any SOP §3.0 intent loop on a Kibana change) to surface forks the generic loop would rediscover late.
Evidence-first still applies: answer each item from the issue, diff, or codebase before asking; only genuine gaps become user questions.
Most items resolve to "not applicable" for small changes — skip silently; this is a fork detector, not a questionnaire to transcribe into the packet.

Provenance: adapted from the `elicitation_questions` in `elastic/plan` `prompts/teams/elastic-kibana/*.yaml` (main @ f6aeec5, 2026-07).
To refresh: re-read that directory in the upstream repo and fold in new/changed questions; keep this file curated, not mirrored.

## API surface

- New public HTTP API endpoints? If so, versioned with the date-format versioning scheme?
- New/modified HTTP routes: internal or public?
- Does the plan break any public HTTP API, Saved Object schema, or exported TypeScript interface?

## Saved Objects

- New or modified SO types? Names? Migrations written for every state change?
- Any SO attributes holding credentials, API keys, tokens, or PII — is Encrypted Saved Objects planned?
- Space-aware: isolated per space or shared across spaces?

## Security

- What feature privileges are registered, and what actions (read/all/manage) do they gate?
- New Elasticsearch queries over user-controlled SO data (e.g. aggregations)?
- Any routes calling Elasticsearch as `kibana_system` on behalf of Kibana itself rather than the end user?
- Does the change touch authn/authz/encryption code that needs a security-aware reviewer?

## Architecture and dependencies

- Cross-plugin or internal to one plugin? If cross-plugin, how are contracts defined?
- New third-party npm dependencies? Alternatives considered; Snyk score ≥ 70; which team owns them in `renovate.json`?

## Rollout

- Feature flag needed (incremental rollout or Feature Freeze proximity)? Proposed flag name and registration point?
- Backports required to released branches? (Supported matrix: `versions.json` on main.)

## Testing

- All three pyramid levels planned where they apply: unit, integration (FTR or TestUtils), functional/e2e?
- Existing FTR API integration tests for the touched area?
- New user-facing UI flows (pages, modals, multi-step interactions) that need browser-level tests?
- New server-side service classes or non-trivial standalone utilities that need unit coverage?
- Where do tests live: alongside source, integration suite, or FTR suite?

## Alerting (only when touching the alerting framework)

- New rule type, modified rule executor, or alerting plugin API interaction?
- Action connectors or notification channels added/modified?

## Observability instrumentation

- New user-facing functionality: which user actions must be measured (usage collectors, EBT events)?
- Modifying an existing usage collector or EBT event schema?
