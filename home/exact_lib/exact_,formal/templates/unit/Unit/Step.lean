import Lean.Data.Json
import Unit.Model

/-!
The transition function plus everything `FormalKit.Spec` needs around it. Anchor every real case
to a `TRANSITIONS.md` row and, when this unit models real code, a repo-relative `path:start-end`
in `ANCHORS.json` (`,formal anchors add`).
-/

namespace Unit

/-- The transition function. This template's single case is a no-op guard away from the real
shape: a real `step` case, in general, first checks whether the event is even enabled in this
state (dispatch/enabledness -- see `Model.Ev`'s docstring) and returns `st` unchanged when it is
not, exactly like a real no-op branch would. -/
def step (st : St) : Ev → St
  | .toggle => match st with
    | .off => .on
    | .on => .off

/-- Every valid starting state. A real unit may need more than one `init` (e.g. one per free
configuration bit set once before the event loop starts). -/
def inits : List St := [.off]

/-- The full, finite enumeration of events, including every argument combination. -/
def events : List Ev := [.toggle]

/-- BFS state identity (`FormalKit.Spec.key`). States with the same key MUST agree on every
property and, for every event, produce equal successor keys under `step` and every mutant step.
Include a finite summary of property-relevant history even when transitions never branch on it.
Exclude a field only when a documented abstraction establishes both property and successor
preservation; otherwise bound the state/history explicitly rather than silently merging it.
This example's whole state is load-bearing, so nothing is excluded. -/
def key : St → UInt64
  | .off => 0
  | .on => 1

/-- Observables the real code can expose, compared field-by-field by `,formal replay`. -/
def obs (st : St) : Lean.Json :=
  Lean.Json.mkObj [("on", Lean.Json.bool (st == .on))]

/-- Renders one event as `{"name": ..., "args": {...}}` for trace/replay output. -/
def evJson : Ev → Lean.Json
  | .toggle => Lean.Json.mkObj [("name", Lean.Json.str "toggle"), ("args", Lean.Json.mkObj [])]

end Unit
