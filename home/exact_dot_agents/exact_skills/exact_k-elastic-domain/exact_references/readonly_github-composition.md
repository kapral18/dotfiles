# Github composition

## GitHub and PR composition

Apply with `k-compose-pr`, `k-compose-issue`, `k-github`, or review flows preparing GitHub-visible text.

Precedence for `elastic/kibana` PR composition:

- this overlay owns Kibana-specific title style, PR body sections, release-note inclusion, and assistance footer policy
- `k-kibana-labels-propose` owns Kibana label/backport/version classification; invoke it and use its packet
- `k-github` owns GitHub mechanics and approval gates for applying metadata
- once this overlay applies, generic skills must not invent fallback Kibana title style, labels, release-note state, or footer policy;
  stop and obtain the domain packet instead of guessing

Public text sanitization:

- For behavior/UI bugs, use portable local repro wording: `local Kibana`, `http://localhost:5601`, `a user with only <privilege>`, or explicit role/user setup.
- Do not publish private hostnames, non-standard local domains, `/tmp/...`, absolute workspace paths, browser session names, or one-off local accounts unless the text tells readers how to create them.

Elastic org PR bodies:

- Append `Assisted with <Tool> using <Model>` at the very end, after all other sections and a blank line.
- Use the actual tool/model when known; if unknown, use a reasonable label and ask the user to confirm.
- Known labels: Cursor, Claude Code, Copilot, OpenCode, pi-coding-agent.
- Gather only verified evidence for summary, root cause/fix, and test plan.

`elastic/kibana` PR bodies:

- Before drafting, invoke `k-kibana-labels-propose` for labels/backports/version targeting.
- Before drafting, read `~/.agents/skills/k-elastic-domain/references/pr-issue-templates.md` and select exactly one Kibana PR template:
  - `Bugfix`: linked issue/proposed labels indicate `bug`, `regression`, or `release_note:fix`
  - `Feature`: proposed label is `release_note:feature`
  - `Chore/Migration`: chores, migrations, refactors, or test-only maintenance
  - `Default`: only when the others do not fit
- Fill the PR publication packet `template` field: selected template, evidence, required headings present, omitted sections with template-allowed reasons.
  For `Bugfix`, `## Root Cause` and `## Fix` are standalone; screenshots use the packet `screenshots` field and require uploaded embeds or explicit skip approval.
- PR titles should use Kibana's bracketed area style when evidence chooses an area, e.g. `[Console] Fix ...`.
  Derive from linked issue, changed-path ownership, or same-area PR precedent; ask if multiple brackets remain plausible.
  Do not use a Conventional Commit header as the PR title unless that exact area has precedent.
- Include `## Release Note` only for `release_note:fix` or `release_note:feature`; omit for enhancement/skip/unverified states.
- Do not skip/defer label proposal; body finalization requires it.
- If reviewer/ownership guidance is requested, load `k-kibana-management-ownership`.
- Never invent issue numbers; choose `Closes #X` vs `Addresses #X` intentionally.

`elastic/kibana` issue bodies: include environment details when UI or deployment matters;
leave unknown stack/deployment/browser fields blank or marked for follow-up; do not invent them.

Templates live in `~/.agents/skills/k-elastic-domain/references/pr-issue-templates.md`.
