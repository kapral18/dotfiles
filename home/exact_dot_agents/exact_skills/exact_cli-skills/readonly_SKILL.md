---
name: cli-skills
description: Author or upgrade CLI tool skills. Use when creating a new skill for a CLI tool or upgrading an existing CLI skill to a newer version.
---

# CLI Tool Skills

Skills that document a CLI tool must include `tool_version` in frontmatter:

```yaml
tool_version: "<binary> <version>" # e.g. "bk 3.32.2", "knip 5.88.0"
```

### Authoring a new skill

1. Run `<tool> --version` to get the installed version.
2. Find the tool's canonical GitHub repo (use `gh` or web search).
3. Clone to `/tmp`:

```bash
git clone <repo-url> /tmp/<tool-name>
```

1. Investigate the CLI surface thoroughly from source — focus on:
   - Command/subcommand registration (entrypoints, command files)
   - Flag and argument declarations
   - Help text templates
   - Default values and output formats

   Skip: tests, CI configs, docs unrelated to CLI surface.

2. Cross-verify every finding against the installed binary:

```bash
<tool> --help
<tool> <subcommand> --help
```

Source is for understanding; `--help` is the truth. Do not include anything that cannot be verified against the installed binary.

1. Create the skill directory and files:
   - `home/exact_dot_agents/exact_skills/exact_<name>/readonly_SKILL.md`
   - Optional: `exact_references/readonly_*.md` for detailed sub-topics
2. Set `tool_version` in frontmatter to the installed version.
3. Use the real binary name on PATH — not wrapper aliases.
4. `chezmoi diff` to verify, then `chezmoi apply`.

### Upgrading an existing skill

1. Read `tool_version` from frontmatter (the **anchor version**).
2. Run `<tool> --version` to get the **installed version**.
3. If they match, stop — no upgrade needed.
4. Clone the repo to `/tmp` (or pull if already cloned):

```bash
git clone <repo-url> /tmp/<tool-name>
# or if reusing an existing clone:
cd /tmp/<tool-name> && git fetch --all --tags && git pull
```

1. Find the version tags and diff between them:

```bash
cd /tmp/<tool-name>
git tag -l                                        # find naming convention
git diff <anchor-tag>...<installed-tag> -- <relevant-paths>
```

Focus on: command definitions, flag declarations, subcommand registration, help text, CLI entrypoints. Skip: tests, CI configs, unrelated docs.

1. For each change in the diff:
   - Verify against `<tool> --help` / `<tool> <subcommand> --help`.
   - Update only the affected skill sections.
   - Do not propagate changes you cannot verify locally.
2. Update `tool_version` in frontmatter to the installed version.
3. `chezmoi diff` — confirm only expected sections changed.

### When version tags are unclear

- `git tag -l` in the cloned repo to find the naming convention.
- Common patterns: `v3.32.2`, `3.32.2`, `cli/v3.32.2`, `bk/v3.32.2`.
- If the anchor tag does not exist, treat the entire skill as unverified — re-audit all commands against `--help` output for the installed version.

## Skill Source Layout

| What               | Path                                          |
| ------------------ | --------------------------------------------- |
| skills source dir  | `home/exact_dot_agents/exact_skills/`         |
| skill entrypoint   | `exact_<name>/readonly_SKILL.md`              |
| optional reference | `exact_<name>/exact_references/readonly_*.md` |
