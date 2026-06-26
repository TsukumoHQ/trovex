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
- **Mutations are gated by a write token.** Set `TROVEX_WRITE_TOKEN` to require the
  `X-TROVEX-Write-Token` header on every write — `trovex_write` / `trovex_tag` /
  `trovex_delete` over MCP and the mutating HTTP endpoints (`/api/doc`, `/api/collections`,
  `/api/backup`, `/api/capture`, `/api/reindex`). With no token set, writes are open — only
  appropriate when the server is bound to localhost / a trusted network.
- **Bind address matters.** The default `TROVEX_HOST=0.0.0.0` listens on all interfaces. If
  the machine is reachable from an untrusted network, set a write token and/or front trovex
  with a reverse proxy that handles authentication and TLS.
- **The browser UI is part of the trusted surface.** The HTML dashboard issues the same API
  calls an operator would. It sets no cookies and holds no session; the write token (when
  configured) is the only mutation gate. Treat access to the UI as operator access.

## What's hardened

These were tightened in response to a public MCP-registry security scan. They reduce the
blast radius of malformed or hostile input; they are not a claim that trovex is unbreakable.

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
