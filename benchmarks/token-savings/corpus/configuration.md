# Configuring Acme Notes API

All settings are read from environment variables with the `ACME_` prefix, or
from `~/.acme-notes/config.toml`. Environment variables win over the file.

## Common settings

- `ACME_DATA_DIR` — where the note index and database live (default
  `~/.acme-notes`).
- `ACME_PORT` — the HTTP listen port (default `8400`).
- `ACME_HOST` — the bind address (default `127.0.0.1`; set `0.0.0.0` to expose).
- `ACME_LOG_LEVEL` — `debug`, `info`, or `warning` (default `info`).

## Index settings

- `ACME_EMBED_MODEL` — the local embedding model used for semantic search
  (default `minilm-local`). Changing it triggers a full re-index on next start.
- `ACME_MAX_NOTE_KB` — notes larger than this are truncated before indexing
  (default `256`).

## Applying changes

Most settings take effect on restart. Changing `ACME_DATA_DIR` starts a fresh,
empty index at the new location; the old one is left untouched.
