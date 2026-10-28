# Check Design

A check names an observable acceptance condition, its independent oracle, the relevant target or input, and the expected exit or result.

- Keep intended differences and preserved behavior distinguishable.
- Do not compare generated data only with itself.
- Make each check distinguish the requested outcome from a plausible wrong implementation, including a no-op that only prints the expected text.
- Invocation and coverage criteria target the actual callers.
  Ordered-output criteria compare the full required output, not a convenient substring.
- Plan static checks (`~/AGENTS.md` §3 step 4): the repository's own unit and static commands and focused fixtures, each under a time limit;
  a project command that step 4 makes a live check is planned only as below.
  Plan a live check as its own `check:` with a hard time limit only when the user asks for one.
  Keep full logs and the real exit status when you run them.
- Run the checks once, on the finished change. Unrun checks are `planned`, never red/green proof.
- Select only cases needed to settle concrete material risks and necessary preserved behavior.
  Prefer source/contracts and existing checks; add a bounded disposable probe only when those cannot settle the risk.
  Separately plan reused behavioral coverage or the smallest durable additions for new/changed material behavior under `~/AGENTS.md` §3.
  Source evidence and disposable probes do not replace missing durable coverage.
- Mutation testing is optional evidence for high-risk criteria, not a prerequisite for every plan.
