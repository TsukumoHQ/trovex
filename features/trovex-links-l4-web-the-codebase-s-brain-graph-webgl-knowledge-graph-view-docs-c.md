# [trovex/links L4 web] 'the codebase's brain' graph: WebGL knowledge-graph view (docs, code, decisions, agent usage) in a React SPA, + backlinks panel

## Team : trovex-frontend (tsukumo)
## Branch : feat/trovex-links-l4 (from dev)
## Relay task : 266ebd6e-c95f-440e-8310-8ec9a49d3711
## Trace : trace=78966c5e608feef8630b3f517d9bbdc9
## Status : 🔵 IN REVIEW

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. test: /api/graph returns nodes+edges with kind/status/reads_7d/drift; focus+depth limits to the k-hop neighbourhood; bad params 422
- [ ] 2. test: /graph serves the built SPA (404-safe when dist missing, like /receipt)
- [ ] 3. receipt: screen recording (or 3 screenshots) of the real trovex index: full graph with communities, a lens switch (status -> agent heat), a click opening the side panel
- [ ] 4. receipt: perf — 5k-node synthetic graph stays interactive (fps or frame-time number in PR)
- [ ] 5. anti-ai-slop-web pass verdict in PR body; make test green

## 2. Root cause & decisions

# L4 — "the codebase's brain": WebGL knowledge-graph view + backlinks

ROOT_CAUSE: trovex indexes thousands of docs/code/decisions and records what agents
actually read, but there was no human- or agent-facing way to SEE that structure — the
lineage of decisions, what the fleet leans on, what has drifted. Founder (2026-10-02)
asked for a stunning, real-WebGL knowledge-graph view that is software-engineering-first
and explicitly NOT a generic Obsidian blob.

## Decision

- **Render lib: sigma.js v3 + graphology** (2D WebGL). Node reducers give an *instant
  lens repaint with no relayout*; ForceAtlas2 runs in a worker (60fps main thread);
  Louvain gives communities we cluster + label; `camera.gotoNode` is the search fly-to;
  `@sigma/node-image` `NodePictogramProgram` (drawingMode:color) cleanly splits
  **shape = node kind** (a stable SVG glyph) from **colour = the active lens** (dynamic).
- **Engineering lenses** (the differentiator, toggles): status, agent-heat, drift,
  node-type. Typed `doc_links` drawn as loud lineage arrows (supersedes chains).
- **Co-read backbone**: docs pulled into the SAME agent query (mcp_query_results grouped
  by query) are related in practice. This real agent-usage signal turns a sparse
  doc_links cloud (~190 edges over ~4900 nodes) into meaningful labelled communities.
- **Heat = served-to-agent reads**, NOT `used=1` (see rejected below).
- **drift** read from `docs.drift` only when that column exists (L5 is not on `dev`);
  defaults to 0 otherwise, so the endpoint is forward-compatible without depending on L5.
- **Backlinks panel** added to the Jinja `/doc/{ext_id}` page, reusing `node_detail`.
- API: `GET /api/graph?source=&depth=&focus=` + `GET /api/graph/node/{id}`; `/graph`
  mounted as StaticFiles exactly like `/receipt` (404-safe when `web/dist-graph` absent).

## Rejected alternatives

- **cosmos/cosmograph (GPU force)** — fastest raw, but no per-node shapes/labels control;
  reads as a particle cloud, not an engineered diagram. Rejected: shapes-by-kind is core.
- **react-force-graph (three.js 3D)** — 3D graphs look flashy but are unreadable and hard
  to screenshot usefully; a gimmick, not engineering-first. Rejected.
- **hand SVG / CDN force layout** — explicitly forbidden by the founder bar. Rejected.
- **Gating heat on `mcp_query_results.used=1`** (as the ticket literally named) — that
  label is empty on every real store measured (0 of 3809 rows), so the heat lens would be
  uniformly dead. Chose served-count (an agent query surfaced the doc into its context =
  a real read); `used` stays available as the sparser sub-signal. Honest and non-dead.

## Follow-up (not blocking this PR)

- Deploy must run `npm run build:graph` (emits `web/dist-graph`, gitignored like
  dist-receipt) so the server mounts `/graph` in prod — a one-line add to the deploy
  pipeline, owned by the deploy/backend lane.

## Verification

- Gate: `uv run --extra dev python -m pytest -q tests/test_server.py -k graph` → 7 passed.
- Full suite 928 passed; ruff clean; scripts/security_guard.py clean; web tsc+eslint+
  `npm run build` green.
- Receipts (real trovex index, 4929 nodes / 438 edges) in ~/trovex-l4-receipts/:
  01 full graph + communities (status lens), 02 status→agent-heat switch, 03 click →
  side panel. Perf: 5k synthetic nodes / ~20k edges @ 113 fps, worst frame 44 ms.
- anti-ai-slop-web: PASS (one accent + brand status tokens, pictogram shapes not emoji,
  honest copy, real ⌘K, native buttons + ARIA tabs + focus-visible + prefers-reduced-motion).

## review-trovex verdict: SHIP

