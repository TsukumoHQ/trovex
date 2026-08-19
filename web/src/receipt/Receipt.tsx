/**
 * trovex savings receipt — the REAL measured number for a running instance.
 *
 * Reads trovex-backend's /api/savings* endpoints same-origin (served by
 * `trovex serve`). This is the honest counterpart to the /savings estimate
 * calculator: no inputs, no modelling knobs — just what this instance actually
 * saved, qualified exactly as the honesty rules demand (see api.ts:resolveHeadline).
 *
 * Local dashboard: private by construction. No analytics, no share loop, no
 * outbound calls beyond the local API.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  type AgentRow,
  type BenchmarkResult,
  type SavingsTotals,
  type SessionRow,
  fetchAgents,
  fetchBenchmark,
  fetchLifetime,
  fetchSessions,
  fetchTotals,
  resolveHeadline,
  showAtPrecision,
} from './api'
import { hasDollarFigure, humanTokens, money, pct, pricingNote, relativeTime, tokenizerLabel } from './format'
import { downloadShareCard } from './shareCard'

const RANGES = [7, 30, 90] as const
type Range = (typeof RANGES)[number]

// A settled result tagged with the range it belongs to. It is "loading" purely
// by absence: when the stored result's `for` doesn't match the current range
// (or is null), the view shows a skeleton. This keeps every setState inside an
// async callback — none run synchronously in an effect (no cascading renders).
type Res<T> = { for: number; ok: true; data: T } | { for: number; ok: false; msg: string }
type Load<T> = { state: 'loading' } | { state: 'ok'; data: T } | { state: 'error'; msg: string }

function view<T>(res: Res<T> | null, range: number): Load<T> {
  if (!res || res.for !== range) return { state: 'loading' }
  return res.ok ? { state: 'ok', data: res.data } : { state: 'error', msg: res.msg }
}

const errMsg = (e: unknown) => String((e as { message?: string })?.message ?? e)

export default function Receipt() {
  const [range, setRange] = useState<Range>(7)
  const [totalsRes, setTotalsRes] = useState<Res<SavingsTotals> | null>(null)
  const [agentsRes, setAgentsRes] = useState<Res<AgentRow[]> | null>(null)
  const [sessionsRes, setSessionsRes] = useState<Res<SessionRow[]> | null>(null)
  const [lifetime, setLifetime] = useState<SavingsTotals | null>(null)
  const [benchmark, setBenchmark] = useState<BenchmarkResult | null>(null)

  const totals = view(totalsRes, range)
  const agents = view(agentsRes, range)
  const sessions = view(sessionsRes, range)

  const load = useCallback((days: Range, signal: AbortSignal) => {
    fetchTotals(days, signal)
      .then((d) => setTotalsRes({ for: days, ok: true, data: d }))
      .catch((e) => signal.aborted || setTotalsRes({ for: days, ok: false, msg: errMsg(e) }))
    fetchAgents(days, signal)
      .then((d) => setAgentsRes({ for: days, ok: true, data: d }))
      .catch((e) => signal.aborted || setAgentsRes({ for: days, ok: false, msg: errMsg(e) }))
    fetchSessions(days, signal)
      .then((d) => setSessionsRes({ for: days, ok: true, data: d }))
      .catch((e) => signal.aborted || setSessionsRes({ for: days, ok: false, msg: errMsg(e) }))
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    load(range, ac.signal)
    return () => ac.abort()
  }, [range, load])

  // Lifetime context strip — fetched once, independent of the range.
  useEffect(() => {
    const ac = new AbortController()
    fetchLifetime(ac.signal)
      .then((d) => setLifetime(d))
      .catch(() => setLifetime(null))
    return () => ac.abort()
  }, [])

  // Reproducible-benchmark card — fetched once. Absent (older server, or no
  // committed result) → the card simply doesn't render; never a hard error.
  useEffect(() => {
    const ac = new AbortController()
    fetchBenchmark(ac.signal)
      .then((d) => setBenchmark(d))
      .catch(() => setBenchmark(null))
    return () => ac.abort()
  }, [])

  return (
    <main className="rc">
      <a className="rc-home" href="/">← trovex</a>

      <header className="rc-head">
        <p className="rc-eyebrow mono">measured · this instance</p>
        <h1>Savings receipt</h1>
        <p className="rc-sub">
          What trovex actually saved on this repo: the real number from your own queries, not an
          estimate. Served locally by <code>trovex serve</code>; nothing leaves your machine.
        </p>
        {lifetime && lifetime.queries > 0 && <LifetimeStrip t={lifetime} />}
      </header>

      {benchmark && <BenchmarkCard b={benchmark} />}

      <div className="rc-range" role="tablist" aria-label="Time range">
        {RANGES.map((d) => (
          <button
            key={d}
            type="button"
            role="tab"
            aria-selected={range === d}
            className={`rc-range-btn mono${range === d ? ' is-on' : ''}`}
            onClick={() => setRange(d)}
          >
            {d}d
          </button>
        ))}
      </div>

      <TotalsCard load={totals} onRetry={() => load(range, new AbortController().signal)} />

      {totals.state === 'ok' && totals.data.queries > 0 && <ShareCard t={totals.data} />}

      <section className="rc-breakdown">
        <AgentsTable load={agents} totals={totals} />
        <SessionsTable load={sessions} totals={totals} />
      </section>

      <footer className="rc-foot mono">
        trovex · one source of truth for your agents' docs · open source, public beta
      </footer>
    </main>
  )
}

function LifetimeStrip({ t }: { t: SavingsTotals }) {
  const h = resolveHeadline(t)
  const hasUsd = hasDollarFigure({ saved_usd: h.savedUsd, pricing: t.pricing })
  return (
    <p className="rc-lifetime mono">
      since day one:{' '}
      <b>{humanTokens(h.saved)}</b> tokens{hasUsd && <> ≈ <b>{money(h.savedUsd)}</b></>} saved across{' '}
      <b>{t.queries.toLocaleString('en-US')}</b> queries{' '}
      <span className="rc-lifetime-note">
        ({h.verified ? 'routing verified' : 'raw estimate'} · {tokenizerLabel(t.tokenizer)})
      </span>
    </p>
  )
}

function TotalsCard({ load, onRetry }: { load: Load<SavingsTotals>; onRetry: () => void }) {
  if (load.state === 'loading') return <div className="rc-card rc-skeleton" aria-busy="true" />
  if (load.state === 'error')
    return (
      <div className="rc-card rc-error">
        <p>Couldn't reach the trovex server.</p>
        <p className="rc-error-detail mono">{load.msg}</p>
        <p className="rc-error-hint">
          This page reads a running instance. Start it with <code>trovex serve</code>, then reload.
        </p>
        <button type="button" className="rc-retry mono" onClick={onRetry}>
          retry
        </button>
      </div>
    )

  const t = load.data
  if (t.queries === 0) {
    return (
      <div className="rc-card rc-empty">
        <p className="rc-empty-h">No queries recorded in this window.</p>
        <p>
          Point an agent at your docs through trovex and your real savings land here. There's no
          number to show until there's a query to measure, and we won't invent one.
        </p>
      </div>
    )
  }

  const h = resolveHeadline(t)
  const readPct = t.would_have_read > 0 ? Math.round((t.actual_read / t.would_have_read) * 100) : 0
  // The $ layer is additive: an older server (or one deployed before the $
  // fields land) has no saved_usd/pricing. Show tokens-only then, never a
  // fabricated "$0.00" — honesty rule #4, under-claim.
  const hasUsd = hasDollarFigure({ saved_usd: h.savedUsd, pricing: t.pricing })

  return (
    <div className="rc-card">
      <div className={`rc-headline${h.verified ? ' is-verified' : ''}`}>
        <div className="rc-big mono">{humanTokens(h.saved)}</div>
        {hasUsd && <div className="rc-big-usd mono">≈ {money(h.savedUsd)} saved</div>}
        <div className="rc-big-label">{h.label}</div>
        <div className="rc-ratio mono">~{pct(t.ratio)}% fewer tokens · {t.queries.toLocaleString('en-US')} queries</div>
      </div>

      {/* $ provenance rides with the number: which rate priced it (rule #1). */}
      {hasUsd && <p className="rc-pricing mono">{pricingNote(t.pricing)}</p>}

      {h.secondary && (
        <p className="rc-secondary">
          {humanTokens(h.secondary.saved)}
          {hasUsd && <> ≈ {money(h.secondary.savedUsd)}</>} · {h.secondary.label}
        </p>
      )}

      {h.caveat && (
        <p className="rc-caveat" role="note">
          <span className="rc-caveat-tag mono">unverified</span> {h.caveat}
        </p>
      )}

      {/* Rule #1: the number never appears without its assumption. */}
      <p className="rc-assumption">
        <span className="rc-assumption-tag mono">assumption</span> {t.assumption}
      </p>

      {/* Rule #3: state the tokenizer, always. */}
      <p className="rc-tokenizer mono">
        counted with <b>{tokenizerLabel(t.tokenizer)}</b>
      </p>

      <div className="rc-bars" aria-hidden="true">
        <Bar label="would have read" value={t.would_have_read} max={t.would_have_read} kind="ghost" />
        <Bar label="actually read" value={t.actual_read} max={t.would_have_read} kind="solid" />
      </div>
      <p className="rc-bars-legend mono">
        {humanTokens(t.actual_read)} read vs {humanTokens(t.would_have_read)} it would have, {readPct}% of the naive cost
        {t.response_tokens > 0 && <> · {humanTokens(t.response_tokens)} response tokens</>}
      </p>
    </div>
  )
}

