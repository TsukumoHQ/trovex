---
name: review-backend
description: Domain review checklist for the trovex backend — the Python/FastAPI + sqlite-vec/fastembed retrieval engine, the MCP server (trovex/trovex_write/read/search/tag/delete + catalog resources), and the Active-Memory boot/capture loop. Applies to a diff touching src/trovex, scripts (CI guards), tests, benchmarks, deploy, or pyproject/server.json. Ordered highest-weight first: recall/data integrity lead, validation & test discipline trail. Each item is a judgment call a linter/pytest/security-guard does NOT already make.
paths: src/, src/trovex/, scripts/, tests/, benchmarks/, deploy/, pyproject.toml, server.json, .trovexignore
---

# review-backend — trovex backend review gate

The backend's product IS retrieval correctness and token-efficiency, served to agents on their critical path. The worst failure here is **silent-wrong**: an agent gets empty or cross-injected recall, or a clobbered record, and has no signal anything broke. This checklist targets exactly the judgment those failures need.

**Already covered by tooling — do NOT re-flag here** (they fail CI mechanically): ruff lint (E/F/I/N/UP/B/SIM/RUF), the pytest suite incl. `tests/test_security.py`, `scripts/security_guard.py` (eval/exec/os.system/shell=True/pickle/yaml.load/`__import__`, hardcoded-secret literals, raw-SQL interpolation, tracked credential files), `scripts/brand_guard.py`, `pip-audit`, and `test_server_json_sync`. If the only issue is one of those, it's a tooling job, not a review finding.

Work the branches **in order**. Design & data-integrity concerns lead; validation and test hygiene trail.

---

## 1. Recall & retrieval integrity — the crown jewel

A retrieval bug returns *something plausible*, so it never trips a test the author thought to write. Scrutinize any change under `search.py`, `store.search_chunks`, `boot.py`, or a new query path.

