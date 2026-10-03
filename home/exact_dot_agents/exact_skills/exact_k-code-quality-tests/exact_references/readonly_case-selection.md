# Case Selection

## Include

- Each distinct branch and outcome: success paths, error handling, each unique return value or thrown error.
- Each independent failure condition, even when several share one status code or error type.
  A deleted account and an expired account that both reject login are two cases: either condition can regress alone.
- Both sides of every declared boundary: the nearest valid and the nearest invalid value.
  Account for inclusive vs exclusive bounds and the smallest meaningful step (`length >= 2` → lengths 1 and 2;
  `x > 0` on integers → 0 and 1).
- At least one case where every constraint passes.
  An existing positive boundary case satisfies this; do not add a separate case only to repeat it.
- Paths through private/internal helpers, reached by varying input to the public entry point.
- Concrete status codes for HTTP handlers: separate cases for 400, 401, 403. Do not assert or name a range such as `4xx`.

## Exclude

- More inputs from the same equivalence partition: one representative per condition unless the contract or code distinguishes them
  (expired by 5 days and by 10 days exercise the same condition).
- Collection-size variants (1, 2, 3 items) unless the code has explicit size-dependent logic.
- Speculative inputs (exotic Unicode, huge payloads) unless the code handles them explicitly.
- `null`/`undefined`/`None` arguments unless the type or contract declares the parameter optional or nullable.

## Isolate the cause

A negative case must fail for exactly one reason.
Keep every other constraint satisfied, including other constraints on the same field.

Done when every branch, independent failure condition, and declared boundary maps to a case, and no case duplicates another's condition.
