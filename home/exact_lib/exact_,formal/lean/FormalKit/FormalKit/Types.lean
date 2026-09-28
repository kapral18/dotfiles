import Lean.Data.Json

/-!
Core types shared by every unit built on `FormalKit`: a `Spec` (state type, event type,
transition function, BFS identity, observables, and properties) plus `Prop'`/`Mutant` used to
state and mutate that spec. No Mathlib; core Lean and `Lean.Data.Json` only.
-/

namespace FormalKit

/-- Whether a property is expected to hold on every reachable state (`holds`), or is a seeded,
documented false claim kept in the property list so `explore`/`audit` still report on it
explicitly (`refuted`) instead of silently dropping a known-false statement. -/
inductive Expect where
  | holds
  | refuted
  deriving Repr, BEq

def Expect.toJsonString : Expect → String
  | .holds => "holds"
  | .refuted => "refuted"

/-- One property over a spec's states and events. `check` is handed whichever step function is
currently under test -- the real model's `step`, or a mutant's -- so every mutant automatically
re-exercises every property with no duplicated statement (quantify over events/args inside
`check`; it gets the state and the step function, nothing else). -/
structure Prop' (St Ev : Type) where
  name   : String
  expect : Expect
  check  : (St → Ev → St) → St → Bool

/-- A finite-state, finite-event unit under verification.
* `key` is the abstract state identity the BFS explorer dedupes on. Equal keys MUST preserve every
  property's truth and produce equal successor keys for every event under the real step and every
  mutant step. A finite property-relevant history summary therefore belongs in the key even when
  no transition branches on it; omit a field only with a justified property-preserving abstraction.
* `obs` exposes the observables the real code can produce; `traces`/`replay` compare against it.
* `evJson` renders one event as `{"name": ..., "args": {...}}` for trace/replay output. -/
structure Spec (St Ev : Type) where
  inits  : List St
  events : List Ev
  step   : St → Ev → St
  key    : St → UInt64
  obs    : St → Lean.Json
  evJson : Ev → Lean.Json
  props  : List (Prop' St Ev)

/-- An alternative `step` reintroducing one specific historical or hypothesized bug, explored and
checked against every property exactly like the real model's `step`. `killedBy` documents which
properties are *expected* to catch it -- cross-checked, not enforced, against `mutate`'s actual
`killed_by`. -/
structure Mutant (St Ev : Type) where
  name     : String
  step     : St → Ev → St
  killedBy : List String

end FormalKit
