.PHONY: sync test lint eval
# A fresh worktree (the review gate's, CI's) has no dev deps: `uv run pytest` would
# fall through to a system pytest and fail on import. Idempotent, seconds when warm.
sync:
	uv sync --all-extras --all-groups --frozen
lint: sync
	uv run ruff check .
test: lint
	uv run pytest
eval: sync
	uv run trovex eval-harness benchmarks/token-savings/corpus --retrieval-only --gate
