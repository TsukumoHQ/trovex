# ⚠ untyped record — no title or acceptance criteria synced (task a1b5a169)

## Team : trovex-backend (trovex)
## Branch : feat/trovex-links-l1 (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

# Decision — index Obsidian-style links as doc_refs (task a1b5a169, trovex/links L1)

ROOT_CAUSE: trovex had no automatic doc-to-doc link graph. The only edges were `doc_links` (db.py:1806) — a small curated/typed set (supersedes/verdict-of/decided-in/resume-of), written by hand through `trovex_write(links=)`, resolved by `ext_id` ONLY, between trovex-owned docs. File-backed docs carry no `ext_id`, so they could never be a link endpoint, and nothing anywhere parsed `[[wikilinks]]` or relative `.md` links out of doc content. Founder (2026-10-02) wants Obsidian-like linking: every `[[link]]` / relative `.md` link in ANY indexed doc a queryable edge, including links to docs that don't exist yet.

## Decision
New table `doc_refs` + new module `src/trovex/links_parse.py`. `doc_links` (typed, curated) left untouched — `doc_refs` is its AUTOMATIC, untyped, extract-at-index-time counterpart.

- **Schema (`db.py` `_init_schema`):** `doc_refs(id, src_id→docs ON DELETE CASCADE, dst_id→docs NULL, dst_raw, dst_norm, anchor, alias, context, kind DEFAULT 'links-to')`. Indexes on `src_id`, `dst_id`, a partial index on `dst_norm WHERE dst_id IS NULL` (dangling-rebind lookup), and `UNIQUE(src_id, dst_raw, COALESCE(anchor,''))`.
- **Parser (`links_parse.parse_links`):** extracts `[[x]]`, `[[x#anchor]]`, `[[x|alias]]`, `![[x]]` (embed), and `[text](rel/path.md#anchor)` (relative `.md` only — external URLs / mailto / in-page `#` anchors are not edges). Code fences and inline code are masked to equal-length spaces first, so links inside code are ignored AND match offsets still index the original text for `context` (surrounding sentence, whitespace-collapsed, ≤160 chars).
- **Resolution (`resolve_ref`), first unique match wins:** (1) same-source relative path (target joined onto the src doc's dir, `normpath`-collapsed, with/without `.md`); (2a) basename unique WITHIN the src doc's own source; (2b) basename globally unique, only when the src source has none (cto review ask: `[[design]]` in repo A must bind to A's design.md even when B has one too); (3) title / canonical_topic, if unique; (4) `ext_id` exact. Else `dst_id` NULL = dangling, KEPT.
- **Sync (`sync_doc_refs`):** replaces the src doc's outgoing refs wholesale (so a dropped link removes its edge), then re-binds any dangling ref whose `dst_norm` could point at THIS doc and now resolves — this is what binds a link to a future doc, and re-binds across a rename (delete+insert). Called from `Indexer._upsert_doc` (file-backed) and `SqliteStore.put` (owned).
- **`delete_doc_cascade`:** two-sided but ASYMMETRIC — a deleted doc's OUTGOING refs die with it; a ref that POINTED AT it survives as dangling (`dst_id` NULL) so it re-binds if the target reappears.

## Rejected alternatives / deviations
- **Add `doc_refs` to `_DOC_CHILD_TABLES` (as the ticket suggested):** rejected — that tuple is walked by bare `DELETE ... WHERE doc_id = ?` (wrong column; `doc_refs` keys on `src_id`) and expresses only a one-sided delete, but the ACs require the incoming side become dangling, not deleted. Handled explicitly in `delete_doc_cascade` next to `doc_links` instead.
- **Re-resolve ALL dangling refs on every insert:** rejected — O(dangling) per inserted doc balloons a full reindex. Instead store `dst_norm` (target basename, no `.md`, lower) and rebind only the dangling rows whose key matches the inserted doc, via the partial index.
- **Store anchorless rows with NULL anchor under a plain `UNIQUE(src_id,dst_raw,anchor)`:** rejected — SQLite treats NULLs as distinct, so two anchorless links to the same target would both insert. Used a `COALESCE(anchor,'')` unique index for correct dedup while keeping NULL anchors readable.

[LEGACY_OPPORTUNITY] `SqliteStore.put_batch` (store.py:~1084) upserts owned docs without calling `sync_doc_refs`, so a batch-created doc neither emits its own refs nor triggers dangling re-bind until individually re-written; L1 scope wired only the single `put` path the AC exercises.

RED_EVIDENCE:
  cmd: uv run pytest -q tests/test_doc_refs.py
  test_sha: 47849fa
  output: |
    ==================================== ERRORS ====================================
    ___________________ ERROR collecting tests/test_doc_refs.py ____________________
    ImportError while importing test module 'tests/test_doc_refs.py'.
    Traceback:
    tests/test_doc_refs.py:21: in <module>
        from trovex.links_parse import parse_links
    E   ModuleNotFoundError: No module named 'trovex.links_parse'
    =========================== short test summary info ============================
    ERROR tests/test_doc_refs.py
    !!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
    1 error in 0.49s
  note: captured on the base tree (31f8712) with only tests/test_doc_refs.py added — the feature files reverted and links_parse.py removed, then restored byte-identical. Proves the test cannot pass without the implementation.

## Verification
- `uv run pytest -q tests/test_doc_refs.py` → 5 passed (verify_cmd).
- Full suite `uv run pytest -q` → 927 passed, 1 warning (hermetic, BagEmbedder).
- `uv run ruff check .` → clean.
- Tests cover: parser forms + code-fence/inline-code skip + anchor/alias/context; resolve then dangling-on-target-delete; dangling rebind on rename + future-doc appearance; owned-doc `[[some/file]]`→file-backed resolution; `delete_doc_cascade` drops outgoing refs with no orphans.

## review-trovex verdict: SHIP
5 files, +586 LoC. Gate green (ruff + pytest 927). New logic isolated in `links_parse.py` (db/store/indexer stayed near-untouched); doc_links + Active-Memory recall/scope/owner-tag/upsert paths unchanged; no secret/brand/host/number leak; no new `.md` on disk. Schema change → PR to cto (no self-merge).

## 3. Files changed

```
features/DEBT.md                                   |   1 +
 ...a169-ab85-4f56-8a2e-d8a290b3eae3-redreverify.md |  81 +++++
 ...-links-wikilinks-relative-md-links-parsed-at.md |  95 ++++++
 src/trovex/db.py                                   |  40 +++
 src/trovex/indexer.py                              |   5 +
 src/trovex/links_parse.py                          | 331 +++++++++++++++++++++
 src/trovex/store.py                                |   7 +
 tests/test_doc_refs.py                             | 253 ++++++++++++++++
 8 files changed, 813 insertions(+)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `a1b5a169-ab85-4f56-8a2e-d8a290b3eae3--redreverify`._
