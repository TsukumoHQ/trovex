# [trovex/links L1] index Obsidian-style links: [[wikilinks]] + relative .md links parsed at index time, stored as resolved/unresolved refs, file docs included

## Team : trovex-backend (tsukumo)
## Branch : feat/trovex-links-l1 (from dev)
## Relay task : a1b5a169-ab85-4f56-8a2e-d8a290b3eae3
## Trace : trace=f2a9334476ed3806535e5e6fe7c04760
## Status : 🔵 IN REVIEW

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. test: parser extracts [[a]], [[a#H]], [[a|alias]], ![[a]], [t](../b.md#x) with anchor/alias/context; ignores links inside code fences and inline code
- [ ] 2. test: fs source with a.md -> [[b]] and b.md: doc_refs row a->b resolved; delete b.md -> ref becomes dangling (dst_id NULL), not deleted
- [ ] 3. test: rename b.md -> c.md and a links [[c]]: ref re-binds on reindex; dangling [[future]] binds when future.md appears
- [ ] 4. test: owned doc via store.put with [[some/file]] in content resolves to the file-backed doc
- [ ] 5. test: delete_doc_cascade removes outgoing refs of the deleted src
- [ ] 6. make test green (ruff + pytest)

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
 ...-links-wikilinks-relative-md-links-parsed-at.md |  86 ++++++
 src/trovex/db.py                                   |  40 +++
 src/trovex/indexer.py                              |   5 +
 src/trovex/links_parse.py                          | 331 +++++++++++++++++++++
 src/trovex/store.py                                |   7 +
 tests/test_doc_refs.py                             | 253 ++++++++++++++++
 7 files changed, 723 insertions(+)
```

## 4. QA Log

### Round 1 — ✅ APPROVED by review-a1b5a169-ab85-4f56-8a2e-d8a290b3eae3
- 🟢 AC1: Behavioral parse test on real Parser output. Covers all 5 AC forms and both code-skip cases. — evidence: src/trovex/links_parse.py:120-160 parse_links handles _WIKILINK_RE (anchor via _split_target, alias, embed via _split_target + group on embed) and _MDLINK_RE (.md href with anchor/alias). _FENCE_RE + _INLINE_CODE_RE blank code spans before scanning (lines 70-78). — test: test_parser_extracts_all_forms_and_ignores_code tests/test_doc_refs.py:67-98
- 🟢 AC2: Real fs ops, real Indexer, real SQL. Pins resolved->dangling transition. — evidence: src/trovex/indexer.py:578 sync_doc_refs called from _upsert_doc; src/trovex/db.py:807-808 delete_doc_cascade removes outgoing + sets incoming to NULL (two-sided, asymmetric). — test: test_resolved_ref_becomes_dangling_when_target_deleted tests/test_doc_refs.py:101-119
- 🟢 AC3: Both rename and future-doc appearance exercised end-to-end on real fs. — evidence: src/trovex/links_parse.py:303-330 sync_doc_refs phase (b): re-resolve dangling refs whose dst_norm matches new doc keys. INSERT of c.md triggers re-bind of [[c]]; INSERT of future.md triggers re-bind of [[future]]. — test: test_dangling_rebinds_on_rename_and_future_doc tests/test_doc_refs.py:122-144
- 🟢 AC4: Real SqliteStore.put, real cross-source resolution path (owned->file-backed). — evidence: src/trovex/store.py:398-400 sync_doc_refs called from put with source_id=TROVEX_SOURCE_ID, path=ext_id. links_parse.py resolve_ref falls through same-source path/basename into global-basename LIKE which matches some/file.md. — test: test_owned_doc_link_resolves_to_file_backed_doc tests/test_doc_refs.py:147-169
- 🟢 AC5: Real fs delete + reindex + SQL orphan count. Pins both removal and no-orphan invariant. — evidence: src/trovex/db.py:807 DELETE FROM doc_refs WHERE src_id=? runs before DELETE FROM docs at line 811. FK pragma OFF, so explicit DELETE is the only path that fires. — test: test_delete_cascade_removes_outgoing_refs tests/test_doc_refs.py:172-190
- 🟢 AC6: Gate green: targeted + full suite + guards all clean. — evidence: uv run pytest -q tests/test_doc_refs.py -> 6 passed in 0.51s. uv run ruff check on all 5 touched files -> All checks passed. uv run pytest -q -> 950 passed full suite. security_guard.py + brand_guard.py clean. — test: verifies locally via the commands above.

## 5. Timeline

- round 1 → **approve** (review-a1b5a169-ab85-4f56-8a2e-d8a290b3eae3)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `a1b5a169-ab85-4f56-8a2e-d8a290b3eae3`._
