"""Constants shared by every ,kbn-stack module, plus the ``fail`` exit helper."""

from __future__ import annotations

import re
import sys
from pathlib import Path

TRIGGER_STRING = "succ kbn/es setup complete"
SERVERLESS_TRIGGER_STRING = "[runServerlessCluster] Security index ready"

# ES log lines proving the data dir's trial license has expired. ES then blocks
# cluster health, kbn-es's readiness poll fails, and kbn-es stops ES ~120s later
# without ever logging TRIGGER_STRING, so waiting for it would only time out.
LICENSE_EXPIRED_MARKERS = ("LICENSE [EXPIRED]", "operation due to expired license")

# Per data dir record of the license ES reported after setup; the preflight
# rotates a dir whose recorded expiry has passed before booting it again.
LICENSE_SIDECAR = ".kbn-stack-license.json"
ES_SETUP_TIMEOUT = 600.0
# How long a start waits for Kibana to answer /api/status.
KIBANA_READY_TIMEOUT = 600.0

# wait_for_trigger verdicts.
WAIT_TRIGGER = "trigger"
WAIT_EXPIRED = "expired"
WAIT_EXITED = "exited"
WAIT_TIMEOUT = "timeout"

# After the setup trigger appears, how long an attacher waits for the shared ES
# port to be identity-verified before treating the trigger as stale evidence.
SHARED_ES_CONFIRM_TIMEOUT = 30.0
# A shared ES with no live Kibana client (none listening, none still starting)
# is stopped after this grace; its reaper watchdog polls every REAPER_POLL seconds.
SHARED_ES_IDLE_TIMEOUT = 60.0
SHARED_ES_REAPER_POLL_SECONDS = 10.0
# Branch changes to server-side paths carrying these fragments alter what a
# Kibana writes into the shared .kibana* indices (saved-object definitions,
# model versions, migrations) or into cluster-wide ES setup, so such a worktree
# gets an isolated ES unless --share-es.
ISOLATION_PATH_MARKERS = ("saved_object", "model_version", "/migrations/", "index_template", "ingest_pipeline")
REGISTRY_PATH = Path.home() / ".cache" / "kbn-stack" / "registry.json"
ES_DATA_ROOT = Path.home() / "work" / "kibana" / "es_data"
ELASTIC_AUTH = ("elastic", "changeme")
ELASTIC_BASIC_AUTH = f"{ELASTIC_AUTH[0]}:{ELASTIC_AUTH[1]}"

# Reserved registry key holding shared ES instances (keyed by ES version).
# Every other top-level key remains an absolute worktree path, so existing
# per-worktree lookups (live-ui contract, skills) keep working unchanged.
ES_INSTANCES_KEY = "__es__"
SHARED_DATA_PREFIX = "shared-"

# Absolute free-space floor for Lucene merges. kbn-es already sets
# cluster.routing.allocation.disk.threshold_enabled=false, but the merge
# scheduler still uses indices.merge.disk.watermark.high=95%. On a ~1TB APFS
# volume at 96% used that budget clamps to 0 bytes despite tens of GB free,
# so overnight Kibana writes explode unmerged segments and trip the 1.5g parent breaker.
MERGE_DISK_WATERMARK = "indices.merge.disk.watermark.high=2gb"

# Kibana server plugin groups from @kbn/projects-solutions-groups KIBANA_GROUPS.
# Default platform covers Management (console, index management, stack management).
# --groups all skips the allowlist so every group loads. Restart to change groups.
PLUGIN_GROUPS = ("platform", "observability", "security", "search", "workplaceai", "vectordb")
DEFAULT_PLUGIN_GROUPS = "platform"
ALLOWLIST_KEY = "plugins.allowlistPluginGroups"

# Snapshot kbn-es otherwise pins -Xms1536m -Xmx1536m. 1g matches serverless kbn-es.
DEFAULT_ES_HEAP = "1g"
HEAP_SIZE_RE = re.compile(r"^[0-9]+[kKmMgG]$")

# SIGTERM grace before SIGKILL. Tests patch this so hang-after-unbind coverage stays fast.
KILL_GRACE_SECONDS = 5.0
KILL_POLL_SECONDS = 0.05

# Slot -> port/cookie/key derivation. Slot 0 reproduces the historical defaults
# (Kibana 5601, ES 9200/9300). Each slot bumps Kibana by 1 and ES by 2 (HTTP +
# transport) so neighbouring slots never collide.
KBN_PORT_BASE = 5601
ES_HTTP_BASE = 9200
ES_TRANSPORT_BASE = 9300
PROJECT_TYPES = ("es", "security", "oblt")
ES_PROJECT_TYPE_FROM_KBN = {
    "es": "elasticsearch_general_purpose",
    "security": "security",
    "oblt": "observability",
}
BACKENDS = ("snapshot", "serverless")
STARTED_BY_AGENT = "agent"
STARTED_BY_USER = "user"


def fail(message: str) -> "None":
    print(f",kbn-stack: {message}", file=sys.stderr)
    raise SystemExit(1)


def setup_trigger(backend: str) -> str:
    """The ES log line that marks setup complete for ``backend``."""
    return SERVERLESS_TRIGGER_STRING if backend == "serverless" else TRIGGER_STRING


def es_slot_log(slot: int) -> Path:
    """Log of an isolated ES on ``slot``."""
    return Path(f"/tmp/es-slot{slot}.log")


def kbn_slot_log(slot: int) -> Path:
    """Log of a detached Kibana on ``slot``."""
    return Path(f"/tmp/kbn-slot{slot}.log")


def shared_es_log(version_slug: str) -> Path:
    """Log of the shared ES instance for a sanitized version."""
    return Path(f"/tmp/es-shared-{version_slug}.log")


def shared_es_reaper_log(version_slug: str) -> Path:
    """Log of the idle-reaper watchdog for a shared ES instance."""
    return Path(f"/tmp/es-shared-{version_slug}-reaper.log")


# Ports occupied by the serverless ES Docker containers (es01/es02), fixed by
# kbn-es. es01 HTTP follows --port (we pin serverless to slot 0 -> 9200); es02
# HTTP and both transports are hardcoded. Snapshot slots 0 and 1 derive into this
# band (9200/9300 and 9202/9302), so a serverless start needs those slots free.
SERVERLESS_SNAPSHOT_CONFLICT_SLOTS = (0, 1)


# The command entrypoint (``main.py`` beside this package); ``--run-with-prune`` re-invokes it.
ENTRYPOINT = Path(__file__).resolve().parents[1] / "main.py"
