/** Session-local GPT context selection shared by Pi and OMP. */

const ENTRY_TYPE = "gpt-context-mode"
// Astra's standard-price input boundary. For GPT catalogs without tier metadata,
// this is a conservative working budget, not a claim about their billing.
const DEFAULT_SHORT_WINDOW = 272_000
type Mode = "short" | "long"

export interface ContextModel {
  provider: string
  id: string
  contextWindow: number | null
  maxContextWindow?: number | null
  cost?: {
    input?: number | null
    longContext?: { inputThreshold: number } | null
    tiers?: readonly { inputTokensAbove: number }[]
  }
}

interface Entry {
  type: string
  customType?: string
  data?: unknown
}

interface Context<M extends ContextModel> {
  model: M | undefined
  modelRegistry: { find(provider: string, id: string): M | undefined }
  sessionManager: { getBranch(): readonly Entry[] }
  getContextUsage(): { tokens: number | null } | undefined
  isIdle(): boolean
  ui: {
    notify(message: string, type?: "info" | "warning" | "error"): void
    setStatus(key: string, text: string | undefined): void
  }
}

function positive(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0
}

function isGpt(model: ContextModel): boolean {
  return /(?:^|\/)gpt-\d/i.test(model.id)
}

function savedMode(entries: readonly Entry[], model: ContextModel): Mode | undefined {
  for (let index = entries.length - 1; index >= 0; index--) {
    const entry = entries[index]
    if (entry.type !== "custom" || entry.customType !== ENTRY_TYPE) continue
    const data = entry.data
    if (!data || typeof data !== "object") continue
    if (!("provider" in data) || data.provider !== model.provider || !("model" in data) || data.model !== model.id) continue
    if ("mode" in data && (data.mode === "short" || data.mode === "long")) return data.mode
  }
}

/** Changes active model metadata only; native compaction and request sizing own enforcement. */
export function createContextMode<M extends ContextModel>(
  selectModel: (model: M) => Promise<void>,
  appendEntry: (customType: string, data: unknown) => void,
) {
  let applying = false
  const originals = new WeakMap<M, M>()

  function selection(ctx: Context<M>, requested?: Mode) {
    const model = ctx.model
    if (!model || !isGpt(model)) return
    const native = ctx.modelRegistry.find(model.provider, model.id) ?? originals.get(model) ?? model
    const capacity = Math.max(
      positive(native.contextWindow) ? native.contextWindow : 0,
      positive(native.maxContextWindow) ? native.maxContextWindow : 0,
    )
    if (!capacity) return
    const stored = savedMode(ctx.sessionManager.getBranch(), model)
    const mode = requested ?? stored ?? "short"
    const thresholds = [
      native.cost?.longContext?.inputThreshold,
      ...(native.cost?.tiers ?? []).map((tier) => tier.inputTokensAbove),
    ].filter(positive)
    const threshold = thresholds.length ? Math.min(...thresholds) : DEFAULT_SHORT_WINDOW
    const short = Math.min(
      positive(native.contextWindow) ? native.contextWindow : capacity,
      threshold,
    )
    return { model, native, mode, window: mode === "long" ? capacity : short, stored }
  }

  async function apply(ctx: Context<M>, requested?: Mode) {
    if (applying) return
    const selected = selection(ctx, requested)
    if (!selected) {
      ctx.ui.setStatus(ENTRY_TYPE, undefined)
      return
    }
    applying = true
    try {
      if (selected.model.contextWindow !== selected.window) {
        const replacement = { ...selected.model, contextWindow: selected.window }
        originals.set(replacement, selected.native)
        await selectModel(replacement)
      }
      ctx.ui.setStatus(ENTRY_TYPE, `context ${selected.mode} · ${selected.window.toLocaleString("en-US")}`)
    } finally {
      applying = false
    }
    return selected
  }

  async function command(args: string, ctx: Context<M>): Promise<void> {
    const requested = args.trim() || "status"
    if (!["short", "long", "status"].includes(requested)) {
      ctx.ui.notify("Usage: /context-mode short|long|status", "error")
      return
    }
    if (applying || !ctx.isIdle()) {
      ctx.ui.notify("Wait for the active turn or model selection to finish before using /context-mode.", "warning")
      return
    }
    const mode = requested === "short" || requested === "long" ? requested : undefined
    const selected = selection(ctx, mode)
    if (!selected) {
      ctx.ui.notify("Context modes apply only to GPT models with a known window. This model is unchanged.", "info")
      return
    }
    const tokens = ctx.getContextUsage()?.tokens
    if (mode === "short" && tokens != null && tokens >= selected.window) {
      ctx.ui.notify("History exceeds the short window. Use /compact or start a new session, then select short. Mode unchanged.", "warning")
      return
    }
    try {
      await apply(ctx, mode)
      if (mode && mode !== selected.stored) {
        try {
          appendEntry(ENTRY_TYPE, { provider: selected.model.provider, model: selected.model.id, mode })
        } catch (error) {
          ctx.ui.setStatus(ENTRY_TYPE, undefined)
          await selectModel(selected.model)
          throw error
        }
      }
      ctx.ui.notify(
        `${selected.model.provider}/${selected.model.id}: ${selected.mode}, ${selected.window.toLocaleString("en-US")} tokens. Session-local working window, not a hard request or credit cap.`,
        "info",
      )
    } catch (error) {
      ctx.ui.notify(`Context mode was not saved: ${error instanceof Error ? error.message : String(error)}`, "error")
    }
  }

  return { apply, command }
}
