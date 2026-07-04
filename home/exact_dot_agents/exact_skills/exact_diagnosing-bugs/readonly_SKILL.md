---
name: diagnosing-bugs
description: "Disciplined diagnosis loop for hard bugs and performance regressions: build a tight red loop first, then reproduce, minimise, hypothesise, instrument, fix, regression-test. Use when the user says diagnose/debug this, or reports something broken, throwing, failing, flaky, or slow."
---

# Diagnosing Bugs

A discipline for hard bugs. Skip phases only when explicitly justified.

The SOP owns the surrounding gates: verification loops (§3.4), the `/tmp/state-machine-verification` harness for stateful/branch-heavy behaviour (§3.5), and runtime truth (§2.2).
This skill is the debugging front-end that forces a **tight** feedback loop before any theorising, then routes into those gates.
When you write the regression test, load `~/.agents/skills/code-quality-tests/SKILL.md`.

## Do not use

- trivial one-line fixes where the cause is already obvious from a stack trace — just fix it
- as a substitute for the SOP's runtime-truth chain when the question is "is X set up correctly" rather than "why is X broken"

## Phase 1 — Build a feedback loop

**This is the skill.** Everything else is mechanical.
With a **tight** pass/fail signal that goes red on _this_ bug, you will find the cause;
bisection, hypothesis-testing, and instrumentation all just consume it. Without one, no amount of staring at code will save you.
Spend disproportionate effort here. Be aggressive, be creative, refuse to give up.

Ways to construct one — try roughly in this order:

1. **Failing test** at whatever seam reaches the bug — unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (use the `playwriter` skill) — drives the UI, asserts on DOM/console/network.
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

Treat the loop as a product.
Once you have one, **tighten** it: faster (cache setup, skip unrelated init, narrow scope), sharper signal (assert the specific symptom, not "didn't crash"), more deterministic (pin time, seed RNG, isolate filesystem, freeze network).
A 30-second flaky loop is barely better than none; a 2-second deterministic one is a superpower.
For non-deterministic bugs the goal is not a clean repro but a **higher reproduction rate** —
loop the trigger, parallelise, add stress, inject sleeps, until it is debuggable.

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

If you catch yourself reading code to build a theory before this command exists, **stop** —
jumping to a hypothesis is the exact failure this skill prevents. No red-capable command, no Phase 2.

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
A fluent, confident rationale for the cause is still only a hypothesis — the red-to-green loop and the negative control are the proof, not the narrative.
Show the ranked list to the user before testing; they often re-rank instantly with domain knowledge.
Do not block on it if they are AFK — proceed with your ranking.

## Phase 4 — Instrument

Each probe maps to a specific prediction. **Change one variable at a time.**
Prefer a debugger/REPL (one breakpoint beats ten logs), then targeted logs at the boundaries that distinguish hypotheses;
never "log everything and grep". **Tag every debug log** with a unique prefix (e.g. `[DEBUG-a4f2]`) so cleanup is a single grep.
For performance regressions, logs are usually wrong: establish a baseline measurement (timing harness, profiler, query plan), then bisect.
Measure first, fix second.
Done when each ranked hypothesis is confirmed or refuted by a recorded probe result, and performance regressions have a before/after measurement.

## Phase 5 — Fix + regression test

Write the regression test **before the fix**, but only if there is a **correct seam** —
one where the test exercises the real bug pattern as it occurs at the call site. A too-shallow seam gives false confidence.
**If no correct seam exists, that itself is the finding** — note it; the architecture is preventing the bug from being locked down, and it is a candidate for `~/.agents/skills/codebase-design/SKILL.md`.
If a correct seam exists: turn the minimised repro into a failing test, watch it fail, apply the fix, watch it pass, then re-run the Phase 1 loop against the original (un-minimised) scenario.
For stateful/branch-heavy fixes, verify against base behaviour buckets via the SOP §3.5 harness.

## Phase 6 — Cleanup + post-mortem

Before declaring done:

- Original repro no longer reproduces (re-run the Phase 1 loop).
- Regression test passes (or absence of seam is documented).
- All `[DEBUG-...]` instrumentation removed (grep the prefix).
- Throwaway prototypes deleted or clearly marked.
- The correct hypothesis is stated in the commit / PR message so the next debugger learns.

Then ask: **what would have prevented this bug?**
If the answer is architectural (no good seam, tangled callers, hidden coupling), hand off to `codebase-design` with specifics —
after the fix is in, when you know more than you did at the start.
