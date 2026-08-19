# Query caching and invalidation

Acme Notes API caches the results of repeated searches so a hot query does not
re-run the vector scan every time.

## How the cache works

Each search key is the normalized query text plus the active filter set. A hit
returns the stored result list without touching the index.

## When entries are invalidated

- Writing, editing, or deleting any note clears the whole result cache, because a
  new note could change the ranking of any query.
- The cache also expires entries after `ACME_CACHE_TTL` seconds (default 300).

## Disabling the cache

Set `ACME_CACHE=off` to bypass caching entirely. This is useful when measuring
raw query latency, since a warm cache would otherwise hide the real cost.
