.DEFAULT_GOAL := help

.PHONY: help fmt lint test check check-full verify-templates verify-bin-surface verify-agent-file-sizes

help: ## Show available targets
	@grep -E '^[a-z][a-z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

fmt: ## Format all files
	bin/fmt

lint: ## Check formatting and lint (no writes)
	bin/fmt --check
	ruff check --select I scripts/ home/exact_lib/

verify-templates: ## Render every chezmoi template to catch breakage before apply
	python3 scripts/verify_templates.py

verify-bin-surface: ## Check ~/bin completions and command-library ownership
	python3 scripts/verify_bin_surface.py

verify-agent-file-sizes: ## Check agent skill/hook markdown stays under the 20KB view limit
	python3 scripts/verify_agent_file_sizes.py

test: ## Run the full Python unit test suite (file-sharded via scripts/test_runner.py)
	python3 scripts/test_runner.py
	python3 home/exact_lib/exact_,history-sync/fish-history-merge.test.py -v

check: ## Affected lint/gates/tests (bin/check)
	bin/check

check-full: ## Human-only full lint/gates/tests (not for agents)
	CHECK_FULL=1 bin/check --full
