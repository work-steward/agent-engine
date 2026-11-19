.PHONY: lint format test check

lint:
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .
	uv run --frozen yamllint -s -c .yamllint.yml .github .yamllint.yml
	uv run --frozen python scripts/check_docs.py
	uv run --frozen python scripts/check_repository.py
	git diff --check

format:
	uv run --frozen ruff check . --fix
	uv run --frozen ruff format .

test:
	uv run --frozen pytest -q

check: lint test
