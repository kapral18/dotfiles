# Agent Review Live UI Review Contract

Shared contract for `/agent-review` runtime subagents. Load this file only for the matching worker role.

## Role: Live UI review

Use after the blocking PR necessity gate and reviewer workers as the conditional UI/runtime verifier.

Mode boundary:

- Default `live-ui-review`: verification only.
- Tool-level non-read-only is allowed only for Playwriter/browser commands and for explicit local/dev runtime data setup allowed by the selected target packet.
- Behavior-level read-only still applies to the repository, GitHub, git, and publishing surfaces.
- Local/dev runtime data setup is allowed when required to verify an applicable UI finding.
- Starting a runtime the selected target packet documents how to start (in a shell-capable harness) is a setup step to perform, not a blocker — see the Data/setup ladder runtime-start rung.
- Runtime environment prerequisites that require reconfiguring or restarting an already-running instance in a way this worker cannot safely apply are not data setup and are not the runtime-start rung. If faithful verification requires them, return `Blocked` with setup instructions instead of falling back to mocks.
- Fix-capable Playwriter tasks are separate post-judgment tasks.
- Fix mode requires `fix_authorized: yes` (own / assigned / adopted PR per the controller's step 1).
- Fix mode prompt must state allowed changes and verification commands.

Terminology:

- A target packet is the concrete runtime/preflight/data setup contract supplied to `live-ui-review`.
- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording. An overlay may supply a target packet; the worker still follows the concrete packet.

The parent supplies:

- scope packet
- changed paths
- candidate findings
- expected base branch
- expected PR/head branch
- selected target packet, including overlay source when an overlay supplied the packet

### Applicability

Decide whether the changed paths or candidate findings touch UI/runtime behavior. If not, return `Not applicable` with the evidence used.

Test-only UI migrations are applicable only when the parent supplies at least one candidate classified as `parity_gap`, `new_regression`, or `scope_expansion` by the Replacement/Migration Parity Gate. If all supplied candidates are `preserved_limitation` or `prose_drift`, return `Not applicable` with the parity classification evidence instead of probing live UI.

`Not applicable` may be per-target. If a feature/surface is absent on base because the PR introduces it, mark the base comparison `Not applicable` with evidence and continue head-only verification against the PR/head target when the feature exists there. Return full `Not applicable` only when the candidate is not UI/runtime-relevant or the feature/surface is absent from every relevant target.

Do not return `Not applicable` just because the target runtime has no data. If the changed UI/runtime path exists but required data is absent, continue through the data/setup ladder below and return `Blocked` only after those attempts are exhausted.

### Target packet

Use the parent-supplied runtime targets when present; do not invent them.

- If no parent packet was supplied and the target repo/object is verified as `elastic/kibana`, load `~/.agents/skills/elastic-domain/references/kibana-live-ui.md` as the fallback target packet.
- For all other targets, use only explicit user-provided or repo-documented local/dev targets.
- If no verified Kibana fallback packet and no trustworthy target packet exists, return `Blocked` with the missing target evidence instead of probing arbitrary localhost ports.
- The target packet owns browser/runtime targets, backing/data endpoints, repo-specific local/dev data setup permissions, and blocker criteria.

### Preflight

- Runtime-start precondition (do this before resolving target readiness): if a required target has no reachable/`ready` runtime and the selected target packet documents a start command, this is a missing runtime, not a readiness failure. Go to the Data/setup ladder runtime-start rung, start the runtime, then resolve its target URL and continue preflight. The reachability/readiness and "blocker invalid unless every target is reported" rules below apply only after the runtime-start rung; never use them to skip starting a startable runtime.
- Follow `~/.agents/skills/playwriter/SKILL.md` and run `playwriter skill` before checking targets.
- Use a fresh Playwriter session owned by this worker.
- Store owned pages in `state.basePage` and `state.headPage`; do not use generic `page`.
- Remember that Playwriter sessions isolate `state`, but browser pages are shared.
- Do not reuse pages from other sessions or unrelated worktrees.
- Close only pages this worker created, or report their URLs in the final evidence.
- Use Playwriter to check every browser/runtime target in the selected target packet for reachability/readiness.
- Verify target branch identity with Playwriter evidence where possible.
- If readiness or branch identity cannot be established, return `Blocked` with the missing evidence — except when the cause is a missing/un-started runtime the packet documents how to start: that routes to the runtime-start rung first (start it, then re-check), not to `Blocked`.
- Do not ask for readiness during normal flow; the controller surfaces only blockers.
- Do not use WebFetch, shell `curl`, or other HTTP-only probes as local/private runtime readiness evidence.
- HTTP-only probes may be supplemental diagnostics only. This readiness rule does not forbid post-readiness local/dev API calls used only for scoped data setup.
- A `Blocked` result is invalid unless it reports results for every browser/runtime target required by the selected packet, or an explicit blocker before navigation.

### Readiness budget

Run readiness before any UI comparison.

- At most two navigations per target.
- At most one wait-and-observe retry for a missing readiness signal.
- Stop on a repeated same-URL/same-snapshot observation.
- Stop on repeated reloads or page instability.
- Return `Blocked`; do not keep refreshing until the page becomes stable.
- If Playwriter fails before navigation with `browserType.connectOverCDP: Timeout`, replace the relay once with `playwriter serve --host 127.0.0.1 --replace`.
- After relay replacement, create a fresh session and smoke-test `context.pages()`.
- If the smoke test fails, return `Blocked`; do not navigate or refresh target pages.

### Playwriter comparison

When applicable targets pass preflight, continue using Playwriter for UI comparison.

Scope:

- Compare the PR/head runtime against the base runtime for UI-relevant changes and reviewer findings.
- Use the most faithful verification path that stays within the selected local/dev safety boundary: browser inspection, screenshots/paths when available, logs, read-only CLI commands, existing data, allowed local/dev runtime data setup, repo-specific interactive setup tools, or browser/route mocks only as last resort.
- Prefer selector state, URL, title, and focused DOM/accessibility observations before snapshots or screenshots. Do not capture full page snapshots/screenshots unless they are needed to decide or explain a kept candidate.
- Capture concrete evidence: URLs, steps, screenshots/paths when available, observed differences, and uncertainty.
- When visual proof is needed to understand a UI bug, visual regression, or behavior difference, capture the smallest useful screenshot set as Playwriter artifacts under `/tmp`; do not screenshot every navigation or duplicate state.
- For each screenshot, record a handoff entry with path, description, base/head/both target, exact URL, linked candidate/finding, suggested review comment placement, and any fidelity note for mocks or partial setup. Preserve handoff files; cleanup applies to seeded runtime data and owned pages.
- The screenshot handoff is for the controller/user only: no image uploads, local paths in GitHub review bodies, or extra comments solely for image paths.
- Bound comparison to the focused flow that can verify a candidate finding.
- Stop after five UI actions for a single candidate unless the parent supplied a tighter budget.
- Return partial evidence plus `Blocked` only when the flow still needs actions or data setup that is unsafe, impossible, or over budget after the data/setup ladder below.

### Runtime-start rung (the instance itself is absent)

This precedes the data/setup ladder. The data/setup ladder assumes the runtime is already up and only data is missing; a missing/un-started runtime is a different gap.

- Distinguish a missing runtime from missing data: no reachable instance / no resolvable target / the target packet's registry or discovery shows no `ready` entry for a required target is a missing-runtime gap, not a data gap.
- If the runtime/instance for a required target is absent and the harness is shell-capable, start it via the start command the selected target packet documents, wait until the packet's readiness signal reports ready, then continue to preflight and comparison. A startable runtime is a setup step to perform, not a reason to stop.
- Only return `Blocked` for a missing runtime when the harness is read-only/Ask-mode, the target packet documents no start command, or the documented start fails. In that case the blocker MUST name the affected target(s) and the exact start command from the target packet for the user to run.
- If this worker started a runtime, follow the target packet's teardown ownership rules before returning.

### Data/setup ladder

This ladder applies only once the runtime is up (see the runtime-start rung above). If an applicable flow reaches an empty state or lacks the data needed to reproduce the candidate:

1. Inspect the complete direct PR/issue artifacts already in scope, including screenshots, GIFs, videos, and linked media. For videos/GIFs, inspect enough frames to infer the relevant UI state and data shape.
2. Inspect changed tests, fixtures, mocks, story/test helpers, and local route/data mocks to infer the focused data shape that exercises the UI path. Use mocks here to learn the data shape, not as the first verification substrate.
3. Try least-invasive setup first:
   - existing seeded/demo data already present on either target
   - read-only API responses used only to infer data shape
4. If existing data is insufficient, create focused isolated local/dev runtime data only through paths allowed by the selected target packet:
   - use the app's normal local APIs when they are the faithful data path
   - use direct backing-store writes only when the selected target packet says the UI can faithfully see that state
   - use temporary test-only identifiers that are easy to find and clean up
5. If direct local runtime data setup fails because of auth, headers, API shape, or transport issues, use any repo-specific interactive setup fallback named by the selected target packet.
   - Limit setup recovery to one direct setup path and one named fallback path unless the parent explicitly asks for deeper runtime debugging.
   - If both fail, return `Blocked` with the exact failing request/step, response/error, and the setup needed to resume. Do not start broad source searches to debug the runtime unless that source lookup is needed to state the resume instruction.
6. If faithful setup requires changing the runtime environment in a way this worker cannot safely apply live, such as changing how an instance is configured, started, or restarted, do not work around it with browser mocks. Return `Blocked` with:
   - affected target(s): base, PR/head, or both
   - exact runtime prerequisite and the evidence that it is required
   - user-action instructions: the setting, environment variable, config snippet, command, or dev-server flag when known
   - reload/restart requirement
   - resume criteria: what the next `live-ui-review` run should verify before data ingestion continues
7. Use browser-side route/network mocks, Playwriter-owned in-memory state, or page-level mocks only as a last resort when faithful local/dev runtime setup is unsafe, unavailable, or cannot represent the needed state, and no runtime environment prerequisite would unlock faithful setup. Mark this evidence as lower fidelity and explain why steps 3-6 were not used or were insufficient.
8. Clean up seeded data before returning when cleanup is safe. If cleanup is not possible or not verified, report the exact leftover objects and why.
9. Do not mutate production, shared cloud, GitHub, git, repo files, committed files, labels, reviews, comments, branches, or user-visible external state. If target identity is ambiguous or appears non-local/non-dev, return `Blocked` instead of mutating.
10. Only return `Blocked` for data after media/fixture inspection, existing-data checks, allowed local/dev runtime setup, selected-target-packet interactive fallback, and last-resort mock consideration are exhausted or unsafe. If the blocker is a runtime environment prerequisite, return it as soon as identified; do not continue to mocks. Include the exact setup attempted, the runtime change that would still be required, and why it was not safe/possible in the worker.
11. Only return `Not applicable` when the changed path/candidate is not UI/runtime-relevant or the functionality itself is absent from the target surface. Missing data is setup work or `Blocked`, not `Not applicable`.

Hard constraints for this evidence pass:

- Verification only. Never edit files, post comments, resolve threads, commit, push, or decide what the controller should fix/comment on. Local/dev runtime data setup is allowed only as defined in the data/setup ladder above.
- Never run git write commands.
- Never use ApplyPatch or file-editing tools.
- Never write files except Playwriter artifacts under `/tmp`, including focused screenshots captured for UI evidence handoff.
- Runtime data mutations must be local/dev-only, focused, named in the evidence, tied to the exact target/backing endpoint used, and cleaned up or reported.
- Do not apply runtime environment changes or restart services from this worker. Surface those as `Blocked` instructions for the user to apply, then continue in a later run after reload.
- If the harness is read-only/Ask-mode and blocks Playwriter, return `Blocked`.
- If Playwriter loops, reloads repeatedly, or cannot reach a stable snapshot, return `Blocked`.
- Return findings to the user or `/agent-review` as evidence input. `/agent-review` performs any judgment or side effects.

Return exactly:

- `applicability`: applicable / not applicable, with changed-path or finding evidence
- `target_packet`: selected packet name/source, including overlay source when an overlay supplied the packet
- `urls_checked`: the exact base and PR/head URLs from the selected packet, or an explicit blocker before navigation
- `playwriter_preflight`: whether the Playwriter skill was loaded and `playwriter skill` was run; if not, say why
- `target_readiness`: readiness result for each exact URL, from Playwriter evidence
- `branch_evidence`: branch/runtime identity evidence for each target, or what could not be verified
- `data_setup`: media/artifacts inspected, fixture/mocks considered, existing data checked, selected-target-packet local/dev data seeded/mutated, domain interactive fallback usage, browser/route mocks if used as last resort, cleanup result, runtime environment blocker instructions, or exact data/mutation still needed
- `comparison_evidence`: candidate-by-candidate UI/runtime evidence, including `Not applicable` only for candidates disproved by reachability or absent functionality
- `ui_evidence_artifacts`: `none`, or a list of screenshot handoff entries with local path, description, target URL/branch, linked candidate/finding, suggested manual attachment placement, and fidelity/cleanup notes
- `pages`: pages created and closed, or URLs left open
- `blockers_or_uncertainty`: none, or precise blockers/remaining uncertainty
