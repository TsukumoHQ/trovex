# Token-savings benchmark — methodology

This is the reproducible proof behind trovex's headline claim: **~60% fewer
tokens per documentation lookup**. It is a *model*, run over a *pinned corpus*
with a *fixed query set*, using trovex's own shipped savings math — not a
hand-picked number.

## The claim, precisely

trovex routes an agent to **one canonical doc** instead of letting it triage a
question by Read-ing several candidate files. So per lookup:

```
would_have_read = Σ tokens of the top-3 candidate docs   (the triage read)
actual_read     = tokens of the 1 doc trovex points at   (top-1 result)
pointer         = tokens of the trovex() response itself
saved           = would_have_read − actual_read − pointer
ratio           = saved / would_have_read
```

This is the exact code path the live dashboard uses (`Searcher.savings_estimate`
→ `src/trovex/savings.py`). Every token is counted with a real BPE tokenizer
(`o200k_base` via tiktoken; see `src/trovex/tokens.py`), never `len/4`.

## Why it is conservative (an under-claim, not a ceiling)

- The counterfactual reads only **3** candidate docs. Real triage often reads
  more; each extra candidate would *raise* the saving, so 3 is a floor.
- trovex is charged the **full** cost of its own pointer output.
- The reported headline is the **median** per-lookup ratio (with p25–p75
  spread available), never the maximum.
- The dollar figure prices the saved tokens at a **mid-market** input rate
  (`gpt-5.4`, $2.50 / 1M input tokens), not the most expensive model.

## Why it is reproducible

- **Fixed corpus.** `corpus/` is 8 self-contained Markdown docs for a fictional
  "Acme Notes API". They are version-controlled, so the number does not drift
  as the trovex repo itself changes.
- **Fixed queries.** `corpus-queries.txt` is a fixed set of 10 doc-lookup
  questions, one per doc topic.
- **Deterministic pipeline.** The local fastembed model
  (`BAAI/bge-small-en-v1.5`, ONNX on CPU) and tiktoken counting are both
  deterministic, and indexing runs into a throwaway temp directory with no
  outside state. Same corpus + same queries + same model ⇒ identical token
  numbers on every run.

The generation timestamp (`ran_at` in `src/trovex/_benchmark.json`) is the only
field that changes between runs; it is metadata, not part of the reproducibility
claim.

## Running it

```
# The pinned corpus + queries behind the published number (also refreshes
# the committed src/trovex/_benchmark.json the /api/savings/benchmark serves):
python benchmarks/token-savings/run.py --fixed

# Any repo of .md docs, your own query file:
python benchmarks/token-savings/run.py --repo /path/to/docs --queries q.txt
```

No API key and no network are required after the one-time model download.

## Current published result

At the time of writing, the pinned corpus yields **~60% pooled savings**
(median 59% per lookup) over 10 queries against 8 docs. Re-run `--fixed` to
regenerate `src/trovex/_benchmark.json`; the numeric fields will match.

## The live number vs this benchmark

This benchmark is the *modelled* proof over a fixed corpus. The `trovex savings`
command and the `/savings` dashboard report the *live* savings from your own
real query ledger, and additionally gate the figure on measured routing
precision (`hit@1`) once you have run `trovex eval`. Both use the same savings
math; this benchmark exists so the claim is reproducible by anyone, offline.
