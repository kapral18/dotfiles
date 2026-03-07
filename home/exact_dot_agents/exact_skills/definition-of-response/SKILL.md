---
name: definition-of-response
description: Use when generating any response; defines what counts as a complete response so the agent does not stop at locally incomplete answers.
---

# Definition of Response

Use this skill for every prompt and every response, without exception: questions, explanations, investigations, walkthroughs, plans, implementations, edits, reviews, fixes, refactors, searches, and any other task.

## Core rule

A response is complete only when all material locally-verifiable unknowns relevant to the user's request have been resolved and the requested work has been carried through to the required stopping point.

This applies to every kind of task: answering, investigating, planning, implementing, editing, validating, and reporting results.

Do not confuse a plausible answer, a doc-based answer, a partially traced answer, or a partially executed task with a complete response.

## Completion standard

Before responding, verify that all of the following are true:

1. **Identity is resolved.**
   - You have verified the exact tool, package, binary, config file, script, or code path being discussed.

2. **The local path is traced end-to-end.**
   - For configuration questions, trace source declaration, value resolution, render/apply steps, and runtime consumers.
   - For behavior questions, trace caller, callee, and the implementation that determines the observed behavior.

3. **Local evidence is sufficient for the stopping point.**
   - If the relevant implementation exists locally, inspect it before concluding.
   - An `Unknown` is allowed only when the remaining gap is genuinely not locally verifiable.

4. **The work matches the user's scope and requested stopping point.**
   - If the user asked a question, answer the asked question fully.
   - If the user asked for action, carry out the action fully unless blocked by a real constraint or approval boundary.
   - Do not stop at a partial implementation, partial investigation, or partial answer when more required work is still locally doable.
   - Do not withhold material parts of the answer or work behind optional next-step offers.

## Required response shape

When the response depends on factual investigation or executed work, structure the response as:

- `Plan:` short checklist of what will be verified or done
- `Verified answer:` concise direct answer when the user asked a question
- `Results:` concise statement of what was done when the user asked for action
- `Evidence:` concrete files, commands, probes, validations, or code paths used
- `Unknowns:` only if a material point is genuinely not locally verifiable after full investigation

## Prohibited endings

Do not end with any of these or similar when local verification is still possible:

- `if you want, I can check X next`
- `I have not inspected the source yet`
- `this appears to`
- `probably`
- `maybe`
- `likely`

## Example

Bad:

- `Pi providers work like other coding agents; docs say X. Unknown: I have not inspected source.`

Why bad:

- Local source may be available.
- The unknown is self-created by stopping early.

Good:

- Inspect docs, config, and local implementation.
- Only after source inspection, answer with the exact provider resolution path and any true remaining unknowns.

## Relationship to other skills

- This skill defines when the response is complete.
- Use `make-no-guesses` for the verification standard that governs what may be claimed as fact.

## Notes

- This skill is about completeness, not just correctness.
- A response can be factually non-false and still be incomplete.
- If you can verify more locally and that verification is still required to reach the user's stopping point, you are not done.
