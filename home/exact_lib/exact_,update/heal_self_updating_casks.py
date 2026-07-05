#!/usr/bin/env python3
"""Detect and heal stale artifacts for Homebrew self-updating casks.

Homebrew's ``auto_updates`` casks are allowed to move themselves past the
version Homebrew knows about. A later ``brew reinstall --cask`` can reassert
Homebrew's older artifact and strand profile/state data that the app already
migrated. This helper checks every installed self-updating cask, then heals only
apps with an explicit adapter that knows how to detect and recover that state.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Adapter:
    token: str
    app_name: str
    process_names: tuple[str, ...]
    bundle_id: str
    app_path: Path
    engine_info_plist: Path
    guard_file: Path
    latest_dmg_url: str
    allowed_hosts: frozenset[str]


@dataclass(frozen=True)
class CaskState:
    token: str
    auto_updates: bool
    pinned: bool


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    exit_failure: bool = False


HOME = Path.home()
APPLICATIONS = Path("/Applications")

ADAPTERS: dict[str, Adapter] = {
    "arc": Adapter(
        token="arc",
        app_name="Arc.app",
        process_names=("Arc",),
        bundle_id="company.thebrowser.Browser",
        app_path=APPLICATIONS / "Arc.app",
        engine_info_plist=APPLICATIONS / "Arc.app/Contents/Frameworks/ArcCore.framework/Resources/Info.plist",
        guard_file=HOME / "Library/Application Support/Arc/User Data/Last Version",
        latest_dmg_url="https://releases.arc.net/release/Arc-latest.dmg",
        allowed_hosts=frozenset({"arc.net", "releases.arc.net"}),
    ),
    "thebrowsercompany-dia": Adapter(
        token="thebrowsercompany-dia",
        app_name="Dia.app",
        process_names=("Dia",),
        bundle_id="company.thebrowser.dia",
        app_path=APPLICATIONS / "Dia.app",
        engine_info_plist=APPLICATIONS / "Dia.app/Contents/Frameworks/ArcCore.framework/Resources/Info.plist",
        guard_file=HOME / "Library/Application Support/Dia/User Data/Last Version",
        latest_dmg_url="https://releases.diabrowser.com/release/Dia-latest.dmg",
        allowed_hosts=frozenset({"releases.diabrowser.com"}),
    ),
}


class HostAllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """urllib redirect handler that refuses unexpected hosts or schemes."""

    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        self.allowed_hosts = allowed_hosts
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_url(newurl, self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def version_parts(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def version_cmp(left: str, right: str) -> int:
    left_parts = version_parts(left)
    right_parts = version_parts(right)
    max_len = max(len(left_parts), len(right_parts))
    padded_left = left_parts + (0,) * (max_len - len(left_parts))
    padded_right = right_parts + (0,) * (max_len - len(right_parts))
    if padded_left < padded_right:
        return -1
    if padded_left > padded_right:
        return 1
    return 0


def decide(
    *,
    installed: bool,
    auto_updates: bool,
    pinned: bool,
    supported: bool,
    app_present: bool,
    guard_version: str | None,
    engine_version: str | None,
    running: bool,
) -> Decision:
    """Return the action for one cask without performing side effects."""
    if not installed:
        return Decision("skip", "not installed")
    if not auto_updates:
        return Decision("skip", "not a Homebrew auto_updates cask")
    if not supported:
        return Decision("unsupported", "no stale-artifact adapter")
    if not app_present:
        return Decision("skip", "app bundle is not present")
    if not guard_version:
        return Decision("ok", "no profile guard found")
    if not engine_version:
        return Decision("warn", "could not read on-disk app baseline", exit_failure=True)
    if version_cmp(engine_version, guard_version) >= 0:
        return Decision("ok", f"on-disk baseline {engine_version} >= guard {guard_version}")
    if running:
        return Decision(
            "warn", f"stale baseline {engine_version} < guard {guard_version}, but app is running", exit_failure=True
        )
    return Decision("heal", f"stale baseline {engine_version} < guard {guard_version}")


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, capture_output=capture, text=True)


def read_plist_string(path: Path, key: str) -> str | None:
    try:
        with path.open("rb") as file:
            value = plistlib.load(file).get(key)
    except (FileNotFoundError, plistlib.InvalidFileException, OSError):
        return None
    return value if isinstance(value, str) and value else None


def read_engine_version(adapter: Adapter) -> str | None:
    return read_plist_string(adapter.engine_info_plist, "CFBundleShortVersionString")


def read_guard_version(adapter: Adapter) -> str | None:
    try:
        value = adapter.guard_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def app_is_running(adapter: Adapter) -> bool:
    for process_name in adapter.process_names:
        result = subprocess.run(
            ["/usr/bin/pgrep", "-x", process_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if result.returncode == 0:
            return True
    return False


def installed_auto_updating_casks() -> list[CaskState]:
    if not shutil.which("brew"):
        return []
    try:
        result = run(["brew", "info", "--json=v2", "--installed"], capture=True)
    except FileNotFoundError:
        return []
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("brew info --json=v2 --installed failed") from exc
    data = json.loads(result.stdout)
    states: list[CaskState] = []
    for cask in data.get("casks", []):
        token = cask.get("token")
        if not isinstance(token, str):
            continue
        states.append(
            CaskState(token=token, auto_updates=bool(cask.get("auto_updates")), pinned=bool(cask.get("pinned")))
        )
    return [state for state in states if state.auto_updates]


def validate_url(url: str, allowed_hosts: frozenset[str]) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"refusing non-HTTPS URL: {url}")
    if parsed.hostname not in allowed_hosts:
        raise ValueError(f"refusing URL outside allowlist: {url}")


def download_latest(adapter: Adapter, target: Path) -> None:
    validate_url(adapter.latest_dmg_url, adapter.allowed_hosts)
    opener = urllib.request.build_opener(HostAllowlistRedirectHandler(adapter.allowed_hosts))
    request = urllib.request.Request(adapter.latest_dmg_url, headers={"User-Agent": "self-updating-cask-healer/1.0"})
    downloaded = 0
    next_report = 50 * 1024 * 1024
    with opener.open(request, timeout=60) as response, target.open("wb") as file:
        final_url = response.geturl()
        validate_url(final_url, adapter.allowed_hosts)
        print(f"download {adapter.token}: {final_url}", flush=True)
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            file.write(chunk)
            downloaded += len(chunk)
            if downloaded >= next_report:
                print(f"download {adapter.token}: {downloaded // (1024 * 1024)} MiB", flush=True)
                next_report += 50 * 1024 * 1024
    print(f"download {adapter.token}: complete ({downloaded // (1024 * 1024)} MiB)", flush=True)


def attach_dmg(dmg_path: Path) -> Path:
    result = run(["/usr/bin/hdiutil", "attach", "-nobrowse", "-readonly", "-plist", str(dmg_path)], capture=True)
    plist = plistlib.loads(result.stdout.encode("utf-8"))
    for entity in plist.get("system-entities", []):
        mount_point = entity.get("mount-point")
        if mount_point:
            return Path(mount_point)
    raise RuntimeError(f"mounted {dmg_path} but no mount point was reported")


def detach_dmg(mount_point: Path) -> None:
    subprocess.run(
        ["/usr/bin/hdiutil", "detach", str(mount_point)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def find_mounted_app(mount_point: Path, app_name: str) -> Path:
    direct = mount_point / app_name
    if direct.is_dir():
        return direct
    for path in mount_point.rglob(app_name):
        if path.is_dir():
            return path
    raise FileNotFoundError(f"{app_name} not found in mounted DMG at {mount_point}")


def verify_app_bundle(adapter: Adapter, app_path: Path) -> None:
    bundle_id = read_plist_string(app_path / "Contents/Info.plist", "CFBundleIdentifier")
    if bundle_id != adapter.bundle_id:
        raise RuntimeError(f"{adapter.token}: expected bundle id {adapter.bundle_id}, got {bundle_id or '<missing>'}")
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app_path)])
    run(["/usr/sbin/spctl", "-a", "-t", "exec", str(app_path)])


def replace_app(adapter: Adapter, mounted_app: Path) -> None:
    backup = adapter.app_path.with_name(f".{adapter.app_name}.selfupdater-backup-{os.getpid()}")
    replaced = False
    if adapter.app_path.exists():
        shutil.move(str(adapter.app_path), str(backup))
        replaced = True
    try:
        run(["/usr/bin/ditto", str(mounted_app), str(adapter.app_path)])
    except Exception:
        if adapter.app_path.exists():
            shutil.rmtree(adapter.app_path)
        if replaced:
            shutil.move(str(backup), str(adapter.app_path))
        raise
    if replaced and backup.exists():
        shutil.rmtree(backup)


def heal(adapter: Adapter, guard_version: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{adapter.token}-heal-") as tmp:
        dmg_path = Path(tmp) / "latest.dmg"
        download_latest(adapter, dmg_path)
        mount_point = attach_dmg(dmg_path)
        try:
            mounted_app = find_mounted_app(mount_point, adapter.app_name)
            verify_app_bundle(adapter, mounted_app)
            if app_is_running(adapter):
                raise RuntimeError(f"{adapter.token}: app started while heal was in progress")
            replace_app(adapter, mounted_app)
            verify_app_bundle(adapter, adapter.app_path)
        finally:
            detach_dmg(mount_point)

    healed_version = read_engine_version(adapter)
    if not healed_version or version_cmp(healed_version, guard_version) < 0:
        raise RuntimeError(
            f"{adapter.token}: heal did not clear guard; on-disk={healed_version or '<missing>'}, guard={guard_version}"
        )
    print(f"healed {adapter.token}: on-disk baseline {healed_version} >= guard {guard_version}", flush=True)


def evaluate_state(state: CaskState) -> tuple[Decision, Adapter | None, str | None, str | None]:
    adapter = ADAPTERS.get(state.token)
    guard_version = read_guard_version(adapter) if adapter else None
    engine_version = read_engine_version(adapter) if adapter else None
    decision = decide(
        installed=True,
        auto_updates=state.auto_updates,
        pinned=state.pinned,
        supported=adapter is not None,
        app_present=bool(adapter and adapter.app_path.is_dir()),
        guard_version=guard_version,
        engine_version=engine_version,
        running=bool(adapter and app_is_running(adapter)),
    )
    return decision, adapter, guard_version, engine_version


def summarize_unsupported(tokens: Iterable[str]) -> None:
    unsupported = sorted(tokens)
    if unsupported:
        print(f"checked unsupported auto_updates casks: {', '.join(unsupported)}", flush=True)


def main() -> int:
    states = installed_auto_updating_casks()
    if not states:
        print("no installed Homebrew auto_updates casks found", flush=True)
        return 0

    unsupported: list[str] = []
    failed = False
    for state in sorted(states, key=lambda item: item.token):
        if not state.pinned:
            print(f"warn {state.token}: auto_updates cask is not pinned", flush=True)
        decision, adapter, guard_version, _engine_version = evaluate_state(state)
        if decision.action == "unsupported":
            unsupported.append(state.token)
            continue
        if decision.action == "heal" and adapter and guard_version:
            print(f"heal {state.token}: {decision.reason}", flush=True)
            try:
                heal(adapter, guard_version)
            except Exception as exc:  # noqa: BLE001 - top-level CLI boundary prints actionable failure.
                print(f"failed {state.token}: {exc}", file=sys.stderr, flush=True)
                failed = True
            continue
        print(f"{decision.action} {state.token}: {decision.reason}", flush=True)
        failed = failed or decision.exit_failure

    summarize_unsupported(unsupported)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
