---
sidebar_position: 5
---

# Add A Go Tool

Go-installed tools are managed via a list.

## Preconditions

- Go is installed.
- You verified the module path for the tool.

## Steps

1. Add the module path to:
   - [`home/readonly_dot_default-golang-pkgs.tmpl`](../../../../home/readonly_dot_default-golang-pkgs.tmpl)

   This installs as `~/.default-golang-pkgs`. The file is a chezmoi template, so entries can be gated per profile, e.g. personal-only:

   ```text
   {{ if ne .isWork true }}
   github.com/owner/personal-only-tool
   {{ end -}}
   ```

2. Apply:

   ```bash
   chezmoi apply
   ```

Hook:

- [`home/.chezmoiscripts/run_onchange_after_05-update-golang-pkgs.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-update-golang-pkgs.sh.tmpl)
- Reconcile helper: [`scripts/reconcile_golang_pkgs.py`](../../../../scripts/reconcile_golang_pkgs.py)

## Verification

```bash
which <tool>
<tool> --version
```

## Rollback / Undo

1. Remove the module path from [`home/readonly_dot_default-golang-pkgs.tmpl`](../../../../home/readonly_dot_default-golang-pkgs.tmpl).
2. Re-apply:

```bash
chezmoi apply
```

The hook reconciles installed binaries against the list: when a module is removed, its binary is deleted from `GOBIN` on the next apply. Reconciliation is tracked via a state ledger at `~/.cache/chezmoi/golang-pkgs-state`, so only binaries this tooling installed are ever removed — binaries you installed by hand with `go install` are left untouched. "Installed" is detected by the presence of the binary in `GOBIN` (`go env GOBIN`, else `$(go env GOPATH)/bin`), not by `go list -m all` (which does not enumerate installed binaries).
