#!/usr/bin/env python3
import json
import sys

import ai_models
from model_display import format_display_name


def main():
    if len(sys.argv) != 5:
        sys.exit("Usage: generate_pi_models.py <base_models_json> <models_yaml> <litellm_api_base> <azure_endpoint>")

    base_models_path = sys.argv[1]
    models_yaml_path = sys.argv[2]
    litellm_api_base = sys.argv[3]
    azure_endpoint = sys.argv[4]

    data = _load_base_models(base_models_path)
    litellm_models = ai_models.load_litellm(models_yaml_path)
    azure_models = ai_models.load_azure(models_yaml_path)

    data["providers"].update(
        {
            "litellm": {
                "baseUrl": litellm_api_base,
                "apiKey": "LITELLM_PROXY_KEY",
                "authHeader": True,
                "models": [_to_pi_model(m, "LiteLLM", litellm_api_base) for m in litellm_models],
            },
            "azure-foundry": {
                "baseUrl": azure_endpoint,
                "apiKey": "AZURE_FOUNDRY_API_KEY",
                "authHeader": True,
                "compat": {
                    "supportsDeveloperRole": False,
                },
                "models": [_to_pi_model(m, "Azure", azure_endpoint) for m in azure_models],
            },
        }
    )

    print(json.dumps(data, indent=2, ensure_ascii=False))


def _load_base_models(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _to_pi_model(m, provider_label, base_url):
    name = format_display_name(m) + f" ({provider_label})"

    api = _infer_pi_api(m["id"], provider_label)

    model = {
        "id": m["id"],
        "name": name,
        "api": api,
        "contextWindow": m["contextWindow"],
    }

    if api == "anthropic-messages" and base_url.endswith("/v1"):
        model["baseUrl"] = base_url[:-3]

    if "maxTokens" in m:
        model["maxTokens"] = m["maxTokens"]

    for k in ["reasoning", "thinkingBudgets", "cost"]:
        if k in m:
            model[k] = m[k]

    return model


def _infer_pi_api(model_id: str, provider_label: str) -> str:
    """Infer Pi API type for a model.

    We route any Claude/Anthropic model IDs to Anthropic Messages, everything else
    uses OpenAI-compatible chat completions.

    This is independent of the upstream gateway/provider; the client must use
    the correct API schema.
    """

    # LiteLLM (and other gateways) commonly expose Anthropic models behind
    # OpenAI-compatible endpoints, but Pi supports a native Anthropic Messages
    # client as well. We want the correct API per model.
    lower = model_id.lower()

    if "claude" in lower or "anthropic" in lower:
        return "anthropic-messages"

    return "openai-completions"


if __name__ == "__main__":
    main()
