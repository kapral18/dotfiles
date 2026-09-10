#!/usr/bin/env python3
"""Fail-closed publication gate for delegated leaves; a §3.8 checklist for the root.

SOP §3.8 gates every action that emits human-visible content (GitHub PRs/issues/comments/reviews,
Slack messages, email, chat). The wording rule lives in `k-communication`, the approval rule in the
SOP, and the leaf contract (§3.7) forbids a delegated child from publishing at all. Until now every
one of those was prose; this hook is the deterministic backstop for the two pieces a harness can see:

- A **delegated leaf** (Claude Code child `agent_id`, Copilot parent session, pi subagent) calling a
  publication tool is denied. Leaves return drafts; only the root publishes under user authority.
- The **root** keeps its authority: the call is allowed and a short §3.8 checklist rides along as
  `additionalContext`, so the reminder lands at the action instead of at the end of the turn.
  `AGENT_PUBLISH_GATE_ROOT=ask` turns the root path into a harness confirmation (Claude Code honours
  `permissionDecision: ask` even under bypassPermissions). `AGENT_PUBLISH_GATE=off` disables the hook.

Publication surfaces recognised here: `gh pr|issue <mutating verb>`, `gh release|gist <mutating verb>`,
non-GET `gh api` REST calls with a body, `gh api graphql` mutations (a GraphQL `query` is a read even
though gh POSTs it), `gws gmail +send|+reply|+reply-all|+forward|users messages send`,
`gws chat +send`, and the Slack MCP mutation tools (`slack_send_message`, `slack_send_message_draft`,
`slack_schedule_message`, `slack_add_reaction`, `slack_create_canvas`, `slack_update_canvas`).
Read-only calls (`gh pr view`, `gh api -X GET`, Slack search/read tools) are never touched.
Unknown payloads and every parse failure are silent no-ops: a wrong block would push the agent to
route around the gate, which is worse than an unverified publication.
"""

from __future__ import annotations

import json
import os
import re
import sys

from hook_common import PARENT_SESSION_ENV, emit, read_payload

GATE_ENV = "AGENT_PUBLISH_GATE"
ROOT_MODE_ENV = "AGENT_PUBLISH_GATE_ROOT"
ANTIGRAVITY_OUTPUT = "antigravity"

SHELL_TOOLS = {"Bash", "shell", "run_command", "run_shell_command", "runTerminalCommand", "terminal"}

# Slack MCP mutation tools. Claude Code reports them as `mcp__slack__<tool>`; other harnesses may
# drop the prefix, so match on the bare tool name as a suffix.
SLACK_MUTATION_TOOLS = (
    "slack_send_message",
    "slack_send_message_draft",
    "slack_schedule_message",
    "slack_add_reaction",
    "slack_create_canvas",
    "slack_update_canvas",
)

# A command position: start of line, after a separator or subshell open, then optional transparent
# wrappers (`env`, `command`, `exec`, `nohup`, `nice`, `timeout N`) and VAR=value prefixes. Anchoring
# here keeps `rg 'gh pr comment' docs/` and `echo gh pr create` (recon *about* publication commands,
# not publication) out of the gate.
CMD_START = (
    r"(?:^|[;&|(]|\$\()\s*"
    r"(?:(?:env|command|exec|nohup|nice|timeout\s+\S+)\s+)*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
)
# `gh` accepts global flags before the subcommand (`gh -R owner/repo pr comment ...`).
GH = CMD_START + r"gh\s+(?:-{1,2}[A-Za-z][\w-]*(?:[= ]\S+)?\s+)*"
GH_PUBLISH = re.compile(
    GH
    + r"(?:pr|issue)\s+(?:create|comment|review|edit|close|reopen|merge|ready|lock|unlock|pin|unpin|transfer|delete)\b"
    r"|" + GH + r"release\s+(?:create|edit|delete|upload)\b"
    r"|" + GH + r"gist\s+(?:create|edit|delete)\b",
    re.M,
)
GH_API = re.compile(GH + r"api\b", re.M)
GH_API_GRAPHQL = re.compile(GH + r"api\s+graphql\b", re.M)
GRAPHQL_MUTATION = re.compile(r"\bmutation\b")
GH_API_GET = re.compile(r"(?:-X|--method)[\s=]+GET\b")
# One shell line may chain several commands; each is judged alone so a read-only
# `gh api -X GET` cannot vouch for a write later in the same line.
SEGMENT_SPLIT = re.compile(r"[;&|\n]+|\$\(|\(")
GH_API_WRITE = re.compile(
    r"(?:-X|--method)[\s=]+(?:POST|PATCH|PUT|DELETE)\b"
    r"|\s-[fF]\s|\s--(?:field|raw-field|input)\b"
)
GWS_PUBLISH = re.compile(
    CMD_START + r"gws\s+(?:gmail\s+(?:\+send|\+reply(?:-all)?|\+forward|users\s+messages\s+send)|chat\s+\+send)\b",
    re.M,
)

