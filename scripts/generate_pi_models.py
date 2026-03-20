#!/usr/bin/env python3
import json
import sys

import litellm_models
from model_display import format_display_name


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: generate_pi_models.py <models_yaml> <litellm_api_base>")

    models_yaml_path = sys.argv[1]
    litellm_api_base = sys.argv[2]
    models = litellm_models.load(models_yaml_path)

    data = {
        "providers": {
            "litellm": {
                "baseUrl": litellm_api_base,
                "api": "openai-completions",
                "apiKey": "LITELLM_PROXY_KEY",
                "authHeader": True,
                "models": [_to_pi_model(m) for m in models],
            }
        }
    }

    print(json.dumps(data, indent=2, ensure_ascii=False))


def _to_pi_model(m):
    name = format_display_name(m) + " (LiteLLM)"

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
