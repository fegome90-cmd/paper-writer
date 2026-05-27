.PHONY: init test lint typecheck verify validate clean

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
	.venv/bin/mypy harness cli validators integrations tests

verify: lint typecheck test

# Phase 6 — Real Material Validation (local-only, never in CI)
# Usage: make validate CASE=verification/local-data/<case>.local.yaml
validate:
	.venv/bin/python verification/run_real_validation.py $${CASE}

validate-dry-run:
	.venv/bin/python verification/run_real_validation.py --dry-run $${CASE}

clean:
	rm -rf .venv .mypy_cache .pytest_cache .ruff_cache build dist *.egg-info