ROOT_CHECKLIST = (
    "### Publication gate (SOP 3.8)",
    "This call publishes human-visible content. Before it runs, confirm:",
    "- the exact target and payload are approved, or an existing authorization covers this exact target, payload, and effect;",
    "- the wording follows ~/.agents/skills/k-communication/SKILL.md, with no session artifacts "
    "(SOP references, skill/agent/packet names, `Compatibility impact:` lines, spec paths, ledger references);",
    "- you will read the result back and report the link.",
    "Do not mention this note in the visible reply.",
)


def command_from(payload: dict) -> str:
    command = payload.get("command")
    if isinstance(command, str) and command:
        return command
    tool_input = payload.get("tool_input") or payload.get("arguments") or {}
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except ValueError:
            return ""
    if isinstance(tool_input, dict):
        value = tool_input.get("command") or tool_input.get("cmd") or ""
        return value if isinstance(value, str) else ""
    return ""


def is_publication_command(command: str) -> bool:
    return any(_segment_publishes(segment) for segment in SEGMENT_SPLIT.split(command) if segment.strip())


def _segment_publishes(segment: str) -> bool:
    if GH_PUBLISH.search(segment) or GWS_PUBLISH.search(segment):
        return True
    if GH_API_GRAPHQL.search(segment):
        # `-f query=` is how every GraphQL call passes its document; only a mutation publishes.
        return bool(GRAPHQL_MUTATION.search(segment))
    if GH_API.search(segment) and not GH_API_GET.search(segment) and GH_API_WRITE.search(segment):
        return True
    return False


def publication_surface(payload: dict) -> str:
    """Return a short label for the surface this call publishes to, or '' when it does not."""
    tool = payload.get("tool_name") or payload.get("tool") or ""
    if isinstance(tool, str) and tool.endswith(SLACK_MUTATION_TOOLS):
        return f"Slack ({tool.rsplit('__', 1)[-1]})"
    if tool and tool not in SHELL_TOOLS:
        return ""
    command = command_from(payload)
    if not command:
        return ""
    if is_publication_command(command):
        return "gh/gws command"
    return ""


def is_delegated_leaf(payload: dict) -> bool:
    agent_id = payload.get("agent_id")
    if isinstance(agent_id, str) and agent_id:
        return True
    if os.environ.get(PARENT_SESSION_ENV, "").strip():
        return True
    return os.environ.get("PI_SUBAGENT_CHILD") == "1"


def _silent(antigravity: bool) -> int:
    print(json.dumps({"decision": "allow"} if antigravity else {}, sort_keys=True))
    return 0


def main() -> int:
    antigravity = os.environ.get("AGENT_HOOK_OUTPUT") == ANTIGRAVITY_OUTPUT
    if os.environ.get(GATE_ENV, "").strip().lower() in {"off", "0", "false"}:
        return _silent(antigravity)
    try:
        payload = read_payload()
    except (ValueError, json.JSONDecodeError):
        return _silent(antigravity)
    if not isinstance(payload, dict):
        return _silent(antigravity)

    surface = publication_surface(payload)
    if not surface:
        return _silent(antigravity)

    event = str(payload.get("hook_event_name") or os.environ.get("AGENT_HOOK_EVENT", "").strip() or "PreToolUse")

    if is_delegated_leaf(payload):
        reason = (
            f"Publication blocked: {surface} is a human-visible effect and this is a delegated leaf. "
            "The leaf contract (SOP 3.7) forbids publishing outside the packet's authority; "
            "return the draft, target, and evidence to the root instead."
        )
        emit(
            {
                "decision": "block",
                "reason": reason,
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
            }
        )
        return 0

    context = "\n".join(ROOT_CHECKLIST)
    specific: dict = {"hookEventName": event, "additionalContext": context}
    if os.environ.get(ROOT_MODE_ENV, "").strip().lower() == "ask":
        specific["permissionDecision"] = "ask"
        specific["permissionDecisionReason"] = (
            f"Human-visible publication via {surface}; confirm the approved target and payload."
        )
    emit({"additional_context": context, "hookSpecificOutput": specific})
    return 0


if __name__ == "__main__":
    sys.exit(main())
