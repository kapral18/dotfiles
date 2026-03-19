# Build Failure Debugging Guide

Step-by-step workflow for diagnosing and resolving Buildkite build failures.

---

## Debugging Sequence

### 1. Find the failed build

```bash
bk build list -p SLUG --state failed
bk build list -p SLUG --state failed --since 24h
```

### 2. View build details

```bash
bk build view BUILD_NUMBER -p SLUG
bk build view BUILD_NUMBER -p SLUG -o json | jq '.jobs[] | select(.state == "failed")'
```

### 3. List failed jobs

```bash
bk job list -p SLUG --state failed --since 24h
```

### 4. Get the failed job's log

```bash
bk job log JOB_UUID -p SLUG -b BUILD_NUMBER
bk job log JOB_UUID -p SLUG -b BUILD_NUMBER --no-timestamps
```

### 5. Check artifacts

```bash
bk artifacts list BUILD_NUMBER -p SLUG
bk artifacts download ARTIFACT_UUID
```

---

## Common Failure Categories

### Test Failures

**Indicators:**

- Exit code 1 from test runner
- Lines like `FAIL`, `FAILED`, `AssertionError`, `Expected ... but got ...`
- Test framework summary (e.g., `3 failed, 42 passed`)

**Log patterns to grep:**

```bash
bk job log JOB_UUID -p SLUG -b BUILD_NUMBER | grep -E '(FAIL|ERROR|AssertionError|Expected.*got)'
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
bk job log JOB_UUID -p SLUG -b BUILD_NUMBER | grep -iE '(ERR!|could not resolve|not found|403|401)'
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
bk build rebuild BUILD_NUMBER -p SLUG

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

**Action:** Check agent status (`bk agent list`), verify Docker registry access,
check network connectivity.

### Permission / Auth Failures

**Indicators:**

- `403 Forbidden`, `401 Unauthorized`
- Secret or environment variable missing
- Deployment credentials expired

**Log patterns to grep:**

```bash
bk job log JOB_UUID -p SLUG -b BUILD_NUMBER | grep -iE '(403|401|forbidden|unauthorized|permission denied|access denied)'
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
- **Use `bk api`** for detailed job metadata if standard commands are
  insufficient.
- **Filter by duration** to find slow builds:
  `bk build list -p SLUG --duration ">30m"`
