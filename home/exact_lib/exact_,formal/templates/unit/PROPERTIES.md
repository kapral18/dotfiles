# PROPERTIES

One row per property in `Unit/Props.lean`. In `source`, cite the anchored requirement/finding and its
init-rooted defect or preserved-invariant witness. For real-code units, name the invoked consumer, production
source, actual fields observed and targeted replay/regression evidence. If generated cover traces omit that
schedule, name the real targeted evidence or record the gap; this table alone does not prove execution.
For `--design` units, cite intended plan/spec behavior and model witness evidence; mark production observations
and replay `n/a-design`. Never invent a production consumer or runtime evidence.
`killing mutants` names mutants that discriminate that witness. `status` tracks the last
`,formal audit`/`explore` outcome (e.g. `holds`, `violated`, `bounded`) -- update it after each run, do not
compute it by hand.

| id  | statement | source | expect | killing mutants | status |
| --- | --------- | ------ | ------ | --------------- | ------ |
|     |           |        |        |                 |        |
