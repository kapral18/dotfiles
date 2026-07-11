package state

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
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
		t.Errorf("generated fallback empty: %+v", d)
	}
	// Diversity gate is enforced server-side; here we only assert the
	// fallback is non-empty and stable. Reviewer & re_reviewer fallbacks are
	// from different families (claude vs gpt) so the gate passes by default.
	if d.Reviewer.Model == d.ReReviewer.Model {
		t.Errorf("reviewer/re_reviewer fallbacks must differ: %s == %s", d.Reviewer.Model, d.ReReviewer.Model)
	}
}

func TestGeneratedFallbackMatchesManagedRolesConfig(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "..", "..", "..", "home", "dot_config", "ralph", "roles.json"))
	if err != nil {
		t.Fatalf("read managed roles.json: %v", err)
	}
	var managed struct {
		Roles map[string]RoleSpec `json:"roles"`
	}
	if err := json.Unmarshal(raw, &managed); err != nil {
		t.Fatalf("parse managed roles.json: %v", err)
	}
	fallback := GeneratedFallback()
	want := map[string]RoleSpec{
		"planner":     fallback.Planner,
		"executor":    fallback.Executor,
		"reviewer":    fallback.Reviewer,
		"re_reviewer": fallback.ReReviewer,
	}
	for role, got := range want {
		if got != managed.Roles[role] {
			t.Errorf("%s fallback=%+v managed=%+v", role, got, managed.Roles[role])
		}
	}
}

func TestGeneratedModelRecommendationsMatchManagedMirror(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "..", "..", "..", "home", "dot_config", "ai", "readonly_model-mirrors.v1.json"))
	if err != nil {
		t.Fatalf("read managed model mirror: %v", err)
	}
	var mirror struct {
		SchemaVersion string `json:"schema_version"`
		Harnesses     map[string]struct {
			Recommended struct {
				Models []string `json:"models"`
			} `json:"recommended"`
		} `json:"harnesses"`
	}
	if err := json.Unmarshal(raw, &mirror); err != nil {
		t.Fatalf("parse managed model mirror: %v", err)
	}
	if mirror.SchemaVersion != generatedModelMirrorSchemaVersion {
		t.Fatalf("schema version generated=%q mirror=%q", generatedModelMirrorSchemaVersion, mirror.SchemaVersion)
	}
	for _, harness := range []string{"cursor", "pi"} {
		got := AvailableModels(harness)
		want := mirror.Harnesses[harness].Recommended.Models
		if !reflect.DeepEqual(got, want) {
			t.Errorf("%s recommendations generated=%v mirror=%v", harness, got, want)
		}
		if len(got) > 0 {
			got[0] = "mutated"
			if AvailableModels(harness)[0] == "mutated" {
				t.Errorf("%s AvailableModels returned mutable generated storage", harness)
			}
		}
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
