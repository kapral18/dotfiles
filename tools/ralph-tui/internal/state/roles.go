package state

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
)

// RoleSpec is the harness/model pair for a single Ralph role. It
// mirrors the per-role entry in ~/.config/ralph/roles.json. The
// role's `extra_args` (e.g. `--mode plan`) live in roles.json and
// are not exposed in the dashboard — see HarnessChoices in
// internal/forms/forms.go for the rationale.
type RoleSpec struct {
	Harness string
	Model   string
}

// RolesDefaults is what the New-Run form pre-fills as "good defaults" — the
// user's own roles.json on disk.
type RolesDefaults struct {
	Planner    RoleSpec
	Executor   RoleSpec
	Reviewer   RoleSpec
	ReReviewer RoleSpec
	// Path is the source file the defaults were read from (for debugging).
	Path string
}

// RolesConfigPath resolves the path roles.json is read from, mirroring
// scripts/ralph.py's resolution order.
func RolesConfigPath() string {
	if v := os.Getenv("RALPH_ROLES_CONFIG"); v != "" {
		return v
	}
	if home, err := os.UserHomeDir(); err == nil {
		return filepath.Join(home, ".config", "ralph", "roles.json")
	}
	return ""
}

// LoadRolesDefaults reads roles.json and returns the per-role harness/model
// defaults. Missing file returns ErrNoDefaults; the caller should fall back
// to the generated mirror (see GeneratedFallback) so the form is always usable.
func LoadRolesDefaults() (RolesDefaults, error) {
	path := RolesConfigPath()
	if path == "" {
		return GeneratedFallback(), ErrNoDefaults
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return GeneratedFallback(), ErrNoDefaults
		}
		return GeneratedFallback(), fmt.Errorf("read %s: %w", path, err)
	}
	var probe struct {
		Roles map[string]struct {
			Harness string `json:"harness"`
			Model   string `json:"model"`
		} `json:"roles"`
	}
	if err := json.Unmarshal(raw, &probe); err != nil {
		return GeneratedFallback(), fmt.Errorf("parse %s: %w", path, err)
	}
	d := GeneratedFallback()
	d.Path = path
	if r, ok := probe.Roles["planner"]; ok {
		d.Planner = RoleSpec{Harness: nonEmpty(r.Harness, d.Planner.Harness), Model: nonEmpty(r.Model, d.Planner.Model)}
	}
	if r, ok := probe.Roles["executor"]; ok {
		d.Executor = RoleSpec{Harness: nonEmpty(r.Harness, d.Executor.Harness), Model: nonEmpty(r.Model, d.Executor.Model)}
	}
	if r, ok := probe.Roles["reviewer"]; ok {
		d.Reviewer = RoleSpec{Harness: nonEmpty(r.Harness, d.Reviewer.Harness), Model: nonEmpty(r.Model, d.Reviewer.Model)}
	}
	if r, ok := probe.Roles["re_reviewer"]; ok {
		d.ReReviewer = RoleSpec{Harness: nonEmpty(r.Harness, d.ReReviewer.Harness), Model: nonEmpty(r.Model, d.ReReviewer.Model)}
	}
	return d, nil
}

// GeneratedFallback returns the generated mirror of the chezmoi-deployed
// roles.json defaults, so a missing runtime file cannot leave a stale duplicate.
func GeneratedFallback() RolesDefaults {
	return RolesDefaults{
		Planner:    generatedRalphRoleDefaults["planner"],
		Executor:   generatedRalphRoleDefaults["executor"],
		Reviewer:   generatedRalphRoleDefaults["reviewer"],
		ReReviewer: generatedRalphRoleDefaults["re_reviewer"],
	}
}

// ErrNoDefaults signals the caller fell back to GeneratedFallback because
// no roles.json was readable. Not actually an error — the form should still
// open with sane defaults.
var ErrNoDefaults = errors.New("roles.json not found; using generated defaults")

func nonEmpty(s, fallback string) string {
	if s == "" {
		return fallback
	}
	return s
}
