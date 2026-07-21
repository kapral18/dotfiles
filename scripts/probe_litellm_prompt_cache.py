#!/usr/bin/env python3

"""Probe prompt-cache signals across LiteLLM models.

Usage:
    probe_litellm_prompt_cache.py [--models a,b] [--repeat 2] [--sleep 0.8]
                                      [--tool-schema-change]

Environment variables:
    LITELLM_API_BASE
    LITELLM_PROXY_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

BASE_TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "cache_probe_lookup",
            "description": "Look up one cache-probe value.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
                "additionalProperties": False,
            },
        },
    }
]
CHANGED_TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "cache_probe_lookup",
            "description": "Look up one cache-probe value with an optional namespace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "namespace": {"type": "string"},
                },
                "required": ["key"],
                "additionalProperties": False,
            },
        },
    }
]


def http_json(url: str, api_key: str, payload: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_models(base_url: str, api_key: str) -> list[str]:
    body = http_json(f"{base_url}/models", api_key)
    return [m["id"] for m in body.get("data", []) if "id" in m]


def extract_usage(usage: dict) -> dict:
    prompt_details = usage.get("prompt_tokens_details") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "cached_tokens": prompt_details.get("cached_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
        "cache_creation_tokens": prompt_details.get("cache_creation_tokens"),
    }


def build_payload(model: str, prompt: str, tools: list[dict] | None = None) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Reply with exactly: OK"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 8,
        "temperature": 0,
    }
    if tools is not None:
        payload["tools"] = tools
    return payload


def call_plan(repeat: int, tool_schema_change: bool) -> list[tuple[str, list[dict] | None]]:
    if tool_schema_change:
        return [
            ("baseline", BASE_TOOL_SCHEMA),
            ("baseline-repeat", BASE_TOOL_SCHEMA),
            ("changed-schema", CHANGED_TOOL_SCHEMA),
            ("changed-schema-repeat", CHANGED_TOOL_SCHEMA),
        ]
    return [("baseline", None), *[(f"repeat-{index}", None) for index in range(1, repeat)]]


def probe_model(
    base_url: str,
    api_key: str,
    model: str,
    repeat: int,
    sleep_s: float,
    tool_schema_change: bool = False,
) -> dict:
    prompt = "CACHE_PROBE_" + ("abcd1234" * 350)
    calls = []
    plan = call_plan(repeat, tool_schema_change)

    for index, (label, tools) in enumerate(plan):
        payload = build_payload(model, prompt, tools)
        body = http_json(f"{base_url}/chat/completions", api_key, payload)
        usage = extract_usage(body.get("usage", {}) or {})
        usage["call"] = index + 1
        usage["label"] = label
        calls.append(usage)
        if index < len(plan) - 1:
            time.sleep(sleep_s)

    cache_signals = [
        (c.get("cached_tokens") or 0) > 0
        or (c.get("cache_read_input_tokens") or 0) > 0
        or (c.get("cache_creation_tokens") or 0) > 0
        or (c.get("cache_creation_input_tokens") or 0) > 0
        for c in calls
    ]

    return {
        "model": model,
        "mode": "tool_schema_change" if tool_schema_change else "repeated_prompt",
        "cache_signal_detected": any(cache_signals),
        "calls": calls,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="", help="Comma-separated model IDs to probe")
    parser.add_argument("--repeat", type=int, default=2, help="Calls per model")
    parser.add_argument("--sleep", type=float, default=0.8, help="Seconds between repeated calls")
    parser.add_argument(
        "--tool-schema-change",
        action="store_true",
        help="Run baseline/repeat/change/repeat calls to expose tool-schema cache invalidation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    base_url = os.getenv("LITELLM_API_BASE", "").rstrip("/")
    api_key = os.getenv("LITELLM_PROXY_KEY", "")

    if not base_url or not api_key:
        sys.exit("Missing env vars: LITELLM_API_BASE and/or LITELLM_PROXY_KEY")

    if not args.tool_schema_change and args.repeat < 2:
        sys.exit("--repeat must be >= 2")

    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        models = list_models(base_url, api_key)

    results = []
    for model in models:
        try:
            results.append(probe_model(base_url, api_key, model, args.repeat, args.sleep, args.tool_schema_change))
        except Exception as exc:
            results.append({"model": model, "error": f"{type(exc).__name__}: {exc}"})

    print(json.dumps({"base_url": base_url, "results": results}, indent=2))


if __name__ == "__main__":
    main()
