# Storage and the local database

Acme Notes API keeps everything in a single SQLite database inside the data
directory. There is no separate database server to run.

## What is stored

- Note bodies and metadata in the `notes` table.
- A full-text index for keyword search.
- Vector embeddings for semantic search, one row per note.

## Migrations

Schema migrations run automatically on start. Each migration is additive and
idempotent, so upgrading is safe and a downgrade simply ignores newer columns.

## Vacuuming

Deleted notes leave tombstone rows so a re-index does not resurrect them. Run
`acme-notes vacuum` occasionally to reclaim space; it is safe to run while the
service is live.

## Corruption recovery

If the database fails an integrity check on start, the service refuses to run and
points you at the most recent backup rather than writing over bad data.
