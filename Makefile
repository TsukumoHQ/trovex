.PHONY: test lint eval
lint:
	uv run ruff check .
test: lint
	uv run pytest
eval:
	uv run trovex eval-harness benchmarks/token-savings/corpus --retrieval-only --gate
