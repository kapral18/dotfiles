# GitHub PR Body Playbook (General)

Scope:

- produces a PR body draft only
- do not run `gh` or change PR metadata; use `~/.agents/playbooks/github/gh_workflow.md` for side effects

When NOT to use:

- user wants to create/edit PR in GitHub: `~/.agents/playbooks/github/gh_workflow.md`
- repo is Elastic/Kibana and you want Elastic-style sections: `~/.agents/playbooks/github/compose_pr_elastic.md`
- user is asking for PR review feedback: `~/.agents/playbooks/review/router.md`

Rules:

- keep it short and reviewable
- prefer bullets over prose
- test plan must be evidence: commands run + observed result
- link issues explicitly:
  - `Closes #X` only when merging should close the issue
  - `Addresses #X` when it should not auto-close
  - never invent issue numbers

Template (copy then delete unused sections):

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan

-
```
