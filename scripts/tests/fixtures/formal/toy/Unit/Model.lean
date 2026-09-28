namespace Unit

/-- The toy machine's control state. -/
inductive Phase where
  | idle
  | running
  | done
  deriving Repr, BEq, DecidableEq

/-- Full state: `phase` plus the finite history summary `recorded`. Properties inspect
`recorded`, and transitions preserve or update it even though dispatch branches only on `phase`,
so the BFS identity MUST retain it. This is the toy's property-preserving ghost/history
abstraction rather than an unbounded event log. -/
structure St where
  phase : Phase
  recorded : Bool
  deriving Repr, BEq, DecidableEq

/-- `finish` carries the nondeterministic outcome as an explicit argument, matching FormalKit's
"push nondeterminism into the event, never into `step`" rule. -/
inductive Ev where
  | start
  | finish (ok : Bool)
  | cancel
  | reset
  deriving Repr, BEq

end Unit
