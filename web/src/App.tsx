import { useEffect, useRef, useState } from 'react'
import { track, trackLandingView, trackInstallClick, trackTsukumoClick, trackNewsletterSignup, getAttribution } from './analytics'

// trovex is public beta: the primary action is install + a GitHub star. The consult band
// is the suite→agency handoff (experiments-batch-1.md E2): it crosses to tsukumo, UTM'd so
// tsukumo reads it as source=suite and the loop closes to assessment_request.
const CONSULT_URL =
  'https://tsukumo.ch/consulting?utm_source=trovex&utm_medium=oss-suite&utm_campaign=consulting'
const reduceMotion =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/* ── reveal ──────────────────────────────────────────────────────── */
function useReveal() {
  useEffect(() => {
    if (reduceMotion) return
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && e.target.classList.add('in')),
      { rootMargin: '0px 0px -10% 0px', threshold: 0.12 },
    )
    document.querySelectorAll('.reveal').forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])
}

/* ── scroll-driven 3D untilt for the hero window ─────────────────── */
function useTilt(ref: React.RefObject<HTMLDivElement | null>) {
  useEffect(() => {
    if (reduceMotion) return
    const el = ref.current
    if (!el) return
    let raf = 0
    const onScroll = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect()
        const vh = window.innerHeight
        const p = Math.min(1, Math.max(0, 1 - (r.top - vh * 0.18) / (vh * 0.7)))
        el.style.transform = `perspective(2200px) rotateX(${(1 - p) * 15}deg) scale(${0.95 + p * 0.05}) translateY(${(1 - p) * 22}px)`
      })
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => { window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll); cancelAnimationFrame(raf) }
  }, [ref])
}

function useCount(to: number, on: boolean) {
  const [n, setN] = useState(reduceMotion ? to : 0)
  useEffect(() => {
    if (!on || reduceMotion) { setN(to); return }
    let raf = 0
    const start = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 1100)
      setN(Math.round(to * (1 - Math.pow(1 - p, 3))))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [on, to])
  return n
}

function useInView(ref: React.RefObject<HTMLElement | null>, threshold = 0.3) {
  const [on, setOn] = useState(reduceMotion)
  useEffect(() => {
    if (reduceMotion) return
    const node = ref.current
    if (!node) return
    const io = new IntersectionObserver((e) => e[0].isIntersecting && (setOn(true), io.disconnect()), { threshold })
    io.observe(node)
    return () => io.disconnect()
  }, [ref, threshold])
  return on
}

const Chrome = ({ url }: { url: string }) => (
  <div className="win-chrome">
    <div className="dots"><i /><i /><i /></div>
    <span className="win-url">{url}</span>
    <span style={{ width: 40 }} />
  </div>
)

