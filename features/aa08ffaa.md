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

## Round 2 — addressed review-aa08ffaa r1 finding
ROOT_CAUSE (r1): the BATCH duplicate pass (compute_status → _detect_duplicates),
run by every reindex / fs-watch, was left un-namespaced — it would demote an owned
canonical governance doc to a duplicate-of-checkpoint (cross-kind, ephemeral
neighbour), and post-c41904dd that HIDES the doc from retrieval. My r1 judgment
that _detect_duplicates was "retired" was wrong: indexer.reindex + fs-watch call
compute_status.
FIX: namespace _detect_duplicates identically to the live paths — drivers exclude
ephemeral kinds; neighbours are same-(source_id, kind), canonical/plan, k widened;
per-kind threshold via settings.dup_threshold_for. Added _ephemeral_sql(settings)
(word-validated, config-controlled) for the batch IN-list.
TEST: test_batch_detect_duplicates_is_namespaced_by_kind — compute_status does NOT
demote a governance canonical against a same-topic checkpoint and never drives off
the checkpoint, while a genuine same-kind near-copy is still collapsed.
GATE: ruff + pytest 350 passed, brand clean.

## 3. Files changed

```
features/aa08ffaa.md        | 78 ++++++++++++++++++++++++++++++++++++++++
 src/trovex/config.py        | 21 +++++++++++
 src/trovex/mcp_app.py       | 12 +++++--
 src/trovex/status.py        | 87 +++++++++++++++++++++++++++++----------------
 src/trovex/store.py         | 47 +++++++++++++++++-------
 tests/test_active_memory.py | 87 ++++++++++++++++++++++++++++++++++++++++-----
 6 files changed, 278 insertions(+), 54 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-aa08ffaa
batch _detect_duplicates left un-namespaced: reindex/fs-watch silently demotes owned canonical governance doc to duplicate-of-checkpoint (cross-kind, ephemeral neighbour) — violates the branch's own dup_ephemeral_kinds invariant

## 5. Timeline

- round 1 → **reject** (review-aa08ffaa)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `aa08ffaa`._
