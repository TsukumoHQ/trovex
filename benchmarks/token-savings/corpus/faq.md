# Frequently asked questions

## Does Acme Notes API send my notes anywhere?

No. It is self-hosted and works fully offline. The embedding model runs locally,
so no note text leaves the host.

## Can I run it without an API key?

Yes. The default embedding and re-ranking models are local, so no key is needed.
You can point it at a hosted model later if you prefer.

## How big can a note be?

Notes are truncated at `ACME_MAX_NOTE_KB` before indexing (default 256 KB). The
full body is still stored; only the indexed slice is capped.

## How do I move to a new machine?

Copy the data directory to the new host and start the service. All notes, tokens,
and the index come with it.

## Where are logs written?

To standard output, at the level set by `ACME_LOG_LEVEL`. Run it under a process
manager to capture and rotate them.
