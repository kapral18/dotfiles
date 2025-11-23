# Dotfiles Project - Agent Instructions

## Homebrew Package Management

When adding formulas or casks to Brewfile:

- **Always verify existence** against formulae.brew.sh or GitHub repos before adding (follow § 6.2 web search priority).
- Use search queries: `"homebrew <package-name>"`, `"brew formulae <package-name>"`.
- Once you identify a package name, verify locally with `brew info <formula|cask>` (works for both formulas and casks).
- Never invent package names, URLs, or tap information. When uncertain, ask the user.
- Correct sources: homebrew-core (default, no tap needed), official taps (e.g., `charliebruce/tap`), or community taps.
- If verification fails, report findings to user instead of guessing.