/* ── HERO WINDOW: real Trovex savings dashboard ──────────────────── */
function HeroWindow() {
  const ref = useRef<HTMLDivElement>(null)
  const onRef = useRef<HTMLDivElement>(null)
  useTilt(ref)
  const on = useInView(onRef)
  const saved = useCount(1_240_000, on)
  const docs = useCount(842, on)
  const queries = useCount(1204, on)
  const canon = useCount(96, on)
  return (
    <div className="stage-wrap">
      <div className="window" ref={ref}>
        <div className="win-glow" />
        <Chrome url="trovex · localhost:8765/savings" />
        <div className="app" ref={onRef}>
          <div className="app-top">
            <span className="b">trovex</span>
            <div className="tabs"><a>Overview</a><a className="on">Savings</a><a>Docs</a><a>Search</a></div>
            <span className="meta"><span className="pulse" />indexed on write</span>
          </div>
          <div className="sav">
            <div className="sav-main">
              <div className="sav-eyebrow">SAVED · LAST 7 DAYS</div>
              <div className="sav-num">{saved.toLocaleString('en-US')}<span className="u">tokens</span></div>
              <div className="sav-ratio">
                <span className="sav-bar"><span className="sav-fill" style={{ width: on ? '60%' : 0 }} /></span>
                <b>60%</b><span>reduction vs no-trovex</span>
              </div>
            </div>
            <div className="sav-side">
              <div className="sav-row"><span className="k">would have read</span><span className="v">2,068,000</span></div>
              <div className="sav-row"><span className="k">actual read (top-1)</span><span className="v">828,000</span></div>
              <div className="sav-row hl"><span className="k">saved</span><span className="v">1,240,000</span></div>
            </div>
          </div>
          <div className="kpis">
            <div className="kpi"><div className="l">docs indexed</div><div className="v">{docs.toLocaleString('en-US')}</div></div>
            <div className="kpi"><div className="l">lookups · 7d</div><div className="v">{queries.toLocaleString('en-US')}</div></div>
            <div className="kpi"><div className="l">canonical</div><div className="v">{canon}<small>%</small></div></div>
          </div>
          <div className="tbl">
            <div className="tr"><span className="th">doc</span><span className="th">status</span><span className="th">saved</span></div>
            <div className="tr"><span className="path">deploy/runbook.md</span><span className="pill pill-canonical"><span className="d" />canonical</span><span className="num">312k</span></div>
            <div className="tr"><span className="path">architecture/overview.md</span><span className="pill pill-canonical"><span className="d" />canonical</span><span className="num">204k</span></div>
            <div className="tr"><span className="path">ops/postmortem-0420.md</span><span className="pill pill-stale"><span className="d" />stale</span><span className="num">—</span></div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── SHOT 1: search → one canonical answer ───────────────────────── */
function SearchShot() {
  return (
    <div className="shot reveal">
      <Chrome url="trovex · search" />
      <div className="s-pad">
        <div className="s-input"><span className="ic">›</span><span className="q">how do we roll back a deploy?</span><span className="car" /><span className="kbd">↵</span></div>
        <div className="s-bar">3 results · 12ms · ranked</div>
        <div className="res top">
          <div className="res-head">
            <span className="pill pill-canonical"><span className="d" />canonical</span>
            <span className="path">deploy/runbook.md</span>
            <span className="age">updated 3d ago</span>
          </div>
          <div className="res-sec">## Rolling back a deploy</div>
          <div className="res-snip">Revert the release commit, then run <span className="mono">./deploy rollback</span>. The previous image is kept warm for 24h…</div>
          <div className="res-foot"><span className="served">served · ~280 tokens</span></div>
        </div>
        <div className="res dim">
          <div className="res-head"><span className="pill pill-stale"><span className="d" />stale</span><span className="path">ops/postmortem-0420.md</span><span className="age">skipped</span></div>
        </div>
        <div className="res dim">
          <div className="res-head"><span className="pill pill-duplicate"><span className="d" />duplicate</span><span className="path">wiki/old-deploy.md</span><span className="age">skipped</span></div>
        </div>
      </div>
    </div>
  )
}

/* ── SHOT 2: doc reader → one section served ─────────────────────── */
function DocShot() {
  return (
    <div className="shot reveal">
      <Chrome url="trovex · /doc/dq7f2a" />
      <div className="reader">
        <div className="r-main">
          <div className="r-back">← docs</div>
          <div className="r-title">Deploy runbook</div>
          <div className="r-meta">
            <span className="pill pill-canonical"><span className="d" />canonical</span>
            <span className="r-id">dq7f2a</span>
            <span>updated 3d ago</span>
          </div>
          <div className="r-body">
            <p className="dim">## On call</p>
            <div className="r-hl">
              <p className="h">## Rolling back a deploy</p>
              <p>Revert the release commit and redeploy the previous image.</p>
              <pre>git revert --no-edit &lt;sha&gt;{'\n'}./deploy rollback --to last-green</pre>
            </div>
            <p className="dim">## Smoke tests</p>
          </div>
        </div>
        <aside className="r-toc">
          <div className="toc-l">On this page</div>
          <a>On call</a>
          <a className="on">Rolling back</a>
          <a>Smoke tests</a>
          <div className="toc-served mono">1 section served<br />~280 tokens</div>
        </aside>
      </div>
    </div>
  )
}

/* ── SHOT 3: store → agents share what they learn ────────────────── */
function StoreShot() {
  return (
    <div className="shot reveal">
      <Chrome url="trovex · store" />
      <div className="store">
        <aside className="st-side">
          <div className="st-l">kind</div>
          <div className="st-link on">record <span>128</span></div>
          <div className="st-link">note <span>54</span></div>
          <div className="st-link">reference <span>312</span></div>
        </aside>
        <div className="st-list">
          <div className="st-row">
            <div className="st-head"><span className="pill pill-plan"><span className="d" />record</span><span className="st-t">incident: api 504s after deploy</span></div>
            <div className="st-by">written by agent · 2h ago</div>
          </div>
          <div className="st-row">
            <div className="st-head"><span className="pill pill-plan"><span className="d" />record</span><span className="st-t">decision: pin sqlite-vec 0.1.6</span></div>
            <div className="st-by">written by agent · 1d ago</div>
          </div>
          <div className="st-row">
            <div className="st-head"><span className="pill pill-canonical"><span className="d" />canonical</span><span className="st-t">rollback steps that actually worked</span></div>
            <div className="st-by">read by 3 agents · 1 teammate</div>
          </div>
        </div>
      </div>
    </div>
  )
}

const FEATURES = [
  { no: '01', kicker: 'Find', title: 'Serve one canonical answer', body: 'Your agent asks in plain language and gets back the one current doc, down to the line. The stale and duplicate copies never reach its context.', shot: <SearchShot />, flip: false },
  { no: '02', kicker: 'Read', title: 'Hand back only the section that matters', body: 'An agent needs two paragraphs, not the whole file. trovex serves just the section that answers, so a short answer costs short-answer tokens.', shot: <DocShot />, flip: true },
  { no: '03', kicker: 'Share', title: 'Keep what one agent learns', body: 'One agent figures something out and saves it once. Every other agent, and your teammates, read it back instead of working it out again.', shot: <StoreShot />, flip: false },
]

// trovex is open source + public beta — the install command is the conversion.
const GITHUB = 'https://github.com/TsukumoHQ/trovex'
// Public-beta support channel (one redirect everyone links — tsukumo.ch/slack).
const SLACK_URL = 'https://tsukumo.ch/slack'
// Sibling OSS tool in the tsukumo suite — now has its own landing (live).
const WRAITH_URL = 'https://tsukumo.ch/wraith?utm_source=trovex&utm_medium=oss-suite&utm_campaign=wraith'
// Shared newsletter hub — ONE Resend audience across the suite (fullstack contract).
// source_site routes attribution; CORS allows trovex.dev. Privacy controller = tsukumo.
const NEWSLETTER_API = 'https://tsukumo.ch/api/newsletter'
const PRIVACY_URL = 'https://tsukumo.ch/privacy'

/* ── Newsletter capture: low-key, double-opt-in, GDPR-clean ──────────
 * One email field + explicit opt-in (unchecked, gates submit) + honeypot. Posts to the
 * shared hub; fires newsletter_signup only on a genuine new insert (no email in analytics,
 * no bot/dup inflation). Not above the fold — the install stays the one primary action. */
type NewsState = 'idle' | 'submitting' | 'ok' | 'already' | 'error'
function NewsletterBand() {
  const [email, setEmail] = useState('')
  const [optIn, setOptIn] = useState(false)
  const [website, setWebsite] = useState('') // honeypot
  const [state, setState] = useState<NewsState>('idle')

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (state === 'submitting' || !optIn) return
    setState('submitting')
    try {
      const res = await fetch(NEWSLETTER_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, website, source_site: 'trovex', ...getAttribution() }),
      })
      const body = await res.json().catch(() => ({}))
      if (res.ok) {
        if (body.new) trackNewsletterSignup('trovex_landing') // only a real new signup counts
        setState(body.status === 'confirmed' && !body.new ? 'already' : 'ok')
        return
      }
      setState('error')
    } catch {
      setState('error')
    }
  }

  return (
    <section className="news-band">
      <div className="wrap news-in">
        <div className="news-copy">
          <div className="news-eyebrow">Newsletter</div>
          <h2 className="news-h">Field notes on running agents in production</h2>
          <p className="news-deck">When we ship or learn something real about running AI coding agents in production. No filler, no fixed schedule.</p>
        </div>
        {state === 'ok' ? (
          <p className="news-status" role="status">Check your inbox — confirm the link to finish subscribing.</p>
        ) : state === 'already' ? (
          <p className="news-status" role="status">You&apos;re already on the list.</p>
        ) : (
          <form className="news-form" onSubmit={onSubmit} noValidate>
            <div className="news-row">
              <input
                className="news-input"
                type="email"
                required
                value={email}
                autoComplete="email"
                placeholder="your@email.com"
                aria-label="Email"
                onChange={(e) => setEmail(e.target.value)}
              />
              <button className="btn btn-primary news-btn" type="submit" disabled={state === 'submitting' || !optIn}>
                {state === 'submitting' ? 'Sending…' : 'Subscribe'}
              </button>
            </div>
            <label className="news-optin">
              <input type="checkbox" checked={optIn} onChange={(e) => setOptIn(e.target.checked)} />
              <span>Yes, email me the newsletter. I can unsubscribe anytime.</span>
            </label>
            {/* honeypot */}
            <input
              type="text"
              name="website"
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              className="news-hp"
            />
            <p className="news-note">
              Occasional, no spam, never shared. See the{' '}
              <a href={PRIVACY_URL} target="_blank" rel="noopener noreferrer">privacy policy</a>.
            </p>
            <div aria-live="polite" aria-atomic="true">
              {state === 'error' && <p className="news-note news-err">Something broke on our end. Try again in a minute.</p>}
            </div>
          </form>
        )}
      </div>
    </section>
  )
}

