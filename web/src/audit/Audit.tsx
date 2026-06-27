/**
 * trovex.dev/audit: "is your agent setup burning tokens?" self-audit.
 *
 * Ungated lead magnet (content doc 4f28762f, voice-gated). A developer ticks a
 * 13-point checklist; the live score lands them in one of three bands. The value
 * is the audit itself: a low score honestly says "you don't need trovex yet,"
 * which is what makes the high-score readers trust the rest. Step 1 is "install
 * and measure" (activation); the 9+ band carries the single soft consulting
 * endplate to tsukumo.ch (convert layer, property-split canon v1.1).
 *
 * No backend, no PII, no email gate. Three events (confirmed w/ analytics-lead):
 * audit_view on mount, command_copied on an install-line copy, tsukumo_clicked
 * on the consulting endplate.
 */
import { useEffect, useMemo, useState } from 'react'
import { track, trackAuditView, trackTsukumoClick } from '../analytics'

// The single soft consulting endplate (9+ band). LINKS canon: the canonical branded
// short link, never a hand-rolled UTM. /go/consulting fires the Plausible Link Click
// server-side then 308s to /consulting; ?s=magnet is the per-surface attribution.
const BOOK_URL = 'https://tsukumo.ch/go/consulting?s=magnet'

type Item = { id: string; text: string }
type Group = { title: string; items: Item[] }

const GROUPS: Group[] = [
  {
    title: 'Your docs',
    items: [
      { id: 'docs-count', text: 'Your repo has more than ~20 markdown files (runbooks, ADRs, READMEs, wikis, notes).' },
      { id: 'docs-dupe', text: "Two or more docs cover the same topic, and you couldn't say which is canonical without opening them." },
      { id: 'docs-stale', text: 'At least one doc is stale but still sitting in the repo where an agent can read it.' },
      { id: 'docs-signal', text: 'You don’t have a reliable signal (a marker, a convention) for "this is the current one."' },
    ],
  },
  {
    title: 'Your agents',
    items: [
      { id: 'agent-grep', text: 'Your agent lists or greps files, then opens several, before it answers a doc question.' },
      { id: 'agent-stale', text: "You've seen it cite or follow an old or duplicate doc." },
      { id: 'agent-reread', text: 'It re-reads the same files in a new session because nothing carried over.' },
      { id: 'agent-many', text: 'You run more than one agent, or more than one session a day, on the same repo.' },
    ],
  },
  {
    title: 'Your team',
    items: [
      { id: 'team-rederive', text: "A teammate's agent re-derives things yours already figured out." },
      { id: 'team-chatlog', text: 'Knowledge an agent discovered (an incident, a decision) lives only in a chat log, not anywhere the next agent can read it.' },
      { id: 'team-blob', text: 'Your CLAUDE.md / AGENTS.md has grown into a long blob that’s half out of date.' },
    ],
  },
  {
    title: 'Your bill',
    items: [
      { id: 'bill-unknown', text: "You can't say how many tokens go to doc lookups versus real work." },
      { id: 'bill-trend', text: "Your agent token spend is trending up and you're not sure which part is avoidable." },
    ],
  },
]

const TOTAL = GROUPS.reduce((n, g) => n + g.items.length, 0)

type Band = { key: string; label: string; body: string }
function bandFor(score: number): Band {
  if (score <= 3)
    return {
      key: 'low',
      label: '0–3 · low',
      body: "Your doc set is small or tidy. Rereading isn't your problem; keep your setup. Honest answer: you probably don't need trovex yet.",
    }
  if (score <= 8)
    return {
      key: 'real',
      label: '4–8 · real tax',
      body: "You're paying for guessing on most sessions. A canonical-doc layer pays for itself quickly. This is the typical solo / small-repo case.",
    }
  return {
    key: 'compounding',
    label: '9+ · compounding',
    body: 'The cost multiplies across agents, sessions, and teammates, and the inconsistency is already causing wrong answers. This gets expensive fast and is hardest to fix by hand.',
  }
}

/* Copyable command: one click to run, no hand-typing. Fires command_copied
 * (closed-enum id, no PII) so install-intent from the audit is measurable. */
function CopyCmd({ cmd, id }: { cmd: string; id: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard
      ?.writeText(cmd)
      .then(() => {
        setCopied(true)
        track('command_copied', { command: id })
        setTimeout(() => setCopied(false), 1500)
      })
      .catch(() => {})
  }
  return (
    <span className="cmd-row">
      <code>{cmd}</code>
      <button type="button" className="cmd-copy" onClick={copy} aria-label={`Copy: ${cmd}`}>
        {copied ? 'copied' : 'copy'}
      </button>
    </span>
  )
}

