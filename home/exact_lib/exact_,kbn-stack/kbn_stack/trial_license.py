"""Trial-license activation and the per-data-dir expiry sidecar that drives expired-dir rotation.

Snapshot data dirs persist under ``~/work/kibana/es_data/<name>`` (branch,
``--data``, or ``shared-<version>``) and carry the cluster's self-generated
30-day trial license, which Elasticsearch lets a cluster start only once. Once
it expires, ES blocks cluster health, kbn-es's readiness poll fails and it stops
ES before the setup trigger, so the dir can never boot again. The tool owns
that lifecycle: after each start it records the license expiry in
``<data dir>/.kbn-stack-license.json``; before a start (recorded expiry passed)
or when the ES log reports ``LICENSE [EXPIRED]`` (legacy dir) it moves the dir
to ``<name>.expired-<timestamp>`` and starts a fresh cluster once. Moved dirs
are kept, not deleted.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from kbn_stack import config


def ensure_trial_license(es_url: str, data_path: Path | None = None) -> None:
    """Activate a trial license once ES is reachable, then record its expiry.

    SAML (mock IdP dev login) requires a trial license; a basic license makes the
    SAML realm non-compliant and Kibana login loops on /security/reset_session.
    start_trial is idempotent: it no-ops once the cluster is already on trial.
    With ``data_path`` the license ES reports afterwards is written to the data
    dir's sidecar so the next start can rotate the dir before the trial expires
    under it (see ``rotate_expired_data_dir``).
    """
    auth = config.ELASTIC_BASIC_AUTH
    for _ in range(60):
        health = subprocess.run(
            ["curl", "-fsS", "-m5", "-u", auth, f"{es_url}/_cluster/health"],
            capture_output=True,
            check=False,
        )
        if health.returncode == 0:
            subprocess.run(
                ["curl", "-fsS", "-m10", "-u", auth, "-X", "POST", f"{es_url}/_license/start_trial?acknowledge=true"],
                capture_output=True,
                check=False,
            )
            if data_path is not None:
                record_license(es_url, data_path)
            return
        time.sleep(2)


def record_license(es_url: str, data_path: Path) -> None:
    """Write the license ES currently reports into the data dir's sidecar (best effort)."""
    probe = subprocess.run(
        ["curl", "-fsS", "-m10", "-u", config.ELASTIC_BASIC_AUTH, f"{es_url}/_license"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return
    try:
        license_info = json.loads(probe.stdout).get("license", {})
    except (json.JSONDecodeError, AttributeError):
        return
    if not isinstance(license_info, dict) or not data_path.is_dir():
        return
    record = {
        "type": license_info.get("type"),
        "status": license_info.get("status"),
        "expiry_date_in_millis": license_info.get("expiry_date_in_millis"),
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    try:
        (data_path / config.LICENSE_SIDECAR).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


def recorded_license_expiry(data_path: Path) -> int | None:
    """The sidecar's ``expiry_date_in_millis``, or None when absent/unreadable/perpetual."""
    sidecar = data_path / config.LICENSE_SIDECAR
    try:
        record = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    expiry = record.get("expiry_date_in_millis") if isinstance(record, dict) else None
    return expiry if isinstance(expiry, int) else None


def license_expired_line(line: str) -> bool:
    return any(marker in line for marker in config.LICENSE_EXPIRED_MARKERS)


def rotate_expired_data_dir(data_path: Path, reason: str) -> Path | None:
    """Move a data dir whose trial is spent aside so the next boot forms a fresh cluster.

    ES lets a cluster start a trial once, so an expired dir can never serve this
    tool again (mock IdP login needs trial). The dir is renamed, never deleted;
    the notice names the new location so the user can inspect or remove it.
    """
    if not data_path.is_dir():
        return None
    target = data_path.with_name(f"{data_path.name}.expired-{time.strftime('%Y%m%d-%H%M%S')}")
    data_path.rename(target)
    print(
        f",kbn-stack: {reason}; moved {data_path} -> {target} and starting a fresh cluster "
        f"(new 30-day trial). Delete {target} to reclaim disk.",
        flush=True,
    )
    return target


def settle_expired_data_dir(data_path: Path, now_millis: int | None = None) -> Path | None:
    """Preflight: rotate ``data_path`` when its recorded trial expiry has passed."""
    expiry = recorded_license_expiry(data_path)
    if expiry is None:
        return None
    now = int(time.time() * 1000) if now_millis is None else now_millis
    if expiry > now:
        return None
    expired_on = time.strftime("%Y-%m-%d", time.localtime(expiry / 1000))
    return rotate_expired_data_dir(data_path, f"data dir {data_path.name}'s trial license expired on {expired_on}")
