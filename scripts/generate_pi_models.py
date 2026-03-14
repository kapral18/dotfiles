#!/usr/bin/env python3
import json
import sys

import litellm_models


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
                "models": [
                    {
                        "id": m["slug"],
                        "name": f"{m['display_name']} (LiteLLM)",
                        "contextWindow": m["context"],
                        "maxTokens": m["output"],
                    }
                    for m in models
                ],
            }
        }
    }

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
