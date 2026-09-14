---
name: k-cli-skills
description: "Use when creating a new CLI tool skill or upgrading an existing CLI skill to a newer installed version."
---

# CLI Tool Skills

Subagent dispatch: inline (implement for a settled skill rewrite) — authoring needs tool inspection plus craft judgment;
a settled edit set may go to the implementation band.

This skill owns CLI mechanics.
Apply `~/.agents/skills/k-writing-great-skills/SKILL.md` for invocation, hierarchy, leading words, completion criteria, and pruning.
Load that craft contract when entering here directly; when it called this skill, continue under the contract it already loaded instead of recursively loading it again.
Read it fresh when its text changes or is pruned.

Skills that document a CLI tool must include `tool_version` in frontmatter:

```yaml
tool_version: "<binary> <version>" # e.g. "bk 3.32.2", "knip 5.88.0"
```

## Authoring a new skill

Before authoring a new CLI skill, read and follow `~/.agents/skills/k-cli-skills/references/authoring.md` in full, before source inspection or edits.

## Upgrading an existing skill

Before checking or upgrading an existing CLI skill, read and follow `~/.agents/skills/k-cli-skills/references/upgrading.md` in full, including the equal-version stop and unclear-tag re-audit fallback.

## Skill Source Layout

| What               | Path                                          |
| ------------------ | --------------------------------------------- |
| skills source dir  | `home/exact_dot_agents/exact_skills/`         |
| skill entrypoint   | `exact_<name>/readonly_SKILL.md`              |
| optional reference | `exact_<name>/exact_references/readonly_*.md` |

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Launch one strong implement packet with the settled edit set and acceptance before rewriting the skill;
the root MUST NOT substitute its own inline rewrite for that packet absent an explicit user no-delegation instruction;
if the lane is unavailable report blocked. Authoring judgment and tool inspection stay with the root.