export default function App() {
  useReveal()
  useEffect(() => { trackLandingView() }, [])
  return (
    <>
      <div className="stage-glow" />
      <div className="stage-grid" />

      <nav className="nav">
        <div className="nav-in">
          <a className="brand" href="/">trovex</a>
          <span className="sp" />
          <a className="lk hide" href="#tour" onClick={() => track('cta_clicked', { cta_id: 'product', location: 'nav' })}>Product</a>
          <a className="lk hide" href="#start" onClick={() => track('cta_clicked', { cta_id: 'quickstart', location: 'nav' })}>Quickstart</a>
          <a className="btn btn-primary nav-cta" href={GITHUB} target="_blank" rel="noopener noreferrer" onClick={() => trackInstallClick('nav')}>star on GitHub</a>
        </div>
      </nav>

      <main>
        {/* Hero — category statement */}
        <section className="hero">
          <div className="wrap">
            <h1>Stop your <span className="ac">coding agents</span><br />rereading the repo.</h1>
            <p className="deck">
              Your coding agents burn tokens hunting for answers scattered across the repo. trovex is
              the canonical doc store: it serves each agent the single current doc that answers a query,
              with a freshness marker, instead of rereading the repo to guess. Same answers, about{' '}
              <b style={{ color: 'var(--fg)' }}>60% fewer tokens</b>.
            </p>
            <div className="hero-cta">
              <a className="btn btn-primary" href="#start" onClick={() => track('cta_clicked', { cta_id: 'get-started', location: 'hero' })}>get started</a>
              <a className="btn btn-ghost" href={GITHUB} target="_blank" rel="noopener noreferrer" onClick={() => trackInstallClick('hero')}>star on GitHub</a>
            </div>
            <a className="hero-see" href="#tour" onClick={() => track('cta_clicked', { cta_id: 'see-it-work', location: 'hero' })}>see it work ↓</a>
          </div>
          <HeroWindow />
        </section>

        {/* Compatibility — real proof, not fake logos */}
        <section className="compat">
          <div className="wrap">
            <div className="lab">Works with</div>
            <div className="row">
              <span>Claude Code</span><span>Cursor</span><span>Windsurf</span><span>Zed</span><span>any MCP client</span>
            </div>
          </div>
        </section>

        {/* Trust — honest signals, no logos/testimonials (none yet) */}
        <section className="section trust reveal">
          <div className="wrap trust-grid">
            <div className="trust-card">
              <div className="trust-h">Runs on your machine</div>
              <p>Indexing and embeddings run locally in SQLite and ONNX. No cloud, no API keys — your code and docs never leave your machine.</p>
            </div>
            <div className="trust-card">
              <div className="trust-h">Open source, AGPL-3.0</div>
              <p>Read the code and run it yourself. Fork it if you want. No lock-in. The CLI is MIT.</p>
            </div>
            <div className="trust-card">
              <div className="trust-h">~60% fewer tokens, measured</div>
              <p>Counted, not marketing: trovex serves the one canonical doc instead of the top few candidates your agent would otherwise read, and shows you the difference.</p>
            </div>
          </div>
        </section>

        {/* Product tour — numbered features, each a real shot */}
        <div id="tour">
          {FEATURES.map((f) => (
            <section className="section feat" key={f.no}>
              <div className={`wrap feat-grid${f.flip ? ' flip' : ''}`}>
                <div className="feat-text">
                  <div className="feat-no">{f.no} <span>/ {f.kicker}</span></div>
                  <h2>{f.title}</h2>
                  <p>{f.body}</p>
                </div>
                <div className="feat-shot">{f.shot}</div>
              </div>
            </section>
          ))}
        </div>

        {/* FAQ — objection handling */}
        <section className="section" id="faq">
          <div className="wrap">
            <div className="sec-head reveal">
              <div className="kicker">Questions</div>
              <h2>Honest answers</h2>
            </div>
            <div className="faq reveal">
              <div className="faq-item">
                <p className="faq-q">Why not just a CLAUDE.md or AGENTS.md?</p>
                <p className="faq-a">Those are one static file. They go stale, don't scale past a handful of topics, and can't route a question to the right doc or section. trovex keeps many docs canonical and serves the one that answers.</p>
              </div>
              <div className="faq-item">
                <p className="faq-q">My context window is huge. Why bother?</p>
                <p className="faq-a">The cost compounds: every session, every agent, every teammate. And a big window isn't a current one. trovex serves the right doc, cheaply, every time.</p>
              </div>
              <div className="faq-item">
                <p className="faq-q">Is it another service to run?</p>
                <p className="faq-a">One local process. Run <code>trovex serve</code>, point your agent at it, and you're set in about a minute. No cloud, no keys.</p>
              </div>
              <div className="faq-item">
                <p className="faq-q">Does my code leave my machine?</p>
                <p className="faq-a">No. Indexing and embeddings run locally in SQLite and ONNX. Nothing is sent anywhere.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Get started — public beta, the install is the conversion */}
        <section className="section" id="start">
          <div className="wrap">
            <div className="cta reveal">
              <h2>Get started.</h2>
              <p>trovex is open source and in public beta. Install it, point your agent at it, and you're running in about a minute. No account, no keys.</p>
              <ol className="start-steps">
                <li><code>uv tool install git+https://github.com/TsukumoHQ/trovex</code></li>
                <li><code>trovex index /path/to/your/repo</code></li>
                <li><code>trovex search "how do we roll back a deploy?"</code> and it prints the tokens it saved.</li>
              </ol>
              <div className="hero-cta">
                <a className="btn btn-primary" href={GITHUB} target="_blank" rel="noopener noreferrer" onClick={() => trackInstallClick('start')}>star on GitHub</a>
              </div>
              <p className="cta-note">No cloud, no API keys. Your docs never leave your machine.</p>
              <p className="cta-note">
                Questions, or stuck on setup?{' '}
                <a href={SLACK_URL} target="_blank" rel="noopener noreferrer" onClick={() => track('cta_clicked', { cta_id: 'slack', location: 'start' })}>Join the Slack →</a>
              </p>
            </div>
          </div>
        </section>

        {/* Consulting — quiet, earned, team-lead intent. Not a sales pitch. */}
        <section className="consult-band">
          <div className="wrap">
            <p className="consult">
              Rolling agents out across a team? We consult on doing it well at scale.{' '}
              <a
                href={CONSULT_URL}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => trackTsukumoClick('consult-band')}
              >
                Let&apos;s talk →
              </a>
            </p>
          </div>
        </section>

        {/* Newsletter — quiet email capture, below the install. Not a competing CTA. */}
        <NewsletterBand />

      </main>

      <footer className="footer">
        <div className="wrap footer-in">
          <a className="brand" href="/">trovex</a>
          <span className="sp" />
          <nav className="lks">
            <a href="#tour" onClick={() => track('cta_clicked', { cta_id: 'product', location: 'footer' })}>Product</a>
            <a href="/vs/" onClick={() => track('compare_clicked', { location: 'footer' })}>Compare</a>
            <a href="/answers/" onClick={() => track('answers_clicked', { location: 'footer' })}>Answers</a>
            <a href="/blog/" onClick={() => track('cta_clicked', { cta_id: 'blog', location: 'footer' })}>Blog</a>
            <a href="/for/" onClick={() => track('setup_clicked', { location: 'footer' })}>Setup</a>
            <a href={SLACK_URL} target="_blank" rel="noopener noreferrer" onClick={() => track('cta_clicked', { cta_id: 'slack', location: 'footer' })}>Slack</a>
            <a
              href="https://tsukumo.ch/?utm_source=trovex&utm_medium=oss-suite&utm_campaign=consulting"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackTsukumoClick('footer')}
            >
              built by tsukumo ↗
            </a>
          </nav>
          <small className="footer-suite">
            part of the tsukumo suite: <a href="/">trovex</a> (docs) ·{" "}
            <a href={WRAITH_URL} target="_blank" rel="noopener noreferrer" onClick={() => track('cta_clicked', { cta_id: 'wraith', location: 'footer-suite' })}>wrai.th</a> (agent orchestration)
          </small>
          <small>© 2026 trovex · one source of truth for your agents' docs</small>
        </div>
      </footer>
    </>
  )
}
