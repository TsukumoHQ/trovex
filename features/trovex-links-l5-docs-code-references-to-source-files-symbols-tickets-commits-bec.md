# [trovex/links L5] docs ↔ code: references to source files/symbols/tickets/commits become edges, and a doc goes 'drifted' when the code it cites changed after it

## Team : trovex-backend (tsukumo)
## Branch : feat/trovex-links-l5 (from dev)
## Relay task : ef1c4106-2c4e-4797-be7d-9f3c3a6dd6c1
## Trace : trace=6bc5a35fd3389c6b33cce7718bcc2744
## Status : 🔵 IN REVIEW

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. test: doc citing `src/a.py` and `pkg.mod.func` -> cites-code edges to the indexed file (symbol resolves to its file + anchor)
- [ ] 2. test: git fixture — doc written, then src/a.py committed later -> doc.drift true with reason naming the file and commit count; doc rewritten after -> drift clears
- [ ] 3. test: unknown sha / nonexistent path -> no edge, no crash
- [ ] 4. test: reindex of an unchanged repo does not call git per doc (cached)
- [ ] 5. make test green

## 2. Root cause & decisions

# Decision — docs↔code graph + drift (task ef1c4106, trovex/links L5)

ROOT_CAUSE: L1/L2 gave trovex a generalist note-link graph (like Obsidian). Founder (2026-10-02) wants the software-engineering differentiator: a doc that cites a source file / symbol / ticket / commit should be a typed edge to the thing it documents, AND trovex should tell an agent when a doc is STALE — the code it describes was committed after the doc last changed. Nothing extracted code citations or tracked doc-vs-code staleness.

## Decision
New module `src/trovex/code_refs.py`; edges reuse the L1 `doc_refs` table (its `kind` column was left open for exactly this), drift is a per-doc flag.

