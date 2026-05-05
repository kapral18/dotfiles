package state

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadRolesDefaultsReadsRolesJson(t *testing.T) {
	dir := t.TempDir()
	cfg := filepath.Join(dir, "roles.json")
	os.WriteFile(cfg, []byte(`{
		"roles": {
			"planner":     {"harness": "pi",     "model": "p-mod"},
			"executor":    {"harness": "cursor", "model": "e-mod"},
			"reviewer":    {"harness": "cursor", "model": "r-mod"},
			"re_reviewer": {"harness": "cursor", "model": "rr-mod"}
		}
	}`), 0o644)
	t.Setenv("RALPH_ROLES_CONFIG", cfg)

	d, err := LoadRolesDefaults()
	if err != nil {
		t.Fatalf("LoadRolesDefaults: %v", err)
	}
	if d.Planner.Harness != "pi" || d.Planner.Model != "p-mod" {
		t.Errorf("planner: %+v", d.Planner)
	}
	if d.Executor.Model != "e-mod" {
		t.Errorf("executor: %+v", d.Executor)
	}
	if d.Reviewer.Model != "r-mod" {
		t.Errorf("reviewer: %+v", d.Reviewer)
	}
	if d.ReReviewer.Model != "rr-mod" {
		t.Errorf("re_reviewer: %+v", d.ReReviewer)
	}
	if d.Path != cfg {
		t.Errorf("Path: %q want %q", d.Path, cfg)
	}
}

func TestLoadRolesDefaultsFallsBackWhenMissing(t *testing.T) {
	t.Setenv("RALPH_ROLES_CONFIG", filepath.Join(t.TempDir(), "absent.json"))

	d, err := LoadRolesDefaults()
	if err != ErrNoDefaults {
		t.Errorf("err: %v want ErrNoDefaults", err)
	}
	if d.Planner.Model == "" || d.ReReviewer.Model == "" {
		t.Errorf("hardcoded fallback empty: %+v", d)
	}
	// Diversity gate is enforced server-side; here we only assert the
	// fallback is non-empty and stable. Reviewer & re_reviewer fallbacks are
	// from different families (claude vs gpt) so the gate passes by default.
	if d.Reviewer.Model == d.ReReviewer.Model {
		t.Errorf("reviewer/re_reviewer fallbacks must differ: %s == %s", d.Reviewer.Model, d.ReReviewer.Model)
	}
}

func TestLoadRolesDefaultsPartialFileFillsHoles(t *testing.T) {
	dir := t.TempDir()
	cfg := filepath.Join(dir, "roles.json")
	// Only override planner; executor/reviewer/re_reviewer should fall back.
	os.WriteFile(cfg, []byte(`{"roles": {"planner": {"harness": "pi", "model": "p-mod"}}}`), 0o644)
	t.Setenv("RALPH_ROLES_CONFIG", cfg)

	d, err := LoadRolesDefaults()
	if err != nil {
		t.Fatalf("LoadRolesDefaults: %v", err)
	}
	if d.Planner.Harness != "pi" {
		t.Errorf("planner harness override missed: %+v", d.Planner)
	}
	if d.Executor.Model == "" {
		t.Errorf("executor fallback dropped: %+v", d.Executor)
	}
}

