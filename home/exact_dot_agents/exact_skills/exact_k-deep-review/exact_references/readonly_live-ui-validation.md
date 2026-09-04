# Live ui validation

## Live UI review

`k-agent-live-ui-review` is the conditional UI/runtime verifier from the "Merge candidates and run conditional live UI verification" orchestration phase: applicability trigger, mode boundary, target-packet selection, worktree identity, and required runtime config are owned there.
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
