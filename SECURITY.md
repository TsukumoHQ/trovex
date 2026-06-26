# Security Policy

## Trust model

trovex is **local-first and single-tenant**. It runs on your own machine (or your own
server), indexes **your own** docs, and serves them to **your own** agents. It is not a
multi-tenant SaaS and does not try to isolate one user's data from another's — there is one
user: you.

Concretely, that means:

- **`project_root` is trusted.** trovex indexes the directory tree you point it at. Files in
  that tree are assumed to be yours. (The indexer still refuses to follow a symlink whose
  real target escapes `project_root` — see below — so an in-repo symlink can't pull
  `/etc/passwd` into the index.)
- **Filesystem scope.** trovex only ever reads from the configured source roots (the
  symlink/traversal guard keeps reads inside them) and only writes to its own `data_dir`
  (the SQLite store, backups, and the write-token file). It does not write to your source
  files and runs no shell. Hook downloads (`/hooks/<name>`) are served only from the
  configured hooks dir (`TROVEX_HOOKS_DIR`, default `~/.claude/hooks`) or the bundled repo
  copy, restricted to a fixed allowlist of filenames, with path-traversal / URL-encoded
  names rejected.
- **Mutations are gated by a write token — and the default is fail-closed.** Writes
  (`trovex_write` / `trovex_tag` / `trovex_delete` over MCP, and the mutating HTTP endpoints
  `/api/doc`, `/api/collections`, `/api/backup`, `/api/capture`, `/api/reindex`) require the
  `X-TROVEX-Write-Token` header.
  - Set `TROVEX_WRITE_TOKEN` to share one token across machines/agents.
  - If you set **nothing**, trovex **auto-generates a per-instance token on first run** and
    persists it to `<data_dir>/.write_token` (chmod 600). Same-machine tooling reads that
    file; the local browser UI fetches it from the loopback-only `/api/write-token` endpoint.
    A network-exposed instance that cannot read the file (or reach loopback) therefore
    **cannot write** — anonymous writes are denied by default.
  - To deliberately run with **open writes** (e.g. a throwaway localhost instance), set
    `TROVEX_ALLOW_UNAUTH_WRITES=1`. This is logged loudly at startup and is the only way to
    get the old open-by-default behaviour.

  This is a posture change from earlier versions, where an unset token meant open writes. It
  is not a claim of network-grade auth: a single shared bearer token, no rotation, no
  per-user scoping. For an untrusted network, still front trovex with a reverse proxy.
- **Bind address matters.** The default `TROVEX_HOST=0.0.0.0` listens on all interfaces. If
  the machine is reachable from an untrusted network, set a write token and/or front trovex
  with a reverse proxy that handles authentication and TLS.
- **The browser UI is part of the trusted surface.** The HTML dashboard issues the same API
  calls an operator would. It sets no cookies and holds no session; the write token (when
  configured) is the only mutation gate. Treat access to the UI as operator access.

## What's hardened

These were tightened in response to a public MCP-registry security scan. They reduce the
blast radius of malformed or hostile input; they are not a claim that trovex is unbreakable.

- **Fail-closed writes by default.** With no token configured, trovex auto-generates and
  persists a per-instance write token instead of leaving writes open (see *Trust model*
  above). Opt back into open writes only via `TROVEX_ALLOW_UNAUTH_WRITES=1`.
- **Hook downloads are allowlisted + traversal-proof.** `/hooks/<name>` serves only a fixed
  set of filenames from a configurable dir (`TROVEX_HOOKS_DIR`); separators, `..`, and
  percent-encoded names are rejected, and the resolved path must stay inside the base dir.
- **Path-filter validation.** The `qpath` browse filter is length-capped and
  charset-restricted (`422` on malformed); regex-on-content helpers cap how much text they
  scan, so a very large doc can't drive pathological regex cost.
- **Query-log retention + redaction.** `mcp_queries` rows older than
  `TROVEX_QUERY_RETENTION_DAYS` (default 90) are purged at startup, and obvious secrets /
  emails are redacted from the stored query text.
- **`/api/reindex` is write-gated** like the other mutating endpoints (was unauthenticated).
- **LIKE-filter escaping.** Browse/autocomplete filters escape SQL `LIKE` wildcards
  (`%`, `_`) and use `ESCAPE '\'`, so a query of `%` filters literally instead of matching
  the whole store. (All SQL uses parameterised queries; this closes the wildcard-as-input
  gap on top of that.)
- **Per-IP rate limiting** on the search and write endpoints (`slowapi`), tunable via
  `TROVEX_RATE_LIMIT_SEARCH` / `TROVEX_RATE_LIMIT_WRITE`.
- **Symlink / path-traversal guard** in the indexer: each file path is canonicalised and
  skipped if its real target escapes `project_root`. `.trovexignore` globs are honoured.
- **Input validation** on `kind` / `tags` query params (length, character set, tag count).
- **Malformed JSON** request bodies return `400`, not an unhandled `500`.
- **Log redaction:** user queries are truncated before they reach the logs.
- **Dependency audits in CI:** `npm audit --audit-level=high` (web) and `pip-audit` (Python)
  run on every PR and fail the build on a known vulnerability, so this can't regress quietly.

## Reporting a vulnerability

Please report security vulnerabilities **privately** — do **not** open a public issue.

Use GitHub's private vulnerability reporting: open the repository's **Security** tab →
**Report a vulnerability** (GitHub Security Advisories). The report is delivered privately
to the maintainers.

We aim to **acknowledge new reports within 3 business days** and will keep you updated as we
investigate and ship a fix. Please give us a reasonable window to remediate before any public
disclosure.

## Supported versions

trovex is pre-1.0; security fixes land on the latest released version (see the latest tag /
the package on PyPI). Please reproduce against the latest release before reporting.
