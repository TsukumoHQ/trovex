"""Real token counting for the savings receipt.

trovex's core claim is token savings; a claim measured with `len/4` is not a
claim you can defend. This counts tokens with a real BPE tokenizer (tiktoken's
`o200k_base` — the GPT-4o/5 family encoder) so `would_have_read` and the
response size are honest.

Why o200k_base as the yardstick: trovex serves agents on many models, so no
single tokenizer is "the" agent's. o200k_base is the modern OpenAI encoder and
tracks Claude's BPE closely enough for a savings figure (within a few percent
on English/markdown/code) — and it is the same across every process, so the
number is comparable over time. The receipt always STATES which tokenizer
produced it (`tokenizer_name()`), and falls back to the honest `chars/4`
estimate (labelled as such) when tiktoken can't load — never silently.

Fully offline after the first load: tiktoken caches the encoding under
~/.cache/tiktoken (or TIKTOKEN_CACHE_DIR). Override the encoding with
TROVEX_TOKENIZER, or force the estimate with TROVEX_DISABLE_TIKTOKEN=1.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("trovex.tokens")

_ESTIMATE_NAME = "chars/4-estimate"
_ENCODING = os.environ.get("TROVEX_TOKENIZER", "o200k_base")

_enc = None  # cached tiktoken.Encoding, or None when unavailable
_tried = False
_name = _ESTIMATE_NAME


def _estimate(text: str) -> int:
    return max(1, len(text) // 4)


def _encoder():
    """Load + memoize the tiktoken encoder once; None if it can't be loaded."""
    global _enc, _tried, _name
    if _tried:
        return _enc
    _tried = True
    if os.environ.get("TROVEX_DISABLE_TIKTOKEN"):
        return None
    try:
        import tiktoken

        _enc = tiktoken.get_encoding(_ENCODING)
        _name = _ENCODING
    except Exception:  # noqa: BLE001 — offline/missing dep/bad encoding all degrade the same
        log.debug("tiktoken unavailable, falling back to %s", _ESTIMATE_NAME, exc_info=True)
        _enc = None
    return _enc


def count_tokens(text: str | None) -> int:
    """Real token count for `text`, or an honest chars/4 estimate on fallback.

    Never raises and never returns 0 for non-empty text (a doc that costs
    something to read must not read as free)."""
    if not text:
        return 0
    enc = _encoder()
    if enc is None:
        return _estimate(text)
    try:
        # disallowed_special=() → treat any "<|...|>"-looking text in a doc as
        # ordinary text instead of erroring on a special-token collision.
        return len(enc.encode(text, disallowed_special=()))
    except Exception:  # noqa: BLE001 — a pathological input must not break indexing/logging
        log.debug("token encode failed, using estimate", exc_info=True)
        return _estimate(text)


def tokenizer_name() -> str:
    """Which method a count came from — the label the receipt must show.

    Returns the encoding name (e.g. "o200k_base") when the real tokenizer is
    loaded, else "chars/4-estimate". Reflects reality only after the first
    count_tokens() call has attempted a load."""
    _encoder()
    return _name
