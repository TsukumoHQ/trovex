# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/). trovex's
version is git-tag-derived (`hatch-vcs`, see `pyproject.toml`) — this file's
entries are what actually shipped in each tagged release, not a bump target.

## Unreleased

### Added
- Opt-in chunk-level indexing for an fs source's markdown (`chunk_markdown` on the
  source, default off) so `tier=passage|card` reads and the `file://` anchor
  links work on fs `.md` docs. `trovex sources chunk-markdown <id> [--dry-run|--off]`
  projects the chunk + embed cost, refuses when the source's partition would pass
  the vec0 KNN ceiling (journaled in `source_runs`), otherwise backfills the docs
  already indexed (task:52385ebc).
- Connector protocol (`trovex/connectors/base.py`: `list_slim` / `poll(cursor)` /
  `fetch`) with `FsConnector` as the first implementation, a `sources` table
  that replaces `sources.yaml` (imported once on the first start; manage it with
  `trovex sources list|add|disable`), and `sync_source` / `gc_source` jobs on
  the index_jobs applier. Each job writes a `source_runs` row with its cursor,
  ok/failed counts and failed ids; the next sync replays only the failed ids.
  `gc_source` aborts when the listing returns fewer than `deletion_safety_ratio`
  of the known ids, otherwise moves missing docs to `pending_delete` and
  hard-deletes them after the grace window. Nothing enqueues these jobs yet: the
  poll/gc scheduler is the next slice (task:960a4b64).

### Fixed
- MCP registry publish of v0.15.1 400'd (`PyPI package 'trovex' exists, but
  version '0.13.4' was not found`): server.json lists one `packages[]` entry
  per transport (stdio + streamable-http) of the same PyPI package, but
  `publish-mcp.yml`'s sync step only updated `packages[0].version`, leaving
  the 2nd stale at whatever was last hand-committed. Sync now updates every
  `packages[].version` and fails the workflow step if any still disagrees
  with the tag afterward, instead of shipping a `server.json` the registry
  rejects (task 5c18adb7).

## 0.15.1

### Fixed
- `trovex import` / `trovex onboard` crashed on every install (`ImportError:
  cannot import name 'onboarding' from 'trovex'`) — `src/trovex/onboarding.py`
  was never committed to git, so the module existed only on the original
  author's machine. Committed the module, with unit + CLI regression tests and
  a source guard that fails `make test` if any `src/trovex/*.py` relative
  import ever again points at a module that doesn't ship (task 7111f05a).
  Note: this entry originally shipped mislabeled `## 0.13.4` — a guessed
  version number that was never actually tagged (PyPI was already past
  0.15.0); corrected here to the tag that really carried this fix.
- Loopback guard (`GET /api/write-token`) is now disabled outright on a
  non-loopback bind (`TROVEX_HOST` != a loopback address — the fleet-host
  0.0.0.0 case), not just peer-address-checked, closing a Docker-Desktop-
  vpnkit gap where container traffic can present as `127.0.0.1` (task
  21c1370f).
