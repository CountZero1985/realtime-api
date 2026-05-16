.PHONY: help install test test-unit test-integration test-api test-all \
       test-config test-session test-audit \
       test-transcription test-tts test-realtime test-mcp test-web \
       coverage coverage-html lint format clean

PYTEST = uv run pytest
RUFF = uv run ruff

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ─── Setup ────────────────────────────────────────────────────────────────────

install: ## Install all dependencies
	uv sync --extra all --extra dev

# ─── Test suites ──────────────────────────────────────────────────────────────

test: ## Run all tests (unit + integration)
	$(PYTEST) tests/ -v --ignore=tests/api/test_web_server_schema.py

test-all: ## Run all tests including schema tests (requires schemathesis)
	$(PYTEST) tests/ -v

test-unit: ## Run unit tests only
	$(PYTEST) tests/unit/ -v

test-integration: ## Run integration tests (E2E flows)
	$(PYTEST) tests/integration/ -v

test-api: ## Run API schema tests (requires schemathesis)
	$(PYTEST) tests/api/ -v

# ─── Unit tests by module ─────────────────────────────────────────────────────

test-config: ## Unit: BaseConfig, AudioFormat, VADConfig
	$(PYTEST) tests/unit/test_config.py -v

test-session: ## Unit: BaseSession lifecycle, state machine
	$(PYTEST) tests/unit/test_base_session.py -v

test-audit: ## Unit: SessionAuditLog, AuditEvent
	$(PYTEST) tests/unit/test_audit_log.py -v

test-transcription: ## Unit: Transcription (API + Session + Config)
	$(PYTEST) tests/unit/test_transcription.py tests/unit/test_transcription_session.py tests/unit/test_transcription_config.py -v

test-tts: ## Unit: TTS (base + config + provider + registry)
	$(PYTEST) tests/unit/test_tts_base.py tests/unit/test_tts_config.py tests/unit/test_tts_openai_provider.py tests/unit/test_tts_registry.py tests/unit/test_synthesis.py -v

test-realtime: ## Unit: Realtime (session + config + events + tools)
	$(PYTEST) tests/unit/test_realtime_session.py tests/unit/test_realtime_config.py tests/unit/test_realtime_events.py tests/unit/test_realtime_tools.py -v

test-mcp: ## Unit: MCP (base + manager + plugins)
	$(PYTEST) tests/unit/test_mcp_base.py tests/unit/test_mcp_manager.py tests/unit/test_mcp_plugins.py -v

test-web: ## Unit + root: Web server tests
	$(PYTEST) tests/unit/test_web_server.py tests/test_web_server.py -v

test-examples: ## Unit: CLI interface + agent framework
	$(PYTEST) tests/unit/test_cli_interface.py tests/unit/test_agent_framework.py -v

# ─── Integration tests by scenario ───────────────────────────────────────────

test-e2e: ## Integration: E2E flows (23 tests, 7 test classes)
	$(PYTEST) tests/integration/test_e2e_flows.py -v

test-public-api: ## Integration: Public API surface validation
	$(PYTEST) tests/integration/test_public_api.py -v

# ─── Coverage ─────────────────────────────────────────────────────────────────

coverage: ## Run tests with coverage report (terminal)
	$(PYTEST) tests/ --cov=openai_apis --cov-report=term-missing --ignore=tests/api/test_web_server_schema.py

coverage-html: ## Run tests with HTML coverage report
	$(PYTEST) tests/ --cov=openai_apis --cov-report=html --ignore=tests/api/test_web_server_schema.py
	@echo "Report: htmlcov/index.html"

# ─── Code quality ─────────────────────────────────────────────────────────────

lint: ## Lint with ruff
	$(RUFF) check openai_apis/ examples/ tests/

format: ## Format with ruff
	$(RUFF) format openai_apis/ examples/ tests/

format-check: ## Check formatting (dry-run)
	$(RUFF) format openai_apis/ examples/ tests/ --check

# ─── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf .pytest_cache htmlcov .coverage __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
