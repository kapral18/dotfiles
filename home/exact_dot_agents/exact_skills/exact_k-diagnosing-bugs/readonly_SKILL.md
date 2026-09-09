---
name: k-diagnosing-bugs
description: "Use for hard bugs, regressions, flaky failures, crashes, thrown errors, or slowness."
---

# Diagnosing Bugs

Supply diagnostic evidence during the root-owned Understand stage; do not create another lifecycle.
The SOP owns runtime truth, state-machine coverage, authorization, and the single final Verify stage.
A delegated diagnosis worker owns only its assigned question and returns evidence or a concrete blocker once.
It MUST NOT implement a fix, run private verification, invoke another agent, or start a follow-up workflow.

## Do not use

- obvious local errors that need only a direct explanation or an already-authorized small fix
- as a substitute for the SOP's runtime-truth chain when the question is "is X set up correctly" rather than "why is X broken"

## Capture the failure

Resolve the affected version, caller/callee, configuration and exact expected-versus-observed behavior.
Read relevant source and existing complete logs, traces or failing-test results first when they can answer the question.
Source inspection is allowed before a runnable reproduction exists; do not block locally available investigation on an unavailable runtime.
Do not treat a plausible explanation, a nearby symptom, or an unrelated green suite as causal evidence.

When existing evidence cannot distinguish the reported failure, choose the smallest safe reproduction that can:

- A focused existing test, CLI/API fixture, or captured-trace replay.
- A browser probe through k-playwriter when the symptom requires the real UI.
- A disposable harness when no existing seam expresses the failure.
- Bisection, differential comparison, or a seeded stress/fuzz experiment for a history-dependent or intermittent failure.

These are alternatives, not a checklist of mandatory techniques.
For a runnable reproduction, retain the command, inputs, environment, complete output and actual exit status.
Its assertion must discriminate the user's symptom, not merely prove that something failed.
Keep it deterministic where possible; intermittent evidence must record its sampling conditions and uncertainty.

Reuse an unchanged baseline instead of rerunning it at each handoff, skill load or continuation.
Minimize only when removing irrelevant inputs will distinguish causes or make the necessary experiment practical.
Do not require every fixture element to be proved indispensable before diagnosis can proceed.

Done when the failure and affected path are evidenced, or the exact missing evidence and its consequence are named.

## Discriminate causes

Keep competing explanations when the evidence permits them.
Do not manufacture a fixed quota of hypotheses or keep testing causes already ruled out.
Each material hypothesis needs a prediction that available source, a trace, or a targeted probe can distinguish.
When causal attribution remains ambiguous, use a relevant negative control: changing an irrelevant input must not produce the claimed effect.
Do not demand a separate control or model judgment for every assertion.
Classify the failure as product, test, infrastructure, mixed, or unresolved from source/reproduction evidence.
A flaky test, green retry, timeout extension, assertion weakening, or quarantine does not establish a test-only cause.
NEVER hide a product defect with a test patch; the original product behavior remains an acceptance criterion.

Choose probes for the uncertainty they remove.
Do not repeat a probe without a changed input, environment, hypothesis, or planned sampling requirement.
For sampling, stress or bisection, define the inputs and stopping condition before execution; use deterministic tools for the experiment.
Do not expand an experiment indefinitely because the result remains uncertain.

Prefer a debugger/REPL or narrowly tagged instrumentation over broad log dumps.
Change the variable needed for the prediction; keep other conditions stable unless the experiment explicitly tests their interaction.
Tag temporary logs with a unique prefix so the requested fix can remove them during Produce.
For slowness, gather a relevant baseline measurement or profile; compare the repaired behavior in final Verify, not in a private worker loop.

Done when evidence settles the material cause and affected interfaces, or a specific unresolved dependency prevents that conclusion.
Do not exhaust hypothetical causes, minimize every input, or rerun the baseline merely to complete a phase.

## Return diagnostic evidence

Return the classification and cause with source/tool anchors, the original expected-versus-observed behavior, relevant ruled-out alternatives and remaining uncertainty.
Distinguish a source-established defect from runtime behavior that could not be reproduced.
Do not report an unrun runtime criterion as passed.

Ask for a missing artifact, access or user-owned decision only when it blocks the requested conclusion and safe local evidence cannot resolve it.
A diagnosis-only request ends with the evidence and proposed fix; it does not authorize edits.
A leaf returns its packet result to the root; it does not ask the user or continue into production.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
For an authorized fix, carry the settled cause, intended/preserved behavior and necessary final checks into Produce.
Before regression-test or fix work, read `~/.agents/skills/k-diagnosing-bugs/references/fix-and-cleanup.md`.
Use k-codebase-design only when resolving an in-scope seam or design question is necessary;
do not start an automatic post-fix architecture pass.
