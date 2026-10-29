---
name: k-instruction-boundaries
description: "Use when writing or refactoring AI-facing instructions; define forbidden behavior with hard boundaries and add affirmatives only when they sharpen execution."
disable-model-invocation: true
---

# Instruction Boundaries For LLM Guidance

LLMs can miss negation, but deleting negation can delete the boundary. Use hard prohibitions for forbidden behavior.
Add affirmative wording when it tells the model exactly what to do next.

Apply this whenever writing or editing AI-facing guidance text: SOPs, skills, prompts, agent profiles, hooks docs, instruction/reference files.

## Rules

1. **Default to hard boundaries for forbidden behavior.**
   Use `MUST NOT`, `NEVER`, `do not`, `only when`, and `stop` when the behavior is banned, gated, or authorized only by an explicit condition.
   Do not soften a ban into a preference, implication, or positive-only sentence.
   - Weak: "Delete branches after user approval."
   - Strong: "NEVER delete a branch unless the user explicitly asks to delete that branch."
2. **Preserve standalone prohibitions when the forbidden set is clearer than the allowed set.**
   Some rules are complete as a ban because the negative behavior is broader than any useful affirmative rewrite.
   - Strong: "Do not build further reasoning on unverified external behavior."
   - Strong: "Never publish human-visible content without explicit approval."
3. **Add affirmatives only where they reduce ambiguity.**
   Add the positive action when it narrows the next move, names the substitute, or makes verification easier.
   - Strong: "Use `ReadFile` for file reads; do not use shell `cat`, `head`, or `tail`."
   - Strong: "Mark unsupported claims as `Unknown`; do not guess from memory or similarity."
4. **Use boundary/action/verification for high-risk gates.** When space allows, express the contract as: `Required: <positive behavior>.
Forbidden: <hard ban>. Verify: <observable check>.` Keep the ban even when the required action is present.
5. **Use emphasis as contract strength, not decoration.**
   `MUST`, `MUST NOT`, and `NEVER` are valid for safety, authorization, destructive, publication, ownership, git, secret, compatibility, and verification gates.
   Repetition or caps alone do not create precision; name the actor, object, condition, and consequence.
6. **Distinguish instruction content from enforcement.** Source review can verify a written boundary; it does not prove model adherence.
   Do not add wording tests, checklists or runtime machinery merely to verify an instruction.
   Additional enforcement needs a concrete material failure; implementation changes follow `~/AGENTS.md` §3's minimum sufficient test protection rule.
7. **Resolve material ambiguity.** Apply the precision rule in `~/AGENTS.md` §8.
   Make the actor, action, scope, conditions, and observable result explicit where they affect execution.
   If a plausible literal reading satisfies the words but misses the goal, rewrite the instruction or explicitly exclude that reading.

## Fidelity Boundaries

Preserve meaning when rewriting:

- Keep factual distinctions, negation, and qualifications; do not turn them into different instructions merely to prefer affirmative wording.
- Preserve quotations and executable or machine-consumed text according to their source and tooling contracts.
- Keep modal strength, scope, conditions, exceptions, identifiers, paths, and flags.
- Rewrite or deduplicate a prohibition only when every independently reachable entry retains its guard.

Examples, tables, and dense clauses may be clarified; their format alone does not require keeping the original sentence.

Done when every forbidden behavior is expressed as a hard boundary, every affirmative clause adds precision rather than replacing the ban, material ambiguity is resolved, and no fact or qualifier was lost.
