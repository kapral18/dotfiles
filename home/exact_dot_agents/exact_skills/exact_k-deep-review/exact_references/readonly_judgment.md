# Judgment

1. **Aggregate.**
   Combine `k-agent-pr-necessity-auditor` greenlight/skip status, each angle lane's output, fresh-eyes output or its skip reason, the verification ledger, live UI evidence/status/artifacts, findings audit result, and final adversarial verification verdicts/family status.
2. **Judge in the controller.**
   - Apply mode-correct reconciliation:
     - all modes: collapse duplicate worker findings, apply the severity model, and keep findings that are implementation-verified, not covered by existing evidence, and not dropped by the parity/deduplication filters.
       If a candidate is not yet implementation-verified because verification was unsafe, mutating, or required a shared/exclusive resource, carry its `verification_needed` in the ledger instead of dropping it.
     - PR modes: apply `pr_common.md` Deduplication + Truth Filter, Existing Pending Review Reconciliation, and CI Coverage Gate, plus `pr_context_audits.md` PR Necessity + Correctly-Open Audit classifications
     - local-changes mode: judge against the staged/unstaged/range scope in the packet;
       PR-thread deduplication and PR CI coverage exemptions apply only to PR modes
   - Judge fresh-eyes clarity candidates with full context, with one guard: a PR body, commit message, or thread that explains the confusing code does not refute the finding — the lane's premise is that the code alone failed to carry that context.
     Use the context to choose the fix (why-comment, rename, extraction), not to drop the finding. Clarity findings cap at MEDIUM.
   - For PR modes, read any current-account pending review and already-submitted current-account review comments/replies before drafting payloads.
     Merge kept pending findings with kept new findings into one final draft; drop stale pending findings with evidence;
     block rather than producing competing or contradictory payloads.
   - For kept UI findings that may become human-visible review feedback, require valid screenshot handoff entries before drafting.
     Before any worker-produced image is uploaded, embedded, or referenced in human-visible output, the controller MUST view every image itself with the view tool and compare it to the claimed caption and finding.
     Reject and re-task on mismatch: illegible crops, duplicate/byte-identical files under different captions, mid-animation captures, wrong target, wrong state, or any image that does not prove the claimed behavior.
     Every published image is controller-viewed first.
     Verify screenshot paths when possible and surface them only in final `UI evidence attachments:`.
     If screenshot handoff is missing, rerun `k-agent-live-ui-review` or block with the exact reason;
     draft a UI-related comment only with screenshot-backed UI evidence.
     Keep local paths out of GitHub review bodies, and carry image paths only in `UI evidence attachments:` rather than extra comments;
     with explicit user approval, upload and embed screenshots as `user-attachments` URLs via the browser-assisted upload flow in `~/.agents/skills/k-github/references/attachments.md`.
   - Drop only with source/API/runtime evidence for one of these hard reasons:
     - unsupported claims
     - unreachable-path findings
     - PR-mode findings covered by verified PR CI or existing PR artifacts
     - candidates classified as `preserved_limitation` or `prose_drift` by the Replacement/Migration Parity Gate
     - candidates refuted by the adversarial verifier, after the controller checks the refutation's source/API/runtime evidence addresses the candidate's actual claim
     - findings that only a worker asserted without evidence and without a decisive `verification_needed` path
     - PR necessity claims that rely only on ambient precedent without proving the current PR's actual diff and directly referenced artifacts
   - A `k-agent-findings-auditor` drop recommendation or a `k-agent-adversarial-verifier` verdict is advisory.
     The controller must name the hard drop reason and evidence; otherwise keep the finding, merge it with a duplicate, run the needed verification, or block with explicit uncertainty.
   - For every verification-ledger item, record one disposition:
     - `resolved`: evidence makes it irrelevant or answers the fork,
     - `run`: the controller ran the serial non-mutating/heavy check,
     - `blocked`: the check is unsafe, out of scope, or impossible, with exact blocker,
     - `not needed`: the item cannot affect keep/drop/action, with evidence.
   - When running serial verification, apply the `shared_rules.md` Read-Only Probes search discipline:
     prefer native search/listing tools for first-pass broad searches, and use shell `rg` only with a path, glob, or exact-symbol scope.
   - A `verification_needed` that can flip a kept/dropped finding, fix decision, or draft payload is blocking until it is `resolved` or `run`.
     Only evidence that it cannot affect keep/drop/action converts it to `not needed`;
     findings audit output or stale PR-intent assumptions are insufficient.
