# [trovex/links L3] implicit edges: unlinked mentions + semantic 'similar' neighbours, computed incrementally, never mixed with explicit links

## Team : trovex-backend (tsukumo)
## Branch : feat/trovex-links-l3 (from dev)
## Relay task : 07b7cdc4-db1c-41ac-8aec-b502c9bab316
## Trace : trace=8bf9cc39f00dc1de7dacaf962394cc51
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. test: doc mentioning another doc's title unlinked -> 1 mentions edge; linked mention -> no duplicate mentions edge
- [ ] 2. test: two near-topic docs inside band -> similar edge with score; below band -> none; duplicates (>= dup threshold) excluded
- [ ] 3. test: incremental reindex of one doc recomputes only its implicit edges
- [ ] 4. make test green

## 2. Root cause & decisions

# Decision — implicit edges: mentions + similar (task 07b7cdc4, trovex/links L3)

ROOT_CAUSE: L1/L2 only surface edges a doc writes EXPLICITLY ([[links]], .md links). Docs that clearly talk about each other — one naming another's title in prose, or two near-topic notes — stay disconnected unless someone links them by hand. There was no inferred-edge layer, and no way to tell an inferred neighbour from an authored link.

## Decision
New module `src/trovex/implicit_refs.py`; edges reuse the L1 `doc_refs` table under two new kinds, kept DISTINCT from explicit/extracted kinds so authored links stay unambiguous.

- **`mentions`:** a driver doc's text contains another doc's title (or file basename), word-bounded, ≥4 chars, case-insensitive, and the driver does NOT already link/cite that doc (an explicit `links-to`/`embeds`/`cites-code` edge suppresses the inferred one). A name that isn't unique across docs is dropped (ambiguous → no mention).
- **`similar`:** the same vec0 KNN the duplicate detector uses (`detect_duplicate_for` pattern), but for neighbours in a band BELOW the dup threshold — stored score in `[threshold - 0.15, threshold)` — top-3, each with its score (in the edge's `context`). Duplicates (≥ threshold) and already-linked docs are excluded, so `similar` is "almost a dup, but not".
- **Incremental:** both run from `compute_status`, AFTER duplicate detection, over the SAME driver set it uses — touched ids on an incremental pass, all canonical/plan on a full recompute. `_sync_one` deletes+rewrites only the driver's own implicit edges, so recomputing one doc never touches another's (AC3).
- **No schema change:** only new `kind` values in `doc_refs`; the score rides in the existing `context` column.
- **L2 render ('≈ similar' line):** deferred — that output lives in L2 (`render_links_block`), not on dev yet; L3 lands the edge DATA, the render is a follow-up once both are on dev.

## Rejected alternatives
- **Mix inferred edges into the existing link kinds:** rejected — the goal is that authored links stay distinguishable from inferred ones; distinct kinds (`mentions`/`similar`) keep them separable in queries and L2 output.
- **Add a `score REAL` column to doc_refs:** rejected to avoid a third schema migration mid-stack; the score is stored in `context` (documented).
- **Run on the store.put live path (like dup detection):** rejected — the ticket scopes implicit edges to the `compute_status` incremental pass (reindex/fs-watch), where the KNN cost is already profiled and driver-scoped.

[LEGACY_OPPORTUNITY] L3 `similar` band is defined on the store's `1 - distance/2` quantity, which for vec0's cosine-distance metric is `(1 + cos)/2`, NOT true cosine (maps cos 0.65 → 0.825) — the band [0.75, 0.90) is tuned against that same non-cosine scale as `dup_cosine_threshold`, per the existing DEBT note; do not unify to real cosine without re-tuning both.

## Verification
- `uv run pytest -q tests/test_doc_refs_implicit.py` → 3 passed (verify_cmd).
- Tests cover: unlinked mention → one `mentions` edge, explicit link suppresses it; in-band neighbour → `similar` with score, below-band → none, duplicate excluded; incremental recompute of one doc leaves another's implicit edges unchanged.

RED_EVIDENCE:
  cmd: uv run pytest -q tests/test_doc_refs_implicit.py
  test_sha: 61400bd
  output: |
    >       assert before  # base has a similar edge
    E       assert set()
    =========================== short test summary info ============================
    FAILED tests/test_doc_refs_implicit.py::test_mention_edge_unless_explicitly_linked
    FAILED tests/test_doc_refs_implicit.py::test_similar_band_scored_and_excludes_dups
    FAILED tests/test_doc_refs_implicit.py::test_incremental_only_recomputes_driver
    3 failed in 0.80s
  note: captured with status.py reverted to origin/dev and implicit_refs.py removed, then restored. Proves no mentions/similar edges exist without the implementation.

## review-trovex verdict: SHIP
2 files + 1 new module + 1 new test. New logic isolated in implicit_refs.py; status.py edit is a scoped call after dup detection. No schema change (new doc_refs kinds only). No recall/owner-tag/upsert change; no secret/brand/host/number leak; no new .md on disk.

## 3. Files changed

```
features/DEBT.md                                   |   1 +
 ...ked-mentions-semantic-similar-neighbours-com.md |  78 +++++++++
 src/trovex/implicit_refs.py                        | 188 +++++++++++++++++++++
 src/trovex/status.py                               |   8 +
 tests/test_doc_refs_implicit.py                    | 135 +++++++++++++++
 5 files changed, 410 insertions(+)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `07b7cdc4-db1c-41ac-8aec-b502c9bab316`._
