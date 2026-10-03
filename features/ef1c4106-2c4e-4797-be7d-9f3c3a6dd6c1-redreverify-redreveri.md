# ⚠ untyped record — no title or acceptance criteria synced (task ef1c4106)

## Team : trovex-backend (trovex)
## Branch : feat/trovex-links-l5 (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

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
...4797-be7d-9f3c3a6dd6c1-redreverify-redreveri.md |  71 ++++
 ...4106-2c4e-4797-be7d-9f3c3a6dd6c1-redreverify.md |  70 ++++
 ...-to-source-files-symbols-tickets-commits-bec.md |  82 +++++
 src/trovex/code_refs.py                            | 362 +++++++++++++++++++++
 src/trovex/db.py                                   |  43 +++
 src/trovex/indexer.py                              |  47 +++
 src/trovex/store.py                                |  13 +
 tests/test_doc_refs_code.py                        | 197 +++++++++++
 8 files changed, 885 insertions(+)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `ef1c4106-2c4e-4797-be7d-9f3c3a6dd6c1--redreverify--redreveri`._
