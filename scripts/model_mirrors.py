#!/usr/bin/env python3
"""Generate model/provider mirrors and run explicit live-catalog drift probes.

Static generation reads only repository registries, configs, and the versioned
installed-harness capability snapshot. The ``probe`` subcommand is the sole
network/command catalog path and is always operator initiated.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

import ai_models
from model_mirror_consumer import VALID_STATUSES, consumer_view

SCHEMA_VERSION = "1.0.0"
MIRROR_KIND = "ai.model-mirrors"
DRIFT_KIND = "ai.model-mirror-drift"
CAPABILITIES_REL = Path("scripts/model_capabilities.v1.json")
MIRROR_REL = Path("home/dot_config/ai/readonly_model-mirrors.v1.json")
HARNESSES = ("cursor", "claude", "codex", "gemini", "opencode", "pi", "copilot")
PROVIDERS = (
    "azure-foundry",
    "cloudflare-openai",
    "cloudflare-workers-ai",
    "litellm",
    "litellm-anthropic",
    "llama-cpp",
    "openrouter",
)
EXPLICIT_POLICY_PROVIDERS = ("openrouter", "cloudflare-workers-ai", "cloudflare-openai")
MODEL_ID_RE = re.compile(r"^[A-Za-z0-9@~][A-Za-z0-9@~+._:/\[\]=-]*$")
CURSOR_MODEL_ROW_RE = re.compile(r"^([a-z0-9][a-z0-9._-]*) - .+$")
MAX_COMMAND_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_HTTP_RESPONSE_BYTES = 8 * 1024 * 1024
AI_MODELS_SOURCE = "home/.chezmoidata/ai_models.yaml"


class CommandOutputTooLarge(RuntimeError):
    """Raised when a live command exceeds the catalog output limit."""


def run_bounded_command(
    command: list[str],
    *,
    capture_output: bool,
    text: bool,
    timeout: float,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a catalog command without buffering unbounded stdout or stderr."""
    if not capture_output or not text:
        raise ValueError("bounded catalog commands require captured text output")

    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if process.stdout is None:
        raise RuntimeError("catalog command stdout pipe is unavailable")

    output = bytearray()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            if not selector.select(remaining):
                raise subprocess.TimeoutExpired(command, timeout)
            chunk = os.read(
                process.stdout.fileno(),
                min(64 * 1024, MAX_COMMAND_OUTPUT_BYTES + 1 - len(output)),
            )
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > MAX_COMMAND_OUTPUT_BYTES:
                raise CommandOutputTooLarge
        returncode = process.wait(timeout=max(0, deadline - time.monotonic()))
    except Exception:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        selector.close()
        process.stdout.close()

    return subprocess.CompletedProcess(
        command,
        returncode,
        output.decode("utf-8", errors="replace"),
        "",
    )


