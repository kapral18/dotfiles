# Live UI phase and result validation

## Merge candidates and run conditional live UI verification

1. **Merge candidates and run conditional live UI verification.**
   - After every launched reviewer lane returns, collapse same-root-cause/same-anchor duplicates into one merged candidate each (merge/dedup only; no new controller investigation).
   - If the merged set is empty, skip live UI, findings audit, and final adversarial verification;
     report the skip reason and continue to action/output with no findings.
   - Immediately after lane merge/dedup, and after the blocking PR necessity gate has passed when it applies, apply a read-only controller parity filter to replacement/test-migration candidates:
     - apply the Replacement/Migration Parity Gate from `judging_core.md` to replacement/test-migration candidates
     - drop candidates classified as `preserved_limitation` or `prose_drift`
     - do not treat test-only UI code as live-UI applicability by itself
   - Launch `k-agent-live-ui-review` when changed paths or any merged candidate touch UI/runtime behavior and runtime evidence is applicable.
     For replacement/test-migration candidates, only `parity_gap`, `new_regression`, and `scope_expansion` can be kept candidates for this trigger.
   - A deterministic, unit, integration, or other-layer proof does NOT discharge a live-UI trigger when the runtime is startable.
     Examples include a resolution/compile harness, a passing test, or a static trace;
     these are corroborating evidence, not substitutes for live verification.
     Once the trigger fires, skipping live UI is valid only via a packet-defined blocker.
     Valid blockers include a read-only/Ask-mode harness, an unstartable runtime, or another blocker the selected target packet recognizes.
     Do not skip because a non-runtime proof already exists or because runtime evidence is judged "unlikely to change the verdict".
     If the runtime is startable (runtime-start rung), start it and verify.
   - Hard runtime read-only/sandbox modes are not the review safety boundary.
     Use harness permissions that allow the lane's permitted verification tools, and enforce no-mutation behavior through the role contract.
   - Use those permissions only for the lane's permitted verification tools: read-only shell/git/`gh` for investigation workers, or the operations permitted by `~/.agents/skills/k-review/references/live-ui-runtime.md` for `k-agent-live-ui-review`.
     The runtime contract retains its verified-target, ownership, and approval limits; this packet grants no additional authority.
   - Mode boundary: default `k-agent-live-ui-review` is verification-only.
   - Keep behavior-level read-only constraints in the prompt:
     - no repo edits
     - no file writes except Playwriter artifacts under `/tmp` and the shared runtime contract's explicitly permitted runtime/connection state and logs
     - no GitHub mutations
     - no git writes
     - no commits or pushes
   - For post-fix UI verification, launch a separate fix-capable Playwriter task after judgment.
   - A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording.
     For live UI, an overlay may provide a concrete target packet; the worker receives the packet, not an unresolved overlay concept.
   - Select a live UI target packet before launch: use the explicit user-provided or repo-documented local/dev packet first.
     Otherwise verify the target repo/org, load its matching domain overlay, and obtain the overlay-owned concrete packet.
     If neither source yields a trustworthy packet, return a target-packet blocker; do not borrow another domain's defaults.
   - Resolve target worktree identity before launch:
     - `controller_cwd` is where the review controller happens to run; it is not automatically the PR/head runtime.
     - `reviewed_head_worktree` is the checkout that contains the code under review for the PR/head branch/sha.
     - For local-changes mode, the current worktree may be `reviewed_head_worktree` only when it contains the changed code being reviewed.
     - For an explicit PR/branch review invoked from another checkout (especially a base/main checkout), do not use `controller_cwd` as the PR/head target unless it is checked out to the reviewed PR/head branch/sha.
       Reuse or create a worktree for the reviewed PR/head branch before live UI, or return a target-worktree blocker with the exact command/setup required.
     - Base/main is comparison-only: resolve/start a base target only when a distinct `reviewed_head_worktree` exists and the target packet requires base-vs-head comparison.
     - Identify which running runtime is head vs base only from the target packet's registry/discovery keyed by worktree path;
       never decide head-vs-base by probing a port, which can mistake an already-running base/main runtime for the head runtime.
   - Resolve required runtime config once, before the first `k-agent-live-ui-review` launch:
     from the changed paths and kept candidates, determine any runtime/feature-flag settings the path under review needs to be reachable.
     Pass them to the worker so the runtime is started correctly the first time instead of started default and reconfigured after a blocker.
     The concrete settings and the start-time mechanism are owned by the selected target packet.
     Keep specific flag names, values, and start mechanisms in the packet/overlay. When none are needed, pass an empty set.
   - Include the selected target/preflight packet and the resolved required runtime config in the worker prompt so the worker starts with it instead of rediscovering it.
   - Windows/VirtualBox coverage is out of scope for this flow: `k-agent-live-ui-review` verifies the local browser only.
     When the user explicitly wants Windows/VirtualBox coverage too, add the manual `~/.agents/skills/k-live-ui-windows/SKILL.md` skill to this turn's work by hand; never infer it from PR/issue context.
   - It returns one of:
     - `Not applicable`
     - comparison evidence with `ui_evidence_artifacts`
     - target/branch/runtime/data blocker for the controller to surface
   - For an applicable UI-related candidate that may become draft review feedback, screenshots are required supporting evidence.
     If `k-agent-live-ui-review` confirms or materially supports the candidate without screenshot handoff entries, rerun the worker or carry a blocker; draft the comment only with screenshot-backed UI evidence.
   - Rerun a blocked live-UI result automatically only for a missing/un-started local runtime in a shell-capable harness when the selected target packet documents a start command.
     That case is the runtime-start rung, not a terminal blocker; have the runtime started and rerun rather than surfacing it as remaining uncertainty.
   - A read-only/Ask-mode Playwriter block is a valid blocker to surface.

