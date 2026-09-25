# [trovex/security] loopback guard fails OPEN when X-Forwarded-For is absent: a non-loopback request without XFF is treated as local and can read the write token (strix vuln-0001) — fail closed on the real peer address

## Team : trovex-backend (tsukumo)
## Branch : fix/loopback-xff-fail-closed (from dev)
## Relay task : 21c1370f-097a-43aa-bfdb-85476ad3fd5c
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. pinned regression test: X-Forwarded-For is never consulted by the loopback guard — a non-loopback peer with no XFF gets 403, a loopback peer with XFF=8.8.8.8 is judged on the peer only; and a source-guard test that server.py never reads the forwarded-for header
- [ ] 2. defense in depth for the Docker-NAT case: when the server is bound to a non-loopback host (TROVEX_HOST != 127.0.0.1/::1), GET /api/write-token is disabled (403 with a message pointing at <data_dir>/.write_token) even for a 127.0.0.1 peer; loopback-bound servers keep today's behaviour; pinned tests for both bindings
- [ ] 3. audit of every other 'local-only' check in server.py / mcp_app.py (grep _is_loopback and client.host): each listed in the PR body with verdict keep / harden, and any that gates a secret gets the same non-loopback-bind rule
- [ ] 4. make test green; PR carries the review-trovex verdict; submitted through the gate against dev

## 2. Root cause & decisions

ROOT_CAUSE: strix's own report (run1 vuln-0001) claims "the loopback guard checks X-Forwarded-For and fails open when absent". That mechanism has never existed in this code: `_is_loopback()` (src/trovex/server.py) has checked only `request.client.host` against `{127.0.0.1, ::1, localhost}` since its introduction (commit ff0e48ce, the original fail-closed-writes commit) — `grep -rin 'forwarded-for' src/ tests/` is empty on both `dev` and `origin/main`. Verified with cto-tsukumo before writing code (relay thread on task 21c1370f) rather than implementing a fix for a mechanism that isn't there.

The real, reproducible mechanism: strix's run1 sandbox (`ghcr.io/usestrix/strix-sandbox`) reached trovex via `host.docker.internal` with the app bound to `0.0.0.0` for container reach. macOS Docker Desktop's vpnkit terminates a container's connection to `host.docker.internal` locally and re-establishes it toward the host process, so `request.client.host` on the FastAPI side legitimately reads `127.0.0.1` even though the true origin was a container — a Docker-Desktop-vpnkit loopback-NAT bypass, not header spoofing. `_is_loopback`'s peer-only check can't distinguish that from a real same-machine caller.

DECISION (cto-tsukumo steer, task 21c1370f, amended ACs): defense in depth, narrow, no new trust surface —
1. Regression tests pin that X-Forwarded-For is never consulted (peer decides, header is inert either direction) plus a source guard that server.py never gains a `headers.get(...forwarded...)` lookup.
2. When the server is bound to a non-loopback interface (`TROVEX_HOST` != a loopback host — the fleet host runs `TROVEX_HOST=0.0.0.0` for dokan containers), `GET /api/write-token` is disabled outright (403, pointing at `<data_dir>/.write_token`) even for a peer that reads `127.0.0.1`. A loopback-bound server (the default, and every normal end-user install) is unchanged.
3. `cli._run_server` now mirrors its `host` argument into `TROVEX_HOST` before `build_app()` constructs the process-wide `Settings()`, since `serve --host` is a CLI flag that deliberately does not read env (see serve-trovex.sh's own comment) and previously never reached `Settings.host` at all — the new guard needs the REAL bind host to make its call.

REJECTED ALTERNATIVES:
- "Only honour XFF for a configured trusted-proxy list" (the ticket's original AC#2, before the steer): rejected — there is no XFF-trusting code path to configure trust for; adding a trusted-proxy allowlist mechanism that nothing ever populates is pure unused surface.
- A per-boot nonce / signed cookie for the write-token bootstrap: rejected by cto-tsukumo steer — out of scope, adds complexity the bind-awareness check doesn't need.
- Trusting `settings.host`'s existing env-only resolution (TROVEX_HOST) without wiring the CLI flag into it: rejected — the fleet host's actual invocation (`serve-trovex.sh`) passes `--host 0.0.0.0` as an explicit flag, never sets the env var, so `settings.host` would have silently stayed "127.0.0.1" (the field default) while uvicorn was actually bound to 0.0.0.0 — the exact gap AC#2 exists to close.

AUDIT (AC#3) — every "local-only" / `client.host` decision in server.py and mcp_app.py:
| site | mechanism | gates a secret? | verdict |
|---|---|---|---|
| `server.py:218 _is_loopback()` / `:1025 GET /api/write-token` | `request.client.host` peer check | yes — the write token | HARDENED this PR (non-loopback-bind disable, AC#2) |
| `mcp_app.py:93-115` `TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=[...])` | MCP SDK's own Host-header allowlist (127.0.0.1/::1/localhost/host.docker.internal + `TROVEX_MCP_ALLOWED_HOSTS`) | yes — the whole MCP write surface (`trovex_write` etc.) | KEEP — different, sound primitive (Host header is what DNS-rebind protection is supposed to check, deny-by-default, SDK-maintained); not the client.host/XFF failure pattern, no fail-open observed |
| `server.py:331 Limiter(key_func=get_remote_address)` (slowapi) | `request.client.host` used as a rate-limit bucket key | no — buckets a quota, grants nothing | KEEP, out of scope (a spoofed/shared key just shares a quota, not a trust decision) |

No other `request.client`, `.client.host`, or header-based trust check exists in either file (verified via full-file grep, not sampled).

Pinned by tests/test_security.py: test_write_token_loopback_peer_succeeds_when_loopback_bound, test_write_token_ignores_forwarded_for_header, test_server_py_never_reads_forwarded_for_header, test_write_token_disabled_on_non_loopback_bind_even_for_loopback_peer (+ the existing test_write_token_endpoint_refuses_non_loopback). V-model verified: reverting server.py's guard change makes test_write_token_disabled_on_non_loopback_bind_even_for_loopback_peer fail (200 instead of 403); with the fix, 502 passed.

Prod (`:8765`, `origin/main`, launchd) already runs `TROVEX_ALLOW_UNAUTH_WRITES=1` — the write-token gate is bypassed there by design regardless of this fix, so nothing changes for the fleet host; this closes the gap for a normal dev box that binds non-loopback (Docker Desktop users) without one.

## review-trovex verdict: SHIP
review-trovex: SHIP — 3 files, ~150 LoC (server.py +~25/-3, cli.py +~7/-1, tests/test_security.py +~90) — gate green (ruff clean, pytest 502 passed), no Active-Memory/doc-router surface touched, no secret value in code/PR/relay (only the literal placeholder string "<data_dir>/.write_token"), no brand/host leak, no contract break (write-token route behavior unchanged for the default loopback bind; new 403 only on an explicit non-loopback bind, which is already an opt-in warned-about posture per cli.py's own "binding ALL interfaces" console warning), V-model pinned.

## 3. Files changed

```
src/trovex/cli.py      |  8 +++++
 src/trovex/server.py   | 34 ++++++++++++++++++---
 tests/test_security.py | 82 ++++++++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 120 insertions(+), 4 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `21c1370f-097a-43aa-bfdb-85476ad3fd5c`._
