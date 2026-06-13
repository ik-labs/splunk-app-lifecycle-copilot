# Splunk App Lifecycle Copilot — developer convenience targets.
#
# Quick start for judges (no Splunk required):
#   make dashboard      # replay both self-heal loops in the browser
#
# Full local build:
#   make setup          # create the Python 3.13 venv + install
#   make demo           # run the loops end-to-end, print where artifacts landed
#   make test           # Python + dashboard test suites

# Use Python 3.13 specifically — AppInspect's analyzer fails to init on 3.14.
PY ?= python3.13
VENV := .venv

.DEFAULT_GOAL := help

.PHONY: help setup demo demo-appinspect demo-onboarding dashboard test \
        splunk-up splunk-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*## "}{printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Create the venv (Python 3.13) and install the package + dev tools
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e '.[dev]'

demo: ## Run the self-heal loops end-to-end and print where artifacts landed
	./scripts/demo.sh

demo-appinspect: ## Run only the AppInspect loop (no Splunk required)
	./scripts/demo.sh appinspect

demo-onboarding: ## Run only the live onboarding loop (needs Splunk + MCP in .env)
	./scripts/demo.sh onboarding

dashboard: ## Install deps and start the replay dashboard (no Splunk required)
	cd ui/dashboard && bun install && bun run dev

serve: ## Start the live SSE server for the dashboard's "Go Live" mode
	$(VENV)/bin/copilot serve

test: ## Run the Python and dashboard test suites
	$(VENV)/bin/python -m pytest -q
	cd ui/dashboard && bun run test

splunk-up: ## Start the local Splunk container
	docker compose up -d

splunk-down: ## Stop the local Splunk container (keeps volumes)
	docker compose stop
