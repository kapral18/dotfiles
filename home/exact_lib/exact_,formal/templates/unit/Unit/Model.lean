namespace Unit

/-- The unit's state. This template ships a minimal two-state example -- replace it with the
real modeled state, one field per behavior-relevant piece of state the properties need. Keep any
finite property-relevant history/bookkeeping summary in `St` and in `Step.key` even when `step`
never branches on it. Omit a field from the key only when the abstraction preserves property
truth and successor keys for the real step and every mutant. -/
inductive St where
  | off
  | on
  deriving Repr, BEq

/-- The unit's events. This template's single nullary event is the minimum that compiles --
give every real event its real arguments (booleans/enums/etc): FormalKit enumerates `events`
exhaustively, so an argument left out here is one the explorer can never vary. Model
dispatch/enabledness (which events are even reachable in which state, e.g. a keyboard shortcut
only live in one view) as a no-op guard inside `step` (see `Step.step`), not by leaving the event
out of `events` -- a guard FormalKit never sees is a guard the explorer cannot falsify. -/
inductive Ev where
  | toggle
  deriving Repr, BEq

end Unit
