# TRANSITIONS

One row per transition case in `Unit/Step.lean`. Name the controllable real event and put its dispatch
enabledness in `guard`. Every row must cite anchors for the event source, enabledness/dispatch, and effect from
`ANCHORS.json` (`A1`, `A2`, ...) when this unit models real code (`,formal anchors add`); a `--design` unit may
cite plan/spec anchors instead. Also list every deliberately unmodeled piece of state or behavior below the
table, with a one-line reason.

| state var | event | guard | effect | anchors |
| --------- | ----- | ----- | ------ | ------- |
|           |       |       |        |         |

## Unmodeled

-
