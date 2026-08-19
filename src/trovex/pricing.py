"""Dollar-pricing for the savings receipt — turn tokens-saved into $ saved.

trovex's saved tokens are INPUT tokens: context an agent would have re-read to
triage a question but didn't, because the router pointed it at one canonical
doc. So we price them at the INPUT ($ / 1M-token) rate of a stated mainstream
model. Offline, key-free, constants only — no live price feed, no network.

Two honesty rails, the same as tokens.py:

- Under-claim: we default to a MID-MARKET input rate, not the most expensive
  model, so the $ figure is a conservative floor — not a marketing ceiling.
- Never context-free: every $ figure ships a `pricing` block naming the model,
  the rate, and the source, so a reader can re-price it against their own model.

The reference model is `gpt-5.4` ($2.50 / 1M input) to match insights.py, so
the whole codebase prices consistently. Override the reference model with
TROVEX_PRICE_MODEL (any key below), or force a raw rate with
TROVEX_PRICE_PER_MTOK (a float, $ per 1M input tokens).
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("trovex.pricing")

# Input $ per 1M tokens — list prices, 2026. Savings are input-side, so only the
# input rate matters here (unlike insights.PRICING which is (in, out) for the
# LLM rerank cost). Mid-market default keeps the $ figure a floor.
INPUT_PRICE_PER_MTOK: dict[str, float] = {
    "gpt-5.5": 5.00,
    "gpt-5.4": 2.50,
    "gpt-5.4-mini": 0.75,
    "gpt-4.1-nano": 0.10,
    "gpt-4o": 2.50,
    "gpt-4o-mini": 0.15,
    "claude-opus": 15.00,
    "claude-sonnet": 3.00,
    "claude-haiku": 0.80,
}

# Stated mid-market reference — matches insights.py's input rate for gpt-5.4.
DEFAULT_MODEL = "gpt-5.4"
_SOURCE = "list price, 2026 (input rate)"


def _resolve() -> tuple[str, float]:
    """(model_label, input_$/Mtok) after applying env overrides.

    Precedence: TROVEX_PRICE_PER_MTOK (raw float) > TROVEX_PRICE_MODEL (table
    key) > DEFAULT_MODEL. A bad override degrades to the default, never raises —
    a savings receipt must not crash on a typo'd env var."""
    raw = os.environ.get("TROVEX_PRICE_PER_MTOK")
    if raw:
        try:
            rate = float(raw)
            if rate < 0:
                raise ValueError("negative rate")
            model = os.environ.get("TROVEX_PRICE_MODEL", "custom")
            return (model, rate)
        except ValueError:
            log.debug("bad TROVEX_PRICE_PER_MTOK=%r, ignoring", raw)

    model = os.environ.get("TROVEX_PRICE_MODEL", DEFAULT_MODEL)
    rate = INPUT_PRICE_PER_MTOK.get(model)
    if rate is None:
        log.debug("unknown TROVEX_PRICE_MODEL=%r, falling back to %s", model, DEFAULT_MODEL)
        model, rate = DEFAULT_MODEL, INPUT_PRICE_PER_MTOK[DEFAULT_MODEL]
    return (model, rate)


def price_model() -> str:
    """The reference model label a $ figure was priced against."""
    return _resolve()[0]


def input_per_mtok() -> float:
    """The input $ per 1M tokens used for the $ conversion."""
    return _resolve()[1]


def usd(tokens: int | None) -> float:
    """Dollar value of `tokens` saved, at the reference input rate.

    Never negative; 0 for None/0 tokens (saved tokens are already floored at 0
    upstream in savings._saved)."""
    if not tokens or tokens <= 0:
        return 0.0
    return (tokens / 1_000_000) * _resolve()[1]


def usd_or_none(tokens: int | None) -> float | None:
    """usd() but None-preserving — for `saved_at_precision`, which is None when
    routing precision is unmeasured (don't fabricate a $ on an unmeasured base)."""
    if tokens is None:
        return None
    return usd(tokens)


def pricing_block() -> dict:
    """The `pricing` block shipped alongside every $ figure so it's never
    context-free: which model, which rate, where the rate came from."""
    model, rate = _resolve()
    return {"model": model, "input_per_mtok": rate, "source": _SOURCE}


def fmt_usd(amount: float) -> str:
    """Human $ for a terminal/receipt. Sub-cent figures keep 4 dp so a small but
    real number never rounds to $0.00 (which would read as 'no savings')."""
    if amount and amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:,.2f}"
