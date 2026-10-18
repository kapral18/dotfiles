# Interface copy

Use for product labels, hints, validation, notifications, confirmations, and progress messages.
Read the operation and its reachable states before changing the wording; apply `~/.agents/skills/k-anti-slop/references/prose.md` for voice without loading it again if already present.

## Name the action and consequence

- Use the same term for the same object across the label, dialog, result, and help text.
  Distinguish actions such as saving a draft, submitting it, and publishing it when the product does.
- Name the affected object and consequential scope when ambiguity could cause loss or a charge.
  A confirmation must describe the real effect and whether recovery exists; never promise undo, cancellation, privacy, or retention behavior the implementation lacks.
  Do not add a confirmation dialog for every routine action.
- Keep choices understandable on their own.
  Avoid double-negative toggles, guilt-laden decline text, disguised opt-ins, and secondary labels that obscure the choice.
  Do not redesign a consent or payment flow as a side effect of a wording-only task.

## Explain the current state

- Give a persistent field label.
  Put format constraints in a hint; placeholder text is not the sole label or the only place a requirement appears.
- A validation error identifies what the user can correct and how. Keep the entered value available when recovery permits.
  A service failure or missing permission must not falsely blame a field value or invite an edit that cannot solve it.
- Recommend only recovery actions the product supports. “Try again” needs a safe retry path; a support link needs a real destination.
  Keep useful diagnostic identifiers available without displaying secrets or an internal stack trace as the whole explanation.
- Match completion claims to the operation: queued, saved locally, synchronized, and completed are different states.
  Never invent a percentage, countdown, or success message to fill an unknown result;
  preserve useful uncertainty and partial-success details.
- Keep essential information available long enough to act on.
  A disappearing toast alone is insufficient when the user must retain an error or recovery instruction.

Check affected wording against the control and state it describes, including the alternative action.
Use `~/.agents/skills/k-anti-slop/references/accessibility.md` when the change affects labels, error associations, or announcements;
a copy edit alone does not justify unrelated UI changes.

Source: [GOV.UK error-message guidance](https://design-system.service.gov.uk/components/error-message/).
