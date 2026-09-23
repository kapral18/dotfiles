#!/usr/bin/env python3
"""Pi managed-leaf dispatch contract: adapter ownership, schema, and admission.

The sole registration owner is
``home/dot_pi/agent/exact_extensions/subagent-contract.ts``: it loads the
installed pi-subagents entry once, projects a narrowed leaf-only
description/schema, and enforces that same registered contract at runtime
through the native pi-ai validator. These tests exercise the real native
loader, the real pi-ai schema validator, and the registered guard (no
model/provider calls, no session, no dispatch).
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER = REPO / "home/dot_pi/agent/exact_extensions/subagent-contract.ts"
RUNTIME_PARITY = REPO / "home/dot_pi/agent/exact_extensions/runtime-parity.ts"
SETTINGS = {profile: REPO / f"home/dot_pi/agent/readonly_settings.{profile}.json" for profile in ("work", "personal")}
PI_SUBAGENTS_SOURCE = "~/.local/share/pnpm-global-links/node_modules/pi-subagents"
PI_PACKAGE = Path.home() / ".local/share/pnpm-global-links/node_modules/@earendil-works/pi-coding-agent"

FORBIDDEN_ADVERTISEMENT_TOKENS = (
    "workflowScript",
    "workflowScriptPath",
    '"guide"',
    "resume",
    "schedule",
    "steer",
    "agentContract",
    "exactly one top-level",
)

# Independent oracle: the exact closed key sets the contract must publish.
# Hardcoded here so the test never compares the adapter against itself.
EXPECTED_LEAF_KEYS = {
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
}
EXPECTED_MGMT_KEYS = {
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
}
EXPECTED_LEAF_REQUIRED = {"agent", "agentScope", "acceptance"}
EXPECTED_MGMT_REQUIRED = {"action"}
# Keys the native consumer reserves for composite-only, time-based creation,
# revival, and per-call override paths. None may appear in the closed root.
FORBIDDEN_SCHEMA_KEYS = {
    "workflowScript",
    "workflowScriptPath",
    "workflow",
    "gate",
    "agentContract",
    "chain",
    "parallel",
    "model",
    "skill",
    "skills",
    "steeringRecovery",
}

NATIVE_VALIDATION_PREFIX = 'Validation failed for tool "subagent"'
GUARD_CLASS_TOKEN = "INVALID_DISPATCH_REQUEST"


def _pi_package_dir() -> Path | None:
    """Use the authoritative pnpm link, not the executable shell shim."""
    if not PI_PACKAGE.exists():
        return None
    target = PI_PACKAGE.resolve(strict=True)
    manifest = json.loads((target / "package.json").read_text(encoding="utf-8"))
    if manifest.get("name") != "@earendil-works/pi-coding-agent":
        raise RuntimeError(f"Unexpected Pi package at {target}")
    if not (target / "dist/core/extensions/loader.js").is_file():
        raise RuntimeError(f"Pi package lacks its extension loader: {target}")
    return target


def _pi_subagents_entry() -> Path | None:
    """The entry the package declares in `pi.extensions` (compiled `index.js` since 0.70.0)."""
    package_dir = Path.home() / ".local/share/pnpm-global-links/node_modules/pi-subagents"
    manifest_path = package_dir / "package.json"
    if not manifest_path.is_file():
        return None
    extensions = json.loads(manifest_path.read_text(encoding="utf-8")).get("pi", {}).get("extensions")
    if not (isinstance(extensions, list) and len(extensions) == 1 and isinstance(extensions[0], str)):
        raise AssertionError(f"pi-subagents manifest must declare exactly one pi.extensions entry: {manifest_path}")
    entry = Path(os.path.realpath(package_dir)) / extensions[0]
    return Path(os.path.realpath(entry)) if entry.is_file() else None


def _run_node(script: str, *args: str, timeout: int = 300) -> dict:
    result = subprocess.run(
        ["node", "--no-warnings", "--experimental-import-meta-resolve", "--input-type=module", "-e", script, *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert result.returncode == 0, f"node driver failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    return json.loads(result.stdout)


CONTRACT_DRIVER = r"""
import { createRequire } from "node:module";
import { realpathSync } from "node:fs";
import { dirname, extname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const PI = process.argv[1];
const ADAPTER = process.argv[2];
const ENTRY = process.argv[3];
const PS = dirname(ENTRY);
const EXT = extname(ENTRY);
const out = {};
// The root fixture must never inherit a child marker: save it, clear it for
// every root section below, and restore it before reporting.
const savedChild = process.env.PI_SUBAGENT_CHILD;
delete process.env.PI_SUBAGENT_CHILD;
try {
  const loaderFile = PI + "/dist/core/extensions/loader.js";
  const req = createRequire(loaderFile);
  const loaderUrl = pathToFileURL(loaderFile).href;
  const alias = { "@earendil-works/pi-coding-agent": PI + "/dist/index.js" };
  for (const name of ["@earendil-works/pi-agent-core", "@earendil-works/pi-tui", "@earendil-works/pi-ai", "@earendil-works/pi-ai/compat", "@earendil-works/pi-ai/oauth", "@earendil-works/pi-ai/providers/all", "typebox", "typebox/value", "typebox/compile"]) {
    alias[name] = fileURLToPath(import.meta.resolve(name, loaderUrl));
  }
  const jitiMod = await import(req.resolve("jiti"));
  const createJiti = jitiMod.createJiti ?? jitiMod.default?.createJiti ?? jitiMod.default;
  const jiti = createJiti(import.meta.url, { moduleCache: false, alias });
  // Exact native dependency resolution: ask Node to resolve pi-ai from the Pi
  // loader, the same edge the adapter's own import uses at runtime.
  const piAiEntry = import.meta.resolve("@earendil-works/pi-ai", loaderUrl);
  const ai = await import(piAiEntry);
  if (typeof ai.validateToolArguments !== "function") {
    throw new Error("subagent-contract probe: pi-ai entry exports no validateToolArguments");
  }
  const noop = () => {};
  const base = {
    on() {}, registerCommand() {}, registerShortcut: noop, registerFlag: noop,
    registerMessageRenderer() {}, registerMarkdownTransformer: noop, registerEntryRenderer: noop,
    getFlag: () => undefined, sendMessage: noop, sendUserMessage: noop, appendEntry: noop,
    setSessionName: noop, getSessionName: () => undefined, setLabel: noop,
    exec: async () => ({ stdout: "", stderr: "", code: 0 }),
    getActiveTools: () => ["read", "bash"], getAllTools: () => [], setActiveTools: noop, getCommands: () => [],
    setModel: async () => true, getThinkingLevel: () => "medium", setThinkingLevel: noop,
    registerProvider: noop, unregisterProvider: noop,
    events: { emit: noop, on() { return noop; } },
  };
  // ONE upstream factory run: the captured native tool below is the identity
  // oracle for the projection. A second factory run would mint fresh closures
  // and make any === comparison meaningless.
  const nativeCalls = [];
  const upstream = await jiti.import(ENTRY);
  await (upstream.default ?? upstream)({ ...base, registerTool(t) { nativeCalls.push(t); } });
  const native = nativeCalls.find((t) => t.name === "subagent");
  out.native = {
    seen: Boolean(native),
    keys: native ? Object.keys(native) : [],
    propCount: native ? Object.keys(native.parameters.properties).length : 0,
    hasSnippet: native ? ("promptSnippet" in native) : false,
    hasGuidelines: native ? ("promptGuidelines" in native) : false,
  };
  const ns = await jiti.import(ADAPTER);
  const factory = ns.default ?? ns;
  const admissionFor = ns.admissionFor;
  const projectSubagentTool = ns.projectSubagentTool;
  if (typeof admissionFor !== "function" || typeof projectSubagentTool !== "function") {
    throw new Error("subagent-contract probe: adapter exports no admissionFor/projectSubagentTool");
  }
  // Project THAT captured native tool and compare callbacks by identity.
  const projected = projectSubagentTool(native);
  out.projection = {
    keys: Object.keys(projected),
    hasSnippet: "promptSnippet" in projected,
    hasGuidelines: "promptGuidelines" in projected,
    description: projected.description,
    identity: {
      execute: projected.execute === native.execute,
      renderCall: projected.renderCall === native.renderCall,
      renderResult: projected.renderResult === native.renderResult,
      label: projected.label === native.label,
    },
  };
  // Separately exercise the real decorated factory: single registration, no
  // duplication, native lifecycle passthrough, and the registered contract.
  const calls = [];
  const handlers = {};
  const commands = [];
  const sent = [];
  let decoratedPi;
  await factory({ ...base, registerTool(t) { calls.push(t); }, on(e, h) { handlers[e] = h; }, registerCommand(n, o) { commands.push(n); }, sendMessage(m, o) { sent.push({ m, o }); } });
  // Upstream watchdog notice, formatted by the REAL pi-subagents formatter, then
  // pushed through the decorated sendMessage the adapter hands upstream. The
  // adapter must strip every steer/resume nudge and keep status/interrupt.
  const control = await jiti.import(PS + "/src/runs/shared/subagent-control" + EXT);
  const notices = await jiti.import(PS + "/src/extension/control-notices" + EXT);
  const event = { type: "active_long_running", reason: "tool_open_threshold", agent: "k-agent-adversarial-verifier", runId: "run-1", index: 0, message: "has had tool 'bash' open for 240s" };
  const upstreamText = control.formatControlNoticeMessage(event, "subagent-k-agent-adversarial-verifier-run-1-1");
  const rewritten = ns.rewriteControlNotice(upstreamText);
  const failed = { type: "needs_attention", reason: "tool_failures", agent: "k-agent-implementer", runId: "run-2", message: "repeated tool failures" };
  const failedUpstream = control.formatControlNoticeMessage(failed);
  const failedRewritten = ns.rewriteControlNotice(failedUpstream);
  const unrelated = "plain text with steer in prose";
  out.notice = {
    upstreamHasSteer: /\bsteer\b/.test(upstreamText),
    upstreamHasResume: /\bresume\b/.test(upstreamText),
    rewrittenHasSteer: /\bsteer\b|action: "steer"/.test(rewritten.replace(ns.CONTROL_NOTICE_HINT, "")),
    rewrittenHasResume: /action: "resume"/.test(rewritten),
    keepsStatus: rewritten.includes('Status: subagent({ action: "status", id: "run-1" })'),
    keepsInterrupt: rewritten.includes('Interrupt: subagent({ action: "interrupt", id: "run-1" })'),
    keepsSignal: rewritten.includes("Signal: has had tool 'bash' open for 240s"),
    keepsIntercom: rewritten.includes("Direct intercom target: subagent-k-agent-adversarial-verifier-run-1-1"),
    hintPresent: rewritten.includes(ns.CONTROL_NOTICE_HINT),
    hintBeforeStatus: rewritten.indexOf(ns.CONTROL_NOTICE_HINT) < rewritten.indexOf("Status: "),
    unrelatedUntouched: ns.rewriteControlNotice(unrelated) === unrelated,
    noticeType: notices.SUBAGENT_CONTROL_MESSAGE_TYPE,
    failedUpstreamHasSteer: /\bsteer\b/.test(failedUpstream) && /\bresume\b/.test(failedUpstream),
    failedRewrittenHasSteerOrResume: /action: "steer"|action: "resume"/.test(failedRewritten),
    failedHintPresent: failedRewritten.includes(ns.CONTROL_NOTICE_HINT),
    failedKeepsSignal: failedRewritten.includes("Signal: repeated tool failures"),
    failedKeepsStatus: failedRewritten.includes('Status: subagent({ action: "status", id: "run-2" })'),
  };
  const names = calls.map((t) => t.name);
  const registered = calls.find((t) => t.name === "subagent");
  const params = registered.parameters;
  const branches = Array.isArray(params.anyOf) ? params.anyOf : [];
  out.factory = {
    subagentCount: names.filter((n) => n === "subagent").length,
    toolCount: names.length,
    bgWait: names.includes("bg_wait"),
    commandCount: commands.length,
    handlerEvents: Object.keys(handlers),
    hasToolCallGuard: "tool_call" in handlers,
    hasPromptNote: "before_agent_start" in handlers,
    hasSnippet: "promptSnippet" in registered,
    hasGuidelines: "promptGuidelines" in registered,
  };
  out.contract = {
    description: registered.description,
    publishedSchema: JSON.stringify(params),
    rootType: params.type,
    rootAdditional: params.additionalProperties,
    branchCount: branches.length,
    leafRequired: branches[0]?.required ?? null,
    mgmtRequired: branches[1]?.required ?? null,
    leafProps: branches[0] ? Object.keys(branches[0].properties ?? {}) : null,
    mgmtProps: branches[1] ? Object.keys(branches[1].properties ?? {}) : null,
    rootProps: Object.keys(params.properties ?? {}),
    leafAdditional: branches[0]?.additionalProperties ?? null,
    mgmtAdditional: branches[1]?.additionalProperties ?? null,
  };
  // The case table runs through the ACTUAL registered consumer parameters:
  // the native validator verdict and the guard verdict must agree everywhere,
  // because the guard owns no policy beyond the child denial below.
  const tool = { name: "subagent", parameters: params };
  const check = (args) => {
    try { ai.validateToolArguments(tool, { type: "toolCall", id: "probe", name: "subagent", arguments: args }); return "ok"; }
    catch (e) { return "reject:" + String(e?.message ?? e).split("\n")[0]; }
  };
  const guard = (args) => {
    const verdict = admissionFor(args, params);
    if (!verdict) return "pass";
    return "block:" + String(verdict.reason ?? "");
  };
  const leafBase = { agent: "k-agent-reviewer", task: "packet", agentScope: "user", acceptance: false };
  const cases = [
    ["leaf-full", { ...leafBase, context: "fresh", async: true }],
    ["leaf-minimal", { ...leafBase }],
    ["leaf-no-task", { agent: "k-agent-reviewer", agentScope: "user", acceptance: false }],
    ["leaf-output-routing", { ...leafBase, async: true, cwd: "/tmp", output: "k-agent-reviewer.md", outputMode: "file-only", timeoutMs: 60000, maxRuntimeMs: 120000, toolTimeoutMs: 300000, toolBudget: { hard: 40 }, usageBudget: { tokens: { hard: 1000 } }, artifacts: true, worktree: true, baseRef: "HEAD" }],
    ["leaf-control", { ...leafBase, control: { enabled: true } }],
    ["leaf-metadata", { ...leafBase, extensionBindings: { "example.data/1": { id: "x" } }, lane: { version: 1, key: "trace" } }],
    ["mgmt-list", { action: "list", capabilities: true }],
    ["mgmt-list-scope", { action: "list", agentScope: "user", capabilities: true }],
    ["mgmt-list-bare", { action: "list" }],
    ["mgmt-status", { action: "status", id: "abc" }],
    ["mgmt-status-view", { action: "status", id: "abc", view: "transcript", lines: 10, index: 0 }],
    ["mgmt-debug", { action: "debug.run", dir: "/tmp/x" }],
    ["mgmt-stop", { action: "stop", runId: "abc" }],
    ["mgmt-stop-id", { action: "stop", id: "abc" }],
    ["mgmt-interrupt", { action: "interrupt", childId: "c1" }],
    ["deny-guide", { action: "guide", topic: "tool-reference" }],
    ["deny-resume", { action: "resume", id: "x" }],
    ["deny-steer", { action: "steer", id: "x", message: "m" }],
    ["deny-schedule", { action: "schedule.create", workflowScript: "x" }],
    ["deny-workflow-script", { workflowScript: "runs.run('x')", async: true }],
    ["deny-workflow-path", { workflowScriptPath: "/tmp/w.ts" }],
    ["deny-workflow", { workflow: "name", args: {} }],
    ["deny-chain", { ...leafBase, chain: [] }],
    ["deny-parallel", { ...leafBase, parallel: [] }],
    ["deny-gate", { ...leafBase, gate: "make check" }],
    ["deny-contract", { ...leafBase, agentContract: {} }],
    ["deny-acceptance-true", { ...leafBase, acceptance: true }],
    ["deny-acceptance-auto", { ...leafBase, acceptance: "auto" }],
    ["deny-acceptance-omitted", { agent: "k-agent-reviewer", task: "packet", agentScope: "user" }],
    ["deny-scope-omitted", { agent: "k-agent-reviewer", task: "packet", acceptance: false }],
    ["deny-scope-project", { ...leafBase, agentScope: "project" }],
    ["deny-scope-both", { ...leafBase, agentScope: "both" }],
    ["deny-context-fork", { ...leafBase, context: "fork" }],
    ["deny-model", { ...leafBase, model: "expensive:high" }],
    ["deny-skill", { ...leafBase, skill: "k-deep-review" }],
    ["deny-skills", { ...leafBase, skills: ["k-code-quality"] }],
    ["deny-steering", { ...leafBase, steeringRecovery: true }],
    ["deny-mixed", { ...leafBase, action: "list" }],
    ["deny-mixed-task-action", { action: "list", task: "packet" }],
    ["deny-empty", {}],
    ["deny-agent-object", { ...leafBase, agent: { name: "x" } }],
    ["deny-agent-empty", { ...leafBase, agent: "" }],
    ["deny-agent-blank", { ...leafBase, agent: "   " }],
    ["deny-task-array", { ...leafBase, task: ["packet"] }],
    ["deny-acceptance-string", { ...leafBase, acceptance: "yes" }],
    ["deny-scope-number", { ...leafBase, agentScope: 123 }],
    ["deny-context-number", { ...leafBase, context: 123 }],
    ["deny-timeout-string", { ...leafBase, timeoutMs: "soon" }],
    ["deny-action-number", { action: 123 }],
    ["deny-capabilities-string", { action: "list", capabilities: "yes" }],
    ["deny-id-object", { action: "status", id: {} }],
  ];
  out.cases = Object.fromEntries(cases.map(([name, args]) => [name, { schema: check(args), guard: guard(args) }]));
  out.note = await handlers.before_agent_start({ systemPrompt: "ordinary root" }, {});
  // Child defense through the REAL registered handler: run the actual factory
  // under the child marker and invoke the hook it installed, never the bare
  // admission function.
  process.env.PI_SUBAGENT_CHILD = "1";
  const childCalls = [];
  const childHandlers = {};
  try {
    await factory({ ...base, registerTool(t) { childCalls.push(t); }, on(e, h) { childHandlers[e] = h; } });
    const hook = (childHandlers.tool_call ?? childHandlers["tool_call"]);
    out.childFactory = childCalls.map((t) => t.name);
    out.childHasGuard = typeof hook === "function";
    if (typeof hook !== "function") {
      out.childHandler = "no-hook";
      out.childOther = "no-hook";
    } else {
      const invoke = async (toolName, input) => {
        const event = { type: "tool_call", toolCallId: "probe", toolName, input };
        const verdict = await hook(event, {});
        if (!verdict) return "pass";
        return "block:" + String(verdict.reason ?? "");
      };
      out.childHandler = await invoke("subagent", { ...leafBase });
      out.childOther = await invoke("read", {});
    }
  } finally {
    delete process.env.PI_SUBAGENT_CHILD;
  }
  out.ok = true;
} catch (error) {
  out.ok = false;
  out.error = String(error?.stack ?? error);
}
if (savedChild === undefined) delete process.env.PI_SUBAGENT_CHILD;
else process.env.PI_SUBAGENT_CHILD = savedChild;
console.log(JSON.stringify(out));
"""

LOADER_DRIVER = r"""
import { mkdtempSync, mkdirSync, writeFileSync, copyFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const PI = process.argv[1];
const ADAPTER = process.argv[2];
const PARITY = process.argv[3];
const SETTINGS_SRC = process.argv[4];
const out = {};
const savedChild = process.env.PI_SUBAGENT_CHILD;
delete process.env.PI_SUBAGENT_CHILD;
const finish = (payload) => {
  if (savedChild === undefined) delete process.env.PI_SUBAGENT_CHILD;
  else process.env.PI_SUBAGENT_CHILD = savedChild;
  process.stdout.write(JSON.stringify(payload) + "\n", () => process.exit(0));
};
try {
  const loader = await import(PI + "/dist/core/extensions/loader.js");
  const { createEventBus } = await import(PI + "/dist/core/event-bus.js");
  if (typeof createEventBus !== "function") {
    throw new Error("subagent-contract probe: event-bus.js exports no createEventBus");
  }
  const cwd = mkdtempSync(join(tmpdir(), "pi-contract-loader-"));
  const loaded = await loader.loadExtensions([PARITY, ADAPTER], cwd, createEventBus());
  const tools = loaded.extensions.flatMap((e) => [...e.tools.values()]);
  const subagents = tools.filter((t) => t.definition.name === "subagent");
  const sub = subagents[0]?.definition;
  let handlerKinds = 0;
  for (const e of loaded.extensions) handlerKinds += e.handlers.size;
  const branches = Array.isArray(sub?.parameters?.anyOf) ? sub.parameters.anyOf : [];
  out.loader = {
    errors: loaded.errors,
    subagentCount: subagents.length,
    bgWait: tools.some((t) => t.definition.name === "bg_wait"),
    handlerKinds,
    hasSnippet: sub ? ("promptSnippet" in sub) : null,
    description: sub?.description ?? null,
    rootType: sub?.parameters?.type ?? null,
    rootAdditional: sub?.parameters?.additionalProperties ?? null,
    branchCount: branches.length,
    leafRequired: branches[0]?.required ?? null,
    mgmtRequired: branches[1]?.required ?? null,
    leafProps: branches[0] ? Object.keys(branches[0].properties ?? {}) : null,
    mgmtProps: branches[1] ? Object.keys(branches[1].properties ?? {}) : null,
    rootProps: sub ? Object.keys(sub.parameters.properties ?? {}) : null,
  };
  // Child defense through the real loader: load the adapter under the child
  // marker, confirm no subagent tool is published, and invoke the registered
  // tool_call handler with a valid leaf shape.
  process.env.PI_SUBAGENT_CHILD = "1";
  const childLoaded = await loader.loadExtensions([ADAPTER], cwd, createEventBus());
  const childTools = childLoaded.extensions.flatMap((e) => [...e.tools.keys()]);
  const childExt = childLoaded.extensions.find((e) => String(e.path ?? "").includes("subagent-contract"));
  const childHooks = childExt ? (childExt.handlers.get("tool_call") ?? []) : [];
  let childVerdict = "no-hook";
  for (const hook of childHooks) {
    const verdict = await hook({ type: "tool_call", toolCallId: "probe", toolName: "subagent", input: { agent: "k-agent-reviewer", task: "packet", agentScope: "user", acceptance: false } }, {});
    if (verdict) { childVerdict = "block:" + String(verdict.reason ?? ""); break; }
    childVerdict = "pass";
  }
  out.childTools = childTools;
  out.childErrors = childLoaded.errors;
  out.childHasGuard = childHooks.length > 0;
  out.childHandler = childVerdict;
  delete process.env.PI_SUBAGENT_CHILD;
  const pm = await import(PI + "/dist/core/package-manager.js");
  const sm = await import(PI + "/dist/core/settings-manager.js");
  const agentDir = mkdtempSync(join(tmpdir(), "pi-contract-agentdir-"));
  mkdirSync(join(agentDir, "extensions"), { recursive: true });
  writeFileSync(join(agentDir, "settings.json"), readFileSync(SETTINGS_SRC, "utf8"));
  copyFileSync(ADAPTER, join(agentDir, "extensions", "subagent-contract.ts"));
  const settings = sm.SettingsManager.create(cwd, agentDir);
  const manager = new pm.DefaultPackageManager({ cwd, agentDir, settingsManager: settings });
  const resolved = await manager.resolve();
  const rel = (p) => String(p).replace(process.env.HOME ?? "", "~");
  out.resolve = {
    extensions: resolved.extensions.map((e) => ({ path: rel(e.path), enabled: e.enabled })),
    skills: resolved.skills.map((e) => ({ path: rel(e.path), enabled: e.enabled })),
    prompts: resolved.prompts.map((e) => ({ path: rel(e.path), enabled: e.enabled })),
  };
  out.ok = true;
} catch (error) {
  out.ok = false;
  out.error = String(error?.stack ?? error);
}
finish(out);
"""


class TestPiSubagentContractSource(unittest.TestCase):
    """Source ownership: one adapter, filtered package, no second policy."""

    def test_settings_filter_pi_subagents_resources_on_both_profiles(self):
        for profile, path in SETTINGS.items():
            with self.subTest(profile=profile):
                settings = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    settings["packages"],
                    [
                        "~/.local/share/pnpm-global-links/node_modules/pi-mcp-adapter",
                        {
                            "source": PI_SUBAGENTS_SOURCE,
                            "extensions": [],
                            "skills": [],
                            "prompts": [],
                        },
                        "~/.local/share/pnpm-global-links/node_modules/@rahularya01/pi-cursor",
                    ],
                )
                self.assertTrue(settings["subagents"]["disableBuiltins"])
                self.assertFalse(settings["subagents"]["asyncByDefault"])
                self.assertEqual(settings["subagents"]["defaultSubagentContext"], "fresh")

    def test_runtime_parity_no_longer_owns_dispatch(self):
        text = RUNTIME_PARITY.read_text(encoding="utf-8")
        self.assertNotIn("DISPATCH_RULE", text)
        self.assertNotIn("subagent", text)
        self.assertIn("enableSearchTools", text)
        self.assertIn("AGENTS.md", text)

    def test_adapter_source_single_policy_owner(self):
        text = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("INVALID_DISPATCH_REQUEST", text)
        self.assertIn("projectSubagentTool", text)
        self.assertIn("admissionFor", text)
        self.assertIn("validateToolArguments", text)
        self.assertIn("ToolDefinition", text)
        self.assertIn("anyOf", text)
        self.assertIn('PI_SUBAGENT_CHILD === "1"', text)
        # Both rejection classes are taught where the contract lives.
        self.assertIn(NATIVE_VALIDATION_PREFIX, text)
        # No suppressed typing: precise native/TSchema types only.
        for suppressed in ("as never", "as any", "Record<string, unknown>"):
            self.assertNotIn(suppressed, text, f"adapter must not suppress typing with {suppressed!r}")
        for token in (
            "workflowScript",
            "exactly one top-level",
        ):
            self.assertNotIn(token, text)


class TestPiSubagentContractNative(unittest.TestCase):
    """Native loader/schema/guard behavior via inert probes (no model calls)."""

    @classmethod
    def setUpClass(cls):
        cls.pi_dir = _pi_package_dir()
        cls.ps_entry = _pi_subagents_entry()
        if cls.pi_dir is not None and cls.ps_entry is not None:
            return
        # The work profile names the pi-subagents package as a filtered source, so an
        # absent checkout is a broken contract, not a skippable environment gap. Skip
        # only when the settings stop naming it.
        named = any(
            PI_SUBAGENTS_SOURCE in path.read_text(encoding="utf-8") for path in SETTINGS.values() if path.is_file()
        )
        if not named:
            raise unittest.SkipTest("settings do not name pi-subagents; cannot run native-loader probes")
        absent = sorted(
            label
            for label, value in (("Pi package", cls.pi_dir), ("pi-subagents checkout", cls.ps_entry))
            if value is None
        )
        raise AssertionError(
            f"settings name {PI_SUBAGENTS_SOURCE} but {' and '.join(absent)} absent; fix the checkout, not the skip"
        )

    def test_adapter_projection_and_contract_table(self):
        payload = _run_node(CONTRACT_DRIVER, str(self.pi_dir), str(ADAPTER), str(self.ps_entry))
        self.assertTrue(payload.get("ok"), payload.get("error"))
        self.assertTrue(payload["native"]["seen"])
        self.assertEqual(payload["native"]["propCount"], 82)
        # Projection keeps THAT captured native tool's callbacks by identity.
        projection = payload["projection"]
        self.assertFalse(projection["hasSnippet"])
        self.assertFalse(projection["hasGuidelines"])
        identity = projection["identity"]
        for callback in ("execute", "renderCall", "renderResult"):
            self.assertTrue(identity[callback], f"native {callback} must pass through by identity")
        self.assertTrue(identity["label"])
        for token in FORBIDDEN_ADVERTISEMENT_TOKENS:
            self.assertNotIn(token, projection["description"], f"projected description advertises {token!r}")
        # The decorated factory publishes exactly one narrowed registration and
        # passes native lifecycle registrations through.
        factory = payload["factory"]
        # Watchdog notices: the real upstream formatter advertises steer/resume; the
        # adapter's sendMessage seam must strip both and keep status/interrupt/facts.
        notice = payload["notice"]
        self.assertEqual(notice["noticeType"], "subagent_control_notice")
        self.assertTrue(notice["upstreamHasSteer"] and notice["upstreamHasResume"], notice)
        self.assertFalse(notice["rewrittenHasSteer"], notice)
        self.assertFalse(notice["rewrittenHasResume"], notice)
        for key in (
            "keepsStatus",
            "keepsInterrupt",
            "keepsSignal",
            "keepsIntercom",
            "hintPresent",
            "hintBeforeStatus",
            "unrelatedUntouched",
        ):
            self.assertTrue(notice[key], (key, notice))
        # needs_attention branch: upstream advertises the same steer/resume nudges; the adapter
        # strips them, adds the status/interrupt hint, and keeps the signal and status lines.
        self.assertTrue(notice["failedUpstreamHasSteer"], notice)
        self.assertFalse(notice["failedRewrittenHasSteerOrResume"], notice)
        for key in ("failedHintPresent", "failedKeepsSignal", "failedKeepsStatus"):
            self.assertTrue(notice[key], (key, notice))
        self.assertEqual(factory["subagentCount"], 1)
        self.assertGreaterEqual(factory["toolCount"], 2)
        self.assertTrue(factory["bgWait"])
        self.assertTrue(factory["hasToolCallGuard"])
        self.assertTrue(factory["hasPromptNote"])
        for event in ("tool_call", "before_agent_start", "agent_end"):
            self.assertIn(event, factory["handlerEvents"], f"factory must register {event}")
        self.assertFalse(factory["hasSnippet"])
        self.assertFalse(factory["hasGuidelines"])
        # Root object schema with closed conditional variants, checked against
        # the independent key sets above, never against the adapter itself.
        contract = payload["contract"]
        for token in FORBIDDEN_ADVERTISEMENT_TOKENS:
            self.assertNotIn(token, contract["description"], f"registered description advertises {token!r}")
            self.assertNotIn(token, contract["publishedSchema"], f"parameter metadata advertises {token!r}")
        self.assertEqual(contract["rootType"], "object")
        self.assertFalse(contract["rootAdditional"])
        self.assertEqual(contract["branchCount"], 2)
        self.assertEqual(set(contract["leafRequired"]), EXPECTED_LEAF_REQUIRED)
        self.assertEqual(set(contract["mgmtRequired"]), EXPECTED_MGMT_REQUIRED)
        self.assertEqual(set(contract["leafProps"]), EXPECTED_LEAF_KEYS)
        self.assertEqual(set(contract["mgmtProps"]), EXPECTED_MGMT_KEYS)
        self.assertEqual(set(contract["rootProps"]), EXPECTED_LEAF_KEYS | EXPECTED_MGMT_KEYS)
        self.assertTrue(set(contract["rootProps"]).isdisjoint(FORBIDDEN_SCHEMA_KEYS))
        cases = payload["cases"]
        allowed = (
            "leaf-full",
            "leaf-minimal",
            "leaf-no-task",
            "leaf-output-routing",
            "leaf-control",
            "leaf-metadata",
            "mgmt-list",
            "mgmt-list-scope",
            "mgmt-list-bare",
            "mgmt-status",
            "mgmt-status-view",
            "mgmt-debug",
            "mgmt-stop",
            "mgmt-stop-id",
            "mgmt-interrupt",
        )
        for name in allowed:
            with self.subTest(case=name):
                self.assertEqual(cases[name]["schema"], "ok", cases[name])
                self.assertEqual(cases[name]["guard"], "pass", cases[name])
        for name, case in cases.items():
            if name in allowed:
                continue
            with self.subTest(case=name):
                # One contract: the native validator and the guard agree on
                # every denied shape, including malformed field types and
                # empty/mixed calls.
                self.assertTrue(case["schema"].startswith("reject"), case)
                self.assertTrue(case["schema"].startswith(f"reject:{NATIVE_VALIDATION_PREFIX}"), case)
                self.assertTrue(case["guard"].startswith(f"block:{GUARD_CLASS_TOKEN}"), case)
                self.assertIn(NATIVE_VALIDATION_PREFIX, case["guard"], case)
        # Both error classes are taught as invalid invocation with the
        # once-only executed-error retry rule.
        note = payload["note"]
        self.assertIn(GUARD_CLASS_TOKEN, note["systemPrompt"])
        self.assertIn(NATIVE_VALIDATION_PREFIX, note["systemPrompt"])
        self.assertIn("once only", note["systemPrompt"])
        # Child defense comes from the real registered factory handler.
        self.assertEqual(payload["childFactory"], [])
        self.assertTrue(payload["childHasGuard"])
        self.assertTrue(payload["childHandler"].startswith(f"block:{GUARD_CLASS_TOKEN}"), payload["childHandler"])
        self.assertEqual(payload["childOther"], "pass")

    def test_real_loader_single_registration_and_child_inert(self):
        payload = _run_node(LOADER_DRIVER, str(self.pi_dir), str(ADAPTER), str(RUNTIME_PARITY), str(SETTINGS["work"]))
        self.assertTrue(payload.get("ok"), payload.get("error"))
        loader = payload["loader"]
        self.assertEqual(loader["errors"], [])
        self.assertEqual(loader["subagentCount"], 1)
        self.assertTrue(loader["bgWait"])
        self.assertGreaterEqual(loader["handlerKinds"], 14)
        self.assertFalse(loader["hasSnippet"])
        for token in FORBIDDEN_ADVERTISEMENT_TOKENS:
            self.assertNotIn(token, loader["description"] or "", f"registered description advertises {token!r}")
        self.assertEqual(loader["rootType"], "object")
        self.assertFalse(loader["rootAdditional"])
        self.assertEqual(loader["branchCount"], 2)
        self.assertEqual(set(loader["leafRequired"]), EXPECTED_LEAF_REQUIRED)
        self.assertEqual(set(loader["mgmtRequired"]), EXPECTED_MGMT_REQUIRED)
        self.assertEqual(set(loader["leafProps"]), EXPECTED_LEAF_KEYS)
        self.assertEqual(set(loader["mgmtProps"]), EXPECTED_MGMT_KEYS)
        self.assertEqual(set(loader["rootProps"]), EXPECTED_LEAF_KEYS | EXPECTED_MGMT_KEYS)
        self.assertTrue(set(loader["rootProps"]).isdisjoint(FORBIDDEN_SCHEMA_KEYS))
        self.assertNotIn("subagent", payload["childTools"])
        self.assertEqual(payload["childErrors"], [])
        self.assertTrue(payload["childHasGuard"])
        self.assertTrue(payload["childHandler"].startswith(f"block:{GUARD_CLASS_TOKEN}"), payload["childHandler"])
        resolve = payload["resolve"]
        pi_entries = [e for e in resolve["extensions"] if "pi-subagents" in e["path"]]
        self.assertTrue(pi_entries)
        for entry in pi_entries:
            with self.subTest(entry=entry["path"]):
                self.assertFalse(entry["enabled"])
        # The package ships two skills (pi-subagents: "scripted chaining"; council-mode) whose
        # text advertises workflow shapes the contract rejects. The filter must REACH them:
        # both must be enumerated by the real resolver and both must be disabled. An empty
        # enumeration would make this loop pass while the skills load in a fresh session.
        package_skills = {
            entry["path"].rsplit("/skills/", 1)[-1].split("/", 1)[0]: entry["enabled"]
            for entry in resolve["skills"]
            if "pi-subagents" in entry["path"]
        }
        self.assertEqual({"pi-subagents": False, "council-mode": False}, package_skills, resolve["skills"])
        for entry in resolve["prompts"]:
            if "pi-subagents" in entry["path"]:
                with self.subTest(entry=entry["path"]):
                    self.assertFalse(entry["enabled"])
        adapter_entries = [e for e in resolve["extensions"] if e["path"].endswith("subagent-contract.ts")]
        self.assertEqual(len(adapter_entries), 1)
        self.assertTrue(adapter_entries[0]["enabled"])
        for package in ("pi-mcp-adapter", "pi-cursor"):
            with self.subTest(package=package):
                package_entries = [e for e in resolve["extensions"] if package in e["path"]]
                self.assertTrue(package_entries)
                self.assertTrue(all(e["enabled"] for e in package_entries))


if __name__ == "__main__":
    unittest.main()
