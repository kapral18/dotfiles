---
name: kibana-management-ownership
description: |-
  Use when the user asks about CODEOWNERS / ownership / reviewers for
  elastic/kibana Management areas. Verify current repo/CODEOWNERS first;
  do not answer from the excerpt alone.
---

# Kibana Management Ownership Guidance

This guidance is derived from a point-in-time scan of `elastic/kibana`
`.github/CODEOWNERS`. Always verify against the current CODEOWNERS in the repo
when in doubt.

Use when:

- the direct ask is about `CODEOWNERS`, reviewers, ownership, or whether a
  change likely falls under Kibana Management
- a loaded Elastic compose/label playbook needs Kibana reviewer/ownership
  guidance

Use it to:

- infer `Team:Kibana Management` label proposals
- infer likely reviewers/ownership when composing PRs/issues
- sanity-check whether a change falls under the team's umbrella

Do not use:

- you cannot verify the current repo is `elastic/kibana` or you don't have the
  repo's current CODEOWNERS available
- the change is clearly outside the listed owned areas

First actions:

1. Verify the current repo is `elastic/kibana`.
2. Read the current `.github/CODEOWNERS` in that repo before trusting this
   guidance.
3. Map the changed paths/areas to current CODEOWNERS first, then use the list
   below only as a shortcut/sanity check.

Output:

- Return the exact paths or areas you mapped, the current ownership signal you
  verified, and any remaining heuristic guess separately.
- Do not present this file's excerpt as authoritative when the live CODEOWNERS
  check is missing.

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
