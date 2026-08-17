---
name: k-affirmative-phrasing
description: "Rewrite LLM instructions from prohibitions to affirmative phrasing (negation reliability)."
disable-model-invocation: true
---

# Affirmative Phrasing For LLM Instructions

Negation is a mechanistic weak spot in LLMs.
Interpretability work on base models (Llama-3.1-8B, Mistral-7B) shows negative-prompt accuracy near 50% versus ~90% on affirmative phrasing, even though the model internally represents the negation: shortcut attention heads in middle-to-late layers promote the most correlated/positive concept and override the "not".
An instruction like "do not use X" is therefore more likely to be silently ignored than "always use Y".
Caveats: the study covers base models on simple factual templates, so the rate is directional intuition for instruction-tuned agents, not a measured failure rate.
The affirmative-phrasing guidance still holds as low-cost, mechanistically grounded practice.

Apply this whenever writing or editing AI-facing guidance text: SOPs, skills, prompts, agent profiles, hooks docs, instruction/reference files.

## Rules

1. **Prefer the affirmative alternative over the prohibition.** Give the model the positive concept you want, not only the one to suppress.
   - Weak: "Do not commit directly to main." → Strong: "Commit to a feature branch, then open a PR."
   - Weak: "Never use `any` in TypeScript." → Strong: "Type every value explicitly; use `unknown` when the type is genuinely unknown."
2. **When a hard prohibition must stay, pair it with the affirmative alternative in the same line.**
   Construction ("build the concept of not-Y") dominates and suppression is weak, so spell out what "not Y" concretely is:
   "Use the project logger (`logger.debug`) instead of `console.log`."
   Safety gates, side-effect bans, and blindness/read-only lane contracts keep their prohibition form.
3. **State critical constraints redundantly rather than as a single "never" line.**
   Put the positive rule first; restate or verify the constraint where it matters instead of stacking emphatic NEVERs.
4. **Back phrasing with verification, not emphasis.**
   A model can parse the negation and still act against it; low black-box accuracy can hide capable internal mechanisms.
   The fix is affirmative phrasing plus tests, checklists, or hooks — never more capital letters.

## Fidelity boundaries (what stays negated)

Fidelity outranks conversion rate. Keep as-is:

- Factual/definitional negations ("a green suite discriminates nothing", "X is not evidence") — facts, not instructions.
- Negations inside quoted example text, BAD/GOOD pairs, code blocks, command flags, and table cells.
- Enumerated boundary contracts where itemized negation is the precise form (read-only lane lists).
- Double negatives and dense gate wording whose rewrite would weaken precision.
- Every condition, qualifier, modal strength (MUST/MAY/only when), example, path, flag, command, and exception clause —
  a rewrite drops none of them.

Done when every convertible prohibition reads affirmatively, every kept prohibition carries its paired alternative, and no fact or qualifier was lost.
