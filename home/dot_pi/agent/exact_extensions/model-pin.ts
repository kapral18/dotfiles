// Managed by chezmoi (source: home/dot_pi/agent/exact_extensions/model-pin.ts).
// Re-pin the routed model after each turn so session resume restores the catalog id.
//
// pi's resume path (core/session-manager.ts getSessionContextSettings) lets every assistant message
// overwrite the restored model with `message.model`, which for anthropic-messages providers is the
// upstream echo from `message_start`, not the catalog id pi routed to. GitHub Copilot echoes
// `claude-fable-5.1` back as `claude-fable-5-1`; `pi -c` then fails the catalog lookup and warns
// "Could not restore model". Upstream: https://github.com/earendil-works/pi/issues/9243.
// Until the read side prefers model_change, append one after any turn whose echo diverges, so the
// last entry on the branch names the real provider/id. Remove once #9243 lands.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"

type ModelChangeAppender = { appendModelChange(provider: string, modelId: string): string }

export default function (pi: ExtensionAPI) {
  pi.on("agent_end", (event, ctx) => {
    const model = ctx.model
    if (!model) return
    const last = [...event.messages].reverse().find((message) => message.role === "assistant")
    if (!last || last.model === model.id) return

    const leaf = ctx.sessionManager.getLeafEntry()
    if (leaf?.type === "model_change" && leaf.provider === model.provider && leaf.modelId === model.id) return

    const appender = ctx.sessionManager as unknown as Partial<ModelChangeAppender>
    if (typeof appender.appendModelChange !== "function") return
    appender.appendModelChange(model.provider, model.id)
  })
}
