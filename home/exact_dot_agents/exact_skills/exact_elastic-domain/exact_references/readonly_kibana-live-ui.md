# Kibana Live UI Overlay

Kibana live UI target packet for verified `elastic/kibana` `/agent-review` and `live-ui-review` flows when no explicit parent/user/repo target packet was supplied.

## Runtime targets

Stacks are started per worktree by `,kbn-stack`, which records each running stack in `~/.cache/kbn-stack/registry.json` keyed by absolute worktree path. Each entry has `slot`, `branch`, `backend`, `kbn_url`, `es_url`, `cookie_name`, and `ready` (true only once Kibana has answered `/api/status`). Stacks run on plain `http://localhost:<port>` with a per-slot cookie name, so there are no fixed hostnames or fixed ports to assume.

A stack may be started interactively by the user (tmux) or by an agent in background mode via `,kbn-stack --detach`, which starts ES + Kibana headless, waits until Kibana is ready, sets `ready: true`, and returns. Both paths flip the registry entry's `ready` to true once Kibana answers `/api/status`, so a stack the user started by hand in tmux from the current worktree is discoverable here. Treat a registry entry as a usable target only when `ready` is true; an entry with `ready: false` is still booting (or failed) and must not be used as a live target.

Backend parallelism: `snapshot` stacks are fully parallel (one per worktree, isolated by slot). `serverless` stacks are single-instance per host (kbn-es runs fixed `es01`/`es02` Docker containers), so a registry entry with `"exclusive": true` is serverless and only one can be live at a time; starting a serverless stack for one worktree tears down any other serverless stack. Do not assume two serverless targets (base and head) can run simultaneously — if base/head both need serverless, they cannot both be live, so verify them sequentially or return `Blocked` noting the serverless single-instance constraint.

The registry is keyed by absolute worktree path. Compute the current PR/head worktree key the same way `,kbn-stack` does: the resolved absolute path of `git rev-parse --show-toplevel` run from the agent's working directory. Look that key up in the registry to find the stack for the worktree the agent is reviewing from, including one the user started interactively in a tmux pane in that same worktree.

Resolve targets from the registry; do not hardcode ports or `*.local` hostnames:

Browser targets:

- Base branch: the `kbn_url` of the registry entry for the base worktree (the `main` worktree under `~/work/kibana/main`).
- PR/head branch: the `kbn_url` of the registry entry for the current PR/head worktree key resolved above.

Backing/data endpoints:

- Base Elasticsearch: the `es_url` of the base worktree's registry entry.
- PR/head Elasticsearch: the `es_url` of the PR/head worktree's registry entry.

If the registry has no entry for a required worktree, the entry's `ready` is not true, or `,kbn-stack` is not running for it, return `Blocked` with the missing target evidence instead of probing arbitrary localhost ports. When the harness allows shell side effects, an agent may start a missing stack itself with `,kbn-stack --detach` run from that worktree and continue once the registry entry reports `ready: true`; in read-only/Ask-mode harnesses, return `Blocked` with the exact `,kbn-stack --detach` command for the user to run.

Teardown ownership: if this worker started a stack with `,kbn-stack --detach`, tear it down with `,kbn-stack --stop` from that worktree once verification is done, and report that it was stopped. Do not stop a stack the user started interactively (one that was already `ready` in the registry before this worker ran) — leave it running and report that it was reused, not started. Never use `--stop-all` from a review worker; that is a user-only cleanup.

## Required preflight

- Read `~/.agents/skills/playwriter/SKILL.md` and run `playwriter skill` before checking targets.
- Run in a fresh Playwriter session owned by this worker.
- Store owned pages in `state.basePage` and `state.headPage`; do not reuse generic `page`.
- Close only pages this worker created, or leave their URLs in the blocker/evidence.
- Use Playwriter to check both exact browser targets are reachable and Kibana-ready.
- Verify branch identity with Playwriter evidence where possible.
- First perform readiness only; do not compare UI until both targets pass readiness.
- Stop after at most two navigations per target during readiness.
- Stop after at most one repeated same-URL/same-snapshot observation.
- A blocker is invalid unless it reports results for both exact browser target URLs.
- Do not fall back to localhost unless the user explicitly overrides the targets.
- Do not use WebFetch, shell `curl`, or other HTTP-only probes as target readiness evidence. They may be supplemental diagnostics, and post-readiness local API calls are allowed for scoped data setup, but Playwriter is the required readiness check.
- Playwriter is the required readiness check for the registry-resolved base and PR/head `kbn_url` targets.
- If Playwriter cannot run because the harness is read-only/Ask-mode, return `Blocked`.
- If Playwriter fails before navigation with `browserType.connectOverCDP: Timeout`:
  - replace the relay once with `playwriter serve --host 127.0.0.1 --replace`
  - create a fresh session
  - smoke-test `context.pages()`
- If the smoke test fails, return `Blocked`; do not navigate or refresh target pages.
- If Playwriter loops, reloads repeatedly, or cannot reach a stable snapshot, return `Blocked`.

## Applicability

