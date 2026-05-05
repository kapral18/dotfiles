#!/usr/bin/env python3
"""JSONC (JSON-with-comments) serializer for OpenCode config files.

OpenCode's JSONC parser accepts trailing commas after object members
and array elements, and the user's hand-curated config style enforces
two specific conventions that stdlib `json.dumps` does not produce:

  1. Trailing comma after every object member (including the last one
     before the closing `}`). This makes diffs that add/remove a
     member touch only the new line, not the previous member's line.

  2. Inline single-line form for arrays of scalars (strings, numbers,
     booleans, nulls). Multi-line array form is reserved for arrays
     of complex (object/array) elements.

Stdlib-only by design: this helper is colocated with the other
generator scripts (`inject_mcp_into_opencode_jsonc.py`,
`merge_opencode_models.py`) which the AGENTS.md "no external
dependencies in helper scripts" rule applies to.
"""

from __future__ import annotations

import json


def dump_jsonc(obj, *, indent: int = 2, _level: int = 0) -> str:
    """Serialize `obj` as JSONC with trailing object-commas and
    inline scalar-arrays. Returned string never has a trailing
    newline; callers append one if needed.

    Output style (matches the goldens under
    `scripts/tests/fixtures/golden_opencode_*.jsonc`):

        {
          "key": "value",
          "list": ["a", "b", "c"],
          "nested": {
            "n": 1,
          },
          "empty_obj": {},
          "empty_list": [],
        }
    """
    pad = " " * (indent * _level)
    inner_pad = " " * (indent * (_level + 1))

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = ["{"]
        for key, value in obj.items():
            key_str = json.dumps(str(key), ensure_ascii=False)
            value_str = dump_jsonc(value, indent=indent, _level=_level + 1)
            lines.append(f"{inner_pad}{key_str}: {value_str},")
        lines.append(pad + "}")
        return "\n".join(lines)

    if isinstance(obj, list):
        if not obj:
            return "[]"
        # Arrays of scalars render inline. Complex items (dict/list)
        # force multi-line form for readability.
        if all(not isinstance(item, (dict, list)) for item in obj):
            scalars = [json.dumps(item, ensure_ascii=False) for item in obj]
            return "[" + ", ".join(scalars) + "]"
        lines = ["["]
        last = len(obj) - 1
        for i, item in enumerate(obj):
            value_str = dump_jsonc(item, indent=indent, _level=_level + 1)
            comma = "," if i < last else ""
            lines.append(f"{inner_pad}{value_str}{comma}")
        lines.append(pad + "]")
        return "\n".join(lines)

    # Scalars: defer to stdlib's JSON encoding (handles strings, ints,
    # floats, booleans, None, with proper escaping).
    return json.dumps(obj, ensure_ascii=False)
