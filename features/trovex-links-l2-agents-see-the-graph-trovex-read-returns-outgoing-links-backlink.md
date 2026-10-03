# [trovex/links L2] agents see the graph: trovex_read returns outgoing links + backlinks (with context), trovex(q) hints link counts, trovex://graph resource

## Team : trovex-backend (tsukumo)
## Branch : feat/trovex-links-l2 (from dev)
## Relay task : b9687dfb-5fc1-46ac-ae5a-4b6075019908
## Trace : trace=b778f7ae3b194106fd93a0268666b17b
## Status : 🔵 IN REVIEW

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. test: trovex_read(doc, links=True) on a doc with 2 out + 1 in + 1 dangling prints all four lines with context, capped with +N more past 10
- [ ] 2. test: trovex(q) result line shows counts only for linked docs; unlinked docs' output byte-identical to before
- [ ] 3. test: trovex://graph/{doc} returns 1-hop neighbours for a file-backed doc
- [ ] 4. test_mcp_contract updated and green; SKILL.md mentions links=True
- [ ] 5. make test green

## 2. Root cause & decisions

# Decision — agents see the doc_refs graph via MCP (task b9687dfb, trovex/links L2)

ROOT_CAUSE: L1 (doc_refs) built the extracted link graph, but nothing exposed it. An agent reading a doc could not learn what it cites or what cites it without a second search, and the MCP surface (plain text, mcp_app.py) had no notion of edges. trovex_read also only reached trovex-OWNED docs (store.get is ext_id-only), so a file-backed doc's graph was unreachable.

## Decision
Expose the graph through the three places an agent already looks, all reading L1's `doc_refs` (no schema change):

- **`trovex_read(doc_id, links=True)`** (new optional param, default False → additive): after the body, append a compact block — outgoing edges `→ out: <path>#<anchor> — <context>`, dangling `∅ <raw>`, backlinks `← in: <path> — <context>` — each side capped at 10 with `+N more`. Applied to the owned doc_id read (content + section) and the query passage/card read. A **file-backed** doc is now reachable here: when `resolve_ext_id` misses and `links=True`, `resolve_doc_handle` resolves the doc by `source:path` / bare path and the body is read from its indexed `absolute_path`.
- **`trovex(q)` / `Searcher.format_minimal`**: each result line gains a ` ⇄<in>/<out>` edge-count hint, emitted ONLY when the doc has edges — an unlinked doc's line is byte-identical to before, so no token cost where there's nothing to point at. Best-effort (try/except) so a count lookup never breaks formatting.
- **`trovex://graph/{doc}`** (new MCP resource beside the catalog resources): the same 1-hop neighbourhood as a read-only resource, for an owned id, a `source:path`, or a bare path.

All graph read logic (`outgoing_links` / `backlinks` / `link_counts` / `render_links_block` / `resolve_doc_handle` / `valid_handle`) lives in `links_parse.py` (mcp_app.py is already 50KB+). `SKILL.md` documents `links=True`; `test_mcp_contract.py` pins the new frozen `trovex_read` signature.

INPUT VALIDATION: the doc handle reaching SQL (`trovex://graph/{doc}`, the file-backed `doc_id`) is length- and charset-bounded by `valid_handle` (`^[A-Za-z0-9._/:#\- ]{1,512}$`) before any query; the queries themselves are parameterised regardless (defence-in-depth).

## Rejected alternatives
- **Put the link block / count logic in mcp_app.py and search.py directly:** rejected — keeps the presentation helpers testable in isolation and keeps the already-large MCP/search modules from accreting graph logic. Formatting returns a plain string the resource and the tool both reuse.
- **Always append the ⇄ hint (even `⇄0/0`):** rejected — breaks the AC's byte-identical guarantee for unlinked docs and spends tokens on every router line. Emitted only when `in+out > 0`.
- **Full file-backed read support on trovex_read for all tiers:** out of scope — the file-backed path is enabled for `links=True` (the AC), leaving the owned-only behaviour unchanged when `links` is off.

