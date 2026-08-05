---
name: k-text-tournament
description: "Use before a material prose rewrite with several plausible directions; compare three candidates."
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
     State the degradation out loud: which condition hit and that tournament authority was dropped. Never silently discard the evaluation.
4. **Continue normally.** Record the rubric and tournament result in the next response only when it materially explains the edit.
   A later eligible rewrite starts a new round.

## Return exactly

- Normal interactive: `Rubric:`, `Tournament:`, and `Edit:` when they materially explain the next edit.
- Worker implement role: include the `TOURNAMENT:` block plus the normal `SELF_CHECK:` output.
