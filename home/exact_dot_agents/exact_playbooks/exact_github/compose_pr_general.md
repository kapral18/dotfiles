# GitHub PR Body Playbook (General)

Use when:

- the user wants a PR body draft only (no `gh` side effects)
- `~/.agents/playbooks/github/gh_workflow.md` needs a draft body before
  creating/editing a PR

Scope:

- produces a PR body draft only
- do not run `gh` or change PR metadata; use `~/.agents/playbooks/github/gh_workflow.md` for side effects

Do not use:

- user wants to create/edit PR in GitHub: `~/.agents/playbooks/github/gh_workflow.md`
- repo is Elastic/Kibana and you want Elastic-style sections: `~/.agents/playbooks/github/compose_pr_elastic.md`
- user is asking for PR review feedback: `~/.agents/playbooks/review/router.md`

First actions:

1. Inspect the current diff/branch context and the user-supplied issue refs.
2. Extract only evidence you can verify (summary, test plan, migration notes).
3. If issue linkage or test evidence is missing, keep placeholders instead of
   inventing details.

Rules:

- keep it short and reviewable
- prefer bullets over prose
- test plan must be evidence: commands run + observed result
- link issues explicitly:
  - `Closes #X` only when merging should close the issue
  - `Addresses #X` when it should not auto-close
  - never invent issue numbers

Output:

- Return only the PR body draft, ready to paste or hand to
  `~/.agents/playbooks/github/gh_workflow.md`.
- If important inputs are missing, say exactly which placeholders still need
  confirmation.

Template (copy then delete unused sections):

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan

-
```