- **Scope-before-score, and widen the pool on a filtered query.** `sqlite-vec` applies its `k` (candidate pool) *before* the metadata filter runs, so a tightly-scoped query over a skewed corpus gets squeezed out of the pool before it is ever filtered — a 14-doc project inside a 2831-doc store returned **zero** hits at `pool=50`. `Searcher.search` must over-fetch when any filter is on (`pool=max(limit*5,50)`) **and** retry once over the whole index when a filtered query still comes back short (`search.py:96-100`). A new filtered retrieval path, or a change to `k`/`pool` that drops the widen-and-retry, silently starves recall — because an agent handed an empty result set has no way to know the answer existed. ([post-filtering starves recall when the filter is selective — Achilles Heel of Vector Search](https://yudhiesh.github.io/2025/05/09/the-achilles-heel-of-vector-search-filters/))
- **Never gate recall on an absolute score floor alone.** Owner/kind/tag scope yields precision≈1 *by construction*; the `floor` (default 0.62 in `boot_pointers`) is a secondary trim applied **after** scope, never the primary filter. A recall path that thresholds on score without scoping first cross-injects another agent's or domain's docs — semantic scores cluster ~0.6–0.7, so an in-domain-absent query sits right on the floor and pulls whatever's nearest. Because a memory system that recalls the *wrong* agent's state is worse than one that recalls nothing.
- **Owner tags are lowercased on BOTH write and read.** `capture_state` writes `owner/{agent.lower()}` and `boot_pointers` queries `owner/{agent.lower()}`; the store also lowercases tags on write. Drop the `.lower()` on either side and a mixed-case agent (`COO`, `CTO`) recalls nothing of its own — permanent, silent memory loss for that identity. Any new owner-scoped read or write must normalize case, and the case path must be regression-tested. Because the mismatch produces empty recall, not an error.
- **Whole-prompt inputs truncate; they never 422.** The prompt hook passes the *entire* user prompt as the boot query, and the hook swallows errors — so rejecting a long query on length is a silently-dropped recall, not a visible failure. Truncate head-first to the encoder window (`BOOT_Q_MAX=2000` ≈ the 512-token bge-small limit; task identity leads, boilerplate trails) rather than adding a hard cap that drops the call. Because a lost recall here is invisible to the agent and the operator both.

## 2. Write-side data integrity

Owned docs are the system of record for agent memory and coordination. A bad write is unrecoverable to the agent that trusted it.

- **Stable `ext_id` ⇒ in-place upsert, and UPDATE must never hit the dup-block.** The near-duplicate block fires only on CREATE (no `doc_id`, no `force`); a write with `doc_id` set must bypass it (`mcp_app.trovex_write`, `store.check_duplicate`). Route updates through the dup guard and the canonical `owner-<agent>-current-state` record can never be refreshed — active-memory freezes. Because one-canonical-doc-per-topic depends entirely on the deterministic-id overwrite path staying open.
- **Section write is patch-or-refuse — it must NEVER fall through to a whole-doc overwrite.** `replace_section` returns `None` when the heading isn't found, and the caller hard-errors writing nothing (`store.py:716`, `mcp_app.py:317`). A new section-aware write that "falls back" to overwriting the whole doc on a missing heading reintroduces exactly the data-loss this guards. Because a silent whole-doc clobber destroys the record the agent meant to patch one line of.
- **Every delete goes through `delete_doc_cascade`.** SQLite FK enforcement is OFF and *cannot* simply be enabled (`docs.dup_of_id` is a NO-ACTION self-reference carried by ~2/3 of rows), so a bare `DELETE FROM docs` orphans chunks, `vec_docs`, `vec_chunks`, `chunks_fts`, tags, and versions — a live store reached 2395 orphaned `doc_tags`. Both delete paths (store-owned and indexer file-backed) must call `delete_doc_cascade`, never raw SQL. Because orphan rows silently corrupt counts, facets, dedup neighbours, and the vector index.
- **An overwrite snapshots the prior content first.** `put()` inserts a `doc_versions` row before the UPDATE so the write is undo-able (`restore_version` depends on it). A new write path that skips the snapshot loses history with no warning. Because "I overwrote my own record and can't get it back" is a data-loss the versioning exists to prevent.

## 3. The reserved source id

- **No configured source may be named `trovex`.** Owned docs live under the virtual `source_id='trovex'` that the file indexer never scans; a real source claiming that id makes `reindex()` treat every owned doc (captures, receipts, verdicts) as a *vanished file* and cascade-delete it. The guard is defense-in-depth in **both** `config.load_sources` (drops it with a warning) and `indexer.reindex` (filters again) — a change touching source resolution must keep both layers, not "simplify" one away. Because a single reindex would silently and irreversibly destroy the entire owned store.

## 4. Auth on mutating surfaces + secret handling

`security_guard.py` catches literal secrets, `eval`, and raw SQL. It does **not** catch a *missing* auth check or a leaked credential in a new code path — that's this branch.

- **Every new mutating MCP tool or `/api` write endpoint fail-closes behind the write token.** `trovex_write/tag/delete` gate on `_authorized()`; the HTTP writers call `_write_authorized()` as their first line. A read-only tool that quietly gains a side effect, or a new `POST`/`DELETE`/`PUT` that forgets the gate, is an unauthenticated mutation on a possibly network-reachable instance. The token is fail-closed by default (auto-generated + persisted), so the *only* thing enforcing it is that check being present. ([MCP least-privilege: a "read" tool must not silently become "write"](https://workos.com/blog/mcp-authorization-patterns-per-tool-scopes))
- **Token comparison is constant-time.** Use `secrets.compare_digest`, never `==`, on the write token — a plain `==` is a timing oracle for the secret. Because the token guards every write on the box.
- **BYOK secrets never persist and never log.** The caller's OpenAI/rerank key and write token live in request-scoped contextvars only; query text passes through `redact_secrets()` before it lands in `mcp_queries`. A new path that logs the raw query, echoes the key back in a response, or writes it to the DB leaks the *user's* credential. Because these are the caller's keys — trovex is a pass-through, not a store, and the local-first promise is void if a key hits disk.
- **The write token is handed out to loopback only.** `/api/write-token` refuses non-loopback clients so a network-exposed instance never leaks it. A new "convenience" endpoint that returns or logs the token more liberally quietly defeats the fail-closed design. Because same-machine bootstrap is the *only* reason the token is ever served.

## 5. Never crash the agent — best-effort vs. genuine error

- **Non-essential side-effects are wrapped so they cannot raise into the tool response; genuine errors must NOT be swallowed.** Logging, the query-cache, dedup flagging, rerank, distil, and retention purge are all `try/except → log.debug` because the tool sits on the agent's critical path (`mcp_app.py`, `store.put`'s dedup, `rerank.maybe_rerank`, `capture.distil_summary`). Review a new `try/except` for which side of the line it's on: swallowing a *real* error (auth failure, unknown source, malformed input) turns a loud failure into a silent-wrong; letting a *best-effort* side-effect propagate crashes the agent's tool call. The judgment is per-except — one shape is required, the other is a bug. Because both directions of getting this wrong are invisible until an agent is stuck.

## 6. Local-first & privacy defaults

- **Don't flip a privacy-preserving default.** The embedder defaults to **local** fastembed (no key, nothing leaves the machine); the host defaults to **127.0.0.1** (the `/usage` `/insights` query-log views are read-open, so an all-interfaces bind exposes the team's query text to anyone who can reach the port); query-log retention purges at 90 days. A change that defaults embeddings to OpenAI, binds `0.0.0.0`, or disables retention silently ships code/docs to a third party or exposes sensitive query text. Opting *in* (via env) is fine and expected; changing the *default* is the breach. Because these defaults literally are the "your data stays on your machine" promise the product is sold on.

## 7. Schema & embed-dim safety

- **A schema change ships an idempotent, ordered migration.** Migrations run *before* `_init_schema` and must check current state first — additive `ALTER ADD COLUMN` for a nullable column, a full table rebuild only when a constraint changes (see `db._migrate_*`). Because the DB is long-lived on a user's machine; a non-idempotent or mis-ordered migration corrupts an existing store on the next `trovex` launch, not in CI.
- **Changing the embed model or dimension forces a reindex and wipes BOTH vec tables.** `embed_dim` must match the model or `sqlite-vec` knn breaks outright; leaving `vec_chunks` at the old dim crashed *every* `trovex_write` with "Expected N dimensions" after a model switch (found live). `_migrate_embed_dim` drops `vec_docs` **and** `vec_chunks` + chunk rows and clears `content_hash` to force re-embed. A dim change that touches only one vec table is a hard runtime failure waiting for the first write. Because a dimension mismatch is a crash, not a quality regression.

## 8. Token-efficiency & honest numbers — the product's whole pitch

- **Default tool output stays minimal; return passages, not whole docs.** `trovex` returns one line per hit; `trovex_read`/`trovex_search` return the best-matching passage via small-to-big (`section_text`), not the full body unless `full=true`. A change that fattens the default response, or returns whole docs by default, spends the exact tokens trovex exists to save. Because minimal-by-design is the reason an agent calls trovex instead of grepping.
- **Savings figures reflect the real measured model — never a fabricated multiple.** `saved = top-3 tokens − top-1 − response` (`savings_estimate`); the dashboards render that, not an invented `Nx`/`%`. A change to the savings math that inflates the headline without a real basis is a credibility defect on a public surface. Because the savings claim is the product's proof-of-value; a number that can't be traced to a measurement is worse than no number.

## 9. Validation & test discipline (trailing — lowest weight, but still judgment)

- **A new user-facing param that reaches a LIKE / regex / SQL clause is length-bounded and charset-validated before it gets there.** `kind`/`tags`/`qpath` carry regex + length caps and `MAX_TAGS`; free-text substring filters pass through `like_escape`; the highlight-term class is deliberately `[a-zA-Z0-9]{2,}` so escaped terms can't split an HTML entity or drive ReDoS. `test_security.py` regression-covers the *existing* params — the judgment is the **new** one: don't add a param that reaches the query layer raw, and don't widen the highlight class without revisiting `_highlight`'s escaping assumption. Because the guard is per-param and a fresh param is outside the existing tests.
- **New route → a test; new retrieval/capture/boot path → a behavior test; all tests stay hermetic.** A new HTTP route needs a `tests/test_server.py` TestClient case (inject `AppState`, no real lifespan); a new scope/case/floor path needs a test that exercises *that* behavior. Tests must use the `BagEmbedder` (no model download) and never call a real embedder, OpenAI, or the network — a test that needs live inference is written wrong and must be mocked. Because CI is hermetic (~13s) and a network-dependent test is both flaky and a silent hole in the gate.

---

## Verdict shape (for the Q&A gate)

Rank findings by branch order — a §1 recall bug or a §2/§3 data-loss outranks any number of §9 nits. For each finding name the file:line, the invariant it breaks, and the **silent** failure it produces (empty recall / clobbered record / leaked key / crashed tool), because "looks fine, passes tests" is exactly the state every item here is designed to catch.
