package state

// AvailableModels returns the curated list of model IDs the New-Run
// form exposes for the given harness. The lists reflect the user's
// stated preferences (Gemini, gpt-5.5, gpt-5.3, opus 4.8 xhigh-only, composer-2.5
// — routed via cursor-agent for `cursor`, via litellm-gateway /
// openrouter for `pi`).
//
// Source of truth:
//   - cursor: cursor-agent --list-models (filtered to the families
//     above; pinned to a snapshot so the TUI never blocks on a slow
//     CLI call).
//   - pi: home/.chezmoidata/ai_models.yaml `litellm_models[*].id` plus
//     a small parallel openrouter slug list for the same model
//     families.
//
// Other harness names (notably `command`, which the runtime supports
// for tests + scripting but the dashboard intentionally hides) return
// nil; callers in the form must defensively render them as "(no
// models)" because the dashboard's HarnessChoices does not surface
// them. See internal/forms/forms.go HarnessChoices for rationale.
func AvailableModels(harness string) []string {
	switch harness {
	case "cursor":
		return cursorModels
	case "pi":
		return piModels
	default:
		return nil
	}
}

// IndexOfModel finds `id` in `list` and returns its index, or 0 if absent.
// Use to seed the picker from the user's roles.json defaults.
func IndexOfModel(list []string, id string) int {
	for i, m := range list {
		if m == id {
			return i
		}
	}
	return 0
}

// cursorModels mirrors the user's curated set from `cursor-agent --list-models`,
// kept stable so the picker stays predictable across cursor-agent updates.
var cursorModels = []string{
	"composer-2.5",
	"composer-2.5-fast",
	"claude-opus-4-8-xhigh",
	"claude-opus-4-8-xhigh-fast",
	"claude-opus-4-8-thinking-xhigh",
	"claude-opus-4-8-thinking-xhigh-fast",
	"gpt-5.5-high",
	"gpt-5.5-high-fast",
	"gpt-5.5-none",
	"gpt-5.5-none-fast",
	"gpt-5.5-low",
	"gpt-5.5-low-fast",
	"gpt-5.5-medium",
	"gpt-5.5-medium-fast",
	"gpt-5.5-extra-high",
	"gpt-5.5-extra-high-fast",
	"gpt-5.3-codex-low",
	"gpt-5.3-codex-low-fast",
	"gpt-5.3-codex",
	"gpt-5.3-codex-fast",
	"gpt-5.3-codex-high",
	"gpt-5.3-codex-high-fast",
	"gpt-5.3-codex-xhigh",
	"gpt-5.3-codex-xhigh-fast",
	"gemini-3.1-pro",
	"gemini-3.5-flash",
}

// piModels combines the litellm-gateway IDs from
// home/.chezmoidata/ai_models.yaml with parallel openrouter slugs covering the
// same families. Pi accepts both prefixes; the gateway list is what the user's
// litellm proxy actually serves locally.
var piModels = []string{
	// litellm-gateway (authoritative, deployed via chezmoi):
	"llm-gateway/gemini-3.1-pro-preview",
	"llm-gateway/gemini-3.1-pro-preview-customtools",
	"llm-gateway/claude-haiku-4-5",
	"llm-gateway/Kimi-K2.6",
	"llm-gateway/gpt-5.5",
	"llm-gateway/claude-opus-4-8",
	"llm-gateway/claude-sonnet-5",
	"llm-gateway/claude-fable-5",
	"llm-gateway/claude-opus-4-7",
	"llm-gateway/gemini-3.5-flash",
	// openrouter (same families, routed via openrouter for fallback / cost):
	"openrouter/anthropic/claude-opus-4.7-thinking",
	"openrouter/anthropic/claude-opus-4.7",
	"openrouter/openai/gpt-5.5",
	"openrouter/openai/gpt-5.3-codex",
	"openrouter/google/gemini-3.1-pro-preview-customtools",
	"openrouter/google/gemini-3.5-flash",
}
