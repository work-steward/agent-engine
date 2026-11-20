.PHONY: lint format test check demo audit

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
	uv run --frozen coverage erase
	uv run --frozen coverage run -m pytest -q
	uv run --frozen coverage combine -q
	uv run --frozen coverage report

check: lint test

demo:
	uv run --frozen python -m examples.inventory run

audit:
	mkdir -p .scratch
	uv export --frozen --all-groups --no-emit-project --output-file .scratch/audit-requirements.txt > /dev/null
	uv run --frozen pip-audit --strict --require-hashes --disable-pip --cache-dir .scratch/pip-audit-cache -r .scratch/audit-requirements.txt
