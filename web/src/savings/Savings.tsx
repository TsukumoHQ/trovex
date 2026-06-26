/**
 * trovex.dev/savings — token-savings estimate calculator.
 *
 * One surface, three cro-approved pieces (specs b9866d6a + 971fb1a + f07e80b7):
 *   1. the calculator — client-side, mirrors src/trovex/savings.py (top-3 triage
 *      baseline → 1 canonical doc + pointer), every default a labeled assumption;
 *   2. the shareable receipt — querystring-encoded result + copy link/line/badge,
 *      honesty-gated (no receipt when the saving is trivial), all carry trovex.dev;
 *   3. the team-scale consulting micro-CTA — a quiet line shown only when the inputs
 *      genuinely imply a team (agents ≥ 2 AND a meaningful monthly number).
 *
 * No backend, no PII, no email gate. Honest by construction: the headline tracks
 * the product's ~60% claim, never inflates, and the "show the math" toggle reveals
 * the exact formula.
 */
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  pctBucket,
  trackCalculatorRun,
  trackConsultSignalShown,
  trackInstallClick,
  trackLandingView,
  trackMathShown,
  trackShareClicked,
  trackTsukumoClick,
} from '../analytics'
import { downloadReceiptCard } from './receiptCard'

const GITHUB = 'https://github.com/TsukumoHQ/trovex'
const INSTALL_HREF = `${GITHUB}?utm_source=trovex&utm_medium=tool&utm_campaign=savings-calculator`
const CONSULT_HREF =
  'https://tsukumo.ch/assessment?utm_source=trovex&utm_medium=tool&utm_campaign=savings-calculator-consult'
const POINTER_TOKENS = 80 // the trovex() pointer response size (small, constant)

// Honesty gates.
const RECEIPT_MIN_RATIO = 0.2 // below this, the saving isn't worth a receipt
const TEAM_MIN_TOKENS_MO = 5_000_000 // "team-scale" monthly bar (AND agents >= 2)

type Inputs = {
  agents: number
  lookupsPerSession: number
  sessionsPerDay: number
  candidates: number
  avgDocTokens: number
  price: number // USD per 1M input tokens
}

const DEFAULTS: Inputs = {
  agents: 3,
  lookupsPerSession: 12,
  sessionsPerDay: 4,
  candidates: 3,
  avgDocTokens: 1200,
  price: 3,
}

// Short querystring keys so a shared link stays compact.
const QS: Record<keyof Inputs, string> = {
  agents: 'a',
  lookupsPerSession: 'l',
  sessionsPerDay: 's',
  candidates: 'c',
  avgDocTokens: 'd',
  price: 'p',
}

const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n))

function readInputs(): Inputs {
  const p = new URLSearchParams(location.search)
  const num = (k: keyof Inputs, def: number, lo: number, hi: number) => {
    const raw = p.get(QS[k])
    const v = raw == null ? def : Number(raw)
    return Number.isFinite(v) ? clamp(v, lo, hi) : def
  }
  return {
    agents: num('agents', DEFAULTS.agents, 1, 500),
    lookupsPerSession: num('lookupsPerSession', DEFAULTS.lookupsPerSession, 1, 1000),
    sessionsPerDay: num('sessionsPerDay', DEFAULTS.sessionsPerDay, 1, 100),
    candidates: num('candidates', DEFAULTS.candidates, 1, 10),
    avgDocTokens: num('avgDocTokens', DEFAULTS.avgDocTokens, 50, 20000),
    price: num('price', DEFAULTS.price, 0, 100),
  }
}

