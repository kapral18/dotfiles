#!/usr/bin/env python3
"""Resolve unified AI controls into a leaf invocation, then delegate."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, Protocol, Sequence

from model_mirror_consumer import load_consumer_view

DEPTH_VALUES = ("fast", "balanced", "deep")
EXECUTION_VALUES = ("readonly", "supervised", "autonomous")
CONNECTIVITY_VALUES = ("online", "offline")
HARNESS_NAMES = ("cursor", "claude", "codex", "gemini", "opencode", "pi", "copilot")
DEFAULT_AXES = {
    "depth": "balanced",
    "execution": "supervised",
    "connectivity": "online",
}
ALIASES = {
    "audit": {"depth": "deep", "execution": "readonly"},
    "offline": {"connectivity": "offline"},
}
DEPTH_EFFORT = {"fast": "low", "balanced": "medium", "deep": "high"}
MODEL_MIRROR_DISPLAY_PATH = "~/.config/ai/model-mirrors.v1.json"


class PlanError(ValueError):
    """A user-visible invocation resolution error."""


class LauncherArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports failures through the launcher's error path."""

    def error(self, message: str) -> None:
        raise PlanError(message)


@dataclass(frozen=True)
class Provenance:
    kind: str
    source: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "source": self.source}


@dataclass(frozen=True)
class Contribution:
    value: str
    provenance: Provenance

    def as_dict(self) -> dict[str, str]:
        return {**self.provenance.as_dict(), "value": self.value}


@dataclass(frozen=True)
class FieldProvenance:
    selected: Provenance
    inputs: tuple[Contribution, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            **self.selected.as_dict(),
            "selected": self.selected.as_dict(),
            "inputs": [item.as_dict() for item in self.inputs],
        }


@dataclass(frozen=True)
class Transport:
    status: str
    argv: tuple[str, ...] = ()
    env: tuple[tuple[str, str], ...] = ()
    unset_env: tuple[str, ...] = ()
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "argv": list(self.argv),
            "env": dict(self.env),
            "unset_env": list(self.unset_env),
            "note": self.note,
        }


@dataclass(frozen=True)
class ResolvedField:
    name: str
    value: str
    explicit: bool
    hard: bool
    provenance: FieldProvenance
    transport: Transport

    def as_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "explicit": self.explicit,
            "hard": self.hard,
            "provenance": self.provenance.as_dict(),
            "transport": self.transport.as_dict(),
        }


@dataclass(frozen=True)
class AvailabilityCatalog:
    consumer: str
    harness: str
    set_name: str
    status: str
    complete: bool | None
    models: tuple[str, ...]
    reason: str | None
    provenance: tuple[dict[str, object], ...]
    schema_version: str
    source: str

    def as_dict(self) -> dict[str, object]:
        return {
            "consumer": self.consumer,
            "harness": self.harness,
            "set": self.set_name,
            "status": self.status,
            "complete": self.complete,
            "model_count": len(self.models),
            "reason": self.reason,
            "provenance": [dict(item) for item in self.provenance],
            "schema_version": self.schema_version,
            "source": self.source,
        }


@dataclass(frozen=True)
class AvailabilitySelection:
    model: str | None
    provider: str | None
    model_provenance: Provenance
    provider_provenance: Provenance
    model_is_explicit: bool
    provider_is_explicit: bool
    availability: AvailabilityCatalog | None = None


class AvailabilityAdapter(Protocol):
    """Seam for future model/provider availability mirrors."""

    def resolve(
        self,
        harness: str,
        requested_model: str | None,
        requested_provider: str | None,
    ) -> AvailabilitySelection:
        """Return a selection without contacting model/provider services."""


