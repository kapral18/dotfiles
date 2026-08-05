---
name: k-diagnosing-bugs
description: "Use for hard bugs, regressions, flaky failures, crashes, thrown errors, or slowness."
---

# Diagnosing Bugs

A discipline for hard bugs. Skip phases only when explicitly justified.

The SOP owns the surrounding gates: verification loops (§3.4) and runtime truth (§2.2).
The `k-code-quality` skill owns the `/tmp/state-machine-verification` harness for stateful/branch-heavy behaviour.
This skill is the debugging front-end that forces a **tight** feedback loop before any theorising, then routes into those gates.
When you write the regression test, load `~/.agents/skills/k-code-quality-tests/SKILL.md`.

## Do not use

- trivial one-line fixes where the cause is already obvious from a stack trace — just fix it
- as a substitute for the SOP's runtime-truth chain when the question is "is X set up correctly" rather than "why is X broken"

## Phase 1 — Build a feedback loop

**This is the skill.** Everything else is mechanical.
With a **tight** pass/fail signal that goes red on _this_ bug, you will find the cause;
bisection, hypotheses, and instrumentation all consume it. Spend disproportionate effort here.

Ways to construct one — try roughly in this order:

1. **Failing test** at whatever seam reaches the bug — unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (use the `k-playwriter` skill) — drives the UI, asserts on DOM/console/network.
5. **Replay a captured trace** — save a real request/payload/event log, replay it through the code path in isolation.
6. **Throwaway harness** — a minimal subset (one service, mocked deps) exercising the bug path with a single call.
7. **Property / fuzz loop** — for "sometimes wrong output", run many random inputs and look for the failure.
8. **Bisection harness** — if the bug appeared between two known states, automate "boot at state X, check, repeat" for `git bisect run`.
9. **Differential loop** — run the same input through old-vs-new (or two configs) and diff outputs.
10. **Human-in-the-loop last resort** — if a human must click, drive them with a structured bash script so the loop stays structured;
    captured output feeds back to you. Minimal shape:

    ```bash
    set -euo pipefail
    step() { printf '\n>>> %s\n' "$1"; read -r -p "  [Enter when done] " _; }
    capture() { local v="$1"; printf '\n>>> %s\n' "$2"; read -r -p "  > " a; printf -v "$v" '%s' "$a"; }
    step "Open the app and reproduce the action."
    capture ERR "Did it throw? Paste the message (or 'none'):"
    printf 'ERR=%s\n' "$ERR"
    ```

### Tighten the loop

Once you have one, **tighten** it: faster (cache setup, skip unrelated init, narrow scope), sharper signal (assert the specific symptom, not "didn't crash"), more deterministic (pin time, seed RNG, isolate filesystem, freeze network).
For non-deterministic bugs, chase a **higher reproduction rate**: loop the trigger, parallelise, add stress, inject sleeps, until debuggable.

### When you genuinely cannot build a loop

Stop and say so. List what you tried.
Ask the user for: access to the environment that reproduces it, a captured artifact (HAR, log dump, core dump, timestamped recording), or permission to add temporary instrumentation.
Do **not** proceed to hypothesise without a loop.

### Completion criterion — a tight loop that goes red

Phase 1 is done when you can name **one command** you have **already run at least once** (paste the invocation and its output) that is:

- **Red-capable** — drives the actual bug path and asserts the user's exact symptom, so it goes red on this bug and green once fixed.
  Not "runs without erroring".
- **Deterministic** — same verdict every run (flaky bugs: a pinned, high reproduction rate).
- **Fast** — seconds, not minutes.
- **Agent-runnable** — you can run it unattended.

If you catch yourself reading code to build a theory before this command exists, **stop**. No red-capable command, no Phase 2.

## Phase 2 — Reproduce + minimise

Run the loop, watch it go red.
Confirm it produces the failure mode the **user** described (not a nearby one —
wrong bug, wrong fix), that it reproduces across runs, and that you have captured the exact symptom.
Then shrink to the **smallest scenario that still goes red**: cut inputs, callers, config, data, and steps one at a time, re-running after each cut.
Done when every remaining element is load-bearing — removing any one makes it go green. Do not proceed until reproduced **and** minimised.

## Phase 3 — Hypothesise

Generate **3–5 ranked hypotheses** before testing any; single-hypothesis generation anchors on the first plausible idea.
Each must be **falsifiable** — state the prediction: "If X is the cause, changing Y makes the bug disappear / changing Z makes it worse."
If you cannot state the prediction, it is a vibe — discard or sharpen it.
Include a **negative control**: name an input your explanation calls irrelevant and predict the verdict is unchanged when you perturb it;
if perturbing that "irrelevant" input flips the verdict, the explanation is not the real cause.
A fluent, confident rationale is still a hypothesis — the loop and the negative control are the proof, not the narrative.
Include the ranked list in the next user-visible message (or final report); they often re-rank it with domain knowledge.
Mid-turn text may never reach the user, so never wait on it — proceed with testing on your own ranking.

## Phase 4 — Instrument

Each probe maps to a specific prediction. **Change one variable at a time.**
Prefer a debugger/REPL (one breakpoint beats ten logs), then targeted logs at the boundaries that distinguish hypotheses;
never "log everything and grep". **Tag every debug log** with a unique prefix (e.g. `[DEBUG-a4f2]`) so cleanup is a single grep.
For performance regressions, logs are usually wrong: establish a baseline measurement (timing harness, profiler, query plan), then bisect.
Done when each ranked hypothesis is confirmed or refuted by a recorded probe result, and performance regressions have a before/after measurement.

## Phase 5 — Fix + regression test

This phase is fix work (SOP §1): on an assessment request, stop after Phase 4 with the verified cause and proposed fix.
Write the regression test **before the fix**, but only if there is a **correct seam** —
one where the test exercises the real bug pattern as it occurs at the call site. A too-shallow seam gives false confidence.
**If no correct seam exists, that itself is the finding** — the architecture prevents lockdown;
hand it to `~/.agents/skills/k-codebase-design/SKILL.md`.
If a correct seam exists: turn the minimised repro into a failing test, watch it fail (revert the fix in place —
see `k-code-quality-tests`), apply the fix, watch it pass, then re-run the Phase 1 loop on the original scenario.
For stateful/branch-heavy fixes, load `k-code-quality` and verify against base behaviour buckets with its state-machine verification harness.

## Phase 6 — Cleanup + post-mortem

Before declaring done:

- Original repro no longer reproduces (re-run the Phase 1 loop).
- Regression test passes (or absence of seam is documented).
- Defect-class sweep: enumerate the class of defect the root cause implies, then sweep the codebase (and sibling repos when the class spans them) for other instances; classify every hit as fixed, out-of-scope (say where it goes), or clean.
  Fix instances beyond the reported bug only when the user asked for a class-wide fix; otherwise list them as findings.
  A fix for instance N is not complete while unexamined siblings remain.
- All `[DEBUG-...]` instrumentation removed (grep the prefix).
- Throwaway prototypes deleted or clearly marked.
- The correct hypothesis is stated in the commit / PR message so the next debugger learns.

Then ask: **what would have prevented this bug?**
If the answer is architectural (no good seam, tangled callers, hidden coupling), hand off to `k-codebase-design` with specifics —
after the fix is in.
