// Managed by chezmoi (source: home/dot_pi/agent/exact_extensions/subagent-contract.ts).
// Sole owner of the Pi `subagent` delegation contract. This adapter loads the
// installed pi-subagents entry exactly once through a decorated ExtensionAPI,
// projects a narrowed leaf-only description/schema before registration, and
// enforces that same registered contract at runtime through the native pi-ai
// schema validator. Native execute/render/backend and lifecycle callbacks pass
// through by identity; only the model-facing advertisement is deployment-owned.
//
// Native anchors (Pi 0.85.1 / pi-subagents 0.67.0):
// - registration point: pi-subagents/src/extension/index.ts registers the
//   `subagent` tool with parameters from createSubagentParamsSchema() in
//   src/extension/schemas.ts (80 flat optional properties).
// - package filter: pi-coding-agent dist/core/package-manager.js
//   (collectPackageResources/applyPackageFilter) disables the package entry's
//   own extensions/skills/prompts, so this adapter is the only registrar and
//   the first-wins race in runner.js getAllRegisteredTools never triggers.
// - enforcement order: pi-agent-core dist/agent-loop.js prepareToolCall runs
//   pi-ai validateToolArguments (dist/utils/validation.js) before
//   beforeToolCall; a schema failure throws
//   `Validation failed for tool "subagent"` and never reaches execute, so no
//   run id exists. The deployment tool_call guard runs after schema
//   validation and prefixes its own refusals with INVALID_DISPATCH_REQUEST.
// Both rejection classes are invalid invocation: final for that shape, never
// a lost authorization, never retried unchanged, never a permission reset.

