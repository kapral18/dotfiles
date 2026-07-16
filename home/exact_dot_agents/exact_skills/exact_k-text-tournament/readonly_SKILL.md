---
name: k-text-tournament
description: "Use when the agent is about to make a material rewrite of human-maintained prose with several plausible directions; compare three candidates before choosing the next edit."
---

# Text Tournament

Compare a small set of text edits against a visible rubric before making a material prose edit.

## Automatic in normal iteration

Run automatically only when the target has multiple materially different edits that could satisfy the user's prose goal.
Skip tiny mechanical edits, factual corrections with one supported wording, and every ineligible surface below.

## Eligibility

- Eligible targets are human-maintained prose: documentation, a prompt, a skill, a plan, help text, or a draft.
- The normal task already authorizes the next text edit.

Do not use for code, generated artifacts, configuration, secret-bearing content, runtime/system behavior, or changes whose quality depends on tests or live probes.
Use the normal engineering flow for those surfaces.

## Tournament round

1. **Set the bar.** State a short rubric: the goal, preservation constraints, and two to four independent quality dimensions.
   The rubric must preserve every explicit requirement in the target; it never optimizes away a safety rule or factual constraint.
2. **Generate candidates.** Generate exactly three surgical candidates, labeled A, B, and C.
   Compare each against the incumbent without writing it yet.
3. **Judge the leader.**
   Select the strongest candidate provisionally, then use the active harness's native isolated-task mechanism for a fresh evaluator when it is available.
   Give the evaluator only the rubric, incumbent, and provisional candidate.
   It compares incumbent and candidate in both presentation orders, with labels reshuffled, and reports a choice, a concise reason, and its model family.
   - Use a verified different model family when the active harness exposes one.
   - Apply a cross-family, two-order winner as the next normal edit.
   - If the evaluator is unavailable, same-family, tied, or mixed, continue normal iteration without tournament authority.
4. **Continue normally.** Record the rubric and tournament result in the next response only when it materially explains the edit.
   A later eligible rewrite starts a new round.

## Legion implement lane

A palantir legion's implement role loads this lane explicitly.
Use it only for an executor iteration targeting eligible material prose with several plausible directions.

1. Set the same rubric and generate exactly three surgical candidates.
2. Apply the provisional candidate that best satisfies the rubric as the iteration's one normal edit.
3. Include this compact block in the work narrative before `SELF_CHECK:`:

   ```text
   TOURNAMENT:
   - rubric: <goal, preservation constraints, dimensions>
   - candidates: A=<short distinction>; B=<short distinction>; C=<short distinction>
   - selected: <A|B|C and why>
   ```

Do not launch a fresh evaluator or a second pairwise comparison.
The legion's adversarial-review role evaluates the selected artifact against this block; it does not regenerate candidates.

## Return exactly

- Normal interactive: `Rubric:`, `Tournament:`, and `Edit:` when they materially explain the next edit.
- Legion implement role: the `TOURNAMENT:` block plus the normal `SELF_CHECK:` output.
