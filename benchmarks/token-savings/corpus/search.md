# How search ranking works

A search in Acme Notes API blends keyword and semantic signals, then optionally
re-ranks the top candidates for precision.

## The two signals

- Keyword: a full-text match over note bodies, good for exact terms.
- Semantic: a vector similarity over the note embeddings, good for paraphrases.

The two scores are combined so a note that matches on either signal can surface.

## Re-ranking

The top 20 candidates are passed through a small local cross-encoder that scores
each note against the query directly. This runs on CPU with no API key and lifts
the best answer toward rank one on hard queries.

## Filters

Attach `tag:` or `author:` filters to narrow a search before ranking. Filters are
applied first, so ranking only ever sees the eligible notes.
