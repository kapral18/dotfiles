---
title: Skills
---

# Skills

Skills are the intent router below the SOP. The SOP says "load the matching skill"; each skill says what to do for that intent.

| Slice                                                                         | Covers                                                               |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| [Review and delivery](review-and-delivery.md)                                 | reviews, GitHub, PR/issue text, communication                        |
| [Memory and orchestration](memory-and-orchestration.md)                       | durable memory, proof receipts, specs, builds, delegation            |
| [Repo workflow and code intelligence](repo-workflow-and-code-intelligence.md) | git/worktrees, semantic tools, clone research, cleanup scanners      |
| [Elastic and Kibana](elastic-and-kibana.md)                                   | domain overlay, Buildkite, labels, ownership, backports, kbn-standup |
| [External tools and media](external-tools-and-media.md)                       | Google Workspace, flights, browser control, images                   |

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

## Loading procedures by branch and phase

Entrypoints retain routing, shared boundaries, and mandatory load triggers. Complete branch procedures live in references; a reference is required before its matching action, not optional background reading. Review controllers record phase, evidence, and unresolved gates in the existing review spec. After compaction they reopen instructions needed by the current phase and revisit gates invalidated by new evidence.

| Skill                     | Conditionally loaded procedure                                                                          |
| ------------------------- | ------------------------------------------------------------------------------------------------------- |
| `k-review`                | State, change, and product gates; drafting/delivery; fix loop; post-review stage                        |
| `k-deep-review`           | Scope, necessity, roster, findings audit, adversarial verification, judgment, live-UI result validation |
| `k-artifact`              | Generated HTML or live overlay                                                                          |
| `k-cli-skills`            | New skill authoring or installed-version upgrade                                                        |
| `k-communication`         | Existing-thread reply procedure; `external-replies.md` remains required for all external drafting       |
| `k-diagnosing-bugs`       | Fix and cleanup after assessment                                                                        |
| `k-elastic-domain`        | GitHub composition or commit attribution                                                                |
| `k-git`                   | Commit/push details before the corresponding operation                                                  |
| `k-kbn-stack`             | Runtime lifecycle and isolation before start, reuse, stop, or runtime interpretation                    |
| `k-kbn-backport`          | Staging and continuing a conflicted run, in the existing conflict reference                             |
| `k-kibana-console-monaco` | Typed demo Enter handling                                                                               |
| `k-letsfg`                | Rendered-UI browser fallback                                                                            |
| `k-playwriter`            | Video recording and frame verification                                                                  |
| `k-research`              | Source inspection or multi-source claims                                                                |
| `k-ui-capture`            | Diff inventory or upload/embedding                                                                      |
| `k-walkthrough`           | Diagram node metadata and example                                                                       |

`k-present-pr` instead uses a bundled template helper: the model reads the complete editable HTML while the helper preserves fixed CSS/JS. Authoring and browser verification remain required.

Measure the entrypoint plus every reference actually needed for the path. Splitting alone does not reduce a complete workflow's total: all-branch paths add routing overhead. These changes target irrelevant branch reads and phase reloading; they do not retire rules or establish universal model-behavior equivalence.

## Cross-skill hygiene

- Composition skills sanitize public GitHub text before drafting or posting.
- `k-compose-pr`, `k-compose-issue`, and `k-github` reuse review's GitHub context intake when output depends on existing PR/issue/comment context.
- Generic skills own portable mechanics only. If a rule names an org, repo, product, team, label, bot login, CI instance, PR template, live-UI target, ownership policy, or release-note/backport rule, put it in a verified domain overlay or dedicated domain skill.
- Generic skills may dispatch to a domain overlay after verifying the target; they must not inline Elastic/Kibana or other domain defaults.
- GitHub issue worktrees prefer `,gh-worktree issue <owner/repo> <issue_number> --branch <branch-base-name>`.

## Credits

Four skills are adapted from Matt Pocock's [`mattpocock/skills`](https://github.com/mattpocock/skills) (MIT-licensed). Attribution lives here rather than inline in each `SKILL.md` so it does not consume model context when the skill loads.

| Skill                    | Adapted from                                                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `k-writing-great-skills` | [`k-writing-great-skills`](https://github.com/mattpocock/skills/tree/main/skills/productivity/writing-great-skills) |
| `k-codebase-design`      | [`k-codebase-design`](https://github.com/mattpocock/skills/tree/main/skills/engineering/codebase-design)            |
| `k-diagnosing-bugs`      | [`k-diagnosing-bugs`](https://github.com/mattpocock/skills/tree/main/skills/engineering/diagnosing-bugs)            |
| `k-prototype`            | [`k-prototype`](https://github.com/mattpocock/skills/tree/main/skills/engineering/prototype)                        |
