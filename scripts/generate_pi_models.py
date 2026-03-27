#!/usr/bin/env python3
import json
import sys

import ai_models
from model_display import format_display_name


def main():
    if len(sys.argv) != 4:
        sys.exit("Usage: generate_pi_models.py <models_yaml> <litellm_api_base> <azure_endpoint>")

    models_yaml_path = sys.argv[1]
    litellm_api_base = sys.argv[2]
    azure_endpoint = sys.argv[3]

    litellm_models = ai_models.load_litellm(models_yaml_path)
    azure_models = ai_models.load_azure(models_yaml_path)

    data = {
        "providers": {
            "litellm": {
                "baseUrl": litellm_api_base,
                "api": "openai-completions",
                "apiKey": "LITELLM_PROXY_KEY",
                "authHeader": True,
                "models": [_to_pi_model(m, "LiteLLM") for m in litellm_models],
            },
            "azure-foundry": {
                "baseUrl": azure_endpoint,
                "api": "openai-completions",
                "apiKey": "AZURE_FOUNDRY_API_KEY",
                "authHeader": True,
                "compat": {
                    "supportsDeveloperRole": False,
                },
                "models": [_to_pi_model(m, "Azure") for m in azure_models],
            },
        }
    }

    print(json.dumps(data, indent=2, ensure_ascii=False))


def _to_pi_model(m, provider_label):
    name = format_display_name(m) + f" ({provider_label})"

    model = {
        "id": m["id"],
        "name": name,
        "contextWindow": m["contextWindow"],
    }

    if "maxTokens" in m:
        model["maxTokens"] = m["maxTokens"]

    for k in ["reasoning", "thinkingBudgets", "cost"]:
        if k in m:
            model[k] = m[k]

    return model


if __name__ == "__main__":
    main()