function Bar({ label, value, max, kind }: { label: string; value: number; max: number; kind: 'ghost' | 'solid' }) {
  const w = max > 0 ? Math.min(100, Math.max(1, (value / max) * 100)) : 0
  return (
    <div className={`rc-bar rc-bar--${kind}`}>
      <span className="rc-bar-label mono">{label}</span>
      <span className="rc-bar-track">
        <span className="rc-bar-fill" style={{ width: `${w}%` }} />
      </span>
    </div>
  )
}

function AgentsTable({ load, totals }: { load: Load<AgentRow[]>; totals: Load<SavingsTotals> }) {
  const atPrecision = totals.state === 'ok' && showAtPrecision(totals.data)
  return (
    <div className="rc-tablewrap">
      <h2 className="rc-h2">By agent</h2>
      {load.state === 'loading' && <div className="rc-skeleton rc-skeleton--table" aria-busy="true" />}
      {load.state === 'error' && <p className="rc-tbl-msg mono">unavailable: {load.msg}</p>}
      {load.state === 'ok' && load.data.length === 0 && (
        <p className="rc-tbl-msg">No agent activity in this window.</p>
      )}
      {load.state === 'ok' && load.data.length > 0 && (
        <div className="rc-table-scroll">
          <table className="rc-table">
            <thead>
              <tr>
                <th>agent</th>
                <th className="rc-num">sessions</th>
                <th className="rc-num">queries</th>
                <th className="rc-num">saved{atPrecision ? ' (verified)' : ''}</th>
                <th className="rc-num">%</th>
                <th className="rc-num">last seen</th>
              </tr>
            </thead>
            <tbody>
              {load.data.map((r) => (
                <tr key={r.agent}>
                  <td className="rc-td-name">{r.agent || '—'}</td>
                  <td className="rc-num mono">{r.sessions.toLocaleString('en-US')}</td>
                  <td className="rc-num mono">{r.queries.toLocaleString('en-US')}</td>
                  <td className="rc-num mono">
                    {humanTokens(atPrecision && r.saved_at_precision != null ? r.saved_at_precision : r.saved)}
                  </td>
                  <td className="rc-num mono">~{pct(r.ratio)}%</td>
                  <td className="rc-num mono rc-td-time">{relativeTime(r.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function SessionsTable({ load, totals }: { load: Load<SessionRow[]>; totals: Load<SavingsTotals> }) {
  const atPrecision = totals.state === 'ok' && showAtPrecision(totals.data)
  return (
    <div className="rc-tablewrap">
      <h2 className="rc-h2">Recent sessions</h2>
      {load.state === 'loading' && <div className="rc-skeleton rc-skeleton--table" aria-busy="true" />}
      {load.state === 'error' && <p className="rc-tbl-msg mono">unavailable: {load.msg}</p>}
      {load.state === 'ok' && load.data.length === 0 && (
        <p className="rc-tbl-msg">No sessions in this window.</p>
      )}
      {load.state === 'ok' && load.data.length > 0 && (
        <div className="rc-table-scroll">
          <table className="rc-table">
            <thead>
              <tr>
                <th>session</th>
                <th>agent</th>
                <th className="rc-num">queries</th>
                <th className="rc-num">saved{atPrecision ? ' (verified)' : ''}</th>
                <th className="rc-num">last seen</th>
              </tr>
            </thead>
            <tbody>
              {load.data.map((r) => (
                <tr key={r.session}>
                  <td className="rc-td-name mono">{shortId(r.session)}</td>
                  <td className="rc-td-name">{r.agent || '—'}</td>
                  <td className="rc-num mono">{r.queries.toLocaleString('en-US')}</td>
                  <td className="rc-num mono">
                    {humanTokens(atPrecision && r.saved_at_precision != null ? r.saved_at_precision : r.saved)}
                  </td>
                  <td className="rc-num mono rc-td-time">{relativeTime(r.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function BenchmarkCard({ b }: { b: BenchmarkResult }) {
  const readPct = b.baseline_tokens > 0 ? Math.round((b.trovex_tokens / b.baseline_tokens) * 100) : 0
  // Same additive-$ guard as TotalsCard: a 200 benchmark whose committed JSON is
  // missing pricing/saved_usd (malformed result, partial deploy) must render the
  // token figure alone, never crash on pricingNote(undefined) and blank /receipt.
  const hasUsd = hasDollarFigure(b)
  return (
    <section className="rc-bench">
      <div className="rc-bench-head">
        <p className="rc-eyebrow mono">reproducible benchmark</p>
        {b.deterministic && <span className="rc-bench-badge mono">deterministic · same result on re-run</span>}
      </div>
      <div className="rc-bench-body">
        <div className="rc-bench-figure">
          <div className="rc-big mono">~{pct(b.savings_pct / 100)}%</div>
          {hasUsd && <div className="rc-big-usd mono">≈ {money(b.saved_usd)} saved</div>}
          <div className="rc-big-label">fewer tokens vs a full-dump baseline</div>
        </div>
        <p className="rc-bench-detail mono">
          {b.baseline_tokens.toLocaleString('en-US')} → {b.trovex_tokens.toLocaleString('en-US')} tokens
          {' '}({readPct}% of the naive cost) over {b.queries.toLocaleString('en-US')} queries on{' '}
          <b>{b.corpus}</b>
        </p>
        <p className="rc-bench-spread mono">
          per-query ratio: median ~{pct(b.median_ratio)}% · pooled ~{pct(b.pooled_ratio)}%
        </p>
        {hasUsd && <p className="rc-pricing mono">{pricingNote(b.pricing)}</p>}
      </div>
      <p className="rc-bench-foot">
        A fixed corpus + fixed query set, re-runnable to the same number: the savings figure is a
        measurement, not a claim.
        {b.methodology_url && (
          <>
            {' '}
            <a href={b.methodology_url}>How it's measured →</a>
          </>
        )}
      </p>
    </section>
  )
}

function ShareCard({ t }: { t: SavingsTotals }) {
  const [done, setDone] = useState<string>('')
  const h = resolveHeadline(t)
  const hasUsd = hasDollarFigure({ saved_usd: h.savedUsd, pricing: t.pricing })
  const tokensLabel = humanTokens(h.saved)
  const moneyLabel = hasUsd ? money(h.savedUsd) : ''
  const pctVal = pct(t.ratio)

  const flash = (k: string) => {
    setDone(k)
    window.setTimeout(() => setDone(''), 1800)
  }

  // The share line carries only aggregate figures: no repo, path, or query.
  const figures = hasUsd ? `${tokensLabel} ≈ ${moneyLabel}` : `${tokensLabel} tokens`
  const line = `trovex saved my coding agents ~${pctVal}% of doc-lookup tokens (${figures}) on this repo. one canonical answer instead of rereading. trovex.dev`

  async function saveCard() {
    try {
      const ok = await downloadShareCard({
        pct: pctVal,
        tokensLabel,
        moneyLabel,
        queries: t.queries,
        verified: h.verified,
      })
      if (ok) flash('card')
    } catch {
      /* canvas/image blocked — no-op; the copy-line path still works */
    }
  }

  async function copyLine() {
    try {
      await navigator.clipboard.writeText(line)
      flash('line')
    } catch {
      /* clipboard blocked — no-op */
    }
  }

  return (
    <section className="rc-share">
      <h2 className="rc-h2">Share this receipt</h2>
      <p className="rc-share-sub">
        A card of your aggregate saving: no repo, paths, or queries, only the totals above. The
        dashboard stays private; this is the one thing you choose to post.
      </p>
      <div className="rc-share-row">
        <button type="button" className="rc-share-btn mono" onClick={saveCard}>
          {done === 'card' ? 'saved ✓' : 'save receipt card (png)'}
        </button>
        <button type="button" className="rc-share-btn mono" onClick={copyLine}>
          {done === 'line' ? 'copied ✓' : 'copy line'}
        </button>
      </div>
    </section>
  )
}

function shortId(s: string): string {
  if (!s) return '—'
  return s.length > 12 ? `${s.slice(0, 8)}…${s.slice(-3)}` : s
}
