---
title: Skills
---

# Skills

Skills are the intent router below the SOP. The SOP says "load the matching skill"; each skill says what to do for that intent.

| Slice                                                                         | Covers                                                           |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| [Review and delivery](review-and-delivery.md)                                 | reviews, GitHub, PR/issue text, communication                    |
| [Repo workflow and code intelligence](repo-workflow-and-code-intelligence.md) | git/worktrees, semantic tools, clone research, cleanup scanners  |
| [Memory and orchestration](memory-and-orchestration.md)                       | durable memory, Ralph, improvement/interview workflows           |
| [Elastic and Kibana](elastic-and-kibana.md)                                   | domain overlay, Buildkite, labels, ownership, backports, standup |
| [External tools and media](external-tools-and-media.md)                       | Google Workspace, flights, browser control, image generation     |

## Entry contract

Every skill should make four things obvious near the top:

| Field           | Purpose                               |
| --------------- | ------------------------------------- |
| `Use when`      | routing triggers                      |
| `Do not use`    | boundaries and escalation             |
| `First actions` | mandatory first probes or skill loads |
| `Output`        | expected deliverable                  |

The `description` frontmatter is the primary routing signal. For non-manual skills, include the concise `Use when` trigger there; the body is only available after routing has already loaded the skill. Body `Use when` blocks may stay as detailed post-load applicability checks, but no routing trigger should exist only in the body. Keep descriptions specific, include non-obvious trigger words, and state repo/org constraints when a skill is gated.

## Source map

| Surface    | Path                                                                                     |
| ---------- | ---------------------------------------------------------------------------------------- |
| Source     | [`home/exact_dot_agents/exact_skills/`](../../../../home/exact_dot_agents/exact_skills/) |
| Target     | `~/.agents/skills/`                                                                      |
| Entrypoint | `SKILL.md` in each skill folder                                                          |
| References | optional `references/` under the skill folder                                            |

## Cross-skill hygiene

- Composition skills sanitize public GitHub text before drafting or posting.
- `compose-pr`, `compose-issue`, and `github` reuse review's GitHub context intake when output depends on existing PR/issue/comment context.
- Generic skills own portable mechanics only. If a rule names an org, repo, product, team, label, bot login, CI instance, PR template, live-UI target, ownership policy, or release-note/backport rule, put it in a verified domain overlay or dedicated domain skill.
- Generic skills may dispatch to a domain overlay after verifying the target; they must not inline Elastic/Kibana or other domain defaults.
- GitHub issue worktrees prefer `,gh-worktree issue <owner/repo> <issue_number> --branch <branch-base-name>`.

## Credits

Four skills are adapted from Matt Pocock's [`mattpocock/skills`](https://github.com/mattpocock/skills) (MIT-licensed). Attribution lives here rather than inline in each `SKILL.md` so it does not consume model context when the skill loads.

| Skill                  | Adapted from                                                                                                      |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `writing-great-skills` | [`writing-great-skills`](https://github.com/mattpocock/skills/tree/main/skills/productivity/writing-great-skills) |
| `codebase-design`      | [`codebase-design`](https://github.com/mattpocock/skills/tree/main/skills/engineering/codebase-design)            |
| `diagnosing-bugs`      | [`diagnosing-bugs`](https://github.com/mattpocock/skills/tree/main/skills/engineering/diagnosing-bugs)            |
| `prototype`            | [`prototype`](https://github.com/mattpocock/skills/tree/main/skills/engineering/prototype)                        |
