# Live UI Runtime Contract (shared)

Mode-neutral runtime machinery shared by the live-UI workers.
Both the review-mode contract (`~/.agents/skills/agent-review/references/live-ui-review.md`) and the proof-mode contract (`~/.agents/skills/ui-proof/SKILL.md`) load this file.
It owns target-packet resolution, Playwriter preflight, readiness, runtime start, data/setup, screenshot artifacts, and the runtime safety boundary.
The loading mode file owns its oracle (what evidence is judged against), its caller inputs, its comparison model, and its return shape.

Throughout this file, "the runtime under verification" is the checkout/runtime that holds the code being verified:
the reviewed PR/head worktree in review mode, or the built/changed worktree in proof mode.

## Mode boundary

- Default: verification only.
- Tool-level non-read-only is allowed only for Playwriter/browser commands.
  It is also allowed for explicit local/dev runtime data setup permitted by the selected target packet.
- Behavior-level read-only still applies to the repository, GitHub, git, and publishing surfaces.
- Local/dev runtime data setup is allowed when required to verify an applicable UI/runtime path.
- Starting a runtime the selected target packet documents how to start (in a shell-capable harness) is a setup step to perform, not a blocker.
  See the Data/setup ladder runtime-start rung.
- Runtime environment prerequisites are not data setup and are not the runtime-start rung.
  This covers prerequisites that require reconfiguring or restarting an already-running instance in a way this worker cannot safely apply.
  If faithful verification requires them, return `Blocked` with setup instructions instead of falling back to mocks.

## Terminology

- A target packet is the concrete runtime/preflight/data setup contract supplied to the worker.
- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording.
  An overlay may supply a target packet; the worker still follows the concrete packet.

## Target packet

Use the caller-supplied runtime targets when present; do not invent them.

- Treat the runtime under verification as the runtime that contains the code being verified.
  The controller cwd is only execution context; it is not a target unless it is the same checkout and branch/sha as the code under verification.
- If the caller requests a specific PR/branch target but supplies only a base/main checkout as that target, return `Blocked` with a target-worktree blocker.
  Do not navigate, start, or validate a base/main runtime as if it were the PR/head runtime.
- Base targets are comparison-only and exist only when the caller's mode selects a base comparison.
  Use or start a base runtime only when the selected packet requires comparison and a distinct runtime under verification exists.
- If no caller-supplied packet was supplied and the target repo/object is verified as `elastic/kibana`, load the fallback target packet.
  The fallback packet is `~/.agents/skills/elastic-domain/references/kibana-live-ui.md`.
- For all other targets, use only explicit user-provided or repo-documented local/dev targets.
- If no verified Kibana fallback packet and no trustworthy target packet exists, return `Blocked` with the missing target evidence instead of probing arbitrary localhost ports.
- The target packet owns browser/runtime targets, backing/data endpoints, repo-specific local/dev data setup permissions, and blocker criteria.

## Preflight

- Runtime-start precondition (do this before resolving target readiness): a required target with no reachable/`ready` runtime is a missing runtime, not a readiness failure.
  This applies when the selected target packet documents a start command.
  Go to the Data/setup ladder runtime-start rung, start the runtime, then resolve its target URL and continue preflight.
  The reachability/readiness and "blocker invalid unless every target is reported" rules below apply only after the runtime-start rung;
  never use them to skip starting a startable runtime.
- Follow `~/.agents/skills/playwriter/SKILL.md` and run `playwriter skill` before checking targets.
- Use a fresh Playwriter session owned by this worker.
- Store owned pages under distinct `state` keys (e.g. `state.headPage`, and `state.basePage` only when a base comparison is selected);
  do not use generic `page`.
- Remember that Playwriter sessions isolate `state`, but browser pages are shared.
- Do not reuse pages from other sessions or unrelated worktrees.
- Close only pages this worker created, or report their URLs in the final evidence.
- Use Playwriter to check every browser/runtime target in the selected target packet for reachability/readiness.
- Verify target branch identity with Playwriter evidence where possible.
- Before any UI observation, verify the target identity from the selected packet.
  If the target URL resolves to the base/main worktree or to the controller cwd while the runtime under verification is elsewhere, return `Blocked`; do not continue with the wrong-runtime evidence.