## Validate the live UI result

`k-agent-live-ui-review` is the conditional UI/runtime verifier; the phase above owns applicability, mode boundaries, target selection, worktree identity, and required config.
Full worker-facing procedure lives in `~/.agents/skills/k-review/references/live-ui-review.md`, which loads the shared runtime contract `~/.agents/skills/k-review/references/live-ui-runtime.md` (preflight, readiness stability guard, runtime-start rung, data/setup ladder, hard runtime constraints); `live-ui-review.md` adds the base-vs-head Playwriter comparison and the exact return shape.

Controller validation: reject and rerun any `k-agent-live-ui-review` result that:

- does not match the selected target packet
- uses the controller cwd or base/main runtime as the PR/head target for an explicit PR/branch review without proving that checkout is on the reviewed PR/head branch/sha
- reports only generic localhost probing when the packet requires named targets
- omits a required target from the selected packet
- uses WebFetch or shell/HTTP probes as readiness evidence
- skips Playwriter target checks
- claims targets are unavailable without showing the selected target/preflight evidence
- uses browser/route/network mocks for a data-dependent UI finding without first attempting or explicitly ruling out faithful local/dev data setup from the selected target packet
- uses browser/route/network mocks when faithful verification is blocked by a required runtime environment change;
  that must be returned as `Blocked` with setup instructions instead
- returns `Blocked` for a missing/un-started local runtime in a shell-capable harness when the selected target packet documents a start command (the runtime-start rung); the worker should start it and continue, so rerun after the runtime is started
- lists screenshot artifacts without local paths, descriptions, target URL/branch, linked candidate/finding placement, suggested embedding placement, or fidelity/cleanup notes
- returns applicable UI comparison evidence for a finding that may become draft review feedback with `ui_evidence_artifacts: none` and no valid blocker/non-applicability result
- omits applicability, exact URLs checked, browser preflight status, readiness result for each target, branch/runtime evidence, comparison evidence for each checked candidate, UI evidence artifact manifest or `none`, page cleanup/owned-page URLs, and blockers/uncertainty
- omits the selected `target_packet` source, including overlay source when an overlay supplied the packet

Do not reject or rerun a result that reports a valid Playwriter harness blocker:

- read-only/Ask-mode blocked Playwriter

- every selected exact browser/runtime target URL was attempted or explicitly blocked before navigation
- repeated reload/same-URL/same-snapshot loop was detected within the readiness stability guard
