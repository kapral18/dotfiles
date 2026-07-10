#!/usr/bin/env node
// Regression tests for the pure payload mappers exported by the Copilot
// agent-memory SDK extension. Run with:
//   COPILOT_AGENT_MEMORY_EXTENSION_TEST=1 node scripts/tests/copilot_agent_memory_extension.test.mjs
// The env guard keeps the module from calling joinSession() on import so the
// exported builders can be tested in isolation, without the Copilot SDK.

import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdtempSync, writeFileSync, chmodSync, rmSync } from "node:fs";

process.env.COPILOT_AGENT_MEMORY_EXTENSION_TEST = "1";

const here = dirname(fileURLToPath(import.meta.url));
const extensionPath = join(
    here,
    "..",
    "..",
    "home",
    "private_dot_copilot",
    "exact_extensions",
    "exact_agent-memory",
    "readonly_extension.mjs",
);

const mod = await import(extensionPath);

const tests = [];
function test(name, fn) {
    tests.push([ name, fn ]);
}

test("sessionStartPayload maps SDK camelCase to the shared snake_case contract", () => {
    const payload = mod.sessionStartPayload(
        {
            sessionId: "copilot-session",
            workingDirectory: "/tmp/workspace",
            source: "new",
            initialPrompt: "hello",
        },
        { sessionId: "invocation-session" },
    );
    assert.equal(payload.hook_event_name, "sessionStart");
    assert.equal(payload.session_id, "copilot-session");
    assert.equal(payload.cwd, "/tmp/workspace");
    assert.deepEqual(payload.workspace_roots, [ "/tmp/workspace" ]);
    assert.equal(payload.source, "new");
    assert.equal(payload.initial_prompt, "hello");
});

test("sessionStartPayload falls back to the invocation session id", () => {
    const payload = mod.sessionStartPayload({ workingDirectory: "/tmp/ws" }, { sessionId: "inv" });
    assert.equal(payload.session_id, "inv");
    assert.deepEqual(payload.workspace_roots, [ "/tmp/ws" ]);
});

test("postToolUsePayload maps successful tool results", () => {
    const payload = mod.postToolUsePayload({
        sessionId: "copilot-session",
        workingDirectory: "/tmp/workspace",
        toolName: "bash",
        toolArgs: { command: "printf ok" },
        toolResult: { textResultForLlm: "ok", resultType: "success" },
    });
    assert.equal(payload.hook_event_name, "postToolUse");
    assert.equal(payload.tool_name, "bash");
    assert.deepEqual(payload.tool_input, { command: "printf ok" });
    assert.equal(payload.tool_output, "ok");
    assert.equal(payload.status, "success");
});

test("postToolUseFailurePayload maps failed tool results", () => {
    const payload = mod.postToolUseFailurePayload({
        sessionId: "copilot-session",
        workingDirectory: "/tmp/workspace",
        toolName: "bash",
        toolArgs: { command: "false" },
        error: "exit 1",
    });
    assert.equal(payload.hook_event_name, "postToolUseFailure");
    assert.equal(payload.status, "failure");
    assert.equal(payload.error_message, "exit 1");
});

test("userPromptSubmittedPayload carries UserPromptSubmit, ids, cwd, roots, and prompt", () => {
    const payload = mod.userPromptSubmittedPayload(
        {
            sessionId: "copilot-session",
            workingDirectory: "/tmp/workspace",
            prompt: "recall dedupe for this turn",
        },
        { sessionId: "invocation-session" },
    );
    assert.equal(payload.hook_event_name, "UserPromptSubmit");
    assert.equal(payload.session_id, "copilot-session");
    assert.equal(payload.cwd, "/tmp/workspace");
    assert.deepEqual(payload.workspace_roots, [ "/tmp/workspace" ]);
    assert.equal(payload.prompt, "recall dedupe for this turn");
});

test("userPromptSubmittedPayload falls back to the invocation session id", () => {
    const payload = mod.userPromptSubmittedPayload({ workingDirectory: "/tmp/ws", prompt: "hi" }, { sessionId: "inv" });
    assert.equal(payload.session_id, "inv");
    assert.deepEqual(payload.workspace_roots, [ "/tmp/ws" ]);
});

test("contextFromHookResult reads every additionalContext shape and defaults to empty", () => {
    assert.equal(mod.contextFromHookResult({ additionalContext: "a" }), "a");
    assert.equal(mod.contextFromHookResult({ additional_context: "b" }), "b");
    assert.equal(mod.contextFromHookResult({ hookSpecificOutput: { additionalContext: "c" } }), "c");
    assert.equal(mod.contextFromHookResult({}), "");
});

test("recallContext fails open: a missing per-turn hook returns '' instead of throwing", async () => {
    const missing = join(here, "does-not-exist-perturn-hook.py");
    const context = await mod.recallContext(missing, { prompt: "x" });
    assert.equal(context, "");
});

test("recallContext fails open: a hook that exits nonzero returns ''", async () => {
    const scratch = mkdtempSync(join(here, "recall-fail-"));
    try {
        const stub = join(scratch, "hook.sh");
        writeFileSync(stub, "#!/bin/sh\ncat >/dev/null\nexit 3\n");
        chmodSync(stub, 0o755);
        assert.equal(await mod.recallContext(stub, { prompt: "x" }), "");
    } finally {
        rmSync(scratch, { recursive: true, force: true });
    }
});

test("recallContext surfaces a successful hook's non-empty additionalContext", async () => {
    const scratch = mkdtempSync(join(here, "recall-ok-"));
    try {
        const stub = join(scratch, "hook.sh");
        writeFileSync(stub, "#!/bin/sh\ncat >/dev/null\nprintf '%s' '{\"additionalContext\":\"recalled\"}'\n");
        chmodSync(stub, 0o755);
        assert.equal(await mod.recallContext(stub, { prompt: "x" }), "recalled");
    } finally {
        rmSync(scratch, { recursive: true, force: true });
    }
});

let failures = 0;
for (const [ name, fn ] of tests) {
    try {
        await fn();
        console.log(`ok - ${name}`);
    } catch (error) {
        failures += 1;
        console.error(`not ok - ${name}`);
        console.error(error.stack || String(error));
    }
}

if (failures > 0) {
    console.error(`\n${failures} of ${tests.length} tests failed`);
    process.exit(1);
}
console.log(`\n${tests.length} tests passed`);
