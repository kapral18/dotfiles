---
name: interview-me
description: Interview the user until you have 100% confidence about what they actually want.
disable-model-invocation: true
---

# Interview Me

Interview me until you have 100% confidence about what I actually want, not what I think I should want.

The SOP (§3.0 Intent Loop) already owns the mechanics: investigate read-only first, ask exactly one fork-closing question at a time, wait, update the spec, repeat.
This skill sharpens how you run that loop.

- **Answer it yourself before asking.**
  Every question I could resolve by reading the code, running a probe, or checking history is a question you should not ask me.
  Ask only what evidence cannot settle.
- **Walk the decision tree, resolving dependencies in order.**
  Later choices often depend on earlier answers; do not ask a question whose relevance a prior answer would eliminate.
  Ask the most branch-eliminating one first, then descend.
- **Give me your recommended answer with each question.**
  State the option you would pick and why, so I can confirm with one word instead of composing a reply.
  If you have a real default, lead with it; if the fork is genuinely open, say so.
- **Stop when the forks are empty.**
  Done means every remaining interpretation produces the same output and the success criteria are testable — not when I stop objecting.