import { validateToolArguments } from "@earendil-works/pi-ai";
import type { Tool, ToolCall } from "@earendil-works/pi-ai";
import type { CustomToolCallEvent, ExtensionAPI, ToolDefinition } from "@earendil-works/pi-coding-agent";
import { realpathSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { Type } from "typebox";
import type { TSchema } from "typebox";

export const INVALID_DISPATCH_REQUEST = "INVALID_DISPATCH_REQUEST";

export const NATIVE_VALIDATION_PREFIX = 'Validation failed for tool "subagent"';

export const CONTRACT_TOOL_NAME = "subagent";

export const UPSTREAM_PACKAGE_ENTRY = join(
  ".local/share/pnpm-global-links/node_modules/pi-subagents/index.ts",
);

export const ALLOWED_MANAGEMENT_ACTIONS = ["list", "status", "debug.run", "stop", "interrupt"] as const;

export type AllowedManagementAction = (typeof ALLOWED_MANAGEMENT_ACTIONS)[number];

// Leaf execution controls preserved from the native consumer. Composite-only,
// time-based creation, and per-call override inputs are absent by design.
export const LEAF_PARAMETER_KEYS = [
  "agent",
  "task",
  "extensionBindings",
  "lane",
  "agentScope",
  "acceptance",
  "context",
  "async",
  "cwd",
  "output",
  "outputMode",
  "timeoutMs",
  "maxRuntimeMs",
  "toolTimeoutMs",
  "toolBudget",
  "usageBudget",
  "artifacts",
  "worktree",
  "baseRef",
  "isolation",
  "control",
  "includeProgress",
  "share",
  "sessionDir",
  "chatProgress",
  "fast",
  "outputSchema",
] as const;

// Observation/cancellation controls preserved from the native consumer. The
// native executor renders an action call with its agent target when present,
// so `agent` stays accepted here while `task` never combines with an action.
export const MANAGEMENT_PARAMETER_KEYS = [
  "action",
  "agent",
  "agentScope",
  "capabilities",
  "id",
  "runId",
  "dir",
  "view",
  "lines",
  "index",
  "childId",
  "cwd",
] as const;

export const SUBAGENT_DESCRIPTION =
  'Managed leaf delegation. Dispatch one ready child packet per call with {agent, agentScope:"user", acceptance:false} and fresh context (omit context or use "fresh"); independent packets may run concurrently with async:true. Only the parameters listed in the schema are accepted; any other parameter is rejected before execution and must be corrected, never retried unchanged. Roster and run inspection use {action:"list"|"status"|"debug.run"|"stop"|"interrupt"} with the documented target fields; any other action value is rejected the same way. Two rejection classes both mean invalid invocation, final for that shape: the native schema validator reports Validation failed for tool "subagent", and the deployment guard prefixes INVALID_DISPATCH_REQUEST. Neither is a lost authorization: do not ask permission to reissue an allowed packet. Retry an identical packet once only after the tool executed and then reported a host, bootstrap, or runner failure; a child that timed out or exhausted its budget is re-sized (split, or ship materialized inputs), never relaunched identical. Call {action:"list",agentScope:"user",capabilities:true} once per session and reuse that roster. Consume a child result once: a file-only pointer means read the file; an inline body means do not re-read the file.';

// Upstream watchdog notices (`subagent_control_notice`) hard-code `steer` and
// `resume` nudges that this contract rejects before execution. The lines are
// rewritten at the sendMessage seam so the parent is never advertised an action
// the guard denies; the notice's facts, status, and interrupt lines are kept.
export const CONTROL_NOTICE_TYPE = "subagent_control_notice";
export const CONTROL_NOTICE_HINT =
  "Hint: inspect status first. A live child is not steered or resumed under this contract (SOP §3.7: workers return once; the root owns recovery). If it is genuinely stuck, interrupt it and re-size the packet; if it is slow but working, let it finish.";
const STEER_OR_RESUME_LINE = /^(Hint: .*\b(steer|resume)\b.*|Top-level live async nudge: .*|Routed live nested nudge: .*)$/;
// completion_guard notices end with "Next: ... retry with a more explicit implementation
// prompt or handle the fix directly" — an identical relaunch and an inline substitution,
// both of which SOP §3.7 forbids the root.
const COMPLETION_GUARD_NEXT_LINE = /^Next: .*\b(retry|handle the fix directly)\b.*$/;
export const COMPLETION_GUARD_HINT =
  "Next: read the output artifact once. A failed worker is a `blocked` return (SOP §3.7): resolve the cause in root Understand, then dispatch a corrected or re-sized packet; never relaunch it identical and never substitute an inline fix.";

// Upstream re-reads `details.noticeText` (control-notices.ts formatSubagentControlNotice),
// so the rewritten text must land in both the content and that field.
function withNoticeText(details: unknown, content: string): unknown {
  if (typeof details !== "object" || details === null || !("noticeText" in details)) return details;
  return { ...details, noticeText: content };
}

export function rewriteControlNotice(content: string): string {
  const lines = content.split("\n");
  const rewritten = lines.flatMap((line) => {
    if (STEER_OR_RESUME_LINE.test(line)) return [];
    if (COMPLETION_GUARD_NEXT_LINE.test(line)) return [COMPLETION_GUARD_HINT];
    return [line];
  });
  const droppedNudge = rewritten.length < lines.length;
  if (!droppedNudge) return rewritten.join("\n");
  const statusIndex = rewritten.findIndex((line) => line.startsWith("Status: "));
  const insertAt = statusIndex === -1 ? rewritten.length : statusIndex;
  return [...rewritten.slice(0, insertAt), CONTROL_NOTICE_HINT, ...rewritten.slice(insertAt)].join("\n");
}

// Pointer to the single substantive contract above. The tool description and
// the registered schema are the contract; this note only names the two
// rejection classes and the retry rule so the prompt cannot drift from them.
export const DISPATCH_NOTE =
  'Subagent dispatch follows the subagent tool description and schema as the sole contract: managed leaf packets only. Both rejection classes are invalid invocation, final for that shape: the native schema validator reports Validation failed for tool "subagent", and the deployment guard prefixes INVALID_DISPATCH_REQUEST. Correct the call instead of retrying it unchanged, and never treat a rejection as lost authorization for already-authorized work. Retry an identical packet once only when the tool executed and then reported a host, bootstrap, or runner failure.';

function nativePropertiesOf(nativeParameters: TSchema): Record<string, TSchema> {
  if (typeof nativeParameters !== "object" || nativeParameters === null || !("properties" in nativeParameters)) {
    throw new Error("subagent-contract: native subagent parameters have no properties table.");
  }
  const properties: unknown = (nativeParameters as { properties: unknown }).properties;
  if (typeof properties !== "object" || properties === null) {
    throw new Error("subagent-contract: native subagent parameters have no properties table.");
  }
  return properties as Record<string, TSchema>;
}

function schemaDescription(schema: TSchema): string | undefined {
  if (typeof schema === "object" && schema !== null && "description" in schema) {
    const description: unknown = (schema as { description: unknown }).description;
    return typeof description === "string" ? description : undefined;
  }
  return undefined;
}

// Provider-compatible root object schema with closed properties and two
// closed conditional variants. The root lists every allowed key (native-wide
// property schemas, additionalProperties:false) and the anyOf branches carry
// the requiredness: the leaf branch requires agent/agentScope/acceptance with
// deployment literals and forbids action by omission; the management branch
// requires an allowed action. Empty, mixed, and malformed shapes fail at least
// one closed layer and never reach native execute.
export function buildSubagentContractParameters(nativeParameters: TSchema): TSchema {
  const native = nativePropertiesOf(nativeParameters);
  const pick = (key: string): TSchema => {
    const property = native[key];
    if (property === undefined) {
      throw new Error(`subagent-contract: native schema lacks property "${key}"`);
    }
    return property;
  };

  const agentSchema = Type.String({
    minLength: 1,
    pattern: ".*\\S.*",
    description: schemaDescription(pick("agent")) ?? "One-child agent.",
  });
  const agentScopeSchema = Type.Literal("user", { description: 'Leaf execution scope; always "user".' });
  const acceptanceSchema = Type.Literal(false, { description: "Leaf acceptance; always false and stated explicitly." });
  const contextSchema = Type.Optional(
    Type.Literal("fresh", { description: "Fresh child context; omit for the configured default." }),
  );
  const actionSchema = Type.Union(
    ALLOWED_MANAGEMENT_ACTIONS.map((action) => Type.Literal(action)),
    { description: "Observation/cancellation only; omit for leaf execution." },
  );

  const literalOverrides: Record<string, TSchema> = {
    agent: agentSchema,
    agentScope: agentScopeSchema,
    acceptance: acceptanceSchema,
    context: contextSchema,
    action: actionSchema,
    worktree: { ...pick("worktree"), description: "Isolate this child in a managed git worktree." },
    output: { ...pick("output"), description: "Child output path or false; relative paths use managed artifact routing. Bind durable output here, not task prose." },
    timeoutMs: { ...pick("timeoutMs"), description: "Child timeout in milliseconds; native single-child defaults apply. Alias maxRuntimeMs." },
    cwd: { ...pick("cwd"), description: "Execution directory." },
  };

  const allowedKeys = [...new Set([...LEAF_PARAMETER_KEYS, ...MANAGEMENT_PARAMETER_KEYS])];
  const rootProperties: Record<string, TSchema> = {};
  for (const key of allowedKeys) {
    rootProperties[key] = Type.Optional(literalOverrides[key] ?? pick(key));
  }
  const leafProperties: Record<string, TSchema> = {};
  for (const key of LEAF_PARAMETER_KEYS) {
    const property = literalOverrides[key] ?? pick(key);
    leafProperties[key] = ["agent", "agentScope", "acceptance"].includes(key) ? property : Type.Optional(property);
  }
  const managementProperties: Record<string, TSchema> = {};
  for (const key of MANAGEMENT_PARAMETER_KEYS) {
    managementProperties[key] = key === "action" ? actionSchema : Type.Optional(literalOverrides[key] ?? pick(key));
  }
  return Type.Object(rootProperties, {
    additionalProperties: false,
    anyOf: [
      Type.Object(leafProperties, { additionalProperties: false }),
      Type.Object(managementProperties, { additionalProperties: false }),
    ],
  });
}

export function projectSubagentTool(native: ToolDefinition): ToolDefinition {
  const projected = { ...native };
  delete projected.promptSnippet;
  delete projected.promptGuidelines;
  projected.description = SUBAGENT_DESCRIPTION;
  projected.parameters = buildSubagentContractParameters(native.parameters);
  return projected;
}

export type DispatchAdmission = { block: true; reason: string } | undefined;

function contractTool(parameters: TSchema): Tool {
  return { name: CONTRACT_TOOL_NAME, description: SUBAGENT_DESCRIPTION, parameters };
}

function contractCall(input: CustomToolCallEvent["input"]): ToolCall {
  return { type: "toolCall", id: "subagent-contract-admission", name: CONTRACT_TOOL_NAME, arguments: input };
}

// Root admission runs the SAME registered parameter schema through the native
// pi-ai validator that prepareToolCall runs before beforeToolCall. The only
// independent condition is the child denial below; every other refusal is the
// native schema verdict prefixed with the deployment class token.
export function admissionFor(input: CustomToolCallEvent["input"], parameters: TSchema): DispatchAdmission {
  if (process.env.PI_SUBAGENT_CHILD === "1") {
    return {
      block: true,
      reason: `${INVALID_DISPATCH_REQUEST} (leaf context): a delegated worker MUST NOT invoke subagents or manage other runs. Return the assigned packet result to the root.`,
    };
  }
  try {
    validateToolArguments(contractTool(parameters), contractCall(input));
    return undefined;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return {
      block: true,
      reason: `${INVALID_DISPATCH_REQUEST}: ${detail} Correct the call instead of retrying it unchanged; this rejection is final for that shape and never a lost authorization.`,
    };
  }
}

function childDenial(): { block: true; reason: string } {
  return {
    block: true,
    reason: `${INVALID_DISPATCH_REQUEST} (leaf context): a delegated worker MUST NOT invoke subagents or manage other runs. Return the assigned packet result to the root.`,
  };
}

export default async function (pi: ExtensionAPI): Promise<void> {
  // A delegated worker must never manage or spawn, even if a subagent tool
  // becomes present through another registration. This defense registers no
  // upstream parent extension and publishes no tool of its own.
  if (process.env.PI_SUBAGENT_CHILD === "1") {
    pi.on("tool_call", (event) => {
      if (event.toolName !== CONTRACT_TOOL_NAME) return undefined;
      return childDenial();
    });
    return;
  }
  const entry = realpathSync(join(process.env.HOME || homedir(), UPSTREAM_PACKAGE_ENTRY));
  const mod: unknown = await import(entry);
  const register: unknown =
    typeof mod === "function" ? mod : (mod as { default?: unknown }).default;
  if (typeof register !== "function") {
    throw new Error(
      "subagent-contract: pi-subagents entry did not export a registration function; refusing to publish a partial subagent tool.",
    );
  }
  let seenSubagent = false;
  let contractParameters: TSchema | undefined;
  const decorated: ExtensionAPI = {
    ...pi,
    sendMessage(message, options) {
      if (message.customType !== CONTROL_NOTICE_TYPE || typeof message.content !== "string") {
        return pi.sendMessage(message, options);
      }
      const content = rewriteControlNotice(message.content);
      const details = withNoticeText(message.details, content);
      return pi.sendMessage({ ...message, content, details }, options);
    },
    registerTool(tool) {
      if (tool.name !== CONTRACT_TOOL_NAME) return pi.registerTool(tool);
      seenSubagent = true;
      const projected = projectSubagentTool(tool);
      // The guard below reads this exact registered object: the schema
      // compiler fields and the guard share one contract, never two lists.
      contractParameters = projected.parameters;
      return pi.registerTool(projected);
    },
  };
  await (register as (pi: ExtensionAPI) => void | Promise<void>)(decorated);
  if (!seenSubagent || contractParameters === undefined) {
    throw new Error(
      "subagent-contract: expected native 'subagent' registration from pi-subagents was not observed; refusing to publish a partial contract.",
    );
  }
  const admitted: TSchema = contractParameters;

  pi.on("tool_call", (event) => {
    if (event.toolName !== CONTRACT_TOOL_NAME) return undefined;
    return admissionFor(event.input, admitted);
  });

  pi.on("before_agent_start", (event) => {
    if (process.env.PI_SUBAGENT_CHILD === "1" || /^\[DELEGATION BOUNDARY\]$/m.test(event.systemPrompt ?? "")) return undefined;
    if (event.systemPrompt.includes(DISPATCH_NOTE)) return undefined;
    return { systemPrompt: `${event.systemPrompt}\n\n${DISPATCH_NOTE}` };
  });
}
