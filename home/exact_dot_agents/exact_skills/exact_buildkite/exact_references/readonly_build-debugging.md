# Build Failure Debugging Guide

Step-by-step workflow for diagnosing and resolving Buildkite build failures.

---

## Triage Workflow

Run `buildkite triage <pipeline-slug>` to automatically fetch failed builds,
analyze logs, and categorize failures.

```bash
# Triage the most recent failed build
buildkite triage my-pipeline

# Triage a specific build
buildkite triage my-pipeline --build 456

# Triage the last 5 failed builds
buildkite triage my-pipeline --last 5
```

The triage command outputs a table of failed jobs with their failure category
and the key log line that triggered the match. Use this to quickly identify root
cause, then apply the remediation guidance below.

---

## Common Failure Categories

### Test Failures

**Indicators:**

- Exit code 1 from test runner
- Lines like `FAIL`, `FAILED`, `AssertionError`, `Expected ... but got ...`
- Test framework summary (e.g., `3 failed, 42 passed`)

**Log patterns to grep:**

```bash
buildkite job log JOB_ID | grep -E '(FAIL|ERROR|AssertionError|Expected.*got)'
```

**Action:** Read the specific test failures, check if they reproduce locally,
fix the code.

### Dependency Resolution Errors

**Indicators:**

- `npm ERR!`, `pip install failed`, `Could not resolve dependencies`
- Package version conflicts, missing packages
- Registry authentication failures

**Log patterns to grep:**

```bash
buildkite job log JOB_ID | grep -iE '(ERR!|could not resolve|not found|403|401)'
```

**Action:** Check lock files, verify registry access, pin problematic versions.

### Timeouts

**Indicators:**

- `Job timed out`, `exceeded time limit`
- Build terminated without test output completing
- Builds that ran much longer than usual

**Action:** Check for infinite loops, long-running tests, or resource
contention. Consider increasing timeout or splitting the job.

### Out of Memory (OOM)

**Indicators:**

- `Killed`, `OOMKilled`, `signal: killed`
- Process terminated without error output
- Memory usage spikes in agent metrics

**Action:** Profile memory usage, reduce parallelism, increase agent memory, or
split into smaller jobs.

### Flaky Tests

**Indicators:**

- Test passes on retry without code changes
- Intermittent failures in the same test
- Timing-dependent assertions

**Diagnosis:**

```bash
# Rebuild to confirm flakiness
buildkite build rebuild BUILD_NUMBER --pipeline SLUG

# Compare logs between failing and passing runs
```

**Action:** Fix timing dependencies, add retries for external service calls,
quarantine flaky tests.

### Infrastructure Issues

**Indicators:**

- `docker pull` failures, registry timeouts
- Agent disconnected, agent lost
- Network connectivity errors
- `No agents available`

**Action:** Check agent status (`buildkite agent list`), verify Docker registry
access, check network connectivity.

### Permission / Auth Failures

**Indicators:**

- `403 Forbidden`, `401 Unauthorized`
- Secret or environment variable missing
- Deployment credentials expired

**Log patterns to grep:**

```bash
buildkite job log JOB_ID | grep -iE '(403|401|forbidden|unauthorized|permission denied|access denied)'
```

**Action:** Rotate credentials, verify environment variables are set in pipeline
settings, check IAM/role permissions.

---

## Tips

- **Start with the last 50 lines** of a failed job log — the error summary is
  usually at the end.
- **Compare with last passing build** — diff the logs to find what changed.
- **Check the commit diff** — the failure is usually in the code that changed
  between the last green build and this one.
- **Use `buildkite api`** for detailed job metadata if `buildkite job list`
  output is insufficient.
