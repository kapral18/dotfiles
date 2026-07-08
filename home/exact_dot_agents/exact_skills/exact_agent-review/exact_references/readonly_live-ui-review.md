# Agent Review Live UI Review Contract

Shared contract for `/agent-review` runtime subagents. Load this file only for the matching worker role.

## Role: Live UI review

Use after the blocking PR necessity gate and reviewer workers as the conditional UI/runtime verifier.

Load `~/.agents/skills/agent-review/references/live-ui-runtime.md` for the shared runtime contract:
mode boundary, terminology, target-packet resolution, Playwriter preflight, readiness stability guard, screenshot & evidence capture, runtime-start rung, data/setup ladder, and the hard runtime constraints.
This file adds only the review-mode specifics: the base-vs-head comparison model, the candidate-finding oracle, and the review return shape.

Review-mode fix boundary (adds to the shared mode boundary):

- Fix-capable Playwriter tasks are separate post-judgment tasks.
- Fix mode requires `fix_authorized: yes` (own / assigned / adopted PR per the controller's step 1).
- Fix mode prompt must state allowed changes and verification commands.

The parent supplies:

- scope packet
- changed paths
- candidate findings
- expected base branch
- expected PR/head branch
- controller cwd
- reviewed PR/head worktree path and branch/sha
- optional base comparison worktree path
- selected target packet, including overlay source when an overlay supplied the packet
- required runtime config: runtime/feature-flag settings the change under review needs to be reachable
  - resolved once by the controller before this launch
  - empty when none
  - concrete settings and how to apply them at start time belong to the selected target packet;
    this contract only carries that the controller resolves them up front so the runtime is started correctly the first time.

### Applicability

Decide whether the changed paths or candidate findings touch UI/runtime behavior. If not, return `Not applicable` with the evidence used.

Test-only UI migrations are applicable only when the parent supplies at least one candidate classified by the Replacement/Migration Parity Gate.
Applicable classifications are `parity_gap`, `new_regression`, or `scope_expansion`.
If all supplied candidates are `preserved_limitation` or `prose_drift`, return `Not applicable` with the parity classification evidence instead of probing live UI.

`Not applicable` may be per-target.
If a feature/surface is absent on base because the PR introduces it, mark the base comparison `Not applicable` with evidence.
Continue head-only verification against the PR/head target when the feature exists there.
Return full `Not applicable` only when the candidate is not UI/runtime-relevant or the feature/surface is absent from every relevant target.

Do not return `Not applicable` just because the target runtime has no data.
If the changed UI/runtime path exists but required data is absent, continue through the shared data/setup ladder and return `Blocked` only after those attempts are exhausted.

### Playwriter comparison

When applicable targets pass the shared preflight, use Playwriter for UI comparison.

- Compare the PR/head runtime against the base runtime for UI-relevant changes and reviewer findings only when the selected packet includes a distinct base target.
  Otherwise perform head-only verification against the PR/head runtime. Never treat a base runtime as evidence for PR/head behavior.
- Use the most faithful verification path that stays within the selected local/dev safety boundary:
  browser inspection, required screenshot captures, logs, read-only CLI commands, existing data, allowed local/dev runtime data setup, and repo-specific interactive setup tools.
  Use browser/route mocks only as last resort.
- Capture candidate-by-candidate evidence per the shared Screenshot & evidence capture rules;
  link each screenshot to the candidate/finding it supports.
- For any applicable UI-related candidate that may become review feedback, screenshot handoff is required supporting evidence.
  Capture the smallest useful screenshot set, or return `Blocked`/uncertainty with the exact reason screenshots could not be captured.
  Do not return a confirmed UI finding for drafting with `ui_evidence_artifacts: none`.
- For an observable UI blocker or uncertainty state, capture a screenshot when it materially supports the blocker.
  If the flow is blocked before navigation or screenshot capture, state that as the no-screenshot reason.
- Return partial evidence plus `Blocked` only when the flow still needs unsafe, impossible, or unstable actions/data setup after the shared data/setup ladder.
  Also block when the remaining setup is outside the selected local/dev safety boundary.

### Review return authority

- Return findings to the user or `/agent-review` as evidence input. `/agent-review` performs any judgment or side effects.

Return exactly:

- `applicability`: applicable / not applicable, with changed-path or finding evidence
- `target_packet`: selected packet name/source, including overlay source when an overlay supplied the packet
- `urls_checked`: the exact PR/head and any selected base URLs from the selected packet, or an explicit blocker before navigation
- `playwriter_preflight`: whether the Playwriter skill was loaded and `playwriter skill` was run; if not, say why
- `target_readiness`: readiness result for each exact URL, from Playwriter evidence
- `branch_evidence`: branch/runtime identity evidence for each target, or what could not be verified
- `data_setup`: media/artifacts inspected, fixture/mocks considered, existing data checked, selected-target-packet local/dev data seeded/mutated, domain interactive fallback usage, browser/route mocks if used as last resort, cleanup result, runtime environment blocker instructions, or exact data/mutation still needed
- `comparison_evidence`: candidate-by-candidate UI/runtime evidence, including `Not applicable` only for candidates disproved by reachability or absent functionality
- `ui_evidence_artifacts`: a list of screenshot handoff entries with local path, description, target URL/branch, linked candidate/finding, suggested manual attachment placement, `folder_opened_or_provided` status, and fidelity/cleanup notes; use `none` only when no applicable UI candidate may become review feedback or when `blockers_or_uncertainty` explains why screenshots could not be captured
- `pages`: pages created and closed, or URLs left open
- `blockers_or_uncertainty`: none, or precise blockers/remaining uncertainty
