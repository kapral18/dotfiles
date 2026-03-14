#!/usr/bin/env python3
import json
import sys

import litellm_models


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: merge_opencode_models.py <src_file> <models_yaml>")

    src_path = sys.argv[1]
    models_yaml_path = sys.argv[2]
    models = litellm_models.load(models_yaml_path)

    models_block = {
        m["slug"]: {
            "name": m["slug"],
            "limit": {"context": m["context"], "output": m["output"]},
        }
        for m in models
    }

    with open(src_path, "r") as f:
        src = f.read()

    replacement = json.dumps(models_block, indent=2)
    indented = replacement.replace("\n", "\n      ")
    print(src.replace('"__LITELLM_MODELS__"', indented))


if __name__ == "__main__":
    main()
