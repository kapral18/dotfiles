# Case Selection

Apply the minimum sufficient test protection rule in `~/.agents/skills/k-code-quality-tests/SKILL.md` before choosing cases.
Do not derive a test list from the implementation's branches, fields or error variants.

## Include only what protects material behavior

- Intended new/changed material behavior and concrete material failure paths through public behavior, with independent expected results.
  Do not wait for a reported bug to protect new behavior.
- The nearest contrasting input or preserved behavior only when the same defect could break it and existing protection is insufficient.
- A boundary, malformed input or state sequence only when it distinguishes that concrete failure.
  Combine related cases when it improves the behavioral test.

## Exclude

- More inputs from the same equivalence partition: one representative per condition unless the contract or code distinguishes them
  (expired by 5 days and by 10 days exercise the same condition).
- Collection-size variants (1, 2, 3 items) unless the code has explicit size-dependent logic.
- Speculative inputs (exotic Unicode, huge payloads) unless the code handles them explicitly.
- `null`/`undefined`/`None` arguments unless the type or contract declares the parameter optional or nullable.
- Tests that duplicate an existing oracle, verify a private helper separately without unique material protection, or merely assert configuration/prose/implementation spelling.

## Isolate the cause

A negative case must fail for exactly one reason.
Keep every other constraint satisfied, including other constraints on the same field.

Done when the smallest sufficient set protects the new/changed material behavior, catches the relevant failures, preserves necessary behavior, and contains no redundant case.
