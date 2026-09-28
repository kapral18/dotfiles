# TRANSITIONS

Extraction table for `Unit/Step.lean`. This is a synthetic fixture with no real-code anchors --
every row's `anchors` column is `n/a (synthetic fixture)` instead of an `ANCHORS.json` id.

| state var       | event         | guard           | effect                           | anchors                 |
| --------------- | ------------- | --------------- | -------------------------------- | ----------------------- |
| phase           | start         | phase = idle    | phase := running                 | n/a (synthetic fixture) |
| phase, recorded | finish(true)  | phase = running | phase := done, recorded := true  | n/a (synthetic fixture) |
| phase           | finish(false) | phase = running | phase := idle                    | n/a (synthetic fixture) |
| phase, recorded | cancel        | phase = running | phase := idle, recorded := true  | n/a (synthetic fixture) |
| phase, recorded | reset         | phase = done    | phase := idle, recorded := false | n/a (synthetic fixture) |

## Unmodeled

- Nothing else -- this is a minimal synthetic fixture, not a model of real code.
