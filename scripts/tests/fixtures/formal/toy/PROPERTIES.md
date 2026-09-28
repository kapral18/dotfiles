# PROPERTIES

See `README.md` for the exact expected `explore`/`mutate` outcome of each row.

| id  | statement                            | source                 | expect  | killing mutants | status   |
| --- | ------------------------------------ | ---------------------- | ------- | --------------- | -------- |
| P1  | done implies recorded                | requirement            | holds   | M_killed        | holds    |
| P2  | idle implies not recorded            | finding (seeded false) | refuted | none            | violated |
| P3  | reset from done always lands on idle | requirement            | holds   | none            | holds    |