def _unique(items: list[str] | tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _provenance(kind: str, source: str, **details: Any) -> dict[str, Any]:
    return {"kind": kind, "source": source, **{key: value for key, value in details.items() if value is not None}}


def _known(models: list[str], *, complete: bool, provenance: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "complete": complete,
        "models": _unique(models),
        "provenance": provenance,
        "reason": None,
        "status": "known",
    }


def _unknown(reason: str, *, provenance: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "complete": None,
        "models": [],
        "provenance": provenance,
        "reason": reason,
        "status": "unknown",
    }


def _error(reason: str, *, provenance: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "complete": None,
        "models": [],
        "provenance": provenance,
        "reason": reason,
        "status": "error",
    }


def _strip_jsonc(text: str) -> str:
    """Remove line comments and trailing commas without changing strings."""
    without_comments: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            without_comments.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            without_comments.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < len(text) and text[index + 1] == "/":
            index = text.find("\n", index)
            if index == -1:
                break
            without_comments.append("\n")
            index += 1
            continue
        without_comments.append(char)
        index += 1

    cleaned = "".join(without_comments)
    result: list[str] = []
    in_string = False
    escaped = False
    for index, char in enumerate(cleaned):
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            result.append(char)
            continue
        if char == ",":
            next_index = index + 1
            while next_index < len(cleaned) and cleaned[next_index].isspace():
                next_index += 1
            if next_index < len(cleaned) and cleaned[next_index] in "}]":
                continue
        result.append(char)
    return "".join(result)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonc(path: Path) -> dict[str, Any]:
    return json.loads(_strip_jsonc(path.read_text(encoding="utf-8")))


def family_of(model: str) -> str:
    lowered = (model or "").lower()
    families = (
        ("claude", ("claude", "opus", "sonnet", "haiku", "anthropic", "fable")),
        ("gpt", ("gpt", "openai", "o3", "o4")),
        ("gemini", ("gemini", "google")),
        ("llama", ("llama", "groq")),
        ("mistral", ("mistral",)),
        ("deepseek", ("deepseek",)),
    )
    for family, keywords in families:
        if any(keyword in lowered for keyword in keywords):
            return family
    return "unknown"


def _catalog_from_capability(
    capability: dict[str, Any],
    configured_models: list[str],
    policy_provenance: list[dict[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    catalog = capability["catalog"]
    identity = capability["identity"]
    provenance = [
        _provenance(
            "installed-harness",
            catalog.get("source", identity["package"]),
            binary=identity["binary"],
            observed_at=observed_at,
            version=identity["version"],
        )
    ]
    provenance.extend(policy_provenance)
    mode = catalog["mode"]
    if mode == "fixed":
        return _known(catalog["models"], complete=bool(catalog["complete"]), provenance=provenance)
    if mode == "configured":
        return _known(configured_models, complete=False, provenance=provenance)
    if mode == "unknown":
        return _unknown(catalog["reason"], provenance=provenance)
    if mode == "error":
        return _error(catalog["reason"], provenance=provenance)
    raise ValueError(f"invalid capability catalog mode: {mode!r}")


def _catalog_policy(
    models: list[str],
    *,
    provenance: list[dict[str, Any]],
    complete: bool = True,
) -> dict[str, Any]:
    return _known(models, complete=complete, provenance=list(provenance))


def _load_claude_policy(repo_root: Path) -> tuple[list[str], list[str], dict[str, str]]:
    profiles = {
        "work": repo_root / "home/dot_claude/settings.work.json",
        "personal": repo_root / "home/dot_claude/settings.personal.json",
    }
    defaults = {name: _read_json(path)["model"] for name, path in profiles.items()}
    models = _unique(list(defaults.values()))
    return models, models, defaults


def _load_codex_policy(repo_root: Path) -> tuple[list[str], list[str], dict[str, str]]:
    profiles = {
        "work": repo_root / "home/dot_codex/private_config.work.toml",
        "personal": repo_root / "home/dot_codex/private_config.personal.toml",
    }
    defaults = {}
    for name, path in profiles.items():
        match = re.search(r'^model\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"), re.MULTILINE)
        if match is None:
            raise ValueError(f"Codex profile has no top-level model: {path}")
        defaults[name] = match.group(1)
    models = _unique(list(defaults.values()))
    return models, models, defaults


def _load_gemini_policy(repo_root: Path) -> tuple[list[str], list[str], dict[str, str]]:
    model = _read_json(repo_root / "home/dot_gemini/settings.json")["model"]["name"]
    return [model], [model], {"default": model}


def _provider_model_selectors(
    provider_name: str,
    provider: dict[str, Any],
) -> list[str]:
    models = provider.get("models")
    if not isinstance(models, dict):
        return []
    return [f"{provider_name}/{model_id}" for model_id in models]


def _load_opencode_policy(
    repo_root: Path,
    litellm_models: list[dict[str, Any]],
    azure_models: list[dict[str, Any]],
) -> tuple[list[str], list[str], dict[str, Any]]:
    profiles = {
        "work": _read_jsonc(repo_root / "home/dot_config/opencode/readonly_opencode.work.jsonc"),
        "personal": _read_jsonc(repo_root / "home/dot_config/opencode/readonly_opencode.personal.jsonc"),
    }
    curated: list[str] = []
    recommended: list[str] = []
    defaults: dict[str, Any] = {}
    for profile_name, config in profiles.items():
        profile_models = [config.get("small_model", "")]
        profile_models.extend(
            agent.get("model", "") for agent in config.get("agent", {}).values() if isinstance(agent, dict)
        )
        recommended.extend(profile_models)
        curated.extend(profile_models)
        defaults[profile_name] = {
            "agent": config.get("default_agent"),
            "model": config.get("agent", {}).get(config.get("default_agent"), {}).get("model"),
            "small_model": config.get("small_model"),
        }
        for provider_name, provider in config.get("provider", {}).items():
            if isinstance(provider, dict):
                curated.extend(_provider_model_selectors(provider_name, provider))

    for model in litellm_models:
        provider = "litellm-anthropic" if _is_anthropic(model["id"]) else "litellm"
        curated.append(f"{provider}/{model['id']}")
    curated.extend(f"azure-foundry/{model['id']}" for model in azure_models)
    return _unique(curated), _unique(recommended), defaults


def _load_pi_policy(
    repo_root: Path,
    litellm_models: list[dict[str, Any]],
    extras: list[dict[str, Any]],
) -> tuple[list[str], list[str], dict[str, Any]]:
    curated = [model["id"] for model in litellm_models] + [model["id"] for model in extras]
    recommended = [model["id"] for model in litellm_models]
    recommended.extend(model["id"] for model in extras if model.get("recommended") is True)
    defaults = {}
    for profile in ("work", "personal"):
        settings = _read_json(repo_root / f"home/dot_pi/agent/readonly_settings.{profile}.json")
        defaults[profile] = {
            "model": settings["defaultModel"],
            "provider": settings["defaultProvider"],
            "selector": f"{settings['defaultProvider']}/{settings['defaultModel']}",
            "thinking": settings["defaultThinkingLevel"],
        }
    return _unique(curated), _unique(recommended), defaults


def _load_copilot_policy(
    agent_review: dict[str, dict[str, str]],
) -> tuple[list[str], list[str], dict[str, str]]:
    values = ["auto"]
    values.extend(value for value in agent_review.get("copilot", {}).values() if value and value != "inherit")
    models = _unique(values)
    return models, models, {"default": "auto"}


def _load_copilot_available(registry_path: Path) -> list[str]:
    entries = ai_models.load_copilot_models(registry_path)
    available: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"copilot_models[{index}] must be a mapping")
        model_id = entry.get("id")
        if not isinstance(model_id, str) or MODEL_ID_RE.fullmatch(model_id) is None:
            raise ValueError(f"copilot_models[{index}].id is invalid")
        if model_id in seen:
            raise ValueError(f"copilot_models contains duplicate id: {model_id}")
        seen.add(model_id)
        available.append(model_id)
    return available


def _validate_cursor_policy(policy: Any) -> list[dict[str, Any]]:
    if not isinstance(policy, list) or not policy:
        raise ValueError("cursor_models must contain at least one model")

    validated = []
    seen = set()
    for index, entry in enumerate(policy):
        if not isinstance(entry, dict):
            raise ValueError(f"cursor_models[{index}] must be a mapping")
        model_id = entry.get("id")
        if not isinstance(model_id, str) or MODEL_ID_RE.fullmatch(model_id) is None:
            raise ValueError(f"cursor_models[{index}].id is invalid")
        if model_id in seen:
            raise ValueError(f"cursor_models contains duplicate id: {model_id}")
        seen.add(model_id)
        validated.append(entry)
    return validated


def _is_anthropic(model_id: str) -> bool:
    lowered = model_id.lower()
    return "claude" in lowered or "anthropic" in lowered


def _load_llama_models(repo_root: Path) -> list[str]:
    base = _read_json(repo_root / "home/dot_pi/agent/readonly_models.json")
    return [model["id"] for model in base["providers"]["llama-cpp"]["models"]]


def _group_provider_policy(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {provider: [] for provider in EXPLICIT_POLICY_PROVIDERS}
    for entry in entries:
        provider = entry.get("provider")
        if provider not in grouped:
            raise ValueError(
                f"provider_models entry {entry.get('id')!r} names unsupported provider {provider!r}; "
                f"expected one of: {', '.join(EXPLICIT_POLICY_PROVIDERS)}"
            )
        grouped[provider].append(entry)
    return grouped


def _live_probe(supported: bool, **fields: Any) -> dict[str, Any]:
    return {"supported": supported, **fields}


def _provider_entries(
    litellm: list[dict[str, Any]],
    azure: list[dict[str, Any]],
    explicit: dict[str, list[dict[str, Any]]],
    llama_models: list[str],
) -> dict[str, dict[str, Any]]:
    litellm_ids = [model["id"] for model in litellm]
    anthropic_ids = [model_id for model_id in litellm_ids if _is_anthropic(model_id)]
    azure_ids = [model["id"] for model in azure]
    policies = {
        "litellm": litellm_ids,
        "litellm-anthropic": anthropic_ids,
        "azure-foundry": azure_ids,
        "llama-cpp": llama_models,
    }
    recommendations = dict(policies)
    for provider in EXPLICIT_POLICY_PROVIDERS:
        policies[provider] = [entry["id"] for entry in explicit[provider]]
        recommendations[provider] = [entry["id"] for entry in explicit[provider] if entry.get("recommended") is True]

    entries = {}
    for provider in PROVIDERS:
        curated = policies.get(provider, [])
        recommended = recommendations.get(provider, [])
        policy_provenance = _provider_policy_provenance(provider)
        available = (
            _known(
                llama_models,
                complete=False,
                provenance=policy_provenance,
            )
            if provider == "llama-cpp"
            else _unknown(
                "live catalog requires an explicit provider probe",
                provenance=policy_provenance,
            )
        )
        entries[provider] = {
            "available": available,
            "curated": _catalog_policy(curated, provenance=policy_provenance),
            "live_probe": _provider_probe(provider),
            "recommended": _catalog_policy(recommended, provenance=policy_provenance),
        }
    return entries


def _provider_probe(provider: str) -> dict[str, Any]:
    adapters = {
        "openrouter": "openrouter-models",
        "litellm": "litellm-models",
        "cloudflare-workers-ai": "cloudflare-workers-models",
        "cloudflare-openai": "cloudflare-openai-models",
        "llama-cpp": "llama-cpp-models",
    }
    if provider in adapters:
        network = "local-only" if provider == "llama-cpp" else "explicit"
        return _live_probe(
            True,
            adapter=adapters[provider],
            max_response_bytes=MAX_HTTP_RESPONSE_BYTES,
            network=network,
            timeout_seconds=10,
        )
    return _live_probe(False, reason="no locally verified complete catalog adapter")


def build_static_mirror(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    registry_path = root / "home/.chezmoidata/ai_models.yaml"
    capabilities = _read_json(root / CAPABILITIES_REL)
    observed_at = capabilities["observed_at"]

    litellm = ai_models.load_litellm(registry_path)
    azure = ai_models.load_azure(registry_path)
    cursor_policy = _validate_cursor_policy(ai_models.load_cursor_models(registry_path))
    pi_extras = ai_models.load_pi_extra_models(registry_path)
    provider_policy = _group_provider_policy(ai_models.load_provider_models(registry_path))
    agent_review = ai_models.load_agent_review_models(registry_path)

    cursor_curated = [model["id"] for model in cursor_policy]
    cursor_recommended_entries = [model for model in cursor_policy if model.get("recommended") is True]
    recommendation_ranks = [
        model["recommendation_rank"] for model in cursor_recommended_entries if "recommendation_rank" in model
    ]
    if len(recommendation_ranks) != len(set(recommendation_ranks)):
        raise ValueError("cursor recommendation ranks must be unique")
    cursor_recommended = [
        model["id"]
        for model in sorted(
            cursor_recommended_entries,
            key=lambda model: model.get("recommendation_rank", sys.maxsize),
        )
    ]
    claude_curated, claude_recommended, claude_defaults = _load_claude_policy(root)
    codex_curated, codex_recommended, codex_defaults = _load_codex_policy(root)
    gemini_curated, gemini_recommended, gemini_defaults = _load_gemini_policy(root)
    opencode_curated, opencode_recommended, opencode_defaults = _load_opencode_policy(root, litellm, azure)
    pi_curated, pi_recommended, pi_defaults = _load_pi_policy(root, litellm, pi_extras)
    copilot_curated, copilot_recommended, copilot_defaults = _load_copilot_policy(agent_review)
    copilot_available = _load_copilot_available(registry_path)

    policies = {
        "cursor": (cursor_curated, cursor_recommended, {}),
        "claude": (claude_curated, claude_recommended, claude_defaults),
        "codex": (codex_curated, codex_recommended, codex_defaults),
        "gemini": (gemini_curated, gemini_recommended, gemini_defaults),
        "opencode": (opencode_curated, opencode_recommended, opencode_defaults),
        "pi": (pi_curated, pi_recommended, pi_defaults),
        "copilot": (copilot_curated, copilot_recommended, copilot_defaults),
    }

    harnesses = {}
    harness_defaults = {}
    for harness in HARNESSES:
        curated, recommended, defaults = policies[harness]
        capability = capabilities["harnesses"][harness]
        curated_provenance = _harness_policy_provenance(harness, "curated")
        recommended_provenance = _harness_policy_provenance(harness, "recommended")
        harnesses[harness] = {
            "available": _catalog_from_capability(
                capability,
                curated,
                curated_provenance,
                observed_at,
            ),
            "curated": _catalog_policy(curated, provenance=curated_provenance),
            "identity": capability["identity"],
            "live_probe": capability["live_probe"],
            "recommended": _catalog_policy(recommended, provenance=recommended_provenance),
        }
        harness_defaults[harness] = defaults

    if copilot_available:
        harnesses["copilot"]["available"] = _catalog_policy(
            copilot_available,
            provenance=[_registry_provenance("copilot_models")],
            complete=True,
        )

    mirror = {
        "adapters": {
            "launcher": {
                "allowed_sets": ["available", "curated", "recommended"],
                "default_set": "recommended",
                "output": "consumer_view.v1",
            },
        },
        "defaults": {
            "harnesses": harness_defaults,
        },
        "generated": {
            "deterministic": True,
            "generator": "scripts/model_mirrors.py",
            "network": "forbidden",
            "sources": [
                "home/.chezmoidata/ai_models.yaml",
                "scripts/model_capabilities.v1.json",
                "home harness configs",
            ],
        },
        "harnesses": harnesses,
        "kind": MIRROR_KIND,
        "providers": _provider_entries(
            litellm,
            azure,
            provider_policy,
            _load_llama_models(root),
        ),
        "schema_version": SCHEMA_VERSION,
    }
    validate_mirror(mirror)
    return mirror


def _registry_provenance(section: str) -> dict[str, Any]:
    return _provenance("registry", AI_MODELS_SOURCE, section=section)


def _harness_policy_provenance(harness: str, set_name: str) -> list[dict[str, Any]]:
    profile_sources = {
        "claude": [
            _provenance("config", "home/dot_claude/settings.work.json"),
            _provenance("config", "home/dot_claude/settings.personal.json"),
        ],
        "codex": [
            _provenance("config", "home/dot_codex/private_config.work.toml"),
            _provenance("config", "home/dot_codex/private_config.personal.toml"),
        ],
        "gemini": [_provenance("config", "home/dot_gemini/settings.json")],
        "opencode": [
            _provenance("config", "home/dot_config/opencode/readonly_opencode.work.jsonc"),
            _provenance("config", "home/dot_config/opencode/readonly_opencode.personal.jsonc"),
        ],
    }
    if harness == "cursor":
        return [_registry_provenance("cursor_models")]
    if harness == "opencode":
        sources = list(profile_sources[harness])
        if set_name == "curated":
            sources.extend(
                [
                    _registry_provenance("litellm_models"),
                    _registry_provenance("azure_models"),
                ]
            )
        return sources
    if harness == "pi":
        return [
            _registry_provenance("litellm_models"),
            _registry_provenance("pi_extra_models"),
        ]
    if harness == "copilot":
        if set_name == "available":
            return [_registry_provenance("copilot_models")]
        return [_registry_provenance("agent_review_models")]
    return profile_sources[harness]


def _provider_policy_provenance(provider: str) -> list[dict[str, Any]]:
    if provider == "llama-cpp":
        return [_provenance("config", "home/dot_pi/agent/readonly_models.json")]
    section = {
        "azure-foundry": "azure_models",
        "litellm": "litellm_models",
        "litellm-anthropic": "litellm_models",
    }.get(provider, "provider_models")
    return [_registry_provenance(section)]


def render_static_mirror(repo_root: str | Path) -> str:
    return json.dumps(build_static_mirror(repo_root), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def load_mirror(path: str | Path) -> dict[str, Any]:
    mirror = _read_json(Path(path))
    validate_mirror(mirror)
    return mirror


def _validate_catalog(path: str, catalog: dict[str, Any]) -> None:
    status = catalog.get("status")
    if status not in VALID_STATUSES:
        raise ValueError(f"{path}: invalid status {status!r}")
    models = catalog.get("models")
    if not isinstance(models, list) or any(not isinstance(model, str) or not model for model in models):
        raise ValueError(f"{path}: models must be non-empty strings")
    if any(MODEL_ID_RE.fullmatch(model) is None for model in models):
        raise ValueError(f"{path}: invalid model id")
    if len(models) != len(set(models)):
        raise ValueError(f"{path}: duplicate models")
    if status in {"unknown", "error"}:
        if models:
            raise ValueError(f"{path}: {status} catalog must not contain models")
        if not catalog.get("reason"):
            raise ValueError(f"{path}: {status} catalog requires reason")
        if catalog.get("complete") is not None:
            raise ValueError(f"{path}: {status} catalog completeness must be null")
    elif catalog.get("complete") not in {True, False}:
        raise ValueError(f"{path}: known catalog requires boolean complete")
    if not isinstance(catalog.get("provenance"), list):
        raise ValueError(f"{path}: provenance must be a list")


def validate_mirror(mirror: dict[str, Any]) -> None:
    if mirror.get("kind") != MIRROR_KIND or mirror.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("model mirror kind/schema_version mismatch")
    if set(mirror.get("harnesses", {})) != set(HARNESSES):
        raise ValueError("model mirror must cover all seven harnesses")
    if set(mirror.get("providers", {})) != set(PROVIDERS):
        raise ValueError("model mirror provider routes are incomplete")

    for namespace in ("harnesses", "providers"):
        for name, entry in mirror[namespace].items():
            for set_name in ("available", "curated", "recommended"):
                _validate_catalog(f"{namespace}.{name}.{set_name}", entry[set_name])
            curated = set(entry["curated"]["models"])
            recommended = set(entry["recommended"]["models"])
            if not recommended <= curated:
                raise ValueError(f"{namespace}.{name}: recommended must be a subset of curated")


def parse_cursor_catalog(output: str) -> list[str] | None:
    lines = [line.strip() for line in output.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    if len(lines) < 3 or lines[0] != "Available models" or not lines[-1].startswith("Tip:"):
        return None
    models: list[str] = []
    for line in lines[1:-1]:
        if not line:
            continue
        match = CURSOR_MODEL_ROW_RE.fullmatch(line)
        if match is None or match.group(1) in models:
            return None
        models.append(match.group(1))
    return models or None


def parse_pi_catalog(output: str) -> list[str] | None:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if not lines or lines[0].split()[:2] != ["provider", "model"]:
        return None
    models = []
    for line in lines[1:]:
        columns = line.split()
        if len(columns) < 6 or not MODEL_ID_RE.fullmatch(columns[0]) or not MODEL_ID_RE.fullmatch(columns[1]):
            return None
        provider, model = columns[:2]
        if provider == "litellm" and model.startswith("llm-gateway/"):
            models.append(model)
        elif model.startswith(f"{provider}/"):
            models.append(model)
        else:
            models.append(f"{provider}/{model}")
    return sorted(set(models)) or None


def parse_opencode_catalog(output: str) -> list[str] | None:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines or any(not MODEL_ID_RE.fullmatch(line) or "/" not in line for line in lines):
        return None
    return sorted(set(lines))


def _parse_openrouter(payload: dict[str, Any]) -> list[str] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return None
    models = []
    for model in payload["data"]:
        model_id = _payload_model_id(model, "id")
        if model_id is None:
            return None
        architecture = model.get("architecture") or {}
        if "text" not in (architecture.get("input_modalities") or []):
            continue
        if "text" not in (architecture.get("output_modalities") or []):
            continue
        models.append(model_id)
    return sorted(set(models)) or None


def _parse_openai_models(payload: dict[str, Any]) -> list[str] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return None
    models = []
    for model in payload["data"]:
        model_id = _payload_model_id(model, "id")
        if model_id is None:
            return None
        models.append(model_id)
    return sorted(set(models)) or None


def _parse_cloudflare_workers(payload: dict[str, Any]) -> list[str] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), list):
        return None
    models = []
    for model in payload["result"]:
        model_id = _payload_model_id(model, "name")
        if model_id is None:
            return None
        models.append(model_id)
    return sorted(set(models)) or None


def _payload_model_id(model: Any, field: str) -> str | None:
    if not isinstance(model, dict):
        return None
    model_id = model.get(field)
    if not isinstance(model_id, str) or MODEL_ID_RE.fullmatch(model_id) is None:
        return None
    return model_id


def _target_entry(mirror: dict[str, Any], target: str) -> dict[str, Any]:
    try:
        namespace, name = target.split(":", 1)
        collection = {"harness": "harnesses", "provider": "providers"}[namespace]
        return mirror[collection][name]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"unknown model mirror target: {target}") from exc


def _fixture_live_state(target: str, fixture: dict[str, Any], adapter: str) -> dict[str, Any]:
    if fixture.get("target") != target:
        return _unknown("fixture_target_mismatch", provenance=[])
    if fixture.get("state") in {"unknown", "error"}:
        return _unknown(fixture.get("reason") or "fixture_failure", provenance=[])
    if "payload" in fixture:
        try:
            models = _parse_payload(adapter, fixture["payload"])
        except Exception:
            return _unknown("unparseable_output", provenance=[])
    elif fixture.get("returncode", 0) != 0:
        return _unknown("command_failed", provenance=[])
    elif not fixture.get("stdout", "").strip():
        return _unknown("empty_output", provenance=[])
    else:
        models = _parse_command_output(adapter, fixture["stdout"])
    if not models:
        return _unknown("unparseable_output", provenance=[])
    return _known(models, complete=True, provenance=[_provenance("fixture", target)])


def _parse_command_output(adapter: str, output: str) -> list[str] | None:
    parsers = {
        "cursor-list-models": parse_cursor_catalog,
        "opencode-models": parse_opencode_catalog,
        "pi-list-models": parse_pi_catalog,
    }
    parser = parsers.get(adapter)
    return parser(output) if parser else None


def _parse_payload(adapter: str, payload: dict[str, Any]) -> list[str] | None:
    if adapter == "openrouter-models":
        return _parse_openrouter(payload)
    if adapter == "cloudflare-workers-models":
        return _parse_cloudflare_workers(payload)
    if adapter in {"litellm-models", "cloudflare-openai-models", "llama-cpp-models"}:
        return _parse_openai_models(payload)
    return None


def _command_live_state(
    target: str,
    probe: dict[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    which: Callable[[str], str | None],
) -> dict[str, Any]:
    command = list(probe["command"])
    binary = which(command[0])
    if not binary:
        return _unknown("missing_binary", provenance=[])
    command[0] = binary
    env = os.environ.copy()
    if probe["adapter"] == "pi-list-models":
        env["PI_OFFLINE"] = "1"
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            timeout=min(int(probe["timeout_seconds"]), 20),
            **({"env": env} if probe["adapter"] == "pi-list-models" else {}),
        )
    except CommandOutputTooLarge:
        return _unknown("output_too_large", provenance=[])
    except subprocess.TimeoutExpired:
        return _unknown("timeout", provenance=[])
    except Exception:
        return _unknown("command_failed", provenance=[])
    if result.returncode != 0:
        return _unknown("command_failed", provenance=[])
    if not result.stdout.strip():
        return _unknown("empty_output", provenance=[])
    output_limit = min(int(probe.get("max_output_bytes", MAX_COMMAND_OUTPUT_BYTES)), MAX_COMMAND_OUTPUT_BYTES)
    if len(result.stdout.encode("utf-8")) > output_limit:
        return _unknown("output_too_large", provenance=[])
    models = _parse_command_output(probe["adapter"], result.stdout)
    if not models:
        return _unknown("unparseable_output", provenance=[])
    return _known(models, complete=True, provenance=[_provenance("live-probe", target, adapter=probe["adapter"])])


def _provider_request(adapter: str) -> tuple[str, dict[str, str]] | None:
    if adapter == "openrouter-models":
        return "https://openrouter.ai/api/v1/models", {}
    if adapter == "litellm-models":
        base = os.environ.get("LITELLM_API_BASE", "").rstrip("/")
        token = os.environ.get("LITELLM_PROXY_KEY", "")
        if not base or not token:
            return None
        if not base.endswith("/v1"):
            base += "/v1"
        return f"{base}/models", {"Authorization": f"Bearer {token}"}
    if adapter == "cloudflare-workers-models":
        account = os.environ.get("CLOUDFLARE_WORKERS_AI_ACCOUNT_ID") or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        token = (
            os.environ.get("CLOUDFLARE_WORKERS_AI_API_KEY")
            or os.environ.get("CLOUDFLARE_API_KEY")
            or os.environ.get("CLOUDFLARE_API_TOKEN")
        )
        if not account or not token:
            return None
        query = urllib.parse.urlencode({"per_page": 100, "task": "Text Generation"})
        return (
            f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/models/search?{query}",
            {"Authorization": f"Bearer {token}"},
        )
    if adapter == "cloudflare-openai-models":
        account = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CLOUDFLARE_WORKERS_AI_ACCOUNT_ID")
        gateway = os.environ.get("CLOUDFLARE_GATEWAY_ID", "default")
        token = (
            os.environ.get("CLOUDFLARE_API_TOKEN")
            or os.environ.get("CLOUDFLARE_WORKERS_AI_API_KEY")
            or os.environ.get("CLOUDFLARE_API_KEY")
        )
        if not account or not token:
            return None
        bearer = token if token.startswith("Bearer ") else f"Bearer {token}"
        return (
            f"https://gateway.ai.cloudflare.com/v1/{account}/{gateway}/openai/models",
            {"cf-aig-authorization": bearer},
        )
    if adapter == "llama-cpp-models":
        base = os.environ.get("LLAMA_CPP_API_BASE", "http://127.0.0.1:8080/v1").rstrip("/")
        return f"{base}/models", {}
    return None


def _fetch_json(url: str, headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_HTTP_RESPONSE_BYTES + 1)
    if len(data) > MAX_HTTP_RESPONSE_BYTES:
        raise ValueError("catalog response exceeded byte limit")
    return json.loads(data)


def _provider_live_state(
    target: str,
    probe: dict[str, Any],
    fetch_json: Callable[[str, dict[str, str], int], dict[str, Any]],
) -> dict[str, Any]:
    request = _provider_request(probe["adapter"])
    if request is None:
        return _unknown("missing_configuration", provenance=[])
    try:
        payload = fetch_json(request[0], request[1], min(int(probe["timeout_seconds"]), 10))
    except Exception:
        return _unknown("probe_failed", provenance=[])
    try:
        models = _parse_payload(probe["adapter"], payload)
    except Exception:
        return _unknown("empty_or_unparseable_output", provenance=[])
    if not models:
        return _unknown("empty_or_unparseable_output", provenance=[])
    return _known(models, complete=True, provenance=[_provenance("live-probe", target, adapter=probe["adapter"])])


def probe_target(
    mirror: dict[str, Any],
    target: str,
    *,
    fixture: dict[str, Any] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_bounded_command,
    which: Callable[[str], str | None] = shutil.which,
    fetch_json: Callable[[str, dict[str, str], int], dict[str, Any]] = _fetch_json,
) -> dict[str, Any]:
    entry = _target_entry(mirror, target)
    probe = entry.get("live_probe", {})
    adapter = probe.get("adapter", "")
    if fixture is not None:
        live = _fixture_live_state(target, fixture, adapter)
    elif not probe.get("supported"):
        live = _unknown(probe.get("reason") or "unsupported_probe", provenance=[])
    elif adapter in {"cursor-list-models", "pi-list-models", "opencode-models"}:
        live = _command_live_state(target, probe, runner=runner, which=which)
    else:
        live = _provider_live_state(target, probe, fetch_json)

    if live["status"] != "known":
        return {
            "kind": DRIFT_KIND,
            "live": live,
            "new_available": [],
            "reason": live["reason"],
            "recommended_unavailable": [],
            "schema_version": SCHEMA_VERSION,
            "stale_curated": [],
            "status": live["status"],
            "target": target,
        }

    live_models = set(live["models"])
    curated = set(entry["curated"]["models"])
    recommended = set(entry["recommended"]["models"])
    stale = sorted(curated - live_models)
    new = sorted(live_models - curated)
    recommended_unavailable = sorted(recommended - live_models)
    return {
        "kind": DRIFT_KIND,
        "live": live,
        "new_available": new,
        "reason": None,
        "recommended_unavailable": recommended_unavailable,
        "schema_version": SCHEMA_VERSION,
        "stale_curated": stale,
        "status": "drift" if stale or new else "ok",
        "target": target,
    }


def synthetic_mirror(
    *,
    target: str,
    curated: list[str],
    recommended: list[str],
) -> dict[str, Any]:
    namespace, name = target.split(":", 1)
    collection = {"harness": "harnesses", "provider": "providers"}[namespace]
    adapters = {
        "harness:cursor": "cursor-list-models",
        "harness:pi": "pi-list-models",
        "harness:opencode": "opencode-models",
        "provider:openrouter": "openrouter-models",
    }
    commands = {
        "harness:cursor": ["cursor-agent", "--list-models"],
        "harness:pi": ["pi", "--offline", "--list-models"],
        "harness:opencode": ["opencode", "models"],
    }
    probe = _live_probe(
        True,
        adapter=adapters[target],
        timeout_seconds=10,
        **({"command": commands[target]} if target in commands else {}),
    )
    entry = {
        "available": _unknown("synthetic", provenance=[]),
        "curated": _catalog_policy(curated, provenance=[_provenance("fixture", "synthetic")]),
        "live_probe": probe,
        "recommended": _catalog_policy(recommended, provenance=[_provenance("fixture", "synthetic")]),
    }
    return {
        collection: {name: entry},
        "kind": MIRROR_KIND,
        "schema_version": SCHEMA_VERSION,
    }


def _write_outputs(repo_root: Path, output: Path) -> None:
    mirror = build_static_mirror(repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(mirror, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def _verify_outputs(repo_root: Path, output: Path) -> None:
    expected_json = render_static_mirror(repo_root)
    if not output.exists() or output.read_text() != expected_json:
        raise SystemExit(f"generated model mirror artifacts are stale: {output}")


def _fixture_for_target(fixture_data: dict[str, Any], target: str) -> dict[str, Any]:
    direct = fixture_data.get(target)
    if isinstance(direct, dict):
        return direct
    case_name = fixture_data.get("target_cases", {}).get(target)
    case = fixture_data.get(case_name) if case_name else None
    if isinstance(case, dict):
        return case
    if fixture_data.get("target") == target:
        return fixture_data
    raise ValueError(f"fixture has no case for target: {target}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("generate", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
        command.add_argument("--output", type=Path)

    adapt = subparsers.add_parser("adapt")
    adapt.add_argument("--mirror", type=Path, required=True)
    adapt.add_argument("--consumer", choices=("launcher",), required=True)
    adapt.add_argument("--harness", choices=HARNESSES, required=True)
    adapt.add_argument("--set", dest="set_name", choices=("available", "curated", "recommended"))

    probe = subparsers.add_parser("probe")
    probe.add_argument("--mirror", type=Path, required=True)
    probe.add_argument("--target", action="append", required=True)
    probe.add_argument("--fixture", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command in {"generate", "verify"}:
        root = args.repo_root.resolve()
        output = args.output or root / MIRROR_REL
        if args.command == "generate":
            _write_outputs(root, output)
        else:
            _verify_outputs(root, output)
        return 0
    if args.command == "adapt":
        print(
            json.dumps(
                consumer_view(load_mirror(args.mirror), args.consumer, args.harness, set_name=args.set_name), indent=2
            )
        )
        return 0

    mirror = load_mirror(args.mirror)
    fixture_data = _read_json(args.fixture) if args.fixture else {}
    results = []
    for target in args.target:
        fixture = _fixture_for_target(fixture_data, target) if args.fixture else None
        results.append(probe_target(mirror, target, fixture=fixture))
    print(json.dumps({"kind": DRIFT_KIND, "results": results, "schema_version": SCHEMA_VERSION}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
