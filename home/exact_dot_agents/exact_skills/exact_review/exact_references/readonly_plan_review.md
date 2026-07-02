# Mode: Plan Review

Precondition:

- You already loaded `~/.agents/skills/review/SKILL.md`.
- Follow `~/.agents/skills/review/references/judging_core.md` and `~/.agents/skills/review/references/shared_rules.md` (loaded once by the router; do not re-load).

Use when:

- the user asks to review a plan, design document, implementation proposal, or RFC before (or during) implementation
- the subject is a document, issue body, or pasted text — not a diff or PR

Out of scope:

- reviewing implemented changes (use `local_changes.md` or the PR modes)
- authoring or rewriting the plan (this mode judges an existing plan)

## Subject Intake (Blocking)

- Read the complete plan artifact: the full raw file/issue/body content, every section, checkbox, and code block (Complete Artifacts rule).
- Resolve every referenced artifact the plan relies on (issues, PRs, docs, prior plans) before judging claims that depend on them.
- If the plan is only partially available (truncated paste, missing linked doc), stop and ask for the full artifact.

## Base Context (Mandatory)

A plan is a set of claims about the codebase plus a set of intended steps. Both must be checked against codebase reality.

- Follow the Base-Branch Context Gate in `shared_rules.md`, adapted for the missing diff:
  generate the SCSI/local-source questions from the plan's claims and named symbols instead of a diff, and report the required line as `Base context: ..., base=<branch the plan targets>, diff=n/a (plan review)`.
- Resolve identity for every file, symbol, system, or behavior the plan names:
  it exists, and the plan's description of it matches the source.
- A plan claim about current behavior is a hypothesis until anchored in a file read, SCSI result, or probe (Truth Validation Framework).

## Judge The Plan

Walk the plan end-to-end, ordered by risk:

1. **Premise:** the problem the plan solves is real and current (the bug exists on base; the need has not been superseded).
2. **Assumptions:** every claim about existing behavior/structure is verified against source; flag each mismatch with evidence.
3. **Feasibility:** each step is implementable as written — named APIs/symbols exist, boundaries are respected, and no step depends on something only a later step creates.
4. **Coverage-checklist classes, reframed for plans:** security, data-loss, and performance implications of the planned approach;
   verification/test steps present for risky behavior; documentation impact acknowledged.
5. **Gates by content:** planned removals get the Deletion-Safety Audit and Historical-Rationale Gate;
   planned replacements the Replacement/Migration Parity Gate; stateful/parser-like planned behavior must include a State-Machine Verification step in the plan; cross-module/deploy plans the Systemic-Risk Checks; user-facing flows the Product-Flow Lens; alerting/monitoring work the Signal-Quality Gate.
6. **Gaps:** missing steps, unowned risks, absent rollback/verification, and co-edit-set members the plan does not mention (docs, diagrams, configs).
7. **Compatibility intent (SOP `2.0`):** the plan's compatibility posture is explicit and matches the request;
   flag unrequested shims/legacy paths.
8. **Simplicity:** flag steps a simpler approach makes unnecessary; name the simpler path and its tradeoff.

## Output

Feedback only. Do not edit the plan document or write code unless the user explicitly asks.

- `Base context:` line (see shared_rules.md).
- Findings ordered by severity, each anchored to the plan section/step plus the code/probe evidence that supports it.
- Assumption ledger: which plan claims were confirmed, which were refuted, and which remain `Unknown` because they are not locally verifiable.
- Missing steps and unowned risks.
- Recommendation: `proceed` / `revise` (name the blocking findings) / `needs clarification` (ask exactly one question first).
