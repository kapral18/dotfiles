---
name: k-code-quality-web
description: "Use for browser-rendered markup, CSS, layout, visual states, accessibility, or focus behavior edits/reviews."
---

# Web Markup And Styling Quality

Use this for browser-rendered markup and styling.

## Secondary Skill Escalation

Do not load secondary skills until read/diff evidence proves the surface is in scope.

- Load `~/.agents/skills/k-anti-slop/SKILL.md` and select the references for the concrete visual, accessibility, responsive, copy, data-display, or localization surface being changed or reviewed.
  Reuse references already loaded for this invocation.
- If the concrete web surface is React/JSX/TSX, load `~/.agents/skills/k-code-quality-react/SKILL.md` unless its full text is already loaded for this active invocation.
  Reuse that load through reciprocal references; read fresh on a new invocation or after its text changes or is pruned.

## Markup And Semantics

- Prefer semantic HTML and existing design-system primitives over custom markup.
- Preserve accessible names, roles, focus order, and keyboard reachability.
- Keep semantic elements in place; replace one with a generic container only when the local component API requires it.
- Keep ARIA minimal and accurate; fix incorrect structure directly rather than papering over it with ARIA.

## CSS And Layout

- Match the local styling system: CSS modules, utility classes, design tokens, variables, or component props.
- Prefer existing spacing, color, typography, and breakpoint tokens over new magic values.
- Keep responsive, overflow, empty, loading, disabled, hover, focus, and error states in mind when styling changes.
- Scope selectors to the intended component or page; a broad selector can leak outside it.

## Verification

- For user-visible UI changes, verify the rendered state from the styles, props, and component contract;
  an interactive browser session is a live check (`~/AGENTS.md` §3 step 4).
- Report static evidence under `Checked:`. Put a claim only a live check could settle under `Open:` with that check as its blocker;
  offer the check only as `~/AGENTS.md` §3 step 8 allows.
