.PHONY: init test lint typecheck verify validate validate-dry-run clean setup-github setup-github-checks

.venv:
	uv venv

init: .venv
	uv pip install --python .venv/bin/python -e .
	uv pip install --python .venv/bin/python pytest ruff mypy types-pyyaml

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .

typecheck:
	.venv/bin/mypy harness cli validators integrations verification parsers engine rules schemas skills

verify: lint typecheck test

# Phase 6 — Real Material Validation (local-only, never in CI)
# Usage: make validate CASE=verification/local-data/<case>.local.yaml
validate:
	.venv/bin/python verification/run_real_validation.py $${CASE}

validate-dry-run:
	.venv/bin/python verification/run_real_validation.py --dry-run $${CASE}

setup-github:
	@./scripts/setup-github.sh

# Usage: CHECKS_SHA=<sha> make setup-github-checks
setup-github-checks:
	@CHECKS_SHA="$${CHECKS_SHA}" ENFORCE_CHECKS=1 ./scripts/setup-github.sh

clean:
	rm -rf .venv .mypy_cache .pytest_cache .ruff_cache build dist *.egg-info
