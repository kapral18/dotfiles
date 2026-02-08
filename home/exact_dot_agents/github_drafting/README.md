# GitHub Drafting (Agent Guidance)

This directory is agent-only guidance for composing PR descriptions and issue
bodies.

It is NOT repository `.github/*` templates. Do not copy it into a repo unless
the user explicitly asks.

How to use:

1. Read `~/.agents/gh.md` for PR creation constraints (issue linking,
   approvals, label confirmation).
2. Pick a domain:
   - General: `~/.agents/github_drafting/general/README.md`
   - Elastic: `~/.agents/github_drafting/elastic/README.md`
3. Use ONLY the contents of a `*.template.md` file as the draft body.
4. Fill placeholders, then delete sections that don’t apply.

Domain layout:

- `general/`: general repos
- `elastic/`: Elastic Stack repos
