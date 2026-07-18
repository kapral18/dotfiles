.DEFAULT_GOAL := help

.PHONY: help fmt lint test check verify-templates verify-mermaids verify-bin-surface verify-docs-navigation verify-agent-file-sizes docs docs-build docs-serve docs-clean

help: ## Show available targets
	@grep -E '^[a-z][a-z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

fmt: ## Format all files
	bin/fmt

lint: ## Check formatting and lint (no writes)
	bin/fmt --check
	ruff check --select I scripts/ home/exact_lib/

verify-templates: ## Render every chezmoi template to catch breakage before apply
	python3 scripts/verify_templates.py

verify-mermaids: ## Check .mermaids/ file-census counts against git ls-files
	python3 scripts/verify_mermaids.py

verify-bin-surface: ## Check ~/bin commands have completions, docs, and catalog coverage
	python3 scripts/verify_bin_surface.py

verify-docs-navigation: ## Check docs/reference links and catalog coverage
	python3 scripts/verify_docs_navigation.py

verify-agent-file-sizes: ## Check agent skill/hook markdown stays under the 20KB view limit
	python3 scripts/verify_agent_file_sizes.py

test: ## Run Python unit tests
	PYTHONPATH=scripts python3 -m unittest discover -s scripts -p 'test_*.py' -t scripts
	python3 home/exact_lib/exact_,history-sync/fish-history-merge.test.py -v
	COPILOT_AGENT_MEMORY_EXTENSION_TEST=1 node scripts/tests/copilot_agent_memory_extension.test.mjs

check: lint verify-templates verify-mermaids verify-bin-surface verify-docs-navigation verify-agent-file-sizes test ## Run all checks

website/node_modules: website/package.json website/yarn.lock
	cd website && yarn install --frozen-lockfile
	@touch $@

docs: website/node_modules ## Start the docs dev server (hot-reload at http://localhost:3000/dotfiles/)
	cd website && yarn start

docs-build: website/node_modules ## Build the production docs site into website/build/
	cd website && yarn build

docs-serve: website/node_modules ## Serve the built docs/ statically (matches GitHub Pages output)
	cd website && yarn serve

docs-clean: ## Clear the Docusaurus cache (.docusaurus/)
	cd website && yarn clear
