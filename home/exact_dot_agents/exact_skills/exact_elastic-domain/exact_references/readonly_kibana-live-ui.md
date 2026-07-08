# Kibana Live UI Overlay

Kibana live UI target packet for verified `elastic/kibana` `/agent-review`, `live-ui-review`, and `ui-proof` flows.
Use it when no explicit parent/user/repo target packet was supplied.
The runtime targets, preflight, and data/setup ladder below are mode-neutral:
review flows compare PR/head against base, and `ui-proof` verifies the built runtime head-only against its intended visual.

## Runtime targets

Stacks are started per worktree by `,kbn-stack`, which records each running stack in `~/.cache/kbn-stack/registry.json` keyed by absolute worktree path.
Load and follow `~/.agents/skills/kbn-stack/SKILL.md` for command mechanics, registry inspection, required `-K` flag parity, and teardown ownership.
Each entry has `slot`, `branch`, `backend`, `kbn_url`, `es_url`, `cookie_name`, `kbn_flags`, `ready`, `started_by`, and `start_mode`.
Detached agent starts also record `kbn_log`.
`kbn_flags` is the list of extra `key=value` Kibana settings the stack was started with via `,kbn-stack -K`;
it is empty when none were supplied. `ready` is true only once Kibana has answered `/api/status`.
`started_by` is `user` for interactive/manual starts and `agent` for `--detach`;
for legacy entries with no `started_by`, infer `agent` only when recorded process ids are present, otherwise treat the entry as user-owned.
Stacks run on plain `http://localhost:<port>` with a per-slot cookie name, so there are no fixed hostnames or fixed ports to assume.

A stack may be started interactively by the user (tmux) or by an agent in background mode via `,kbn-stack --detach`.
The detach path starts ES + Kibana headless, waits until Kibana is ready, sets `ready: true`, and returns.
Both paths flip the registry entry's `ready` to true once Kibana answers `/api/status`, so a stack the user started by hand in tmux from the current worktree is discoverable here and marked user-owned.
Treat a registry entry as a usable target only when `ready` is true; an entry with `ready: false` is still booting (or failed) and must not be used as a live target.

Backend parallelism: `snapshot` stacks are fully parallel (one per worktree, isolated by slot).
`serverless` stacks are single-instance per host because kbn-es runs fixed `es01`/`es02` Docker containers.
A registry entry with `"exclusive": true` is serverless and only one can be live at a time;
starting a serverless stack for one worktree may tear down another agent-owned serverless stack, but must not auto-stop a user-owned serverless stack.
Do not assume two serverless targets (base and head) can run simultaneously —
if base/head both need serverless, verify them sequentially (start, verify, tear down, then the other).
Return `Blocked` for the serverless single-instance constraint only when sequential verification is itself impossible.
For example, block if the user's serverless stack must stay up; do not treat the constraint as a peer option to skip verification.

The registry is keyed by absolute worktree path. Target identity is based on the reviewed code, not on where the controller happens to run:

- `controller_cwd`: the checkout where the review controller is executing.
- `reviewed_head_worktree`: the checkout for the PR/head branch or commit being reviewed.
- `base_worktree`: optional comparison checkout for the base branch.

For local-changes mode, `controller_cwd` may be `reviewed_head_worktree` when it contains the changed code.
For an explicit PR/branch review launched from another checkout, especially a base/main checkout, `controller_cwd` is not a valid PR/head target unless it is checked out to the reviewed PR/head branch/sha.
Find or create a worktree for the reviewed PR/head branch before live UI, then compute the PR/head registry key from that worktree with `git rev-parse --show-toplevel`.
If no reviewed-head worktree is available and the harness cannot create one, return `Blocked` with target-worktree setup instructions;
never verify PR/head behavior against the base/main runtime.

Resolve targets from the registry; do not hardcode ports or `*.local` hostnames:

Browser targets:

