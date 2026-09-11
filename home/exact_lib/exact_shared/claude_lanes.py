"""Project managed Claude leaves onto exact cross-provider model selectors.

Claude's Agent call accepts only aliases, but --agents definitions accept full
model IDs. Keep the managed prompt/tools/skills and let that definition win by
removing the call's model override in the band gate.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ORCHESTRATION_TOOLS = {"Agent", "Task", "SendMessage"}


def _scalar(value: str) -> str:
    if value.startswith('"'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def leaf_definition(source: str, name: str, wire: str) -> dict:
    """Parse only the managed frontmatter subset; reject unknown control shapes."""
    if not source.startswith("---\n"):
        raise ValueError(f"missing Claude profile frontmatter: {name}")
    header, separator, body = source[4:].partition("\n---\n")
    if not separator:
        raise ValueError(f"unterminated Claude profile frontmatter: {name}")
    fields = {}
    key = None
    for line in header.splitlines():
        if line.startswith("  - ") and key == "skills":
            fields[key].append(_scalar(line[4:].strip()))
            continue
        match = re.fullmatch(r"([A-Za-z]+):\s*(.*)", line)
        if not match or match[1] in fields:
            raise ValueError(f"unsupported Claude profile header: {name}")
        key, value = match.groups()
        if key not in {"name", "description", "model", "readonly", "tools", "disallowedTools", "skills"}:
            raise ValueError(f"unsupported Claude profile setting {key}: {name}")
        fields[key] = [] if key == "skills" and not value else _scalar(value)
    if fields.get("name") != name or not fields.get("description"):
        raise ValueError(f"invalid Claude profile identity: {name}")
    result = {"description": fields["description"], "prompt": body, "model": wire}
    for key in ("tools", "disallowedTools"):
        if key in fields:
            result[key] = [item.strip() for item in fields[key].split(",") if item.strip()]
    if "skills" in fields:
        if not isinstance(fields["skills"], list) or not all(isinstance(s, str) and s for s in fields["skills"]):
            raise ValueError(f"unsupported Claude profile skills: {name}")
        result["skills"] = fields["skills"]
    # readonly is not a native Markdown/JSON agent permission control. Preserve
    # the actual tools and prompt, not an invented permission-mode equivalent.
    if fields.get("readonly", "false") not in {"true", "false"}:
        raise ValueError(f"unsupported readonly annotation: {name}")
    if "tools" in result:
        result["tools"] = [tool for tool in result["tools"] if tool not in ORCHESTRATION_TOOLS]
    result["disallowedTools"] = sorted(set(result.get("disallowedTools", [])) | ORCHESTRATION_TOOLS)
    return result


def project_roles(harness: str, available: set[str] | None = None) -> tuple[list[str], dict[str, str]]:
    """Return native definitions and a role-to-wire admission map for this launch."""
    path = Path(os.environ.get("AGENT_BANDS_FILE", Path.home() / ".config/ai/agent-bands.v1.json"))
    agents = json.loads(path.read_text())["harnesses"][harness]["agents"]
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    definitions, routes = {}, {}
    sources = {p.stem: p for p in (home / "agents").glob("*.md") if p.is_file()}
    for name, pick in agents.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("invalid Claude lane role name")
        source = sources.get(name)
        if source is None:
            continue
        model, effort = pick["model"], pick["effort"]
        if harness == "pi":
            model, separator, suffix = model.rpartition(":")
            if not separator or suffix != effort:
                raise ValueError(f"invalid OpenRouter lane pair: {name}")
            wire = f"{model.removeprefix('openrouter/')}@preset/effort-{effort}"
        else:
            wire = f"{model}@lane-{effort}"
        if available is not None and wire not in available:
            continue
        definitions[name] = leaf_definition(source.read_text(), name, wire)
        routes[name] = wire
    if not routes:
        raise ValueError("no managed Claude lane profiles are available")
    return ["--agents", json.dumps(definitions)], {"AGENT_BAND_CLAUDE_ROUTES": json.dumps(routes)}


def validate_forwarded(arguments: list[str]) -> None:
    for argument in arguments:
        if argument == "--":
            break
        if argument == "--agents" or argument.startswith("--agents="):
            raise ValueError("--agents cannot replace the wrapper's managed Claude lane profiles")


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] != "--":
        print("Usage: claude_lanes.py HARNESS -- CLAUDE [ARGS...]", file=sys.stderr)
        return 2
    try:
        validate_forwarded(argv[3:])
        args, env = project_roles(argv[0])
        os.environ.pop("CLAUDE_CODE_SUBAGENT_MODEL", None)
        os.execvpe(argv[2], [argv[2], *args, *argv[3:]], {**os.environ, **env})
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"Error: cannot project Claude lanes: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
