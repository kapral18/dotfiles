---
sidebar_position: 4
---

# Verifying Templates

`chezmoi apply` renders every `*.tmpl` file through Go's templating engine. A typo in an action (`{{ ... }}`), an unbalanced `{{ if }}`, or a renamed `.chezmoidata` key makes the render fail — and on a fresh machine that surfaces mid-bootstrap, the worst possible time. The template verification check catches these in the source repo first.

## What runs

```bash
make verify-templates
```

This renders every managed template under `home/` and fails if any template does not render. It is also part of `make check` (and therefore the pre-commit hook), so any commit that touches a `.tmpl` is validated automatically.

Under the hood it calls `scripts/verify_templates.py`, which:

- discovers every `*.tmpl` under `home/`
- skips chezmoi's own config template (`.chezmoi.toml.tmpl`), which uses interactive `prompt*` functions that exist only during `chezmoi init`, not `chezmoi execute-template`
- pipes each file through `chezmoi execute-template` and reports any that fail, with the chezmoi error line

## Scope

This is a render/parse check that runs locally, where template functions that read the host or secrets (`lookPath`, `output`, `pass`, 1Password, and friends) resolve normally. It verifies that templates _render_; it does not assert the rendered _content_.

## When it fails

The output names the offending file and the chezmoi error:

```text
template verification failed (1/49 did not render):
  ✗ home/dot_config/example/something.tmpl
      template: stdin:12: unexpected EOF
```

Render the single file to iterate on the fix:

```bash
chezmoi execute-template < home/path/to/file.tmpl
```

See also [Debugging Chezmoi Hooks](./debug-hooks.md).