class ModelMirrorAvailabilityAdapter:
    """Validate low-level selections against the generated launcher catalog."""

    def __init__(self, path: Path | None = None, *, source: str | None = None) -> None:
        self.path = path or Path.home() / ".config" / "ai" / "model-mirrors.v1.json"
        self.source = source or (MODEL_MIRROR_DISPLAY_PATH if path is None else str(path))

    def resolve(
        self,
        harness: str,
        requested_model: str | None,
        requested_provider: str | None,
    ) -> AvailabilitySelection:
        try:
            view = load_consumer_view(self.path, "launcher", harness, set_name="available")
        except ValueError as exc:
            raise PlanError(f"generated model mirror {self.source} is unavailable or invalid: {exc}") from exc
        availability = AvailabilityCatalog(
            consumer=view["consumer"],
            harness=view["harness"],
            set_name=view["set"],
            status=view["status"],
            complete=view["complete"],
            models=tuple(view["models"]),
            reason=view["reason"],
            provenance=tuple(dict(item) for item in view["provenance"]),
            schema_version=view["schema_version"],
            source=self.source,
        )
        candidates = {requested_model} if requested_model is not None else set()
        if harness == "pi" and requested_model is not None and requested_provider is not None:
            candidates.add(f"{requested_provider}/{requested_model}")
        if (
            requested_model is not None
            and availability.status == "known"
            and availability.complete is True
            and candidates.isdisjoint(availability.models)
        ):
            raise PlanError(
                f"{harness} model {requested_model!r} is absent from the complete generated available catalog"
            )
        model_provenance = (
            Provenance("option", "--model")
            if requested_model is not None
            else Provenance("harness-default", "current harness config")
        )
        provider_provenance = (
            Provenance("option", "--provider")
            if requested_provider is not None
            else Provenance("harness-default", "current harness config")
        )
        return AvailabilitySelection(
            model=requested_model,
            provider=requested_provider,
            model_provenance=model_provenance,
            provider_provenance=provider_provenance,
            model_is_explicit=requested_model is not None,
            provider_is_explicit=requested_provider is not None,
            availability=availability,
        )


@dataclass(frozen=True)
class HarnessCapability:
    leaf: str
    verified_version: str
    depth_transport: str
    execution: dict[str, tuple[str, ...] | None]
    connectivity: dict[str, tuple[str, ...] | None]
    model_flag: str
    provider_flag: str | None
    owned_options: dict[str, str]
    sensitive_options: frozenset[str] = frozenset()
    variadic_sensitive_options: frozenset[str] = frozenset()