- PR/head branch: the `kbn_url` of the registry entry for `reviewed_head_worktree`.
- Base branch: optional comparison target.
  Use the `kbn_url` of the registry entry for the selected `base_worktree` only when base-vs-head comparison is required and `reviewed_head_worktree` is distinct.
  If no parent/user packet selected a base worktree, use the local default base worktree (`~/work/kibana/main`) only as a fallback comparison target.

Backing/data endpoints:

- PR/head Elasticsearch: the `es_url` of the PR/head worktree's registry entry.
- Base Elasticsearch: optional comparison endpoint from the base worktree's registry entry when a base target is used.

If the registry has no `ready:true` entry for a required worktree (always PR/head, plus base only when comparison is required), the stack is missing — this is a runtime-start step, not a target blocker.
Before reusing a `ready:true` entry, correlate it with liveness evidence for that registry entry:
recorded `kbn_pid`/`es_pid` when present, derived Kibana/ES port listeners for the entry's `slot`, and the referenced `log`/`kbn_log` paths.
Use this only to validate or reject the entry keyed by the reviewed worktree;
never use a port probe to discover or substitute an arbitrary localhost target.
If a ready entry's process/port/log evidence contradicts the registry, treat it as stale or corrupt:
for an agent-owned entry, stop/recreate it when safe; for a user-owned entry, return `Blocked` with the exact `,kbn-stack --stop && ,kbn-stack --detach ...` recovery command.
If the registry has no usable entry after that integrity check, the stack is missing.
In a shell-capable harness you MUST start it yourself with `,kbn-stack --detach` from that worktree and continue once the registry entry reports `ready: true` (see Data/setup ladder Rung 0).
Return `Blocked` for a missing stack only in a read-only/Ask-mode harness or when `,kbn-stack --detach` fails.
Include the exact `,kbn-stack --detach` command for each missing worktree for the user to run. Never probe arbitrary localhost ports.

Teardown ownership: record the registry state before starting anything.
If this worker created a stack with `,kbn-stack --detach`, it is marked `started_by: "agent"` and must be torn down with `,kbn-stack --stop` from that worktree once verification is done.
Report that it was stopped. Do not stop a `started_by: "user"` stack; leave it running and report that it was reused, not started.
If a pre-existing `started_by: "agent"` stack is reused, leave it running unless this worker explicitly replaced it;
report that it was reused as an agent-owned stack. Never use `--stop-all` from a review worker; that is a user-only cleanup.

## Required runtime config

Some Kibana UI/runtime paths are only reachable when the stack runs with extra Kibana settings.
Most often this is a dev/feature flag, e.g. `xpack.index_management.dev.enableSemanticField=true`.
A default `,kbn-stack` start does not enable these, so a stack started or reused without them will not show the path under review.
That would otherwise cost a reconfigure/restart round-trip mid-verification.

`required_kbn_flags` is a list of `key=value` Kibana settings the change under review needs.
The controller resolves it once before the first `live-ui-review` launch and includes it in this packet; this worker does not rediscover it.
When the parent supplies none, treat it as the empty list and start/reuse stacks with default config.

This value flows straight into `,kbn-stack -K`: each `key=value` becomes one `-K key=value` at start time (Rung 0).
The registry entry's `kbn_flags` records what a running stack was started with so a reused stack can be checked for parity.

## Required preflight

- Runtime-start precondition (do this before resolving target URLs): if a required target stack has no `ready:true` registry entry, do not treat the missing URL as a readiness failure.
  Go to Data/setup ladder Rung 0 and start it with `,kbn-stack --detach` plus one `-K key=value` per entry in `required_kbn_flags` (shell-capable harness), then resolve its `kbn_url` and continue preflight.
  The reachability/readiness checks below assume the stacks are up; the "cannot establish readiness -> `Blocked`" and "blocker invalid unless every selected target URL is reported" rules apply only after Rung 0, never as a reason to skip starting a startable stack.
