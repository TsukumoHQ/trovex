# ⚠ untyped record — no title or acceptance criteria synced (task b9687dfb)

## Team : trovex-backend (trovex)
## Branch : feat/trovex-links-l2 (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

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
...7dfb-5fc1-46ac-ae5a-4b6075019908-redreverify.md |  74 +++++++++++
 ...-trovex-read-returns-outgoing-links-backlink.md |  85 ++++++++++++
 src/trovex/assets/skill/SKILL.md                   |   7 +
 src/trovex/links_parse.py                          | 128 +++++++++++++++++-
 src/trovex/mcp_app.py                              |  72 +++++++++-
 src/trovex/search.py                               |  19 +++
 tests/test_doc_refs_mcp.py                         | 146 +++++++++++++++++++++
 tests/test_mcp_contract.py                         |   5 +-
 8 files changed, 532 insertions(+), 4 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `b9687dfb-5fc1-46ac-ae5a-4b6075019908--redreverify`._