CAPABILITIES = {
    "cursor": HarnessCapability(
        leaf=",cursor",
        verified_version="2026.07.09-a3815c0",
        depth_transport="cursor-model",
        execution={
            "readonly": ("--mode", "plan"),
            "supervised": ("--auto-review",),
            "autonomous": ("--yolo",),
        },
        connectivity={"online": (), "offline": None},
        model_flag="--model",
        provider_flag=None,
        owned_options={
            "--mode": "execution",
            "--plan": "execution",
            "--auto-review": "execution",
            "-f": "execution",
            "--force": "execution",
            "--yolo": "execution",
            "--sandbox": "execution",
            "--model": "model selection",
        },
        sensitive_options=frozenset({"--api-key", "-H", "--header"}),
    ),
    "claude": HarnessCapability(
        leaf="claude",
        verified_version="2.1.206",
        depth_transport="effort-flag",
        execution={
            "readonly": ("--permission-mode", "plan"),
            "supervised": ("--permission-mode", "manual"),
            "autonomous": ("--dangerously-skip-permissions",),
        },
        connectivity={"online": (), "offline": None},
        model_flag="--model",
        provider_flag=None,
        owned_options={
            "--permission-mode": "execution",
            "--dangerously-skip-permissions": "execution",
            "--allow-dangerously-skip-permissions": "execution",
            "--allowedTools": "execution",
            "--allowed-tools": "execution",
            "--disallowedTools": "execution",
            "--disallowed-tools": "execution",
            "--tools": "execution",
            "--effort": "depth",
            "--model": "model selection",
        },
        sensitive_options=frozenset({"--settings", "--mcp-config"}),
        variadic_sensitive_options=frozenset({"--mcp-config"}),
    ),
    "codex": HarnessCapability(
        leaf=",codex",
        verified_version="0.144.1",
        depth_transport="codex-config",
        execution={
            "readonly": ("--sandbox", "read-only", "--ask-for-approval", "untrusted"),
            "supervised": ("--sandbox", "workspace-write", "--ask-for-approval", "on-request"),
            "autonomous": ("--sandbox", "danger-full-access", "--ask-for-approval", "never"),
        },
        connectivity={"online": (), "offline": None},
        model_flag="--model",
        provider_flag=None,
        owned_options={
            "-s": "execution",
            "--sandbox": "execution",
            "-a": "execution",
            "--ask-for-approval": "execution",
            "--dangerously-bypass-approvals-and-sandbox": "execution",
            "-m": "model selection",
            "--model": "model selection",
        },
    ),
    "gemini": HarnessCapability(
        leaf="gemini",
        verified_version="0.50.0",
        depth_transport="unsupported",
        execution={
            "readonly": ("--approval-mode", "plan"),
            "supervised": ("--approval-mode", "default"),
            "autonomous": ("--approval-mode", "yolo"),
        },
        connectivity={"online": (), "offline": None},
        model_flag="--model",
        provider_flag=None,
        owned_options={
            "--approval-mode": "execution",
            "-y": "execution",
            "--yolo": "execution",
            "-m": "model selection",
            "--model": "model selection",
        },
    ),
    "opencode": HarnessCapability(
        leaf="opencode",
        verified_version="1.17.15",
        depth_transport="unsupported",
        execution={"readonly": None, "supervised": None, "autonomous": ("--auto",)},
        connectivity={"online": (), "offline": None},
        model_flag="--model",
        provider_flag=None,
        owned_options={
            "--auto": "execution",
            "--variant": "depth",
            "-m": "model selection",
            "--model": "model selection",
        },
        sensitive_options=frozenset({"-p", "--password"}),
    ),
    "pi": HarnessCapability(
        leaf="pi",
        verified_version="0.80.6",
        depth_transport="thinking-flag",
        execution={
            "readonly": ("--tools", "read,grep,find,ls"),
            "supervised": None,
            "autonomous": ("--tools", "read,bash,edit,write,grep,find,ls"),
        },
        connectivity={"online": (), "offline": None},
        model_flag="--model",
        provider_flag="--provider",
        owned_options={
            "--tools": "execution",
            "-t": "execution",
            "--no-tools": "execution",
            "-nt": "execution",
            "--no-builtin-tools": "execution",
            "-nbt": "execution",
            "--exclude-tools": "execution",
            "-xt": "execution",
            "--thinking": "depth",
            "--offline": "connectivity",
            "--model": "model selection",
            "--provider": "provider selection",
        },
        sensitive_options=frozenset({"--api-key"}),
    ),
    "copilot": HarnessCapability(
        leaf=",copilot",
        verified_version="1.0.70",
        depth_transport="effort-flag",
        execution={
            "readonly": ("--mode", "plan"),
            "supervised": ("--mode", "interactive"),
            "autonomous": ("--mode", "autopilot", "--allow-all"),
        },
        connectivity={"online": (), "offline": None},
        model_flag="--model",
        provider_flag=None,
        owned_options={
            "--mode": "execution",
            "--plan": "execution",
            "--autopilot": "execution",
            "--allow-all": "execution",
            "--allow-all-tools": "execution",
            "--allow-all-paths": "execution",
            "--allow-all-urls": "execution",
            "--allow-all-mcp-server-instructions": "execution",
            "--allow-tool": "execution",
            "--deny-tool": "execution",
            "--available-tools": "execution",
            "--excluded-tools": "execution",
            "--yolo": "execution",
            "--effort": "depth",
            "--reasoning-effort": "depth",
            "--model": "model selection",
        },
        sensitive_options=frozenset({"--additional-mcp-config"}),
    ),
}


