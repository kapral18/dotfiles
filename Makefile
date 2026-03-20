.DEFAULT_GOAL := help

.PHONY: help fmt lint test check

help: ## Show available targets
	@grep -E '^[a-z][a-z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

fmt: ## Format all files
	bin/fmt

lint: ## Check formatting and lint (no writes)
	bin/fmt --check
	ruff check --select I scripts/

test: ## Run Python unit tests
	python3 scripts/tests/test_scripts.py -v

check: lint test ## Run all checks (lint + test)
