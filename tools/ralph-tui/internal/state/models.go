package state

// AvailableModels returns the generated recommended set exposed by the New-Run
// form. The v1 mirror keeps available, curated, and recommended distinct; the
// TUI adapter deliberately consumes only recommended models.
func AvailableModels(harness string) []string {
	models := generatedRecommendedModels[harness]
	if models == nil {
		return nil
	}
	return append([]string(nil), models...)
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