@dataclass(frozen=True)
class ParsedCommand:
    harness: str
    aliases: tuple[str, ...]
    depth_values: tuple[str, ...]
    execution_values: tuple[str, ...]
    connectivity_values: tuple[str, ...]
    model: str | None
    provider: str | None
    dry_run: bool
    explain: bool
    leaf_args: tuple[str, ...]


@dataclass(frozen=True)
class SelectionPlan:
    model: str | None
    provider: str | None
    model_provenance: Provenance
    provider_provenance: Provenance
    model_is_explicit: bool
    provider_is_explicit: bool
    transport_args: tuple[str, ...]
    availability: AvailabilityCatalog | None

    def as_dict(self) -> dict[str, object]:
        return {
            "model": {
                "value": self.model,
                "explicit": self.model_is_explicit,
                "provenance": self.model_provenance.as_dict(),
            },
            "provider": {
                "value": self.provider,
                "explicit": self.provider_is_explicit,
                "provenance": self.provider_provenance.as_dict(),
            },
            "transport_trace": [",ai-selection", *self.transport_args],
            "availability": self.availability.as_dict() if self.availability is not None else None,
        }


@dataclass(frozen=True)
class InvocationPlan:
    harness: str
    aliases: tuple[str, ...]
    fields: dict[str, ResolvedField]
    selection: SelectionPlan
    actual_argv: tuple[str, ...]
    env: tuple[tuple[str, str], ...]
    unset_env: tuple[str, ...]
    capability: HarnessCapability

    def public_dict(self) -> dict[str, object]:
        return {
            "kind": "InvocationPlan",
            "schema_version": 1,
            "harness": {
                "value": self.harness,
                "provenance": Provenance("positional", "harness").as_dict(),
            },
            "aliases": list(self.aliases),
            "fields": {name: field.as_dict() for name, field in self.fields.items()},
            "selection": self.selection.as_dict(),
            "capability": {
                "verified_version": self.capability.verified_version,
                "verified_source": "local --version/--help probes on 2026-07-11",
            },
            "leaf": {
                "argv": _redact_argv(self.actual_argv, self.capability),
                "env": dict(self.env),
                "unset_env": list(self.unset_env),
            },
        }