- Dev-optimizer bundle precondition (freshly started snapshot stacks): `,kbn-stack --detach` and the registry `ready:true` flag mean Kibana answered `/api/status` — they do NOT mean the browser plugin bundles are built.
  A dev stack compiles bundles lazily via the `@kbn/optimizer`, so the first browser navigation to a just-started stack can 404 / MIME-error plugin bundles (e.g. `discover.plugin.js`, `lens.plugin.js`) or throw render errors like `Cannot read properties of null (reading 'dataset')` while the optimizer is still building.
  Do not treat this first-load bundle failure as a terminal readiness/bounded-reload blocker:
  first confirm optimizer completion from the registry entry's `kbn_log` when present (detached stacks write `/tmp/kbn-slot<N>.log`), then allow one bounded wait for it and re-navigate.
  Source-verified completion signals include `bundles compiled successfully` from webpack optimizer and `RSPack build completed` from rspack optimizer.
  If `kbn_log` is absent (for example, an interactive tmux stack), use the Kibana pane/log the user or registry evidence identifies;
  do not read the ES-only `log` field as optimizer evidence.
  Only return `Blocked` if bundles still fail to load after the optimizer reports built.
  This wait is compatible with the readiness stability guard (it is a single bounded wait on a log signal, not reload-spamming).
- Required-config precondition (do this when `required_kbn_flags` is non-empty, after resolving each ready target):
  compare the target's registry `kbn_flags` against `required_kbn_flags`.
  If a `ready:true` stack with `started_by: "user"` is missing a required flag, it cannot show the path under review and you cannot safely restart it — return `Blocked` per Data/setup ladder Rung 6 with the exact `,kbn-stack --stop && ,kbn-stack --detach -K <flag> ...` the user must run, naming the affected target(s).
  If a `ready:true` stack with `started_by: "agent"` is missing a required flag, the worker may stop and recreate it only when doing so will not conflict with another active task; record the replacement in the evidence.
  A stack this worker just started via Rung 0 already carries the flags, so no parity check is needed for it.
- Load `~/.agents/skills/kbn-stack/SKILL.md` before starting, stopping, or reusing stack targets.
- Read `~/.agents/skills/playwriter/SKILL.md` and run `playwriter skill` before checking targets.
- Run in a fresh Playwriter session owned by this worker.
- Store owned pages in `state.basePage` and `state.headPage`; do not reuse generic `page`.
- Close only pages this worker created, or leave their URLs in the blocker/evidence.
- Use Playwriter to check every selected exact browser target is reachable and Kibana-ready.
- Verify branch identity with Playwriter evidence where possible.
- First perform readiness only; do not compare UI until every selected target passes readiness.
- Stop after at most two navigations per target during readiness.
- Stop after at most one repeated same-URL/same-snapshot observation.
- A blocker is invalid unless it reports results for every selected exact browser target URL.
- Do not fall back to localhost unless the user explicitly overrides the targets.
- Do not use WebFetch, shell `curl`, or other HTTP-only probes as target readiness evidence.
  They may be supplemental diagnostics, and post-readiness local API calls are allowed for scoped data setup, but Playwriter is the required readiness check.
- Playwriter is the required readiness check for the registry-resolved PR/head and any selected base `kbn_url` targets.
- If Playwriter cannot run because the harness is read-only/Ask-mode, return `Blocked`.
- If Playwriter fails before navigation with `browserType.connectOverCDP: Timeout`:
  - replace the relay once with `playwriter serve --host 127.0.0.1 --replace`
  - create a fresh session
  - smoke-test `context.pages()`
- If the smoke test fails, return `Blocked`; do not navigate or refresh target pages.
- If Playwriter loops, reloads repeatedly, or cannot reach a stable snapshot, return `Blocked`.

## Applicability

- `Not applicable` can be per-target.
  If the feature/surface is absent on base because the PR introduces it, mark base comparison `Not applicable` with evidence and continue head-only verification on the PR/head target when the feature exists there.
- Return full `Not applicable` only when the candidate is not UI/runtime-relevant or the feature/surface is absent from every relevant target.
- Do not return `Not applicable` because the target has no data. Missing data is setup work or `Blocked`.

## Data/setup ladder

