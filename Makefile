.DEFAULT_GOAL := help

.PHONY: help fmt lint test check verify-templates verify-mermaids docs docs-build docs-serve docs-clean

help: ## Show available targets
	@grep -E '^[a-z][a-z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

fmt: ## Format all files
	bin/fmt

lint: ## Check formatting and lint (no writes)
	bin/fmt --check
	ruff check --select I scripts/
	(cd tools/ralph-tui && go vet ./... && go test ./...)

verify-templates: ## Render every chezmoi template to catch breakage before apply
	python3 scripts/verify_templates.py

verify-mermaids: ## Check .mermaids/ file-census counts against git ls-files
	python3 scripts/verify_mermaids.py

test: ## Run Python unit tests
	python3 scripts/tests/test_scripts.py -v
	python3 scripts/tests/test_blackboard.py -v
	python3 home/exact_bin/utils/exact_history/executable_fish-history-merge.test.py -v

check: lint verify-templates verify-mermaids test ## Run all checks (lint + templates + mermaids + test)

website/node_modules: website/package.json website/pnpm-lock.yaml
	cd website && pnpm install --frozen-lockfile
	@touch $@

docs: website/node_modules ## Start the docs dev server (hot-reload at http://localhost:3000/dotfiles/)
	cd website && pnpm start

docs-build: website/node_modules ## Build the production docs site into website/build/
	cd website && pnpm build

docs-serve: website/node_modules ## Serve the built docs/ statically (matches GitHub Pages output)
	cd website && pnpm serve

docs-clean: ## Clear the Docusaurus cache (.docusaurus/)
	cd website && pnpm clear
