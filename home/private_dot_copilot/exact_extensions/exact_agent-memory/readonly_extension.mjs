import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const HOOK_TIMEOUT_MS = 10_000;
const SESSION_CONTEXT_HOOK = "session_context.py";
const WORKLOG_RECORDER_HOOK = "worklog_recorder.py";
const EXTENSION_INFO = { source: "user", name: "agent-memory" };

function hookPath(name) {
    return join(process.env.HOME || homedir(), ".agents", "hooks", name);
}

function sessionIdFrom(input, invocation = {}) {
    return String(input?.sessionId || invocation?.sessionId || "");
}

function workspaceRoots(input) {
    return input?.workingDirectory ? [ input.workingDirectory ] : [];
}

export function sessionStartPayload(input, invocation = {}) {
    return {
        hook_event_name: "sessionStart",
        session_id: sessionIdFrom(input, invocation),
        cwd: input?.workingDirectory,
        workspace_roots: workspaceRoots(input),
        source: input?.source,
        initial_prompt: input?.initialPrompt,
    };
}

export function postToolUsePayload(input, invocation = {}, eventName = "postToolUse") {
    const result = input?.toolResult || {};
    return {
        hook_event_name: eventName,
        session_id: sessionIdFrom(input, invocation),
        cwd: input?.workingDirectory,
        workspace_roots: workspaceRoots(input),
        tool_name: input?.toolName,
        tool_input: input?.toolArgs,
        tool_output: result.textResultForLlm || result.sessionLog || "",
        status: result.resultType,
        error_message: result.error,
    };
}

export function postToolUseFailurePayload(input, invocation = {}) {
    return {
        hook_event_name: "postToolUseFailure",
        session_id: sessionIdFrom(input, invocation),
        cwd: input?.workingDirectory,
        workspace_roots: workspaceRoots(input),
        tool_name: input?.toolName,
        tool_input: input?.toolArgs,
        status: "failure",
        error_message: input?.error,
    };
}

export function contextFromHookResult(result) {
    return (
        result?.additionalContext ||
        result?.additional_context ||
        result?.hookSpecificOutput?.additionalContext ||
        ""
    );
}

export function runHookScript(scriptPath, payload, timeoutMs = HOOK_TIMEOUT_MS) {
    return new Promise((resolve, reject) => {
        const child = spawn(scriptPath, [], { stdio: [ "pipe", "pipe", "pipe" ] });
        let stdout = "";
        let stderr = "";
        let settled = false;

        const finish = (fn, value) => {
            if (settled) {
                return;
            }
            settled = true;
            clearTimeout(timer);
            fn(value);
        };

        const timer = setTimeout(() => {
            child.kill("SIGTERM");
            finish(reject, new Error(`${scriptPath} timed out after ${timeoutMs}ms`));
        }, timeoutMs);

        child.stdout.setEncoding("utf8");
        child.stderr.setEncoding("utf8");
        child.stdout.on("data", (chunk) => {
            stdout += chunk;
        });
        child.stderr.on("data", (chunk) => {
            stderr += chunk;
        });
        child.on("error", (error) => finish(reject, error));
        child.on("close", (code) => {
            if (code !== 0) {
                finish(reject, new Error(`${scriptPath} exited ${code}: ${stderr.trim()}`));
                return;
            }
            const text = stdout.trim();
            if (!text) {
                finish(resolve, {});
                return;
            }
            try {
                finish(resolve, JSON.parse(text));
            } catch (error) {
                finish(reject, new Error(`${scriptPath} emitted invalid JSON: ${error.message}`));
            }
        });

        child.stdin.end(JSON.stringify(payload));
    });
}

async function main() {
    const { joinSession } = await import("@github/copilot-sdk/extension");
    await joinSession({
        extensionInfo: EXTENSION_INFO,
        tools: [],
        hooks: {
            onSessionStart: async (input, invocation) => {
                const result = await runHookScript(
                    hookPath(SESSION_CONTEXT_HOOK),
                    sessionStartPayload(input, invocation),
                );
                const additionalContext = contextFromHookResult(result);
                return additionalContext ? { additionalContext } : undefined;
            },
            onPostToolUse: async (input, invocation) => {
                await runHookScript(
                    hookPath(WORKLOG_RECORDER_HOOK),
                    postToolUsePayload(input, invocation),
                );
            },
            onPostToolUseFailure: async (input, invocation) => {
                await runHookScript(
                    hookPath(WORKLOG_RECORDER_HOOK),
                    postToolUseFailurePayload(input, invocation),
                );
            },
        },
    });
}

if (process.env.COPILOT_AGENT_MEMORY_EXTENSION_TEST !== "1") {
    await main();
}