RED_EVIDENCE:
  cmd: uv run pytest -q tests/test_mcp_contract.py tests/test_doc_refs_mcp.py
  test_sha: 67bba6f
  output: |
    >       out = mcp_app.doc_graph("code:a.md")
    E       AttributeError: module 'trovex.mcp_app' has no attribute 'doc_graph'
    =========================== short test summary info ============================
    FAILED tests/test_mcp_contract.py::test_each_tool_params_and_required_pinned
    FAILED tests/test_doc_refs_mcp.py::test_read_links_block_lists_out_in_and_dangling
    FAILED tests/test_doc_refs_mcp.py::test_read_links_block_caps_each_side_at_ten
    FAILED tests/test_doc_refs_mcp.py::test_minimal_counts_only_for_linked_docs
    FAILED tests/test_doc_refs_mcp.py::test_graph_resource_for_file_backed_doc
    5 failed, 13 passed in 3.74s
  note: captured with the L2 source files reverted to the L1 tip (15130dd) and the L2 tests kept, then restored. Proves trovex_read(links=), the ⇄ count hint, and trovex://graph don't exist without the implementation.

## review-trovex verdict: SHIP
6 files, +~370 LoC. New logic isolated in links_parse.py; no schema change (reads L1 doc_refs); recall/scope/owner-tag/upsert paths untouched; count hint is additive + guarded + byte-identical for unlinked docs; handle input validated before SQL; no secret/brand/host/number leak; no new .md on disk (SKILL.md edited in place). Stacked on L1 (a1b5a169) — submits after L1 merges to dev.

## 3. Files changed

```
...-trovex-read-returns-outgoing-links-backlink.md |  78 +++++++++++
 src/trovex/assets/skill/SKILL.md                   |   7 +
 src/trovex/links_parse.py                          | 125 +++++++++++++++++-
 src/trovex/mcp_app.py                              |  72 +++++++++-
 src/trovex/search.py                               |  19 +++
 tests/test_doc_refs_mcp.py                         | 146 +++++++++++++++++++++
 tests/test_mcp_contract.py                         |   5 +-
 7 files changed, 448 insertions(+), 4 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-b9687dfb-5fc1-46ac-ae5a-4b6075019908
- 🟢 AC1: Both pass under verify_cmd (18 passed). Main covers 4-line+context; cap covers +N more past 10. — evidence: src/trovex/mcp_app.py:716-823 adds links=True; render_links_block in src/trovex/links_parse.py:431-454 emits out/in/dangling with context; tests/test_doc_refs_mcp.py:75-101 covers 2 out + 1 in + 1 dangling + context — test: test_read_links_block_lists_out_in_and_dangling tests/test_doc_refs_mcp.py:75 + test_read_links_block_caps_each_side_at_ten tests/test_doc_refs_mcp.py:106
- 🟢 AC2: Test verifies hint present in linked line, absent in unlinked line; passes. — evidence: src/trovex/search.py:401-422 _link_hint returns empty when counts are zero, leaving base byte-identical for unlinked — test: test_minimal_counts_only_for_linked_docs tests/test_doc_refs_mcp.py:118-133
- 🟢 AC3: Test indexes code:a.md -> code:b.md, asserts out+b.md for a.md and in for b.md; passes. — evidence: src/trovex/mcp_app.py:1315-1332 doc_graph resource resolves source:path via valid_handle+resolve_doc_handle then renders render_links_block — test: test_graph_resource_for_file_backed_doc tests/test_doc_refs_mcp.py:140-146
- 🟢 AC4: Both files updated, contract test green in 18 passed. — evidence: tests/test_mcp_contract.py:53-56 adds 'links' to trovex_read props set; src/trovex/assets/skill/SKILL.md:32-38 documents trovex_read(doc_id, links=True) — test: test_mcp_contract trovex_read props assertion
- 🟢 AC5: make test runs lint + pytest; lint clean, pytest green. — evidence: make test -> exit 0; uv run pytest tests/ -> 960 passed in 186s — test: Full suite under make test target

## 5. Timeline

- round 1 → **reject** (review-b9687dfb-5fc1-46ac-ae5a-4b6075019908)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `b9687dfb-5fc1-46ac-ae5a-4b6075019908`._
