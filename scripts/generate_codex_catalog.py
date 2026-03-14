#!/usr/bin/env python3
import json
import sys

import litellm_models


def main():
    if len(sys.argv) != 4:
        sys.exit("Usage: generate_codex_catalog.py <models_yaml> <cache_file> <dst_file>")

    models_yaml_path, src_path, dst_path = sys.argv[1], sys.argv[2], sys.argv[3]
    models_spec = litellm_models.load(models_yaml_path)

    with open(src_path, "r") as f:
        data = json.load(f)

    models = data.get("models", [])
    existing = {m["slug"] for m in models}
    by_slug = {m["slug"]: m for m in models}
    changed = False

    for spec in models_spec:
        if spec["slug"] in existing:
            continue
        base_model = by_slug.get(spec.get("codex_base"))
        if not base_model:
            continue

        entry = dict(base_model)
        entry["slug"] = spec["slug"]
        entry["display_name"] = f"{spec['display_name']} (LiteLLM)"
        entry["context_window"] = spec["context"]
        models.append(entry)
        changed = True

    if changed:
        data["models"] = models
        with open(dst_path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
            f.write("\n")


if __name__ == "__main__":
    main()
