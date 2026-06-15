import { useEffect, useRef, useState } from 'react'

const REPO = 'https://github.com/Synergix-lab/trovex'
// TODO(human): swap to the real consulting contact (private email / Cal.com booking / form).
// Points at the repo for now so the link works; this is the OSS->consulting funnel entry.
const CONSULT_URL = REPO
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

function Cmd({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  return (
    <span className="cmd">
      <span className="p">$</span>
      <code>{text}</code>
      <button onClick={() => navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500) })} aria-label="Copy command">
        {done ? 'copied' : 'copy'}
      </button>
    </span>
  )
}

const Github = (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.9a3.4 3.4 0 0 0-.9-2.6c3-.3 6.2-1.5 6.2-6.7A5.2 5.2 0 0 0 19 4.8 4.9 4.9 0 0 0 18.9 1S17.7.6 15 2.5a13.4 13.4 0 0 0-7 0C5.3.6 4.1 1 4.1 1A4.9 4.9 0 0 0 4 4.8 5.2 5.2 0 0 0 2.7 8.4c0 5.2 3.2 6.4 6.2 6.7A3.4 3.4 0 0 0 8 17.7V22" />
  </svg>
)
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
  { no: '02', kicker: 'Read', title: 'Hand back only the section that matters', body: 'An agent needs two paragraphs, not the whole file. Trovex serves just the section that answers, so a short answer costs short-answer tokens.', shot: <DocShot />, flip: true },
  { no: '03', kicker: 'Share', title: 'Keep what one agent learns', body: 'One agent figures something out and saves it once. Every other agent, and your teammates, read it back instead of working it out again.', shot: <StoreShot />, flip: false },
]

export default function App() {
  useReveal()
  return (
    <>
      <div className="stage-glow" />
      <div className="stage-grid" />

      <nav className="nav">
        <div className="nav-in">
          <a className="brand" href="/">trovex</a>
          <span className="sp" />
          <a className="lk hide" href="#tour">Product</a>
          <a className="lk" href={REPO} target="_blank" rel="noreferrer">GitHub</a>
          <a className="btn btn-primary nav-cta" href={REPO} target="_blank" rel="noreferrer">Get trovex</a>
        </div>
      </nav>

      <main>
        {/* Hero — category statement */}
        <section className="hero">
          <div className="wrap">
            <h1>trovex is the canonical doc store<br />for your <span className="ac">coding agents</span>.</h1>
            <p className="deck">
              Your agents reread the repo every session to work out which doc is current. trovex keeps
              one canonical copy and hands them the right one. Same answers, about{' '}
              <b style={{ color: 'var(--fg)' }}>60% fewer tokens</b>.
            </p>
            <div className="hero-cta">
              <a className="btn btn-primary" href={REPO} target="_blank" rel="noreferrer">{Github} Get trovex</a>
            </div>
            <Cmd text="uv run trovex index /path/to/repo" />
            <a className="hero-see" href="#tour">see it work ↓</a>
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
                <p className="faq-a">Those are one static file. They go stale, don't scale past a handful of topics, and can't route a question to the right doc or section. Trovex keeps many docs canonical and serves the one that answers.</p>
              </div>
              <div className="faq-item">
                <p className="faq-q">My context window is huge. Why bother?</p>
                <p className="faq-a">The cost compounds: every session, every agent, every teammate. And a big window isn't a current one. Trovex serves the right doc, cheaply, every time.</p>
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

        {/* CTA */}
        <section className="section">
          <div className="wrap">
            <div className="cta reveal">
              <h2>Give your agents one source of truth.</h2>
              <p>Point trovex at your repo. Your agents stop guessing in about a minute.</p>
              <div className="hero-cta">
                <a className="btn btn-primary" href={REPO} target="_blank" rel="noreferrer">{Github} Get trovex</a>
              </div>
              <Cmd text="uv run trovex index /path/to/repo" />
              <p className="cta-note">No cloud, no API keys. Your docs never leave your machine.</p>
            </div>
          </div>
        </section>

        {/* Consulting — quiet, earned, team-lead intent. Not a sales pitch. */}
        <section className="consult-band">
          <div className="wrap">
            <p className="consult">
              Rolling agents out across a team? We consult on doing it well at scale.{' '}
              <a href={CONSULT_URL} target="_blank" rel="noreferrer">Let's talk →</a>
            </p>
          </div>
        </section>

      </main>

      <footer className="footer">
        <div className="wrap footer-in">
          <a className="brand" href="/">trovex</a>
          <span className="sp" />
          <nav className="lks">
            <a href="#tour">Product</a>
            <a href="/vs/">Compare</a>
            <a href={REPO} target="_blank" rel="noreferrer">GitHub</a>
          </nav>
          <small>© 2026 trovex · one source of truth for your agents' docs</small>
        </div>
      </footer>
    </>
  )
}
