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
- Collection-size variants (1, 2, 3 items) unless the contract or a concrete material failure distinguishes them.
- Unusual inputs (exotic Unicode, huge payloads) without a contract requirement or evidenced material risk.
- `null`/`undefined`/`None` arguments outside both the accepted-input contract and a concrete input-validation failure path.
- Tests that duplicate an existing oracle, verify a private helper separately without unique material protection, or merely assert configuration/prose/implementation spelling.

## Isolate the cause

Isolate the intended failure by keeping unrelated constraints satisfied.
Use multiple invalid constraints only when their interaction or validation precedence is the behavior being protected.

Done when the smallest sufficient set protects the new/changed material behavior, catches the relevant failures, preserves necessary behavior, and contains no redundant case.
