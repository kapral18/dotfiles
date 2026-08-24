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
   - Weak: "Commit after user approval."
   - Strong: "NEVER commit unless the user explicitly requests a commit in the current conversation."
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
6. **Back critical boundaries with checks.** Instruction wording is not enforcement by itself.
   Add tests, checklists, hooks, probes, or acceptance criteria when the repository gives you a local way to verify the boundary.

## Fidelity Boundaries

Fidelity outranks conversion style. Keep as-is:

- Factual/definitional negations ("a green suite discriminates nothing", "X is not evidence") because they are facts, not instructions.
- Negations inside quoted examples, BAD/GOOD pairs, code blocks, command flags, and table cells.
- Dense gate wording where rewriting would weaken modal strength, scope, examples, paths, flags, commands, or exception clauses.
- Existing hard prohibitions that define the full boundary.

Done when every forbidden behavior is expressed as a hard boundary, every affirmative clause adds precision rather than replacing the ban, and no fact or qualifier was lost.
