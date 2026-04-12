#!/usr/bin/env python3

"""Probe prompt-cache signals across LiteLLM models.

Usage:
    probe_litellm_prompt_cache.py [--models a,b] [--repeat 2] [--sleep 0.8]

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


def probe_model(base_url: str, api_key: str, model: str, repeat: int, sleep_s: float) -> dict:
    prompt = "CACHE_PROBE_" + ("abcd1234" * 350)
    calls = []

    for i in range(repeat):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Reply with exactly: OK"},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 8,
            "temperature": 0,
        }
        body = http_json(f"{base_url}/chat/completions", api_key, payload)
        usage = extract_usage(body.get("usage", {}) or {})
        usage["call"] = i + 1
        calls.append(usage)
        if i < repeat - 1:
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
        "cache_signal_detected": any(cache_signals),
        "calls": calls,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="", help="Comma-separated model IDs to probe")
    parser.add_argument("--repeat", type=int, default=2, help="Calls per model")
    parser.add_argument("--sleep", type=float, default=0.8, help="Seconds between repeated calls")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    base_url = os.getenv("LITELLM_API_BASE", "").rstrip("/")
    api_key = os.getenv("LITELLM_PROXY_KEY", "")

    if not base_url or not api_key:
        sys.exit("Missing env vars: LITELLM_API_BASE and/or LITELLM_PROXY_KEY")

    if args.repeat < 2:
        sys.exit("--repeat must be >= 2")

    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        models = list_models(base_url, api_key)

    results = []
    for model in models:
        try:
            results.append(probe_model(base_url, api_key, model, args.repeat, args.sleep))
        except Exception as exc:
            results.append({"model": model, "error": f"{type(exc).__name__}: {exc}"})

    print(json.dumps({"base_url": base_url, "results": results}, indent=2))


if __name__ == "__main__":
    main()
