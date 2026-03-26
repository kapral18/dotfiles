#!/usr/bin/env python3
import json
import sys

import ai_models
from model_display import format_display_name


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: merge_opencode_models.py <src_file> <models_yaml>")

    src_path = sys.argv[1]
    models_yaml_path = sys.argv[2]

    litellm_models = ai_models.load_litellm(models_yaml_path)
    azure_models = ai_models.load_azure(models_yaml_path)

    with open(src_path, "r") as f:
        src = f.read()

    litellm_block = {}
    for m in litellm_models:
        name = format_display_name(m)
        litellm_block[m["id"]] = {
            "name": name,
            "limit": {"context": m["contextWindow"], "output": m.get("maxTokens", 8192)},
        }
    replacement = json.dumps(litellm_block, indent=2, ensure_ascii=False)
    indented = replacement.replace("\n", "\n      ")
    src = src.replace('"__LITELLM_MODELS__"', indented)

    azure_block = {}
    for m in azure_models:
        name = format_display_name(m)
        azure_block[m["id"]] = {
            "name": name,
            "limit": {"context": m["contextWindow"], "output": m.get("maxTokens", 8192)},
        }
    replacement = json.dumps(azure_block, indent=2, ensure_ascii=False)
    indented = replacement.replace("\n", "\n      ")
    src = src.replace('"__AZURE_MODELS__"', indented)

    sys.stdout.write(src)


if __name__ == "__main__":
    main()