- If readiness or branch identity cannot be established, return `Blocked` with the missing evidence —
  except when the cause is a missing/un-started runtime the packet documents how to start:
  that routes to the runtime-start rung first (start it, then re-check), not to `Blocked`.
- Do not ask for readiness during normal flow; the caller surfaces only blockers.
- Do not use WebFetch, shell `curl`, or other HTTP-only probes as local/private runtime readiness evidence.
- HTTP-only probes may be supplemental diagnostics only.
  This readiness rule does not forbid post-readiness local/dev API calls used only for scoped data setup.
- A `Blocked` result is invalid unless it reports results for every browser/runtime target required by the selected packet.
  The only exception is an explicit blocker before navigation.

## Readiness stability guard

Run readiness before any UI observation.

- At most two navigations per target.
- At most one wait-and-observe retry for a missing readiness signal.
- Stop on a repeated same-URL/same-snapshot observation.
- Stop on repeated reloads or page instability.
- Return `Blocked`; do not keep refreshing until the page becomes stable.
- If Playwriter fails before navigation with `browserType.connectOverCDP: Timeout`, replace the relay once.
  Use `playwriter serve --host 127.0.0.1 --replace`.
- After relay replacement, create a fresh session and smoke-test `context.pages()`.
- If the smoke test fails, return `Blocked`; do not navigate or refresh target pages.

## Screenshot & evidence capture

- Prefer selector state, URL, title, and focused DOM/accessibility observations before snapshots or screenshots.
  Do not capture full page snapshots/screenshots unless they are needed to decide or explain the finding or proof under capture.
- Capture concrete evidence: URLs, steps, screenshots/paths when available, observed state, and uncertainty.
- When visual proof is needed, capture the smallest useful screenshot set as Playwriter artifacts.
  Store them in a distinct `/tmp/<folder-name>/` directory — one dedicated folder per single screenshot, per comparison pair (e.g. base + the runtime under verification), or per logically grouped set that proves one thing.
  Never write screenshots loose in `/tmp`, and never mix an unrelated screenshot/pair/set into the same folder.
  Name the folder for what it captures (the finding, candidate, or acceptance criterion) so sibling sets stay separate and openable on their own.
  Do not screenshot every navigation or duplicate state.
- For each screenshot, record a handoff entry with its folder and file path, description, target classification (the runtime under verification, base, or both selected targets), exact URL, the linked candidate/finding or acceptance criterion, and suggested placement.
  Include any fidelity note for mocks or partial setup. Preserve handoff files; cleanup applies to seeded runtime data and owned pages.
- The screenshot handoff is for the controller/user only.
  Never upload images or put local paths in GitHub review bodies/comments, and never add extra comments solely for image paths;
  when screenshots belong in a PR body, the user attaches them.
- Bound observation to the focused flow that can verify the finding or acceptance criterion.
- Do not wander outside that focused flow.
  After five UI actions for a single finding or criterion, continue only when the next action is specifically tied to it and still inside the selected local/dev safety boundary.

## Runtime-start rung (the instance itself is absent)

This precedes the data/setup ladder.
The data/setup ladder assumes the runtime is already up and only data is missing; a missing/un-started runtime is a different gap.

- Distinguish a missing runtime from missing data.
  No reachable instance, no resolvable target, or no `ready` entry in the target packet's registry/discovery for a required target is a missing-runtime gap, not a data gap.
- If the runtime/instance for a required target is absent and the harness is shell-capable, start it via the start command the selected target packet documents.
  Apply the caller-supplied required runtime config through the mechanism the packet defines.
  Wait until the packet's readiness signal reports ready, then continue to preflight and observation.
  Starting with the required config in one shot is what avoids a reconfigure/restart round-trip mid-verification.
  A startable runtime is a setup step to perform, not a reason to stop.
- Only return `Blocked` for a missing runtime when the harness is read-only/Ask-mode, the target packet documents no start command, or the documented start fails.
  In that case the blocker MUST name the affected target(s) and the exact start command from the target packet for the user to run.
- If this worker started a runtime, follow the target packet's teardown ownership rules before returning.

## Data/setup ladder

This ladder applies only once the runtime is up (see the runtime-start rung above).
If an applicable flow reaches an empty state or lacks the data needed to exercise the path under verification:

1. Inspect the complete direct PR/issue artifacts already in scope, including screenshots, GIFs, videos, and linked media.
   For videos/GIFs, inspect enough frames to infer the relevant UI state and data shape.
2. Inspect changed tests, fixtures, mocks, story/test helpers, and local route/data mocks to infer the focused data shape that exercises the UI path.
   Use mocks here to learn the data shape, not as the first verification substrate.
3. Try least-invasive setup first:
   - existing seeded/demo data already present on either target
   - read-only API responses used only to infer data shape
4. If existing data is insufficient, create focused isolated local/dev runtime data only through paths allowed by the selected target packet:
   - use the app's normal local APIs when they are the faithful data path
   - use direct backing-store writes only when the selected target packet says the UI can faithfully see that state
   - use temporary test-only identifiers that are easy to find and clean up
5. If direct local runtime data setup fails because of auth, headers, API shape, or transport issues, use a repo-specific interactive setup fallback.
   Use only fallbacks named by the selected target packet.
   - Limit setup recovery to one direct setup path and one named fallback path unless the caller explicitly asks for deeper runtime debugging.
   - If both fail, return `Blocked` with the exact failing request/step, response/error, and the setup needed to resume.
     Do not start broad source searches to debug the runtime unless that source lookup is needed to state the resume instruction.
6. If faithful setup requires changing the runtime environment in a way this worker cannot safely apply live, do not work around it with browser mocks.
   Examples include changing how an instance is configured, started, or restarted. Return `Blocked` with:
   - affected target(s): base, the runtime under verification, or both
   - exact runtime prerequisite and the evidence that it is required
   - user-action instructions: the setting, environment variable, config snippet, command, or dev-server flag when known
   - reload/restart requirement
   - resume criteria: what the next run should verify before data ingestion continues
7. Use browser-side route/network mocks, Playwriter-owned in-memory state, or page-level mocks only as a last resort.
   This applies when faithful local/dev runtime setup is unsafe, unavailable, or cannot represent the needed state, and no runtime environment prerequisite would unlock faithful setup.
   Mark this evidence as lower fidelity and explain why steps 3-6 were not used or were insufficient.
8. Clean up seeded data before returning when cleanup is safe.
   If cleanup is not possible or not verified, report the exact leftover objects and why.
9. Do not mutate production, shared cloud, GitHub, git, repo files, committed files, labels, reviews, comments, branches, or user-visible external state.
   If target identity is ambiguous or appears non-local/non-dev, return `Blocked` instead of mutating.
10. Only return `Blocked` for data after the allowed setup ladder is exhausted or unsafe.
    The ladder includes media/fixture inspection, existing-data checks, allowed local/dev runtime setup, selected-target-packet interactive fallback, and last-resort mock consideration.
    If the blocker is a runtime environment prerequisite, return it as soon as identified; do not continue to mocks.
    Include the exact setup attempted, the runtime change that would still be required, and why it was not safe/possible in the worker.
11. Only return `Not applicable` when the changed path/candidate/criterion is not UI/runtime-relevant or the functionality itself is absent from the target surface.
    Missing data is setup work or `Blocked`, not `Not applicable`.

## Hard runtime constraints

- Verification only. Never edit files, post comments, resolve threads, commit, push, or decide what the caller should fix/comment on.
  Local/dev runtime data setup is allowed only as defined in the data/setup ladder above.
- Never run git write commands.
- Never use ApplyPatch or file-editing tools.
- Never write files except Playwriter artifacts under `/tmp`, including focused screenshots captured for UI evidence handoff;
  store each screenshot/pair/set in its own distinct `/tmp/<folder-name>/` directory, never loose directly in `/tmp`.
- Runtime data mutations must be local/dev-only, focused, named in the evidence, and tied to the exact target/backing endpoint used.
  They must be cleaned up or reported.
- Do not apply runtime environment changes or restart services from this worker.
  Surface those as `Blocked` instructions for the user to apply, then continue in a later run after reload.
- If the harness is read-only/Ask-mode and blocks Playwriter, return `Blocked`.
- If Playwriter loops, reloads repeatedly, or cannot reach a stable snapshot, return `Blocked`.
