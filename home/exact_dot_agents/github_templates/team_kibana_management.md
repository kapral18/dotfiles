# Kibana Management Ownership (Agent Guidance)

This file captures Kibana Management-owned areas in `elastic/kibana` based on CODEOWNERS.

Use it to:
- infer `Team:Kibana Management` label proposals
- infer likely reviewers/ownership when composing PRs/issues
- sanity-check whether a change falls under the team's umbrella

Source:
- `elastic/kibana` `.github/CODEOWNERS`

Owned areas (non-exhaustive excerpt; prefer checking CODEOWNERS when in doubt):
- `src/platform/plugins/shared/console`
- `src/platform/plugins/shared/dev_tools`
- `src/platform/plugins/shared/management`
- `src/platform/plugins/private/advanced_settings`
- `src/platform/packages/shared/kbn-management/**`
- `src/platform/packages/shared/kbn-unsaved-changes-prompt`
- `x-pack/platform/plugins/private/grokdebugger`
- `x-pack/platform/plugins/private/index_lifecycle_management`
- `x-pack/platform/plugins/private/license_api_guard`
- `x-pack/platform/plugins/private/painless_lab`
- `x-pack/platform/plugins/private/reindex_service`
- `x-pack/platform/plugins/private/remote_clusters`
- `x-pack/platform/plugins/private/snapshot_restore`
- `x-pack/platform/plugins/private/transform`
- `x-pack/platform/plugins/private/upgrade_assistant`
- `x-pack/platform/plugins/private/watcher`
- `x-pack/platform/plugins/shared/index_management`
- `x-pack/platform/plugins/shared/ingest_pipelines`
- `x-pack/platform/plugins/shared/license_management`
- `x-pack/platform/plugins/shared/searchprofiler`

Note: this list is derived from a point-in-time scan; always verify against the current CODEOWNERS in the repo.
