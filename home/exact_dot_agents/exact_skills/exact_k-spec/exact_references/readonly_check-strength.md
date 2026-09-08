# Final Check Design

A check names an observable acceptance condition, its independent oracle, relevant target/input, and expected exit/result.
Keep intended differences and preserved behavior distinguishable. Avoid tests that compare generated data only with itself.
Use actual repository commands and focused fixtures; retain full logs and command exit status when executed.
Prepare checks during Produce and execute them once in final Verify. Unrun checks are `planned`, never red/green proof.
A baseline reproduction in Understand answers a diagnostic question; it is not a required per-criterion rehearsal.
Mutation discrimination is risk-selected final evidence, not a prerequisite for approving every packet.
