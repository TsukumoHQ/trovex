"""Shared off-loop dispatch for every blocking call trovex's server makes.

Wedge-class-2 (2026-08-22 prod outage, recurred 2026-08-31 despite 33ca98a):
a blocking sync call anywhere on the asyncio event loop thread freezes the
WHOLE server — including unrelated routes sharing the loop (server.py mounts
the MCP app into the same FastAPI app) — because a single-threaded event loop
can't run ANY other coroutine, including a `wait_for` timeout's own callback,
while it's stuck inside synchronous/native code. 33ca98a fixed this for the 9
MCP `@mcp.tool()` handlers only; the recurrence traced (live `sample` dump,
2026-08-31, pid wedged 407%+ CPU) to `/api/capture` still calling
`capture_state()` -> `store.put()` -> `embedder.embed()` (onnxruntime
inference, CPU-bound, spin-waits its own worker threads) directly inline in
its `async def` route — never offloaded at all.

This module centralizes the fix so every call site (MCP tools AND FastAPI
routes) uses the SAME bounded, timeout-guarded dispatch, instead of each
route reinventing (or forgetting) it.

Bounded pool, not the shared default: starlette's `run_in_threadpool` uses
anyio's process-wide default `CapacityLimiter` (shared with unrelated work,
sized independently of this app). A genuinely stuck sync call can't be
killed from Python — `wait_for` timing out only abandons the *await*, the
underlying thread keeps running until it finishes on its own (or never) —
so repeated timeouts leak threads. A dedicated, small, bounded
`ThreadPoolExecutor` here means those orphans can only ever starve OFF-LOOP
dispatch (bounded blast radius), never anything else on the process, and
`watchdog.saturated_for()` gives visibility into exactly that state so ops
(or the self-heal below) can act on it instead of it going silently unbounded.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

log = logging.getLogger("trovex.offload")

TOOL_TIMEOUT_SEC = float(os.environ.get("TROVEX_TOOL_TIMEOUT_SEC", "30"))

# Small on purpose: this bounds how many orphaned (timed-out but still
# running) native calls can pile up before new off-loop calls start queuing
# behind them instead of running — the whole point is a bounded blast radius,
# not maximum throughput (fastembed/onnxruntime already uses multiple cores
# per call internally, so a large pool would just contend with itself).
OFFLOAD_MAX_WORKERS = int(os.environ.get("TROVEX_OFFLOAD_WORKERS", "4"))

# How long the pool must stay FULLY saturated (every worker occupied past its
# own call's TOOL_TIMEOUT_SEC, i.e. orphaned) before the watchdog treats the
# process as wedged beyond self-recovery and exits so launchd restarts it —
# the same recovery `launchctl kickstart` already does manually today, just
# automatic. 0 disables self-heal (log only).
WATCHDOG_SATURATION_SEC = float(os.environ.get("TROVEX_WATCHDOG_SATURATION_SEC", "120"))
WATCHDOG_POLL_SEC = float(os.environ.get("TROVEX_WATCHDOG_POLL_SEC", "5"))

_pool = ThreadPoolExecutor(max_workers=OFFLOAD_MAX_WORKERS, thread_name_prefix="trovex-offload")


@dataclass
class _Call:
    started_at: float = field(default_factory=time.monotonic)
    label: str = ""
    # None (e.g. /api/reindex, deliberately unbounded — see its call site) means
    # this call has no deadline and can never count as "orphaned" below,
    # however long it runs.
    deadline: float | None = None


_lock = threading.Lock()
_inflight: dict[int, _Call] = {}
_next_id = 0


def _register(label: str, timeout: float | None) -> int:
    global _next_id
    with _lock:
        cid = _next_id
        _next_id += 1
        deadline = None if timeout is None else time.monotonic() + timeout
        _inflight[cid] = _Call(label=label, deadline=deadline)
    return cid


def _unregister(cid: int) -> None:
    with _lock:
        _inflight.pop(cid, None)


_UNSET = object()  # distinct from `timeout=None` (deliberately unbounded)


async def off_loop(fn, *args, timeout=_UNSET, **kwargs):
    """Run a blocking callable on the dedicated bounded pool, bounded by
    `timeout` seconds (None = unbounded — only for callers that are
    deliberately long-running AND already have their own concurrency guard,
    e.g. /api/reindex's single-flight lock). Omitting `timeout` reads
    `offload.TOOL_TIMEOUT_SEC` at CALL time, not at def time — so
    monkeypatching it (tests; TROVEX_TOOL_TIMEOUT_SEC at startup) takes
    effect for every caller that doesn't pass its own timeout. Raises
    `TimeoutError` on timeout — the underlying call is NOT cancelled (Python
    can't cancel a running native thread) and keeps occupying its pool slot
    until it finishes; that orphan is what the watchdog below tracks."""
    if timeout is _UNSET:
        timeout = TOOL_TIMEOUT_SEC
    label = getattr(fn, "__name__", repr(fn))
    cid = _register(label, timeout)
    loop = asyncio.get_running_loop()
    # Submit to the RAW concurrent.futures.Future ourselves (not via
    # loop.run_in_executor's return value) and hang the unregister callback on
    # THAT — not on an asyncio-wrapped future. `wait_for`'s cancel() on an
    # asyncio future returned by run_in_executor marks it done+cancelled
    # SYNTHETICALLY at the asyncio layer the moment it gives up, even while
    # the real pool thread keeps running underneath (confirmed empirically —
    # its done-callback fires immediately, not on real completion). The raw
    # concurrent.futures.Future has the semantics we actually need: its own
    # .cancel() only succeeds (and only then fires callbacks) if the call
    # hasn't started running yet; once it's actually executing, .cancel()
    # is a no-op and its callback fires only on genuine completion — which is
    # exactly what lets `cid` stay in `_inflight` for as long as the pool
    # thread is truly busy, independent of whether wait_for below already
    # gave the caller a TimeoutError and moved on. asyncio.wrap_future gives
    # `wait_for` an awaitable that still cooperates correctly with that raw
    # future's cancellation semantics.
    raw_future = _pool.submit(fn, *args, **kwargs)
    raw_future.add_done_callback(lambda _f: _unregister(cid))
    return await asyncio.wait_for(asyncio.wrap_future(raw_future, loop=loop), timeout=timeout)


def saturated_for() -> float:
    """Seconds the dedicated pool has been fully occupied by calls that have
    ALREADY exceeded their own timeout (i.e. orphans, not merely busy) — 0.0
    if the pool isn't currently in that state. A pool doing normal bounded
    work never counts, however busy: only calls stuck past their own deadline
    do, and an unbounded call (deadline=None, e.g. reindex) never counts."""
    now = time.monotonic()
    with _lock:
        calls = list(_inflight.values())
    if len(calls) < OFFLOAD_MAX_WORKERS:
        return 0.0
    orphaned_since = [
        now - c.deadline for c in calls if c.deadline is not None and now > c.deadline
    ]
    if len(orphaned_since) < OFFLOAD_MAX_WORKERS:
        return 0.0
    return min(orphaned_since)


async def run_watchdog(*, on_wedged=None) -> None:
    """Background task (started at app startup): if every pool worker is
    occupied by an orphaned (past-deadline) call for WATCHDOG_SATURATION_SEC
    straight, the process is wedged beyond what this pool can recover from
    on its own — log CRITICAL and self-heal via `on_wedged` (default:
    os._exit(1), so launchd restarts the service, matching the manual
    `launchctl kickstart` mitigation already in use). Disabled by
    TROVEX_WATCHDOG_SATURATION_SEC=0."""
    if WATCHDOG_SATURATION_SEC <= 0:
        return
    if on_wedged is None:
        on_wedged = lambda: os._exit(1)  # noqa: E731
    while True:
        await asyncio.sleep(WATCHDOG_POLL_SEC)
        stuck_for = saturated_for()
        if stuck_for >= WATCHDOG_SATURATION_SEC:
            log.critical(
                "offload pool saturated by orphaned calls for %.0fs (>= %.0fs) — "
                "self-healing (process restart)",
                stuck_for,
                WATCHDOG_SATURATION_SEC,
            )
            on_wedged()
            return