Rung 0 — ensure the stack is running with the required config (runtime-start, before any data rung):
if the registry has no `ready:true` entry for a required worktree key (PR/head, plus base when selected), the stack is missing, not the data.
When the harness allows shell side effects, start it yourself with `,kbn-stack --detach` plus one `-K key=value` for each entry in `required_kbn_flags` from that worktree, wait until the registry entry reports `ready: true`, then continue to preflight.
Starting with the required flags here is what avoids a reconfigure/restart round-trip later.
Only in a read-only/Ask-mode harness (or if `,kbn-stack --detach` fails) return `Blocked` with the exact `,kbn-stack --detach -K <flag> ...` command (including every required flag) for each missing worktree for the user to run.
Honor the serverless single-instance constraint (`"exclusive": true`) and the teardown ownership rule under Runtime targets.

The rungs below apply only once every selected required stack reports `ready:true`. If the relevant UI exists but required data is absent:

1. Inspect complete direct PR/issue artifacts already in scope, including screenshots, GIFs, videos, and linked media.
   For videos/GIFs, inspect enough frames to infer the relevant UI state and data shape.
2. Inspect changed tests, fixtures, mocks, story/test helpers, and local route/data mocks to infer the focused data shape.
   Use mocks here to learn the data shape, not as the first verification substrate.
3. Use existing seeded/demo data when it already exercises the path.
4. Create focused isolated local/dev runtime data through one of the allowed paths:
   Playwriter/browser actions, the app's real local APIs, or the registry-resolved Elasticsearch endpoints:
   - base: local Kibana APIs or the base worktree's `es_url` from the registry
   - PR/head: local Kibana APIs or the PR/head worktree's `es_url` from the registry
   - use direct Elasticsearch indexing only when that is how the UI can faithfully see the state
   - use temporary test-only identifiers that are easy to find and clean up
5. If direct local Kibana/Elasticsearch setup fails because of auth, headers, API shape, or transport issues, use Kibana Dev Tools Console.
   Use it on the matching verified target.
   Load `~/.agents/skills/kibana-console-monaco/SKILL.md` when automating Console editor interactions.
6. If faithful setup requires reconfiguring or restarting an already-running ES/Kibana instance in a way this worker cannot safely apply, do not work around it with browser mocks.
   This is not Rung 0, which starts a missing stack via `,kbn-stack --detach`. Return `Blocked` with:
   - affected target(s): base, PR/head, or both
   - exact runtime prerequisite and the evidence that it is required
   - user-action instructions: setting, environment variable, config snippet, command, or dev-server flag when known
   - reload/restart requirement for Kibana/Elasticsearch
   - resume criteria: what the next live-UI run should verify before data ingestion continues
7. Use browser-side route/network mocks, Playwriter-owned in-memory state, or page-level mocks only as a last resort.
   This applies when faithful local/dev runtime setup is unsafe, unavailable, or cannot represent the needed state, and no runtime environment prerequisite would unlock faithful setup.
   Mark this evidence as lower fidelity and explain why earlier setup levels were not used or were insufficient.
8. Clean up seeded data before returning when cleanup is safe.
   If cleanup is not possible or not verified, report the exact leftover objects and why.

## Safety boundary

- Verification only: no repo edits, GitHub mutations, git writes, commits, pushes, or decisions.
- Never use ApplyPatch or file-editing tools.
- Never write files except Playwriter artifacts under `/tmp`, including focused screenshots;
  store each screenshot/pair/set in its own distinct `/tmp/<folder-name>/` directory, never loose directly in `/tmp`.
- Mutating local/dev runtime data via Playwriter/browser actions, local Kibana APIs, Dev Tools Console, or local Elasticsearch API calls is allowed for verification after target readiness/identity is established.
- Do not mutate production, shared cloud, GitHub, git, repo files, committed files, labels, reviews, comments, branches, or user-visible external state.
- Runtime data mutations must be local/dev-only, focused, named in the evidence, tied to the exact target/Elasticsearch endpoint used, and cleaned up or reported.
- Do not apply ES/Kibana runtime environment changes or restart services from this worker.
  Surface them as `Blocked` instructions for the user to apply, then continue in a later run after reload.
