function __comma_provider_models --argument-names provider
    command -q python3; or return 1

    set -l config_base "$HOME/.config"
    set -q XDG_CONFIG_HOME; and set config_base "$XDG_CONFIG_HOME"
    set -l mirror "$config_base/ai/model-mirrors.v1.json"

    python3 -c '
import json
import sys
from pathlib import Path

provider_aliases = {
    "cloudflare": "cloudflare-workers-ai",
    "cloudflare-openai": "cloudflare-openai",
    "litellm": "litellm",
    "openrouter": "openrouter",
    "vertex": "vertex",
}

provider = provider_aliases.get(sys.argv[1])
if provider is None:
    raise SystemExit(1)

try:
    mirror = json.loads(Path(sys.argv[2]).read_text())
    catalog = mirror["providers"][provider]["curated"]
except (OSError, KeyError, TypeError, ValueError):
    raise SystemExit(1)

if catalog.get("status") != "known":
    raise SystemExit(1)
for model in catalog.get("models") or []:
    print(f"{model}\t{provider} curated model")
' "$provider" "$mirror"
end
