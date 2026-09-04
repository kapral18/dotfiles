# Authoring

## Authoring a new skill

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
3. Use the real binary name on PATH, rather than wrapper aliases.
4. Authoring is done when every command, subcommand, and flag documented in the skill appears in `<tool> --help` / `<tool> <subcommand> --help` output and `tool_version` matches `<tool> --version`; then `chezmoi diff` to verify and `chezmoi apply`.