def _parser() -> LauncherArgumentParser:
    parser = LauncherArgumentParser(
        prog=",ai",
        description="Resolve unified AI controls and delegate to an existing harness.",
        epilog=(
            "Aliases: audit => depth=deep + execution=readonly; "
            "offline => connectivity=offline. Use -- before leaf-specific arguments."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("harness", choices=HARNESS_NAMES)
    parser.add_argument("--alias", action="append", choices=tuple(ALIASES), default=[])
    parser.add_argument("--depth", action="append", choices=DEPTH_VALUES, default=[])
    parser.add_argument("--execution", action="append", choices=EXECUTION_VALUES, default=[])
    parser.add_argument("--connectivity", action="append", choices=CONNECTIVITY_VALUES, default=[])
    parser.add_argument("--model")
    parser.add_argument("--provider")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--dry-run", action="store_true", help="Emit redacted InvocationPlan JSON; execute nothing")
    output.add_argument("--explain", action="store_true", help="Explain the redacted plan; execute nothing")
    return parser


def parse_cli(argv: Sequence[str]) -> ParsedCommand:
    """Parse launcher arguments, preserving the exact leaf suffix after ``--``."""

    raw = list(argv)
    if "--" in raw:
        separator = raw.index("--")
        launcher_args = raw[:separator]
        leaf_args = raw[separator + 1 :]
    else:
        launcher_args = raw
        leaf_args = []
    args = _parser().parse_args(launcher_args)
    return ParsedCommand(
        harness=args.harness,
        aliases=tuple(args.alias),
        depth_values=tuple(args.depth),
        execution_values=tuple(args.execution),
        connectivity_values=tuple(args.connectivity),
        model=args.model,
        provider=args.provider,
        dry_run=args.dry_run,
        explain=args.explain,
        leaf_args=tuple(leaf_args),
    )


def _axis_contributions(command: ParsedCommand, name: str) -> tuple[Contribution, ...]:
    values = [Contribution(DEFAULT_AXES[name], Provenance("default", f"default:{name}"))]
    for alias in command.aliases:
        if name in ALIASES[alias]:
            values.append(Contribution(ALIASES[alias][name], Provenance("alias", f"alias:{alias}")))
    for value in getattr(command, f"{name}_values"):
        values.append(Contribution(value, Provenance("option", f"--{name}")))
    return tuple(values)


def _resolve_axis(command: ParsedCommand, name: str) -> ResolvedField:
    contributions = _axis_contributions(command, name)
    explicit = contributions[1:]
    selected_values = {item.value for item in explicit}
    if len(selected_values) > 1:
        detail = ", ".join(f"{item.provenance.source}={item.value}" for item in explicit)
        raise PlanError(f"contradictory {name} selections: {detail}")
    option_values = [item for item in explicit if item.provenance.kind == "option"]
    selected = option_values[-1] if option_values else explicit[-1] if explicit else contributions[0]
    hard = name in {"execution", "connectivity"} and bool(explicit)
    return ResolvedField(
        name=name,
        value=selected.value,
        explicit=bool(explicit),
        hard=hard,
        provenance=FieldProvenance(selected.provenance, contributions),
        transport=Transport("unresolved"),
    )


def _option_base(arg: str, known_options: Collection[str] = ()) -> str:
    if arg.startswith("--"):
        return arg.split("=", 1)[0]
    if arg.startswith("-") and len(arg) > 2:
        exact_short = arg.split("=", 1)[0]
        if exact_short in known_options:
            return exact_short
        return arg[:2]
    return arg


def _validate_leaf_args(command: ParsedCommand, capability: HarnessCapability) -> None:
    index = 0
    while index < len(command.leaf_args):
        arg = command.leaf_args[index]
        base = _option_base(arg, capability.owned_options)
        owner = capability.owned_options.get(base)
        if owner is not None:
            raise PlanError(f"leaf argument {base} contradicts launcher-owned {owner}; use the unified option")
        if command.harness == "codex" and base in {"-c", "--config"}:
            value = None
            if base == "-c" and arg != "-c":
                value = arg[2:].removeprefix("=")
            elif base == "--config" and "=" in arg:
                value = arg.split("=", 1)[1]
            if value is None and index + 1 < len(command.leaf_args):
                value = command.leaf_args[index + 1]
            if value and any(key in value for key in ("model_reasoning_effort", "approval_policy", "sandbox_mode")):
                raise PlanError("leaf Codex config contradicts launcher-owned depth/execution")
        index += 1


def _cursor_model_with_effort(model: str, effort: str) -> str:
    if not model.endswith("]") or "[" not in model:
        return f"{model}[effort={effort}]"
    base, raw_parameters = model.rsplit("[", 1)
    parameters = [item.strip() for item in raw_parameters[:-1].split(",") if item.strip()]
    for parameter in parameters:
        key, separator, value = parameter.partition("=")
        if key.strip() != "effort":
            continue
        if not separator or value.strip() != effort:
            raise PlanError(f"Cursor model effort={value.strip() or 'unknown'} contradicts depth effort={effort}")
        return model
    parameters.append(f"effort={effort}")
    return f"{base}[{','.join(parameters)}]"


def _depth_transport(
    command: ParsedCommand,
    field: ResolvedField,
    selection: AvailabilitySelection,
    capability: HarnessCapability,
) -> tuple[Transport, str | None]:
    if not field.explicit:
        return Transport("inherited", note="current harness depth/default remains in control"), selection.model
    effort = DEPTH_EFFORT[field.value]
    if capability.depth_transport == "cursor-model":
        if selection.model is None:
            note = "Cursor depth is advisory until an explicit model or availability adapter supplies a model"
            return Transport("advisory", note=note), None
        model = _cursor_model_with_effort(selection.model, effort)
        return Transport("applied", note=f"model parameter effort={effort}"), model
    if capability.depth_transport == "effort-flag":
        return Transport("applied", argv=("--effort", effort)), selection.model
    if capability.depth_transport == "codex-config":
        value = f'model_reasoning_effort="{effort}"'
        return Transport("applied", argv=("-c", value)), selection.model
    if capability.depth_transport == "thinking-flag":
        return Transport("applied", argv=("--thinking", effort)), selection.model
    note = f"{command.harness} has no verified interactive depth control; soft preference remains in AI_AGENT_DEPTH"
    return Transport("advisory", note=note), selection.model


def _hard_transport(
    harness: str,
    field: ResolvedField,
    supported: dict[str, tuple[str, ...] | None],
) -> Transport:
    if not field.explicit:
        return Transport("inherited", note="current harness default remains in control")
    argv = supported[field.value]
    if argv is None:
        raise PlanError(f"{harness} does not support explicit {field.name}={field.value}")
    return Transport("applied", argv=argv)


def _connectivity_transport(
    harness: str,
    field: ResolvedField,
    capability: HarnessCapability,
) -> Transport:
    transport = _hard_transport(harness, field, capability.connectivity)
    if harness != "pi" or not field.explicit:
        return transport
    return Transport(
        transport.status,
        argv=transport.argv,
        unset_env=("PI_OFFLINE",),
        note=transport.note,
    )


def _selection_plan(
    harness: str,
    selection: AvailabilitySelection,
    capability: HarnessCapability,
    model: str | None,
) -> SelectionPlan:
    args: list[str] = []
    if selection.provider is not None:
        if capability.provider_flag is None:
            raise PlanError(f"{harness} does not accept an explicit provider; encode it in --model if supported")
        if selection.provider_is_explicit and (model is None or not model.strip()):
            raise PlanError(f"{harness} explicit provider requires a concrete model")
        args.extend([capability.provider_flag, selection.provider])
    if model is not None:
        args.extend([capability.model_flag, model])
    return SelectionPlan(
        model=model,
        provider=selection.provider,
        model_provenance=selection.model_provenance,
        provider_provenance=selection.provider_provenance,
        model_is_explicit=selection.model_is_explicit,
        provider_is_explicit=selection.provider_is_explicit,
        transport_args=tuple(args),
        availability=selection.availability,
    )


def resolve_plan(
    command: ParsedCommand,
    availability: AvailabilityAdapter | None = None,
) -> InvocationPlan:
    """Resolve a parsed command without executing a harness or contacting a provider."""

    capability = CAPABILITIES[command.harness]
    _validate_leaf_args(command, capability)
    adapter = availability or ModelMirrorAvailabilityAdapter()
    selection = adapter.resolve(command.harness, command.model, command.provider)
    fields = {name: _resolve_axis(command, name) for name in DEFAULT_AXES}

    depth_transport, model = _depth_transport(command, fields["depth"], selection, capability)
    execution_transport = _hard_transport(command.harness, fields["execution"], capability.execution)
    connectivity_transport = _connectivity_transport(command.harness, fields["connectivity"], capability)
    fields["depth"] = _with_transport(fields["depth"], depth_transport)
    fields["execution"] = _with_transport(fields["execution"], execution_transport)
    fields["connectivity"] = _with_transport(fields["connectivity"], connectivity_transport)
    selection_plan = _selection_plan(command.harness, selection, capability, model)

    argv = [capability.leaf, *selection_plan.transport_args]
    env = {
        "AI_AGENT_DEPTH": fields["depth"].value,
        "AI_AGENT_EXECUTION": fields["execution"].value,
        "AI_AGENT_CONNECTIVITY": fields["connectivity"].value,
    }
    unset_env: list[str] = []
    for name in ("depth", "execution", "connectivity"):
        transport = fields[name].transport
        argv.extend(transport.argv)
        env.update(dict(transport.env))
        unset_env.extend(transport.unset_env)
    argv.extend(command.leaf_args)
    unique_unsets = tuple(sorted(set(unset_env) - set(env)))
    return InvocationPlan(
        harness=command.harness,
        aliases=command.aliases,
        fields=fields,
        selection=selection_plan,
        actual_argv=tuple(argv),
        env=tuple(sorted(env.items())),
        unset_env=unique_unsets,
        capability=capability,
    )


def _with_transport(field: ResolvedField, transport: Transport) -> ResolvedField:
    return ResolvedField(
        name=field.name,
        value=field.value,
        explicit=field.explicit,
        hard=field.hard,
        provenance=field.provenance,
        transport=transport,
    )


def _redact_argv(argv: tuple[str, ...], capability: HarnessCapability) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    redact_variadic = False
    secret_assignment = re.compile(r"(?i)^([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|AUTHORIZATION))=(.*)$")
    for arg in argv:
        if redact_variadic:
            if not arg.startswith("-") or arg == "-":
                redacted.append("<redacted>")
                continue
            redact_variadic = False
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        base = _option_base(arg, capability.sensitive_options)
        if base in capability.sensitive_options:
            if "=" in arg:
                redacted.append(f"{base}=<redacted>")
            elif base.startswith("-") and not arg.startswith("--") and len(arg) > 2:
                redacted.append(f"{base}<redacted>")
            else:
                redacted.append(arg)
                if base in capability.variadic_sensitive_options:
                    redact_variadic = True
                else:
                    redact_next = True
            continue
        assignment = secret_assignment.match(arg)
        redacted.append(f"{assignment.group(1)}=<redacted>" if assignment else arg)
    return redacted


def explain_plan(plan: InvocationPlan) -> str:
    public = plan.public_dict()
    lines = ["InvocationPlan", f"harness={plan.harness}"]
    for name in ("depth", "execution", "connectivity"):
        field = plan.fields[name]
        strength = "hard" if field.hard else "soft/default"
        lines.append(f"{name}={field.value} ({field.provenance.selected.source}; {strength}; {field.transport.status})")
        if field.transport.note:
            lines.append(f"  note: {field.transport.note}")
    lines.append(f"model={plan.selection.model or '<harness-default>'} ({plan.selection.model_provenance.source})")
    lines.append(
        f"provider={plan.selection.provider or '<harness-default>'} ({plan.selection.provider_provenance.source})"
    )
    lines.append(f"argv: {json.dumps(public['leaf']['argv'])}")
    lines.append(f"env: {json.dumps(public['leaf']['env'], sort_keys=True)}")
    if plan.unset_env:
        lines.append(f"unset env: {json.dumps(list(plan.unset_env))}")
    return "\n".join(lines)


def execute_plan(plan: InvocationPlan) -> int:
    env = dict(os.environ)
    for name in plan.unset_env:
        env.pop(name, None)
    env.update(dict(plan.env))
    try:
        os.execvpe(plan.actual_argv[0], list(plan.actual_argv), env)
    except FileNotFoundError:
        print(f",ai: leaf command not found: {plan.actual_argv[0]}", file=sys.stderr)
        return 127
    except PermissionError:
        print(f",ai: leaf command is not executable: {plan.actual_argv[0]}", file=sys.stderr)
        return 126
    return 127


def main(argv: Sequence[str] | None = None) -> int:
    try:
        command = parse_cli(sys.argv[1:] if argv is None else argv)
        plan = resolve_plan(command)
    except PlanError as error:
        print(f",ai: error: {error}", file=sys.stderr)
        return 2
    if command.dry_run:
        print(json.dumps(plan.public_dict(), indent=2, sort_keys=True))
        return 0
    if command.explain:
        print(explain_plan(plan))
        return 0
    return execute_plan(plan)


if __name__ == "__main__":
    raise SystemExit(main())