function humanTokens(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1).replace(/\.0$/, '')}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(1).replace(/\.0$/, '')}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1).replace(/\.0$/, '')}k`
  return String(Math.round(n))
}

function money(n: number): string {
  if (n >= 1000) return `$${Math.round(n).toLocaleString('en-US')}`
  if (n >= 100) return `$${Math.round(n)}`
  return `$${n.toFixed(n < 10 ? 1 : 0)}`
}

export default function Savings() {
  const [inp, setInp] = useState<Inputs>(() => (typeof window === 'undefined' ? DEFAULTS : readInputs()))
  const [showMath, setShowMath] = useState(false)
  const [copied, setCopied] = useState<string>('')

  const m = useMemo(() => {
    const wouldHaveRead = inp.candidates * inp.avgDocTokens
    const trovexRead = inp.avgDocTokens + POINTER_TOKENS
    const savedPerLookup = Math.max(0, wouldHaveRead - trovexRead)
    const ratio = wouldHaveRead > 0 ? savedPerLookup / wouldHaveRead : 0
    const lookupsPerDay = inp.lookupsPerSession * inp.sessionsPerDay * inp.agents
    const tokensPerDay = savedPerLookup * lookupsPerDay
    const tokensPerMonth = tokensPerDay * 30
    const dollarsPerMonth = (tokensPerMonth / 1e6) * inp.price
    return { wouldHaveRead, trovexRead, savedPerLookup, ratio, lookupsPerDay, tokensPerMonth, dollarsPerMonth }
  }, [inp])

  const pct = Math.round(m.ratio * 100)

  // Sync inputs → URL (replaceState, no history spam) so any result is linkable.
  useEffect(() => {
    if (typeof window === 'undefined') return
    const p = new URLSearchParams()
    ;(Object.keys(QS) as (keyof Inputs)[]).forEach((k) => p.set(QS[k], String(inp[k])))
    window.history.replaceState(null, '', `${location.pathname}?${p.toString()}`)
  }, [inp])

  // Landing/OSS-surface view once.
  useEffect(() => {
    trackLandingView()
  }, [])

  // calculator_run — coarse bucket only, debounced so dragging a field is one event.
  const runTimer = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (typeof window === 'undefined') return
    window.clearTimeout(runTimer.current)
    runTimer.current = window.setTimeout(() => trackCalculatorRun(pctBucket(m.ratio)), 600)
    return () => window.clearTimeout(runTimer.current)
  }, [m.ratio])

  const showReceipt = m.ratio >= RECEIPT_MIN_RATIO && m.tokensPerMonth > 0
  const showTeam = inp.agents >= 2 && m.tokensPerMonth >= TEAM_MIN_TOKENS_MO

  // Fire consult_signal_shown once per time the team-CTA appears.
  const teamFired = useRef(false)
  useEffect(() => {
    if (showTeam && !teamFired.current) {
      teamFired.current = true
      trackConsultSignalShown('team_scale')
    }
    if (!showTeam) teamFired.current = false
  }, [showTeam])

  // Build the share link straight from the inputs (not location.href, which an effect
  // updates a render late) so it's always in sync. Tag the link itself so arrivals from
  // a shared receipt attribute to the referral loop.
  const shareUrl = useMemo(() => {
    if (typeof window === 'undefined') return ''
    const p = new URLSearchParams()
    ;(Object.keys(QS) as (keyof Inputs)[]).forEach((k) => p.set(QS[k], String(inp[k])))
    p.set('utm_source', 'savings-share')
    p.set('utm_medium', 'referral')
    p.set('utm_campaign', 'savings-calculator')
    return `${location.origin}${location.pathname}?${p.toString()}`
  }, [inp])

  const tweetLine = `my coding agents would burn ~${pct}% fewer tokens rereading the repo (~${money(
    m.dollarsPerMonth,
  )}/mo) if they had one canonical answer. that's what trovex does. ${shareUrl}`
  // One-click X composer, prefilled with the same line copy-post hands over (the trailing
  // shareUrl auto-cards). Kills the copy → switch tab → paste step on the dominant dev channel.
  const xIntentUrl = `https://x.com/intent/post?text=${encodeURIComponent(tweetLine)}`
  // The README badge is the longest-lived share artifact (it sits permanently in a public
  // repo), so its link carries referral attribution too — own source, same taxonomy as the
  // link/post shares (utm_medium=referral, campaign=savings-calculator).
  const badgeHref =
    'https://trovex.dev/savings?utm_source=savings-badge&utm_medium=referral&utm_campaign=savings-calculator'
  // A DYNAMIC shields.io endpoint badge (not a baked-in number): shields fetches
  // /savings/badge with these inputs and recomputes, so the honesty gate is enforced
  // server-side and one embed stays live. Carry only the 6 numeric inputs (no UTM, no PII).
  const badgeEndpoint = (() => {
    const p = new URLSearchParams()
    ;(Object.keys(QS) as (keyof Inputs)[]).forEach((k) => p.set(QS[k], String(inp[k])))
    return `https://trovex.dev/savings/badge?${p.toString()}`
  })()
  const badge = `[![trovex saves ~${pct}% of doc-lookup tokens](https://img.shields.io/endpoint?url=${encodeURIComponent(
    badgeEndpoint,
  )})](${badgeHref})`

  async function copy(text: string, format: string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(format)
      trackShareClicked(format)
      window.setTimeout(() => setCopied(''), 1800)
    } catch {
      /* clipboard blocked — no-op, the text is still selectable in the field */
    }
  }

  // Save the receipt as a PNG (drags straight into a post). Honesty-gated inside
  // downloadReceiptCard — no-op when the saving isn't worth a card.
  async function saveCard() {
    try {
      const ok = await downloadReceiptCard({
        pct,
        ratio: m.ratio,
        tokensPerMonth: m.tokensPerMonth,
        tokensLabel: humanTokens(m.tokensPerMonth),
        moneyLabel: money(m.dollarsPerMonth),
      })
      if (!ok) return
      setCopied('card')
      trackShareClicked('card')
      window.setTimeout(() => setCopied(''), 1800)
    } catch {
      /* canvas/image render blocked — no-op; the copy-link/post paths still work */
    }
  }

  const set = (k: keyof Inputs) => (e: ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value)
    setInp((s) => ({ ...s, [k]: Number.isFinite(v) ? v : s[k] }))
  }

  return (
    <main className="sv-wrap">
      <header className="sv-head">
        <a className="sv-brand mono" href="https://trovex.dev/">
          trovex<span>.dev</span>
        </a>
        <p className="sv-eyebrow mono">token-savings estimate</p>
        <h1 className="sv-h1">how many tokens do your agents burn rereading the repo?</h1>
        <p className="sv-sub">
          Every session, your coding agents reread the same docs to work out which one is current.
          trovex keeps the canonical copy and hands them a single answer. Estimate the difference on
          your own numbers. No install needed, nothing leaves this page.
        </p>
      </header>

      <section className="sv-grid">
        <form className="sv-inputs" onSubmit={(e) => e.preventDefault()}>
          <Field label="agents / teammates sharing the repo" value={inp.agents} onChange={set('agents')} min={1} max={500} />
          <Field label="doc lookups per session" value={inp.lookupsPerSession} onChange={set('lookupsPerSession')} min={1} max={1000} />
          <Field label="sessions per day" value={inp.sessionsPerDay} onChange={set('sessionsPerDay')} min={1} max={100} />
          <Field label="candidate docs read to triage (without trovex)" value={inp.candidates} onChange={set('candidates')} min={1} max={10} hint="the product's model uses the top 3" />
          <Field label="avg tokens per doc" value={inp.avgDocTokens} onChange={set('avgDocTokens')} min={50} max={20000} step={50} />
          <Field label="model input price ($ / 1M tokens)" value={inp.price} onChange={set('price')} min={0} max={100} step={0.5} />
          <button type="button" className="sv-reset mono" onClick={() => setInp(DEFAULTS)}>
            reset to defaults
          </button>
        </form>

        <div className="sv-result">
          <div className="sv-result-pct mono">~{pct}%</div>
          <div className="sv-result-label">fewer tokens per doc lookup</div>
          <div className="sv-result-roll">
            <span><b className="mono">{humanTokens(m.tokensPerMonth)}</b> tokens / month</span>
            <span><b className="mono">~{money(m.dollarsPerMonth)}</b> / month</span>
          </div>
          <p className="sv-estimate">
            An estimate on the inputs you set, using the same model as trovex's own savings number.
            Install trovex to measure the real figure on your repo.{' '}
            <a className="sv-estimate-link" href="/measure">How we measured the ~60% →</a>
          </p>

          <a className="sv-cta" href={INSTALL_HREF} onClick={() => trackInstallClick()} target="_blank" rel="noopener noreferrer">
            see trovex on GitHub →
          </a>

          <button type="button" className="sv-math-toggle mono" aria-expanded={showMath} onClick={() => { setShowMath((v) => { if (!v) trackMathShown(); return !v }) }}>
            {showMath ? '− hide the math' : '+ show the math'}
          </button>
          {showMath && (
            <pre className="sv-math mono">{`without trovex, an agent reads the top ${inp.candidates} candidate docs to triage:
  would_have_read = ${inp.candidates} × ${inp.avgDocTokens} = ${m.wouldHaveRead.toLocaleString('en-US')} tokens

with trovex, it reads 1 canonical doc + the pointer:
  trovex_read     = ${inp.avgDocTokens} + ${POINTER_TOKENS} = ${m.trovexRead.toLocaleString('en-US')} tokens

  saved / lookup  = ${m.savedPerLookup.toLocaleString('en-US')}   (${pct}%)
  lookups / day   = ${inp.lookupsPerSession} × ${inp.sessionsPerDay} × ${inp.agents} = ${m.lookupsPerDay.toLocaleString('en-US')}
  saved / month   = ${humanTokens(m.tokensPerMonth)} tokens ≈ ${money(m.dollarsPerMonth)}

same model as the product (src/trovex/savings.py). every input above is editable.`}</pre>
          )}
        </div>
      </section>

      {showReceipt && (
        <section className="sv-share">
          <h2 className="sv-h2">share this estimate</h2>
          <p className="sv-share-sub">A linkable receipt of your own numbers. Every copy carries a link back.</p>
          <div className="sv-share-row">
            <a
              className="sv-share-btn sv-share-btn--x mono"
              href={xIntentUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackShareClicked('x_intent')}
            >
              post to X →
            </a>
            <button type="button" className="sv-share-btn mono" onClick={() => copy(shareUrl, 'link')}>
              {copied === 'link' ? 'copied ✓' : 'copy link'}
            </button>
            <button type="button" className="sv-share-btn mono" onClick={() => copy(tweetLine, 'tweet')}>
              {copied === 'tweet' ? 'copied ✓' : 'copy post'}
            </button>
            <button type="button" className="sv-share-btn mono" onClick={() => copy(badge, 'badge')}>
              {copied === 'badge' ? 'copied ✓' : 'copy README badge'}
            </button>
            <button type="button" className="sv-share-btn mono" onClick={saveCard}>
              {copied === 'card' ? 'saved ✓' : 'save card (png)'}
            </button>
          </div>
        </section>
      )}

      {showTeam && (
        <p className="sv-consult">
          Running agents across a team? We help teams roll this out well.{' '}
          <a href={CONSULT_HREF} onClick={() => trackTsukumoClick('savings_calculator')} target="_blank" rel="noopener noreferrer">
            talk to us →
          </a>
        </p>
      )}

      <footer className="sv-foot">
        <span>© 2026 trovex · one source of truth for your agents' docs</span>
        <a href={INSTALL_HREF} onClick={() => trackInstallClick()} target="_blank" rel="noopener noreferrer">GitHub</a>
      </footer>
    </main>
  )
}

function Field(props: {
  label: string
  value: number
  onChange: (e: ChangeEvent<HTMLInputElement>) => void
  min: number
  max: number
  step?: number
  hint?: string
}) {
  return (
    <label className="sv-field">
      <span className="sv-field-label">
        {props.label}
        {props.hint && <em className="sv-field-hint"> · {props.hint}</em>}
      </span>
      <input
        className="sv-field-input mono"
        type="number"
        inputMode="decimal"
        value={props.value}
        min={props.min}
        max={props.max}
        step={props.step ?? 1}
        onChange={props.onChange}
      />
    </label>
  )
}
