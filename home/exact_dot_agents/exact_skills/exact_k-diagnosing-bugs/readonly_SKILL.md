---
name: k-diagnosing-bugs
description: "Use for hard bugs, regressions, flaky failures, crashes, thrown errors, or slowness."
---

# Diagnosing Bugs

Find the cause with evidence before changing code.

## Do not use

- obvious local errors that need only a direct explanation or an already-authorized small fix
- setup questions ("is X configured correctly") rather than "why is X broken";
  trace config source → rendered config → consumer → live probe instead

## Capture the failure

Resolve the affected version, caller/callee, configuration and exact expected-versus-observed behavior.
Read relevant source and existing complete logs, traces or failing-test results first when they can answer the question.
Source inspection is allowed before a runnable reproduction exists; do not block locally available investigation on an unavailable runtime.
Do not treat a plausible explanation, a nearby symptom, or an unrelated green suite as causal evidence.

When existing evidence cannot distinguish the reported failure, choose the smallest safe reproduction that can:

- A focused existing test, CLI/API fixture, or captured-trace replay.
- A browser probe through k-playwriter when the symptom requires the real UI.
- A disposable harness when no existing seam expresses the failure.
- For stateful behavior, the shortest sequence of transitions from the initial state to the bad state, run against the real code.
- Bisection, differential comparison, or a seeded stress/fuzz experiment for a history-dependent or intermittent failure.

These are alternatives, not a checklist of mandatory techniques.
For a runnable reproduction, retain the command, inputs, environment, complete output and actual exit status.
Its assertion must discriminate the user's symptom, not merely prove that something failed.
Keep it deterministic where possible; intermittent evidence must record its sampling conditions and uncertainty.

Reuse an unchanged baseline instead of rerunning it at each skill load or continuation.
Minimize only when removing irrelevant inputs will distinguish causes or make the necessary experiment practical.

Done when the failure and affected path are evidenced, or the exact missing evidence and its consequence are named.

## Discriminate causes

Keep competing explanations when the evidence permits them.
Drop causes the evidence has already ruled out.
Each material hypothesis needs a prediction that available source, a trace, or a targeted probe can distinguish.
When causal attribution remains ambiguous, use a relevant negative control: changing an irrelevant input must not produce the claimed effect.
Classify the failure as product, test, infrastructure, mixed, or unresolved from source/reproduction evidence.
A flaky test, green retry, timeout extension, assertion weakening, or quarantine does not establish a test-only cause.
NEVER hide a product defect with a test patch; the original product behavior remains an acceptance criterion.

Choose probes for the uncertainty they remove.
Do not repeat a probe without a changed input, environment, hypothesis, or planned sampling requirement.
For sampling, stress or bisection, define the inputs and stopping condition before execution; use deterministic tools for the experiment.
Do not expand an experiment indefinitely because the result remains uncertain.

Prefer a debugger/REPL or narrowly tagged instrumentation over broad log dumps.
Change the variable needed for the prediction; keep other conditions stable unless the experiment explicitly tests their interaction.
Tag temporary logs with a unique prefix so the fix can remove them.
For slowness, gather a relevant baseline measurement or profile and compare the repaired behavior against it once.

Done when evidence settles the material cause and affected interfaces, or a specific unresolved dependency prevents that conclusion.

## Report

Report the classification and cause with source/tool anchors, the original expected-versus-observed behavior, relevant ruled-out alternatives and remaining uncertainty.
Distinguish a source-established defect from runtime behavior that could not be reproduced.
Do not report an unrun runtime criterion as passed.

Ask for a missing artifact, access or user-owned decision only when it blocks the requested conclusion and safe local evidence cannot resolve it.
A diagnosis-only request ends with the evidence and proposed fix; it does not authorize edits.
For a requested fix, read `~/.agents/skills/k-diagnosing-bugs/references/fix-and-cleanup.md` before writing the regression test or fix.
Use `k-codebase-design` only when an in-scope seam or design question blocks the fix; do not start an automatic post-fix architecture pass.
