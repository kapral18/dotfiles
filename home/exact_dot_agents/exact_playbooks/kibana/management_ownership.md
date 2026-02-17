# Kibana Management Ownership Guidance

This guidance is derived from a point-in-time scan of `elastic/kibana` `.github/CODEOWNERS`.
Always verify against the current CODEOWNERS in the repo when in doubt.

Use it to:

- infer `Team:Kibana Management` label proposals
- infer likely reviewers/ownership when composing PRs/issues
- sanity-check whether a change falls under the team's umbrella

When NOT to use:

- you cannot verify the current repo is `elastic/kibana` or you don't have the repo's current CODEOWNERS available
- the change is clearly outside the listed owned areas

Owned areas (non-exhaustive excerpt):

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