export default function Audit() {
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  useEffect(() => {
    trackAuditView()
  }, [])

  const score = useMemo(() => Object.values(checked).filter(Boolean).length, [checked])
  const band = bandFor(score)
  const toggle = (id: string) => setChecked((c) => ({ ...c, [id]: !c[id] }))

  return (
    <main className="audit">
      <a className="audit-home" href="/">← trovex</a>

      <header className="audit-head">
        <h1>Is your coding agent burning tokens on docs?</h1>
        <p className="audit-sub">A 5-minute self-audit.</p>
        <p className="audit-intro">
          Coding agents reread your repo's markdown every session to work out which doc is
          current, then answer from a guess. You pay for that on every session, every agent,
          every teammate. This audit tells you whether that tax is small or large for your
          setup, before you change anything. Score one point per "yes."
        </p>
      </header>

      <div className="audit-grid">
        <section className="audit-checklist" aria-label="Self-audit checklist">
          {GROUPS.map((g) => (
            <fieldset key={g.title} className="audit-group">
              <legend>{g.title}</legend>
              {g.items.map((it) => (
                <label key={it.id} className={`audit-item${checked[it.id] ? ' is-checked' : ''}`}>
                  <input
                    type="checkbox"
                    checked={!!checked[it.id]}
                    onChange={() => toggle(it.id)}
                  />
                  <span>{it.text}</span>
                </label>
              ))}
            </fieldset>
          ))}
        </section>

        <aside className="audit-score" aria-live="polite">
          <div className={`audit-scorecard band-${band.key}`}>
            <div className="audit-score-num">
              {score}
              <span className="audit-score-of">/ {TOTAL}</span>
            </div>
            <div className="audit-band-label">{band.label}</div>
            <p className="audit-band-body">{band.body}</p>
          </div>
        </aside>
      </div>

      <section className="audit-do">
        <h2>What to do about it</h2>
        <ol>
          <li>
            <strong>Measure it first.</strong> Don't guess at the guessing. Point trovex at the
            repo and read the savings number on your own docs:
            <span className="audit-cmds">
              <CopyCmd cmd="uvx trovex index /path/to/your/repo" id="audit-index" />
              <CopyCmd cmd="uvx trovex serve" id="audit-serve" />
            </span>
            <span className="audit-note">
              (Or <code>uv tool install trovex</code> once, then <code>trovex index ...</code>.)
              The Savings tab shows would-have-read versus actual tokens. That's your real
              number. Want it without installing?{' '}
              <a
                className="audit-link"
                href="/savings"
                onClick={() => track('cta_clicked', { cta_id: 'estimate-savings', location: 'audit' })}
              >
                estimate it in the browser →
              </a>
            </span>
          </li>
          <li>
            <strong>Make one doc per topic canonical.</strong> Mark the current one; let the
            stale and duplicate copies be skipped instead of read.
          </li>
          <li>
            <strong>Give agents one read/write path.</strong> When an agent learns something, it
            should save it once, where every other agent and teammate reads it back, instead of
            re-deriving it.
          </li>
          <li>
            <strong>Re-run the audit in a week.</strong> The score should drop. If it doesn't, the
            bottleneck is somewhere else, and you've spent five minutes to learn that.
          </li>
        </ol>
      </section>

      <section className={`audit-endplate${band.key === 'compounding' ? ' is-live' : ''}`}>
        <p>
          {band.key === 'compounding'
            ? "You scored 9+ and you're rolling agents out across a team. The by-hand version of the steps above is a real project."
            : 'Rolling agents out across a team and the by-hand version is getting heavy?'}{' '}
          tsukumo, the studio behind trovex, sets this up with teams.{' '}
          <a
            className="audit-consult"
            href={BOOK_URL}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => trackTsukumoClick('audit_endplate')}
          >
            Working with a team? →
          </a>
        </p>
      </section>

      <footer className="audit-foot">
        <p>
          trovex is open source and in public beta ·{' '}
          <a href="/" onClick={() => track('cta_clicked', { cta_id: 'home', location: 'audit_footer' })}>
            trovex.dev
          </a>{' '}
          ·{' '}
          <a
            href="https://github.com/TsukumoHQ/trovex"
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => track('github_clicked', { location: 'audit_footer' })}
          >
            GitHub
          </a>
        </p>
      </footer>
    </main>
  )
}
