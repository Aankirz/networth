.PHONY: check

check:
	uv run ruff check . && uv run ruff format --check . && uv run pytest -q

.PHONY: evals

evals:
	uv run python -m evals