- **Extraction (`extract_code_refs`):** from INLINE code spans (the opposite of L1, which blanks them) + markdown-link paths + `#123` in prose. Fenced blocks are blanked (examples, not citations). Recognises: repo paths ending in a known code extension with optional `:line` (`src/a.py`, `agentd/src/qa.rs:52`); dotted symbols (`Indexer._upsert_doc`); 7–40 hex shas; `#123` PRs. New kinds: `cites-code` / `cites-ticket` / `cites-commit`.
- **Resolution (`sync_code_refs`):** a path → the indexed code doc at that path in the same source. A symbol `a.b.c` → (A) a code chunk whose breadcrumb leaf is the symbol (exact anchor), else (B) a code file whose basename is a module segment and which contains the leaf (small files are one line-labelled chunk, so (A) can't fire). A sha → validated with `git cat-file -e` against the source repo; an 8-hex non-commit falls back to a task-id (`cites-ticket`); an unknown longer sha / nonexistent path produces NO edge (never a crash).
- **Drift (`_compute_drift`):** for each resolved `cites-code` edge, the cited file's last commit ts (git) vs the doc's last change (the doc's own last commit ts, else mtime). Drifted when any cited file is newer; `docs.drift` + `docs.drift_reason` ("src/a.py changed N commit(s) after this doc"). `recompute_drift_for_code_docs` re-drifts the non-touched docs that cite a code file which changed this run (incremental).
- **No git per query / per unchanged doc:** drift runs only in a post-upsert pass over this run's TOUCHED docs (`_sync_code_graph` in both `reindex` + `reindex_paths`), so an unchanged-repo reindex shells out to git ZERO times. A cited file's last-commit ts is cached in the new `code_commit_cache` table keyed by the file's content_hash — reused until the file changes.
- **Schema (cto review):** `docs.drift INTEGER DEFAULT 0` + `docs.drift_reason TEXT` (CREATE + `_migrate_add_drift` additive ALTER); new `code_commit_cache` table. No change to `doc_refs` shape (only new `kind` values).

## Rejected alternatives
- **Resolve symbols ONLY via code-chunk breadcrumbs:** rejected — a small file is chunked as one line-labelled chunk with no per-symbol breadcrumb, so a bare symbol wouldn't resolve. Added the module-segment→file fallback.
- **Compute drift lazily at query time:** rejected — the ticket forbids shelling to git per query. Drift is computed at index time and stored on the doc.
- **Shell git per doc every reindex:** rejected — AC4. Cached by content_hash + only touched docs re-evaluated; an unchanged reindex calls git zero times.
- **Surface `⚠ drift` in trovex_read now:** deferred — that render lives in L2 (`render_links_block`), which isn't on dev yet. L5 lands the drift DATA; the L2-output integration is a follow-up once both are on dev.

RED_EVIDENCE:
  cmd: uv run pytest -q tests/test_doc_refs_code.py
  test_sha: fb6ac84
  output: |
    _________________ ERROR collecting tests/test_doc_refs_code.py _________________
    tests/test_doc_refs_code.py:16: in <module>
        from trovex import code_refs
    E   ImportError: cannot import name 'code_refs' from 'trovex'
    =========================== short test summary info ============================
    ERROR tests/test_doc_refs_code.py
    !!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
    1 error in 1.07s
  note: captured with db.py/indexer.py/store.py reverted to origin/dev and code_refs.py removed, then restored. Proves the edges + drift don't exist without the implementation.

## review-trovex verdict: SHIP
3 files + 1 new module + 1 new test file. New logic isolated in code_refs.py (db/store/indexer edits are thin wiring). Schema change (docs.drift + code_commit_cache) → PR to cto. git calls are graceful-degrading (None on no-repo/timeout, never raise into indexing); sha/path inputs resolved against the repo, no shell injection (argv list, no shell). No secret/brand/host/number leak; no new .md on disk.

## 3. Files changed

```
...-to-source-files-symbols-tickets-commits-bec.md |  76 +++++
 src/trovex/code_refs.py                            | 362 +++++++++++++++++++++
 src/trovex/db.py                                   |  43 +++
 src/trovex/indexer.py                              |  47 +++
 src/trovex/store.py                                |  13 +
 tests/test_doc_refs_code.py                        | 197 +++++++++++
 6 files changed, 738 insertions(+)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-ef1c4106-2c4e-4797-be7d-9f3c3a6dd6c1
- 🟢 AC1: Symbol resolution: leaf-matched chunks (heading_path leaf == func) -> file + anchor. Verified by test_cites_code_resolves_path_and_symbol. — evidence: src/trovex/code_refs.py:184-228 _resolve_code resolves cites-code to (doc_id, anchor); src/trovex/code_refs.py:66-91 extract_code_refs parses path and symbol tokens. — test: test_cites_code_resolves_path_and_symbol tests/test_doc_refs_code.py:90 - doc cites src/mod.py and pkg.mod.func, asserts dst_id=mod_id for both path and symbol, asserts symbol anchor is truthy.
- 🟢 AC2: Drift flag and reason follow the fixture: code-committed-after-doc sets drift; doc-rewritten-after-code clears it. — evidence: src/trovex/code_refs.py:306-340 _compute_drift sets docs.drift=1 + drift_reason naming the file and commit count; cleared when doc_ts >= code_ts after rewrite. — test: test_drift_sets_and_clears tests/test_doc_refs_code.py:145 - commits doc at 2021-01-01, then commits src/a.py at 2021-02-01, asserts drift=1 with reason containing 'src/a.py' and 'commit'; commits updated doc at 2021-03-01, asserts drift=0.
- 🟢 AC3: Both unsafe inputs degrade to no-edge without exception. — evidence: src/trovex/code_refs.py:285-303 sync_code_refs: dst_id=None on unresolvable cites-code -> INSERT skipped; unknown sha falls through 'continue'; nonexistent path returns _resolve_code -> (None, None). — test: test_unknown_sha_and_missing_path_make_no_edge tests/test_doc_refs_code.py:118 - doc cites src/nope.py and a bogus 40-hex sha; reindex must not raise; asserts no row with dst_raw=src/nope.py and no cites-commit rows.
- 🟢 AC4: Cache key on content_hash + short-circuit on _touched_ids both honored. Monkeypatch count confirms zero _git invocations on unchanged reindex. — evidence: src/trovex/indexer.py:613-615 _sync_code_graph short-circuits when self._touched_ids is empty (no docs touched -> no _git calls). src/trovex/code_refs.py:153-181 _cached_last_commit_ts keys on (source_id, path) + content_hash so an unchanged file reuses the row. — test: test_unchanged_reindex_calls_no_git tests/test_doc_refs_code.py:174 - monkeypatches code_refs._git to count invocations; second _reindex on unchanged repo asserts calls==0.
- 🟢 AC5: All 5 ticket tests green under the project venv (3.11.15). Daemon pytest invocation exited 2 with ModuleNotFoundError only because .venv/bin/pytest shebang points at a deleted prior-worktree venv; python -m pytest resolves to the correct interpreter and the suite passes. Worktree artifact, not a doer-introduced defect. — evidence: uv run --extra dev python -m pytest -q tests/test_doc_refs_code.py -> 5 passed. Adjacent suites test_db.py + test_doc_links.py + test_doc_refs.py + test_doc_versioning.py -> 35 passed. — test: tests/test_doc_refs_code.py::test_extract_code_refs_forms, test_cites_code_resolves_path_and_symbol, test_unknown_sha_and_missing_path_make_no_edge, test_drift_sets_and_clears, test_unchanged_reindex_calls_no_git.

## 5. Timeline

- round 1 → **reject** (review-ef1c4106-2c4e-4797-be7d-9f3c3a6dd6c1)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `ef1c4106-2c4e-4797-be7d-9f3c3a6dd6c1`._
