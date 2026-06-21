# Packages

This setup treats package installation as declarative: edit a source list, run `chezmoi apply`, and let hooks converge the installed tools.

## Read path

| Slice                                               | Owns                                                                     |
| --------------------------------------------------- | ------------------------------------------------------------------------ |
| [Package catalog](catalog/index.md)                 | what the managed tools are for, grouped across package managers          |
| [Sources and scope](sources-and-scope.md)           | every package registry, list file, hook, and `.isWork` scoping rule      |
| [Reconcile behavior](reconcile-behavior.md)         | what each hook installs, updates, removes, or intentionally leaves alone |
| [Verification and troubleshooting](verification.md) | high-signal checks and common failure modes                              |

## Add-package recipes

| Priority | Package type                 | Recipe                                      |
| -------- | ---------------------------- | ------------------------------------------- |
| 1        | Homebrew formula/cask        | [Add a Homebrew package](homebrew.md)       |
| 2        | mise runtime/tool version    | [Pin a tool version](mise.md)               |
| 3        | Cargo crate                  | [Add a Cargo crate](cargo.md)               |
| 4        | Go tool                      | [Add a Go tool](go.md)                      |
| 5        | Ruby gem                     | [Add a Ruby gem](ruby.md)                   |
| 6        | Global yarn package          | [Add a global yarn package](yarn.md)        |
| 7        | uv Python tool               | [Add a uv tool](uv.md)                      |
| 8        | Custom GitHub/source package | [Add a custom package](custom.md)           |
| 9        | llama.cpp GGUF model         | [Add a llama.cpp model](llama-cpp-model.md) |

## Core workflow

1. Edit the source file under [`home/`](../../../../home/).
2. Run `chezmoi apply`.
3. Verify the tool is installed and available.

The package lists are source-of-truth declarations. For Homebrew specifically, `brew bundle cleanup --global --force` removes packages not present in the assembled Brewfile.

## Related

- [Chezmoi update](../chezmoi/update.md)
- [Custom commands](../../workflow/custom-commands/index.md)
- [Formatting and validation](../../code-quality/formatting.md)
