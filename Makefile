.PHONY: init test lint typecheck verify clean

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

clean:
	rm -rf .venv .mypy_cache .pytest_cache .ruff_cache build dist *.egg-info
