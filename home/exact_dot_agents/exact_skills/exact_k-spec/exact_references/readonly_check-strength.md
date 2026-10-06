# Check Design

A check names an observable acceptance condition, its independent oracle, the relevant target or input, and the expected exit or result.

- Keep intended differences and preserved behavior distinguishable.
- Do not compare generated data only with itself.
- Make each check distinguish the requested outcome from a plausible wrong implementation, including a no-op that only prints the expected text.
- Invocation and coverage criteria target the actual callers.
  Ordered-output criteria compare the full required output, not a convenient substring.
- Use the repository's own commands and focused fixtures. Keep full logs and the real exit status when you run them.
- Run the checks once, on the finished change. Unrun checks are `planned`, never red/green proof.
- For stateful or parser-like behavior, list explicit transition cases (intended, preserved, malformed input, terminal actions).
  When tests cannot express them, compare against an independent table in a disposable harness under `/tmp`.
- Mutation testing is optional evidence for high-risk criteria, not a prerequisite for every plan.
