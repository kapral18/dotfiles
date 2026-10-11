---
sidebar_position: 2
---

# Identity and keys

Private keys do not live in this repo or on disk. The checked-in files are selectors, public keys, and agent config.

## SSH agent

SSH is wired to the 1Password agent socket through:

- [`home/private_dot_ssh/private_executable_config`](../../../../home/private_dot_ssh/private_executable_config)

The 1Password agent key set is configured by:

- [`home/dot_config/exact_private_1Password/exact_ssh/readonly_agent.toml.tmpl`](../../../../home/dot_config/exact_private_1Password/exact_ssh/readonly_agent.toml.tmpl)

Installed target:

```text
~/.ssh/config
```

## Public keys on disk

Git uses public-key paths as identity selectors. The matching private keys stay in 1Password.

Templates:

- [`home/private_dot_ssh/readonly_primary_public_key.pub.tmpl`](../../../../home/private_dot_ssh/readonly_primary_public_key.pub.tmpl)

## Troubleshooting

```bash
echo "$SSH_AUTH_SOCK"
ssh-add -l
git config --show-origin --get core.sshCommand
```

## Related

- [Git config](git-config.md)
- [Security and secrets](../../security/security-and-secrets.md)
