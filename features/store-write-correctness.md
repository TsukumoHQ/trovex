# store-write-correctness

## Team : trovex-backend (tsukumo)
## Branch : fix/store-write-correctness (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

# fix/store-write-correctness — 3 review follow-ups (steal #2 + #5)

Batches the store.put/search.py correctness findings from review-9d03f31d (steal
#2) and review-d1266690 (steal #5) — all in the same write/retrieval path, so one
cohesive PR instead of three.

ROOT_CAUSE (three, one path):
1. review-9d03f31d WARNING — store.put `content_unchanged` gate hashed only the
   body, not the title; embed_text (doc + chunk) fuses the title, so a title-only
   rewrite took the no-op early-return and left the OLD title in the vectors.
2. review-d1266690 WARNING (major) — the overwrite UPDATE omitted `lifecycle`, so
   re-writing an archived doc via its stable ext_id kept it archived: fresh
   content stayed hidden. For the Active-Memory owner-current-state doc (a stable
   ext_id that capture overwrites), an accidental archive would silently swallow
   every later capture.
3. review-d1266690 NOTICE ×2 — `_HIDDEN_LIFECYCLE` frozenset was dead (the check
   is inlined); and the always-on lifecycle filter wasn't reflected in the
   `filtered` flag, so an archived-heavy KNN pool could return an unfiltered query
   short with no widen-retry (recall squeeze).

## Decision

- **Title in the skip gate**: content_unchanged = content-hash match AND
  title unchanged. A title change now re-embeds (correct vectors); a truly
  identical (body+title) reput is still the no-op fast path.
- **Write resets lifecycle=active**: the overwrite UPDATE sets lifecycle='active'
  on every write (both the changed + early-return paths, one UPDATE). A write is
  a "this doc is live" signal — re-writing resurrects an archived doc into
  retrieval. Re-archive via trovex_archive after, if truly intended. Documented.
- **Dead code**: removed `_HIDDEN_LIFECYCLE`.
- **Widen-retry**: fires whenever a result comes back short (dropped the
  `filtered and` guard; the `total > pool` guard still prevents pointless
  retries), because the lifecycle exclusion is ALWAYS applied and can squeeze
  even an unfiltered query. Removed the now-unused `filtered` param from
  `_vector_rows`.

No schema change (uses existing lifecycle/content_hash columns).

## Gate

`uv run ruff check src tests` clean; `uv run pytest -q` → 340 passed (+5 new
test_store_write_correctness: title-only reput re-embeds, identical reput still
no-op, write un-archives (new + identical content), active doc surfaces despite
archived neighbours). brand + security guards green. Left pre-existing ruff-format
debt untouched (cto reflow).

review-trovex: ✅ ship — 3 files, ~155 LoC — gate green (ruff+pytest), correctness
fixes for the write/retrieval path (no schema, no wire change), no
leak/secret/number issue.

## 3. Files changed

```
src/trovex/search.py                  |  13 ++--
 src/trovex/store.py                   |  30 +++++---
 tests/test_store_write_correctness.py | 134 ++++++++++++++++++++++++++++++++++
 3 files changed, 158 insertions(+), 19 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `store-write-correctness`._
