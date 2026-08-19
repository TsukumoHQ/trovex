# aa08ffaa

## Team : trovex-backend (tsukumo)
## Branch : feat/namespace-dedup (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

## review-trovex verdict: SHIP

ROOT_CAUSE: The near-duplicate guard compared ACROSS unrelated kinds and probed
with a NON-title-fused vector. A governance audit was blocked as ~92% similar to a
stale checkpoint, and force=true was needed for genuinely-new docs. Two paths
shared the bug: store.check_duplicate (interactive block-and-point) and
status.detect_duplicate_for (the live auto-flagger). Post-c41904dd the auto-flag
bug is worse: a cross-kind false flag sets status='duplicate', which now EXCLUDES
the doc from retrieval — silently hiding a legit governance doc.

DECISION: Namespace dedup by (source_id, kind); compare like-with-like.
- check_duplicate(content, title, kind, source_id): ephemeral kinds
  (record/checkpoint/resume) excluded as DRIVERS (return None early) and as
  NEIGHBOURS (SQL class filter). Probe is title-fused (title+content) to match
  stored vectors. k widened to 20 because sqlite-vec applies k BEFORE the WHERE
  class filter, so a same-kind neighbour could otherwise be squeezed out by nearer
  other-kind docs. Threshold via settings.dup_threshold_for(kind).
- mcp_app.py:401 passes kind, TROVEX_SOURCE_ID, and _extract_title(content) — the
  exact title the store fuses on a CREATE (the only path that calls the guard).
- status.detect_duplicate_for gets the SAME namespacing (same-source, same-kind,
  non-ephemeral, per-kind threshold, widened k) — necessary so a cross-kind
  false flag can't hide a doc.
- config: dup_cosine_threshold_by_kind (per-kind override, env JSON) +
  dup_ephemeral_kinds + Settings.dup_threshold_for/is_ephemeral_kind helpers.
  dup_cosine_threshold kept as the default/fallback (back-compat).

REJECTED / OUT OF SCOPE: status._detect_duplicates (the RETIRED batch flagger, run
only by the retired indexer) left untouched — not in the live path; touching it
adds risk for no runtime benefit. Noted as a latent inconsistency if ever
re-enabled.

VERIFICATION: new test asserts a governance doc is NOT blocked against a
same-topic checkpoint AND the checkpoint is never auto-flagged a duplicate of the
governance doc; a genuine same-kind near-copy IS still blocked. Existing near-dup
test updated to pass the incoming kind (reflects the namespaced semantics). Full
gate green: ruff check src tests, pytest -q -> 349 passed, brand guard clean.

review-trovex: ✅ ship — 5 files (config/store/status/mcp_app + tests), gate green
(ruff + pytest 349 passed), brand clean, no schema/wire change (only a new
optional config field + widened kwargs, all defaulted/back-compat), no
secret/host/number leak.

## 3. Files changed

```
src/trovex/config.py        | 21 +++++++++++++++++++
 src/trovex/mcp_app.py       | 12 +++++++++--
 src/trovex/status.py        | 34 ++++++++++++++++++++----------
 src/trovex/store.py         | 47 +++++++++++++++++++++++++++++------------
 tests/test_active_memory.py | 51 +++++++++++++++++++++++++++++++++++++--------
 5 files changed, 130 insertions(+), 35 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `aa08ffaa`._
