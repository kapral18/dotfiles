# Upgrading

## Upgrading an existing skill

1. Read `tool_version` from frontmatter (the **anchor version**).
2. Run `<tool> --version` to get the **installed version**.
3. If they match, stop — no upgrade needed.
4. Clone/reuse the repo under `/tmp`; refresh without `git pull`:

```bash
git clone <repo-url> /tmp/<tool-name>
# or if reusing an existing clone:
cd /tmp/<tool-name> && git fetch --prune --tags
```

1. Find the version tags and diff between them:

```bash
cd /tmp/<tool-name>
git tag -l                                        # find naming convention
git diff <anchor-tag>...<installed-tag> -- <relevant-paths>
```

Focus on: command definitions, flag declarations, subcommand registration, help text, CLI entrypoints.
Skip: tests, CI configs, unrelated docs.

1. For each change in the diff:
   - Verify against `<tool> --help` / `<tool> <subcommand> --help`.
   - Update only the affected skill sections.
   - Do not propagate changes you cannot verify locally.
2. Update `tool_version` in frontmatter to the installed version.
3. Upgrade is done when the diffed CLI changes are reflected in the skill, `tool_version` matches `<tool> --version`, and `chezmoi diff` shows only expected sections changed.

## When version tags are unclear

- `git tag -l` in the cloned repo to find the naming convention.
- Common patterns: `v3.32.2`, `3.32.2`, `cli/v3.32.2`, `bk/v3.32.2`.
- If the anchor tag does not exist, treat the entire skill as unverified — re-audit all commands against `--help` output for the installed version.
