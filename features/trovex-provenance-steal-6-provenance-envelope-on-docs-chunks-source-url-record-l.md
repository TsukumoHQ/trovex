# [trovex/provenance] steal #6: provenance envelope on docs + chunks (source_url, record_locator, remote_version, owners, fetched_at; chunk anchor + link) served on every search hit and trovex_read slice

## Team : trovex-backend (tsukumo)
## Branch : feat/provenance-envelope (from dev)
## Relay task : 0284016e-b97f-4af2-80d6-c37403a34c05
## Trace : trace=4212d9cb141d95e36de8c23d565204b1
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. docs gains external_id, source_url, record_locator JSON, remote_version, remote_updated_at, owners JSON, parents JSON, fetched_at; chunks gains anchor and link; migration is idempotent on an existing store (pinned test opens a pre-migration fixture twice)
- [ ] 2. the fs indexer fills record_locator={path, line_range} and chunks.anchor (heading slug or line range) and chunks.link on every indexed doc; pinned test on a 3-doc fixture
- [ ] 3. trovex_search hits and trovex_read(section=|tier=) responses include link and record_locator; pinned MCP test asserts the fields on a hit and on a read
- [ ] 4. index_runs timings unchanged in shape; make test green

## 2. Root cause & decisions

# Decision — provenance envelope (task 0284016e)

ROOT_CAUSE: A search hit or trovex_read slice carried no citation an agent could verify or re-fetch: docs/chunks had no source_url/record_locator/anchor/link columns, so connectors (steal #5) would have had to land on a schema that could not hold remote-record identity, and even fs hits gave only `trovex:<id>`.

## Decision
- One additive migration `_migrate_add_provenance` (db.py), called before `_init_schema`: docs +external_id, source_url, record_locator (JSON), remote_version, remote_updated_at, owners (JSON), parents (JSON), fetched_at; chunks +anchor, link. Single BEGIN IMMEDIATE, no vec rebuild, idempotent: a normal boot finds the columns and no `anchor=''` chunk and takes no writer lock. Legacy fs docs get `record_locator={"path"}`, legacy chunks get anchor+link backfilled in the same transaction.
- `sync_doc_chunks` (shared by trovex-owned + code chunking) stamps `anchor` (slug of the last heading / code line-range label, else `chunk-<n>`) and `link` (`source_url` | `file://<abs path>` | `trovex:<ext_id>` + `#anchor`), also on reused chunks.
- Fs indexer fills `record_locator={"path", "line_range":[1,n]}` + `fetched_at` on add and update.
- Served as one trailing line `↳ <link> · loc=<record_locator>` on search citations, passage, card, and trovex_read(doc_id, section=).

## Rejected alternatives
- Serve-time derivation of link with no stored columns: rejected, connectors need the stored fields and a per-chunk anchor that survives re-chunking.
- Structured JSON hit shape for the text output: rejected, changes every consumer; the budget JSON envelope is unchanged.
- Per-chunk line ranges (anchor as line range): [LEGACY_OPPORTUNITY] chunks have no line offsets and markdown fs docs are not chunked at all; dev-codex f460f703 owns chunk line ranges.

## Verification
`make test`: 845 passed (ruff clean). New tests/test_provenance.py: migration on a pre-migration fixture opened twice, indexer fixture of 3 docs, MCP search + read + section assertions.

## review-trovex verdict: SHIP
Additive schema only; no retrieval/scope/owner-tag change; no secret/brand/host leak; single-writer preserved.

RED_EVIDENCE:
  cmd: uv run pytest tests/test_provenance.py -q
  test_sha: 15800be
  output: |
    E           sqlite3.OperationalError: no such column: "external_id"
    E       sqlite3.OperationalError: no such column: record_locator
    E       assert '↳ file:///.../repo/svc.py#' in 'svc.py > L1:1-L3  — trovex:None ...'
    E       AssertionError: assert '↳ trovex:<id>#deploy-step' in '## Deploy step\n\nrestart the pool'
    FAILED tests/test_provenance.py::test_migration_adds_provenance_and_is_idempotent_on_pre_migration_store
    FAILED tests/test_provenance.py::test_indexer_fills_record_locator_and_chunk_anchor_on_three_docs
    FAILED tests/test_provenance.py::test_search_hit_and_read_slice_serve_link_and_record_locator
    FAILED tests/test_provenance.py::test_read_section_of_owned_doc_serves_anchored_link
    4 failed in 1.53s

## 3. Files changed

```
features/DEBT.md                                   |   1 +
 ...-envelope-on-docs-chunks-source-url-record-l.md |  76 +++++++++
 src/trovex/db.py                                   | 123 +++++++++++++-
 src/trovex/indexer.py                              |  15 +-
 src/trovex/mcp_app.py                              |  29 +++-
 src/trovex/store.py                                |  19 +++
 tests/test_provenance.py                           | 180 +++++++++++++++++++++
 7 files changed, 430 insertions(+), 13 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by human:cto-tsukumo

### Round 2 — ❌ REJECTED by human:cto-tsukumo

### Round 2 — ❌ REJECTED by human:cto-tsukumo

## 5. Timeline

- round 1 → **reject** (human:cto-tsukumo)
- round 2 → **reject** (human:cto-tsukumo)
- round 2 → **reject** (human:cto-tsukumo)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `0284016e-b97f-4af2-80d6-c37403a34c05`._
