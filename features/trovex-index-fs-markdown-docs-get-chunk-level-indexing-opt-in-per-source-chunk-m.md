# [trovex/index] fs markdown docs get chunk-level indexing (opt-in per source, chunk_markdown: bool) so passage/card/section + provenance link work on them like owned docs

## Team : trovex-backend (tsukumo)
## Branch : feat/fs-md-chunking (from dev)
## Relay task : 52385ebc-8278-4a0a-b4b1-47896d1df4f8
## Trace : trace=8e463241dc5eac33aa844978bf61e2b8
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. sources config gets chunk_markdown: bool (default false); when true Indexer._upsert_doc chunks md/mdx via chunk_markdown through sync_doc_chunks (Merkle reuse, chunker_version); pinned test: flag off = zero chunks, flag on = chunks carrying anchor + link
- [ ] 2. Enabling on a fixture source and editing one section re-embeds only the changed sections (embedded-count assertion); reindex timings shape unchanged; make test green
- [ ] 3. Capacity guard: chunk_markdown refuses (journals the reason, stays off) when the source's vec_chunks partition would exceed the vec0 ceiling used by the capacity status; pinned test
- [ ] 4. PR body states which live sources it recommends flipping on and the projected chunk + embed cost for each (numbers), niwa-lessons excluded by default

## 2. Root cause & decisions

# Decision — opt-in chunk_markdown for fs sources (task 52385ebc)

ROOT_CAUSE: Indexer._upsert_doc chunked only code files (scope cut at 9299f37d), so the 1433 fs markdown docs held 26 chunks in total and trovex_read tier=passage|card, search_chunks and the provenance link never had a section to return for them; the cut was never revisited because turning chunking on for a whole source can push its vec0 partition past the KNN ceiling.

## Decision
- `Source.chunk_markdown: bool = False`, stored in `sources.config` JSON (the sources table from task 960a4b64). `_upsert_doc` chunks md/mdx through `chunk_markdown` + `sync_doc_chunks` (Merkle reuse, markdown `CHUNKER_VERSION`) when the flag is on; the code path is unchanged (one chunker/version pair picked, one shared `sync_doc_chunks` call).
- `fs_chunking.enable_chunk_markdown` is the only thing that turns the flag on: project chunks with `chunk_markdown` over the source's unchunked md docs (reads files, writes nothing), refuse when `current_chunks + new_chunks > VEC0_K_CEILING` (journals a `source_runs` row kind='guard' with the reason, flag stays off), else set the flag and backfill the docs indexed before it (a doc whose hash is unchanged never reaches `_upsert_doc`, so without the backfill flipping the flag would do nothing until each file was edited).
- `disable_chunk_markdown` turns it off and purges the source's md chunks: with the flag off nothing keeps them in step with the files, so they would go stale.
- CLI `trovex sources chunk-markdown <id> [--dry-run|--off]`. sources.yaml cannot set the flag (`Source.from_dict` ignores it), so the guard cannot be bypassed by the one-shot import.

## Rejected alternatives
- Guard at index time on every run: rejected for this slice; the DoD is "no source can be *flipped* past the ceiling", and growth after the flip is already visible in `capacity_report`. Follow-up if wanted.
- Backfill as an applier job kind: rejected, more surface than the AC needs; the CLI backfills inline exactly like the existing `backfill-chunks` command.
- `reindex(full=True)` to chunk existing docs: rejected, it re-embeds every doc body (tokens per source below), the backfill embeds only the new chunks.

## Recommended flips (read-only projection on the live store, 2026-09-26; chunks + embed tokens = what `--dry-run` reports; partition ceiling 4096)
| source | md docs | new chunks | embed tokens | partition after | verdict |
|---|---|---|---|---|---|
| trovex-repo | 61 | 460 | 61,082 | 1631 (40%) | flip on |
| tsukumo | 162 | 1445 | 230,050 | 3358 (82%) | only if the cto accepts 82%; over the 80% warn line |
| wraith | 180 | 1484 | 222,729 | 5989 (146%) | guard REFUSES: already 4505 chunks (code) |
| niwa-lessons | 1036 | 1488 | 620,912 | 1514 (37%) | excluded by default per the ticket |
The `trovex` owned partition is untouched (still the 228% case from 02fb48b).

## Verification
`uv run pytest`: 908 passed, ruff clean. tests/test_fs_md_chunking.py: flag default off = zero chunks, enable backfills with anchor + file:// link on every chunk and vec rows 1:1, flag-on indexes a new doc with chunks, editing one section re-embeds exactly one chunk (embedder saw 2 texts: doc + the edited chunk) and unchanged sections keep their rows, refuse past the ceiling with journal + zero chunks + flag off, projection writes nothing, disable purges and stops chunking, CLI dry-run/on/off.

## review-trovex verdict: SHIP
Default off, additive, no schema change; code chunk path unchanged; capacity guard on the only enable path; no secrets, no brand/host strings.

DEPENDS: stacked on feat/connectors-fs (task 960a4b64, needs the sources table), which is stacked on feat/provenance-envelope (task 0284016e). Do not submit before both merge.

RED_EVIDENCE:
  cmd: uv run pytest tests/test_fs_md_chunking.py -q
  test_sha: e434a39
  output: |
    E   ImportError: cannot import name 'fs_chunking' from 'trovex'
    ERROR tests/test_fs_md_chunking.py
    1 error in 0.50s

## 3. Files changed

```
CHANGELOG.md                      |  18 +++
 src/trovex/cli.py                 |  98 ++++++++++++
 src/trovex/config.py              |  14 +-
 src/trovex/connectors/__init__.py |  12 ++
 src/trovex/connectors/base.py     |  64 ++++++++
 src/trovex/connectors/fs.py       |  84 ++++++++++
 src/trovex/db.py                  |  43 +++++-
 src/trovex/fs_chunking.py         | 139 +++++++++++++++++
 src/trovex/index_jobs.py          |  12 +-
 src/trovex/indexer.py             |  22 +--
 src/trovex/sources.py             | 111 ++++++++++++++
 src/trovex/sync.py                | 211 ++++++++++++++++++++++++++
 tests/connector_conformance.py    |  72 +++++++++
 tests/test_connectors_fs.py       | 131 ++++++++++++++++
 tests/test_fs_md_chunking.py      | 211 ++++++++++++++++++++++++++
 tests/test_sources_registry.py    | 176 +++++++++++++++++++++
 tests/test_sync_source.py         | 311 ++++++++++++++++++++++++++++++++++++++
 17 files changed, 1716 insertions(+), 13 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `52385ebc-8278-4a0a-b4b1-47896d1df4f8`._
