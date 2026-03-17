# Buildkite Skill — Troubleshooting Reference

Common failures with the `buildkite` CLI, with symptom, cause, and fix.

---

## Authentication

### 401 Unauthorized

**Symptom:** `buildkite` commands fail with `401 Unauthorized` or
`buildkite whoami` returns an auth error.

**Causes:**

- API token expired or revoked
- Token lacks required scopes
- Token copied with leading/trailing whitespace

**Fix:**

1. Generate a new token at <https://buildkite.com/user/api-access-tokens>
2. Ensure the token has `read_builds`, `write_builds`, `read_pipelines` scopes
   at minimum
3. Re-run setup:
   ```
   skills/buildkite/scripts/setup
   ```

---

### 403 Forbidden

**Symptom:** A specific operation returns `403 Forbidden` (e.g., triggering a
build, canceling a build).

**Causes:**

- API token missing required scopes for that operation
- User lacks permissions in the Buildkite organization

**Fix:**

- Check token scopes at <https://buildkite.com/user/api-access-tokens>
- Required scopes: `read_builds`, `write_builds` for build operations;
  `read_pipelines` for pipeline listing
- Ask an org admin to grant the necessary permissions

---

## Configuration

### `buildkite` wrapper or `bk` CLI not found

**Symptom:** Shell returns `command not found: buildkite` or
`command not found: bk`.

**Cause:** The `buildkite` wrapper isn't on PATH, or the underlying `bk` CLI is
not installed.

**Fix:**

```bash
# Install the bk CLI via Homebrew
brew tap buildkite/buildkite && brew install buildkite/buildkite/bk
```

Or download a binary from <https://github.com/buildkite/cli/releases>.

---

### `buildkite` commands fail with "not configured"

**Symptom:** `buildkite` commands exit with a configuration error or prompt for
setup.

**Cause:** `bk configure` was never run, or the config file is
missing/corrupted.

**Fix:**

```bash
# Re-run configuration
bk configure

# Or run the full skill setup
skills/buildkite/scripts/setup
```

---

### `~/.buildkite-env` not found

**Symptom:** First-time use of the `buildkite` wrapper triggers interactive
setup.

**Cause:** The env file doesn't exist — this is expected on first run. The
wrapper auto-detects and launches `scripts/setup`.

**Fix:** If setup was interrupted, re-run manually:

```bash
skills/buildkite/scripts/setup

# Or create manually
echo "BUILDKITE_ORG=your-org-slug" > ~/.buildkite-env
chmod 600 ~/.buildkite-env
```

---

## Rate Limiting

### 429 Too Many Requests

**Symptom:** `buildkite` commands or `buildkite api` calls return
`429 Too Many Requests`.

**Cause:** Buildkite enforces API rate limits (varies by plan).

**Fix:**

- Wait 60 seconds before retrying
- Reduce request frequency — avoid rapid sequential `buildkite api` calls
- Use pagination to limit result sets

---

## Common CLI Errors

### Pipeline not found

**Symptom:** `buildkite build list --pipeline SLUG` returns a "not found" error.

**Causes:**

- Pipeline slug is wrong (check for typos)
- Pipeline is in a different organization than the configured one
- Pipeline was recently deleted

**Fix:**

```bash
# List all pipelines to find the correct slug
buildkite pipeline list

# Verify the current org
buildkite whoami
```

---

### Build number not found

**Symptom:** `buildkite build view BUILD_NUMBER --pipeline SLUG` returns "not
found".

**Causes:**

- Build number is wrong
- Build belongs to a different pipeline

**Fix:**

```bash
# List recent builds to find the correct number
buildkite build list --pipeline SLUG
```

---

## Quick Diagnostic Commands

```bash
# Test authentication
buildkite whoami

# Check CLI version
buildkite version

# List pipelines (verifies auth + org access)
buildkite pipeline list

# Test API access directly
buildkite api /v2/organizations/ORG/pipelines | jq 'length'

# Re-run full setup
skills/buildkite/scripts/setup
```