- If target identity is ambiguous or appears non-local/non-dev, return `Blocked` instead of mutating.

## Screenshot handoff

- Capture screenshots whenever the generic `live-ui-review` contract requires them for UI findings that may become review feedback.
  Otherwise capture screenshots only when they materially improve a candidate finding or blocker.
  For pre-navigation blockers, record why no screenshot exists.
- Store screenshots as Playwriter artifacts in a distinct `/tmp/<folder-name>/` directory —
  one dedicated folder per single screenshot, per comparison pair (base + PR/head), or per grouped set;
  never loose in `/tmp` and never mixed with an unrelated set. Use descriptive names and preserve handoff files.
  After storing a set, open the enclosing folder for the user when the local environment supports it;
  otherwise report that the folder could not be opened and provide the folder path.
- For each screenshot, record:
  - folder + local file path
  - folder-open/provided status
  - description
  - target classification: PR/head, base, or both selected targets
  - exact URL
  - linked candidate/finding
  - suggested manual review comment placement
  - fidelity note for mocks or partial setup
- The screenshot handoff is for the controller/user only: no image uploads, local paths in GitHub review comments or bodies, or extra comments solely for image paths.
- Proof-mode (`ui-proof`) stores each visual criterion's proof set in its own distinct `/tmp/<folder-name>/` folder (e.g. `/tmp/<topic>-<criterion-slug>/`) and hands the manifest to `compose-pr`; the user attaches the files to the PR body.
  The agent still never uploads images or writes local paths into GitHub.

## Live feedback overlay

When the user wants to point at specific real Kibana UI elements, use `,artifact live` after Playwriter has verified the registry-resolved local/dev `kbn_url`.

- Load and follow `~/.agents/skills/artifact/SKILL.md`.
- Use `,artifact live script <name>` and inject the returned JavaScript into the verified Playwriter page with `page.evaluate`.
- Tell the user capture is armed.
  The overlay intercepts page clicks until paused, uses Shadow DOM, and can be removed without changing the app.
- Keep `,artifact poll <name>` running and treat returned `source: live-overlay` items as user-guided live UI feedback.
- Preserve the screenshot handoff path for async review, visual comparison, or cases where live injection is blocked.

## Controller validation for Kibana overlay

Reject and rerun any `live-ui-review` result for this overlay that:

- reports only generic localhost probing
- omits any selected exact target URL
- uses WebFetch or shell/HTTP probes as readiness evidence
- skips Playwriter target checks
- claims targets are unavailable without showing the exact target/preflight evidence above
- omits the selected `target_packet` / overlay source
- uses browser/route/network mocks for a data-dependent UI finding without first attempting or explicitly ruling out faithful local/dev data setup through existing data, local Kibana/Elasticsearch APIs, or Kibana Dev Tools Console
- uses browser/route/network mocks when faithful verification is blocked by a required ES/Kibana runtime environment change;
  that must be returned as `Blocked` with setup instructions instead
- returns `Blocked` citing a missing/un-started `,kbn-stack` (no `ready:true` registry entry) in a shell-capable harness, instead of starting it with `,kbn-stack --detach` and continuing (Rung 0); rerun after the stack is started
- lists screenshot artifacts without local paths, descriptions, target URL/branch, or linked candidate/finding placement
- omits applicability, exact URLs checked, Playwriter preflight status, readiness result for each target, branch/runtime evidence, comparison evidence for each checked candidate, UI evidence artifact manifest or `none`, page cleanup/owned-page URLs, and blockers/uncertainty

Do not reject or rerun a result that reports a valid Playwriter harness blocker:

- read-only/Ask-mode blocked `playwriter skill` or Playwriter commands
- every selected exact browser target URL was attempted or explicitly blocked before navigation
- repeated reload/same-URL/same-snapshot loop was detected within the readiness stability guard
