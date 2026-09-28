import FormalKit
import Unit.Step
import Unit.Props
import Unit.Mutants

/-- The compiled `unit` executable's spec, assembled from `Unit/Step.lean`/`Unit/Props.lean`. -/
def spec : FormalKit.Spec Unit.St Unit.Ev :=
  { inits := Unit.inits
    events := Unit.events
    step := Unit.step
    key := Unit.key
    obs := Unit.obs
    evJson := Unit.evJson
    props := Unit.props }

def main (args : List String) : IO UInt32 := FormalKit.main spec Unit.mutants args
