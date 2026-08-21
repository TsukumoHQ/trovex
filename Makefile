.PHONY: test lint
lint:
	uv run ruff check .
test: lint
	uv run pytest
