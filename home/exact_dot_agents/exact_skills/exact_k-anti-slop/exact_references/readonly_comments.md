# Code comments

Default to no comment or docstring.
Keep one only when removing it would lose a critical non-obvious constraint that clearer names, types or code cannot express, or when law/tooling requires it.
Complexity, a new function or a reviewer asking for explanation does not establish necessity. Fix confusing code before explaining it.

- Remove comments that merely narrate imports, assignments, loops, or the next workflow step.
  Empty section labels, decorative separators, emoji banners, end markers, and signature-echo docstrings add little unless tooling or a local convention depends on them.
- NEVER use comments, docstrings or TODOs as implementation plans, progress logs, intermediate solutions, or excuses for unfinished code.
  Keep task state in the task record; finish the implementation.
- A necessary workaround comment states the verified external constraint and removal condition once, briefly.
  Do not narrate the fix history.
- In touched code, delete obsolete or redundant comments instead of polishing them.
  Verify behavioral claims against code and consumers; comments are not proof.
- Preserve license notices, required attribution, compiler/type/lint/formatter directives, generated-file markers and other machine-consumed text.
  Documentation examples and executable doctests follow their actual contract.
  A visually decorative comment can still have a machine consumer.
- On a comment-only cleanup, do not change executable code, identifiers, imports, layout, or unrelated whitespace.
  Documentation strings and special comments can affect runtime introspection, generated docs, or tooling;
  check those consumers before treating them as inert prose.
- Do not use a blanket regex or length limit to strip comments.
  Compare the final diff with the requested scope and confirm that required text and critical constraints remain;
  accurate but nonessential information may be removed.
