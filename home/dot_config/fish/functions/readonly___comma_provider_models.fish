function __comma_provider_models --argument-names provider
    set -l cache_base "$HOME/.cache"
    set -q XDG_CACHE_HOME; and set cache_base "$XDG_CACHE_HOME"
    set -l cache_root "$cache_base/comma-provider-models"
    set -l ttl_seconds 86400
    set -l fallback

    switch "$provider"
        case cloudflare
            set fallback \
                '@cf/zai-org/glm-5.2' \
                '@cf/moonshotai/kimi-k2.7-code' \
                '@cf/moonshotai/kimi-k2.6' \
                minimax/m3
        case openrouter
            set fallback \
                'z-ai/glm-5.2' \
                'qwen/qwen3.7-plus' \
                'moonshotai/kimi-k2.7-code' \
                'openai/gpt-5.5' \
                'anthropic/claude-opus-4.8'
        case litellm
            set fallback \
                'llm-gateway/gemini-3.1-pro-preview' \
                'llm-gateway/gemini-3.1-pro-preview-customtools' \
                llm-gateway/claude-haiku-4-5 \
                'llm-gateway/Kimi-K2.6' \
                'llm-gateway/gpt-5.5' \
                llm-gateway/claude-opus-4-8 \
                llm-gateway/claude-sonnet-5 \
                llm-gateway/claude-fable-5 \
                llm-gateway/claude-opus-4-7 \
                'llm-gateway/gemini-3.5-flash'
        case cloudflare-openai
            set fallback \
                'gpt-5.5' \
                'gpt-5.4' \
                'gpt-5.3-codex' \
                'gpt-5.2' \
                gpt-4o \
                o4-mini
        case '*'
            return 1
    end

    command -q python3; or begin
        for model in $fallback
            printf '%s\t%s\n' "$model" 'Configured fallback model'
        end
        return
    end

    mkdir -p "$cache_root" 2>/dev/null
    python3 -c '
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


provider = sys.argv[1]
cache_root = Path(sys.argv[2]).expanduser()
ttl_seconds = int(sys.argv[3])
fallback = sys.argv[4:]
cache = cache_root / f"{provider}.txt"


def read_cache():
    try:
        lines = [line.strip() for line in cache.read_text().splitlines()]
    except OSError:
        return []
    return [line for line in lines if line]


def cache_is_fresh():
    try:
        return time.time() - cache.stat().st_mtime < ttl_seconds
    except OSError:
        return False


def fetch_openrouter():
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=5) as response:
        payload = json.load(response)
    out = []
    for model in payload.get("data") or []:
        model_id = model.get("id")
        arch = model.get("architecture") or {}
        inputs = arch.get("input_modalities") or []
        outputs = arch.get("output_modalities") or []
        if model_id and "text" in inputs and "text" in outputs:
            out.append(model_id)
    return out


def fetch_cloudflare_workers():
    account_id = (
        os.environ.get("CLOUDFLARE_WORKERS_AI_ACCOUNT_ID")
        or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        or ""
    )
    token = (
        os.environ.get("CLOUDFLARE_WORKERS_AI_API_KEY")
        or os.environ.get("CLOUDFLARE_API_KEY")
        or os.environ.get("CLOUDFLARE_API_TOKEN")
        or ""
    )
    if not account_id or not token:
        return []
    query = urllib.parse.urlencode({"per_page": 100, "task": "Text Generation"})
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search?{query}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.load(response)
    return [model.get("name") for model in payload.get("result") or [] if model.get("name")]


def fetch_cloudflare_openai():
    account_id = (
        os.environ.get("CLOUDFLARE_WORKERS_AI_ACCOUNT_ID")
        or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        or ""
    )
    gateway_id = os.environ.get("CLOUDFLARE_GATEWAY_ID") or "default"
    token = (
        os.environ.get("CLOUDFLARE_API_TOKEN")
        or os.environ.get("CLOUDFLARE_WORKERS_AI_API_KEY")
        or os.environ.get("CLOUDFLARE_API_KEY")
        or ""
    )
    if not account_id or not gateway_id or not token:
        return []
    if not token.startswith("Bearer "):
        token = "Bearer " + token
    url = f"https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/openai/models"
    request = urllib.request.Request(url, headers={"cf-aig-authorization": token})
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.load(response)
    return [model.get("id") for model in payload.get("data") or [] if model.get("id")]


def fetch_litellm():
    base_url = os.environ.get("LITELLM_API_BASE") or ""
    token = os.environ.get("LITELLM_PROXY_KEY") or ""
    if not base_url or not token:
        return []
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"
    request = urllib.request.Request(f"{base_url}/models", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.load(response)
    return [model.get("id") for model in payload.get("data") or [] if model.get("id")]


def unique(items):
    seen = set()
    out = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


cached = read_cache() if cache_is_fresh() else []
if cached:
    models = unique(fallback + cached)
else:
    try:
        if provider == "openrouter":
            fetched = fetch_openrouter()
        elif provider == "litellm":
            fetched = fetch_litellm()
        elif provider == "cloudflare-openai":
            fetched = fetch_cloudflare_openai()
        else:
            fetched = fetch_cloudflare_workers()
    except Exception:
        fetched = []
    models = unique(fallback + fetched)
    if fetched:
        try:
            cache.write_text("\n".join(fetched) + "\n")
        except OSError:
            pass
    elif cache.exists():
        models = unique(fallback + read_cache())

for model in models:
    print(f"{model}\t{provider} model")
' "$provider" "$cache_root" "$ttl_seconds" $fallback
end