- `Not applicable` can be per-target. If the feature/surface is absent on base because the PR introduces it, mark base comparison `Not applicable` with evidence and continue head-only verification on the PR/head target when the feature exists there.
- Return full `Not applicable` only when the candidate is not UI/runtime-relevant or the feature/surface is absent from every relevant target.
- Do not return `Not applicable` because the target has no data. Missing data is setup work or `Blocked`.

## Data/setup ladder

If the relevant UI exists but required data is absent:

1. Inspect complete direct PR/issue artifacts already in scope, including screenshots, GIFs, videos, and linked media. For videos/GIFs, inspect enough frames to infer the relevant UI state and data shape.
2. Inspect changed tests, fixtures, mocks, story/test helpers, and local route/data mocks to infer the focused data shape. Use mocks here to learn the data shape, not as the first verification substrate.
3. Use existing seeded/demo data when it already exercises the path.
4. Create focused isolated local/dev runtime data through Playwriter/browser actions, the app's real local APIs, or the registry-resolved Elasticsearch endpoints:
   - base: local Kibana APIs or the base worktree's `es_url` from the registry
   - PR/head: local Kibana APIs or the PR/head worktree's `es_url` from the registry
   - use direct Elasticsearch indexing only when that is how the UI can faithfully see the state
   - use temporary test-only identifiers that are easy to find and clean up
5. If direct local Kibana/Elasticsearch setup fails because of auth, headers, API shape, or transport issues, use Kibana Dev Tools Console on the matching verified target. Load `~/.agents/skills/kibana-console-monaco/SKILL.md` when automating Console editor interactions.
6. If faithful setup requires changing how an ES/Kibana instance is configured, started, or restarted, do not work around it with browser mocks. Return `Blocked` with:
   - affected target(s): base, PR/head, or both
   - exact runtime prerequisite and the evidence that it is required
   - user-action instructions: setting, environment variable, config snippet, command, or dev-server flag when known
   - reload/restart requirement for Kibana/Elasticsearch
   - resume criteria: what the next live-UI run should verify before data ingestion continues
7. Use browser-side route/network mocks, Playwriter-owned in-memory state, or page-level mocks only as a last resort when faithful local/dev runtime setup is unsafe, unavailable, or cannot represent the needed state, and no runtime environment prerequisite would unlock faithful setup. Mark this evidence as lower fidelity and explain why earlier setup levels were not used or were insufficient.
8. Clean up seeded data before returning when cleanup is safe. If cleanup is not possible or not verified, report the exact leftover objects and why.

## Safety boundary

- Verification only: no repo edits, GitHub mutations, git writes, commits, pushes, or decisions.
- Never use ApplyPatch or file-editing tools.
- Never write files except Playwriter artifacts under `/tmp`, including focused screenshots.
- Mutating local/dev runtime data via Playwriter/browser actions, local Kibana APIs, Dev Tools Console, or local Elasticsearch API calls is allowed for verification after target readiness/identity is established.
- Do not mutate production, shared cloud, GitHub, git, repo files, committed files, labels, reviews, comments, branches, or user-visible external state.
- Runtime data mutations must be local/dev-only, focused, named in the evidence, tied to the exact target/Elasticsearch endpoint used, and cleaned up or reported.
- Do not apply ES/Kibana runtime environment changes or restart services from this worker. Surface them as `Blocked` instructions for the user to apply, then continue in a later run after reload.
- If target identity is ambiguous or appears non-local/non-dev, return `Blocked` instead of mutating.

## Screenshot handoff

- Capture screenshots only when they materially improve a candidate finding or blocker.
- Store screenshots as Playwriter artifacts under `/tmp`, use descriptive names, and preserve handoff files.
- For each screenshot, record:
  - local path
  - description
  - base/head/both target
  - exact URL
  - linked candidate/finding
  - suggested manual review comment placement
  - fidelity note for mocks or partial setup
- The screenshot handoff is for the controller/user only: no image uploads, local paths in GitHub review comments or bodies, or extra comments solely for image paths.

## Controller validation for Kibana overlay

Reject and rerun any `live-ui-review` result for this overlay that:

- reports only generic localhost probing
- omits either exact target URL
- uses WebFetch or shell/HTTP probes as readiness evidence
- skips Playwriter target checks
- claims targets are unavailable without showing the exact target/preflight evidence above
- omits the selected `target_packet` / overlay source
- uses browser/route/network mocks for a data-dependent UI finding without first attempting or explicitly ruling out faithful local/dev data setup through existing data, local Kibana/Elasticsearch APIs, or Kibana Dev Tools Console
- uses browser/route/network mocks when faithful verification is blocked by a required ES/Kibana runtime environment change; that must be returned as `Blocked` with setup instructions instead
- lists screenshot artifacts without local paths, descriptions, target URL/branch, or linked candidate/finding placement
- omits applicability, exact URLs checked, Playwriter preflight status, readiness result for each target, branch/runtime evidence, comparison evidence for each checked candidate, UI evidence artifact manifest or `none`, page cleanup/owned-page URLs, and blockers/uncertainty

Do not reject or rerun a result that reports a valid Playwriter harness blocker:

- read-only/Ask-mode blocked `playwriter skill` or Playwriter commands
- both exact browser target URLs were attempted or explicitly blocked before navigation
- repeated reload/same-URL/same-snapshot loop was detected within the budget
