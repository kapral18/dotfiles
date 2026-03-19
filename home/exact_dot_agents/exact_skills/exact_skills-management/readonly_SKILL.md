---
name: skills-management
description: |-
  Author, update, or audit agent skills under ~/.agents/skills/. Use when
  creating a new skill, upgrading a tool-wrapping skill to a newer CLI
  version, or reviewing skill conventions.
---

# Skills Management

## Tool-Wrapping Skills

Skills that document a CLI tool must include `tool_version` in frontmatter:

```yaml
tool_version: "<binary> <version>"  # e.g. "bk 3.32.2", "knip 5.88.0"
```

### Authoring rules

- Use the real binary name on PATH — not wrapper aliases.
- All flags, syntax, defaults, and positional/named arguments must be verified
  against `<tool> --help` for the installed version. Do not guess.

### Upgrade procedure

1. Read `tool_version` from the skill's frontmatter (the **anchor version**).
2. Run `<tool> --version` to get the **installed version**.
3. If they match, stop — no upgrade needed.
4. Find the tool's canonical GitHub repo. Clone it to `/tmp`:

```bash
git clone --no-checkout <repo-url> /tmp/<tool-name>
```

5. Diff between the anchor version tag and the installed version tag:

```bash
cd /tmp/<tool-name>
git diff <anchor-version-tag>...<installed-version-tag> -- <relevant-paths>
```

   Focus on: help text, command definitions, flag declarations, subcommand
   registration, CLI entrypoints. Skip: tests, CI configs, docs unrelated to
   CLI surface.

6. For each change found in the diff:
   - Verify the change against `<tool> --help` / `<tool> <subcommand> --help`
     on the installed version.
   - Update the corresponding skill section with the verified behavior.
   - Do not propagate changes you cannot verify locally.

7. Update `tool_version` in frontmatter to the installed version.
8. `chezmoi diff` — confirm only expected sections changed.

### When version tags are unclear

- `git tag -l` in the cloned repo to find the naming convention.
- Common patterns: `v3.32.2`, `3.32.2`, `cli/v3.32.2`, `bk/v3.32.2`.
- If the anchor version tag does not exist (tool was authored without one),
  treat the entire skill as unverified — re-audit all commands against
  `--help` output for the installed version.

## Skill Source Layout

| What               | Path                                               |
| ------------------ | -------------------------------------------------- |
| skills source dir  | `home/exact_dot_agents/exact_skills/`               |
| skill entrypoint   | `exact_<name>/readonly_SKILL.md`                    |
| optional reference | `exact_<name>/exact_references/readonly_*.md`       |
