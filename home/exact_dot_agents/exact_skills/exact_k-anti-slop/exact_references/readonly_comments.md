# Code comments

Keep information the code alone cannot explain: intent, constraints, units, invariants, security or concurrency reasoning, compatibility requirements, and public API contracts.
Verify behavioral claims against the implementation and its consumers before retaining or adding them.

- Remove comments that merely narrate imports, assignments, loops, or the next workflow step.
  Empty section labels, decorative separators, emoji banners, end markers, and signature-echo docstrings add little unless tooling or a local convention depends on them.
- Remove a vague TODO only after checking whether it records an actual unresolved obligation.
  Preserve actionable issue links, reproduction context, and the condition under which a workaround can be removed.
- Explain the non-obvious decision once at the level where it matters.
  Avoid line-by-line narration, repeated explanations, stiff phrasing, and unnecessary all-caps.
  Use as much space as the contract needs; no fixed two-line cap.
- Preserve license notices, attribution, compiler/type/lint/formatter directives, generated-file markers, region markers used by tooling, doctests, documentation examples, and necessary rationale.
  A visually decorative comment can still have a machine consumer.
- On a comment-only cleanup, do not change executable code, identifiers, imports, layout, or unrelated whitespace.
  Documentation strings and special comments can affect runtime introspection, generated docs, or tooling;
  check those consumers before treating them as inert prose.
- Do not use a blanket regex or length limit to strip comments.
  Compare the final diff with the requested scope and confirm that every removed fact is redundant or obsolete.
