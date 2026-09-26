# [trovex/links] typed doc_links (supersedes, verdict-of, decided-in, resume-of) written at capture time + as-of resolution in trovex_read/search — the zero-LLM answer to 'what is the current decision on X' (GraphRAG rejected)

## Team : trovex-backend (tsukumo)
## Branch : feat/typed-doc-links (from dev)
## Relay task : edaf8627-ae76-471c-95b7-209dab0a543f
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. doc_links table with a closed rel enum; trovex_write accepts links and rejects unknown rels; pinned tests
- [ ] 2. trovex_read with as_of resolves the supersedes chain to the version valid at that time; pinned test on a 3-version chain
- [ ] 3. trovex_search hides superseded targets by default and shows them with current_only=false; pinned test
- [ ] 4. delete_doc_cascade removes links in both directions; pinned test
- [ ] 5. make test green; MCP contract test updated; PR carries the review-trovex verdict; submitted through the gate against dev

## 2. Root cause & decisions

ROOT_CAUSE: no prior doc_links/typed-edge mechanism existed — trovex had document-level supersession (docs.status/lifecycle/canonical_topic SSOT swap) but no explicit, queryable edge between two owned docs, so "what verdict answers this ticket" or "what decision superseded this one" had no zero-LLM answer. Founder-direction item (Miner D F7), promoted once its two gating tasks (cbb8e8fb, b47301eb) merged.

DECISION: new doc_links(src_doc_id, rel, dst_doc_id, created_at, created_by) table, rel a closed enum in code (db.DOC_LINK_RELS: supersedes/verdict-of/decided-in/resume-of) rather than a CHECK constraint, so adding a rel later needs no migration. trovex_write gains `links=[{"rel","target"}]`, validated + written inside the SAME transaction as the doc content (store.put's _add_links_locked) — an unknown rel or unresolvable target raises ValueError, rolling the whole write back via the existing _retry_on_locked wrapper, so a bad link never half-lands. Only 'supersedes' carries retrieval semantics: store.search_chunks(current_only=True, default) hides a doc that is any edge's dst; store.resolve_as_of walks the chain backward via docs.first_indexed to resolve trovex_read(as_of=...). delete_doc_cascade prunes doc_links by hand in both directions (src and dst) since it has two doc-id columns and isn't a _DOC_CHILD_TABLES member (no FK-cascade pragma enabled in this store, matching every other child table).

REJECTED_ALTERNATIVE: LightRAG/GraphRAG-style LLM-derived edges (one LLM call per chunk at ingest, re-derivation on delete) — rejected per the task's own research citation: for a store of verdicts/decisions/resumes the relevant edges are ALREADY KNOWN by the writer at write time, so paying an LLM to re-discover them is pure waste and adds a non-deterministic failure mode.

## review-trovex verdict: SHIP

review-trovex: ✅ ship — 5 files, +409 LoC — gate green (ruff+pytest, 827 passed after rebase onto origin/dev @52ff67d). AC1: doc_links table + closed rel enum; trovex_write validates rel/target inside store.put's transaction, unknown rel or unresolvable target rolls back the whole write (tests/test_doc_links.py: test_put_rejects_unknown_rel_and_writes_nothing, test_put_rejects_unresolvable_target_and_writes_nothing, test_put_with_links_creates_doc_links_row, test_put_accepts_a_short_prefix_target, test_put_links_idempotent_on_identical_redeclare, test_put_writes_multiple_rel_kinds). AC2: resolve_as_of walks a 3-version supersedes chain via docs.first_indexed, pinned on exactly the 3-version scenario the AC asks for (test_resolve_as_of_walks_a_three_version_chain, plus unlinked/unknown-doc edge cases). AC3: search_chunks current_only=True (default) hides a supersedes target, current_only=False shows it, unlinked docs unaffected (test_search_chunks_hides_superseded_target_by_default, test_search_chunks_current_only_does_not_hide_unlinked_docs); wired into trovex_search. AC4: delete_doc_cascade prunes doc_links as both src and dst (test_delete_prunes_doc_links_as_source, test_delete_prunes_doc_links_as_target). MCP contract test updated for trovex_write/trovex_read/trovex_search's new optional params (links/as_of/current_only) — additive, no existing client breaks. make test green, submitted against dev.

## 3. Files changed

```
src/trovex/db.py           |  30 +++++++
 src/trovex/mcp_app.py      |  55 ++++++++++++
 src/trovex/store.py        | 103 +++++++++++++++++++++-
 tests/test_doc_links.py    | 211 +++++++++++++++++++++++++++++++++++++++++++++
 tests/test_mcp_contract.py |  15 +++-
 5 files changed, 409 insertions(+), 5 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `edaf8627-ae76-471c-95b7-209dab0a543f`._
