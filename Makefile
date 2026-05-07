.DEFAULT_GOAL := help

.PHONY: help fmt lint test check docs docs-build docs-serve docs-clean

help: ## Show available targets
	@grep -E '^[a-z][a-z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

fmt: ## Format all files
	bin/fmt

lint: ## Check formatting and lint (no writes)
	bin/fmt --check
	ruff check --select I scripts/

test: ## Run Python unit tests
	python3 scripts/tests/test_scripts.py -v

check: lint test ## Run all checks (lint + test)

website/node_modules: website/package.json website/pnpm-lock.yaml
	pnpm -C website install --frozen-lockfile
	@touch $@

docs: website/node_modules ## Start the docs dev server (hot-reload at http://localhost:3000/dotfiles/)
	pnpm -C website start

docs-build: website/node_modules ## Build the production docs site into website/build/
	pnpm -C website build

docs-serve: website/node_modules ## Serve the built docs/ statically (matches GitHub Pages output)
	pnpm -C website serve

docs-clean: ## Clear the Docusaurus cache (.docusaurus/)
	pnpm -C website clear