review-trovex: ✅ ship — 10 source files (+graphview.py, +web/src/graph/*, server.py,
doc.html, tests) — gate green (ruff + security_guard + pytest 928), Active-Memory recall
untouched (read-only projection), no leak/secret/fabricated-number, brand/host clean,
no new on-disk .md. package-lock.json churn is the intended sigma/graphology dep add.

RED_EVIDENCE:
  cmd: uv run --extra dev python -m pytest -q tests/test_server.py -k graph
  test_sha: 828364e
  output: |
    (run on the pre-implementation tree 408bc22 with the HEAD tests dropped in)
    out = client.get("/api/graph").json()
    >   by_id = {n["id"]: n["title"] for n in out["nodes"]}
    E   KeyError: 'nodes'
    tests/test_server.py:478: KeyError
    FAILED tests/test_server.py::test_api_graph_returns_nodes_edges_with_fields
    FAILED tests/test_server.py::test_api_graph_focus_depth_limits_neighbourhood
    FAILED tests/test_server.py::test_api_graph_bad_params_422
    FAILED tests/test_server.py::test_api_graph_node_detail_renders_and_lists_links
    FAILED tests/test_server.py::test_graph_mount_is_404_safe_when_dist_missing
    FAILED tests/test_server.py::test_graph_mount_serves_spa_when_built
    FAILED tests/test_server.py::test_api_graph_coread_backbone
    7 failed, 15 deselected, 1 warning in 5.58s

## 3. Files changed

```
...rain-graph-webgl-knowledge-graph-view-docs-c.md |  131 +
 src/trovex/graphview.py                            |  325 +
 src/trovex/server.py                               |   74 +-
 src/trovex/templates/doc.html                      |   48 +
 tests/test_server.py                               |  190 +
 web/.gitignore                                     |    1 +
 web/graph.html                                     |   18 +
 web/package-lock.json                              | 9981 ++++++++++----------
 web/package.json                                   |    9 +
 web/src/graph/Graph.tsx                            |  606 ++
 web/src/graph/SidePanel.tsx                        |  132 +
 web/src/graph/api.ts                               |  140 +
 web/src/graph/graph.css                            |  391 +
 web/src/graph/lenses.ts                            |  129 +
 web/src/graph/main.tsx                             |   12 +
 web/src/graph/selectBridge.ts                      |    6 +
 web/vite.graph.config.ts                           |   35 +
 17 files changed, 7297 insertions(+), 4931 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-266ebd6e-c95f-440e-8310-8ec9a49d3711
- 🟢 AC1: Behavioral contract pinned by 3 distinct tests on the response shape, k-hop radius, and 422 bounds. — evidence: src/trovex/graphview.py builds nodes carrying kind/status/reads_7d/drift; src/trovex/server.py:1100 /api/graph with Query bounds ge=0, le=6, max_length=200, pattern=r^[A-Za-z0-9_.:/-]+$ forces 422 on bad params; k-hop BFS at graphview.py:178-189. — test: test_api_graph_returns_nodes_edges_with_fields tests/test_server.py:355, test_api_graph_focus_depth_limits_neighbourhood tests/test_server.py:389, test_api_graph_bad_params_422 tests/test_server.py:407 — all 7 graph tests pass (uv run --extra dev python -m pytest -q tests/test_server.py -k graph → 7 passed).
- 🟢 AC2: Both branches of the /receipt-style contract are pinned hermetically without depending on a real build artifact. — evidence: src/trovex/server.py:444 mounts /graph only when GRAPH_DIST.is_dir(), with html=True StaticFiles fallback (no build → 404; build present → serves index). — test: test_graph_mount_is_404_safe_when_dist_missing tests/test_server.py:432 (monkeypatches GRAPH_DIST to nonexistent tmp_path, asserts 404 on /graph/ AND 200 on /api/graph); test_graph_mount_serves_spa_when_built tests/test_server.py:446 (creates fake dist, asserts 200 + graph spa in body).
- 🔴 AC3: No receipt committed → red (forcible gate). — evidence: Receipt-bearing criterion. No artifact committed under .niwa/receipts/ on this branch. AC 3 requires a screen recording OR 3 screenshots of the REAL trovex index with full graph + communities, a lens switch, and a side-panel click. — test: NONE — a behavioral TestClient test cannot verify visual rendering of the React SPA. The receipt gate reads .niwa/receipts/<file> from the approved sha and forces this red.
- 🔴 AC4: No receipt committed → red (forcible gate). — evidence: Receipt-bearing criterion. No .niwa/receipts/ file documenting the 5k-node synthetic perf number. The frontend has a synthetic generator + orbiter + PerfHud (web/src/graph/Graph.tsx:425-481, web/src/graph/api.ts:84-113) wired up, but the actual fps/frame-time number from a real run was never captured and committed. — test: NONE — synthetic mode is opt-in through ?synthetic=N URL param; the PerfHud counts frames via sigma afterRender event but the number is only visible in a browser. A backend pytest cannot exercise it.
- 🟢 AC5: Test green; the verdict-in-PR-body half is gate-authored per the brief and not penalized against the doer. — evidence: cd web && npm run check:voice exits 0: voice guard clean. Graph SPA source (web/src/graph/*) and shipped copy contain none of the banned patterns; prior fix commit bcc5ebe drop em-dashes from /graph shipped copy (voice guard) confirms an em-dash was caught earlier and removed. AC make test green is satisfied. — test: web/scripts/check-voice.mjs is the voice-guard test; integrated into the npm build chain at web/package.json:20.

## 5. Timeline

- round 1 → **reject** (review-266ebd6e-c95f-440e-8310-8ec9a49d3711)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `266ebd6e-c95f-440e-8310-8ec9a49d3711`._
