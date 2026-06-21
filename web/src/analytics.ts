/**
 * Privacy-respecting analytics wrapper for trovex.dev.
 *
 * Design (see growth/analytics/tracking-plan.md):
 *  - No hard dependency: `track()` calls window.plausible if the script is loaded,
 *    and is a no-op otherwise. The site ships zero tracking if no script loads.
 *  - No PII: referrer is reduced to its host, query strings are dropped, every
 *    derived value is a closed enum. No cookies, no fingerprinting, no identifiers.
 *  - GEO source is derived from referrer host + UTM, and is honest about its limits
 *    (AI-engine referrers are often stripped; we report a floor, not a census).
 */

type GeoSource =
  | 'chatgpt'
  | 'perplexity'
  | 'claude'
  | 'gemini'
  | 'copilot'
  | 'bing'
  | 'search'
  | 'social'
  | 'producthunt'
  | 'referral'
  | 'direct'
  | 'unknown'

type Channel = 'ai_engine' | 'search' | 'social' | 'referral' | 'direct'

export type EventName =
  | 'landing_view'
  | 'cta_clicked'
  | 'github_clicked'
  | 'command_copied'
  | 'consult_clicked'
  | 'compare_clicked'
  | 'answers_clicked'
  | 'setup_clicked'
  | 'tsukumo_clicked'
  | 'section_viewed'
  | 'request_access_clicked'
  | 'waitlist_submitted'
  | 'newsletter_signup'
  // canonical cross-property suite→agency funnel (funnel-event-taxonomy memory).
  // trovex = reference impl; wrai.th/yoru inherit this module + fire the same events.
  | 'oss_surface_view'
  | 'oss_adopt'
  | 'suite_to_agency_click'
  // /savings token-savings calculator (spec b9866d6a §5; names confirmed w/ analytics-lead).
  // No PII: only coarse buckets + closed-enum location/trigger props. install-intent REUSES
  // github_clicked{location:'savings_calculator'} — no parallel event (one funnel).
  | 'calculator_run'
  | 'math_shown'
  | 'share_clicked'
  | 'consult_signal_shown'

type Props = Record<string, string>

declare global {
  interface Window {
    plausible?: (event: string, opts?: { props?: Props; callback?: () => void }) => void
  }
}

/* Referrer host → geo_source. Closed map; anything else falls through to referral. */
const HOST_SOURCE: Array<[RegExp, GeoSource]> = [
  [/(^|\.)chatgpt\.com$/, 'chatgpt'],
  [/(^|\.)chat\.openai\.com$/, 'chatgpt'],
  [/(^|\.)openai\.com$/, 'chatgpt'],
  [/(^|\.)perplexity\.ai$/, 'perplexity'],
  [/(^|\.)claude\.ai$/, 'claude'],
  [/(^|\.)gemini\.google\.com$/, 'gemini'],
  [/(^|\.)copilot\.microsoft\.com$/, 'copilot'],
  [/(^|\.)bing\.com$/, 'bing'],
  // Google AI Overviews are not separable from organic Google by referrer — bucket as search.
  [/(^|\.)google\.[a-z.]+$/, 'search'],
  [/(^|\.)duckduckgo\.com$/, 'search'],
  [/(^|\.)(x|twitter)\.com$/, 'social'],
  [/(^|\.)t\.co$/, 'social'],
  [/(^|\.)linkedin\.com$/, 'social'],
  [/(^|\.)lnkd\.in$/, 'social'],
  [/(^|\.)reddit\.com$/, 'social'],
  [/(^|\.)news\.ycombinator\.com$/, 'social'],
  [/(^|\.)lobste\.rs$/, 'social'],
  [/(^|\.)producthunt\.com$/, 'producthunt'],
]

/* UTM source → geo_source. Links WE control are the only reliable AI-engine signal. */
const UTM_SOURCE: Record<string, GeoSource> = {
  chatgpt: 'chatgpt',
  openai: 'chatgpt',
  perplexity: 'perplexity',
  claude: 'claude',
  anthropic: 'claude',
  gemini: 'gemini',
  copilot: 'copilot',
  bing: 'bing',
  google: 'search',
  producthunt: 'producthunt',
  ph: 'producthunt',
  // launch + community sources — map BEFORE launch day or their ROI decays to direct/unknown.
  hackernews: 'social',
  hn: 'social',
  reddit: 'social',
  lobsters: 'social',
  x: 'social',
  twitter: 'social',
  linkedin: 'social',
  discord: 'social',
  'mcp-registry': 'referral',
  newsletter: 'referral',
}

const AI_ENGINES: GeoSource[] = ['chatgpt', 'perplexity', 'claude', 'gemini', 'copilot']

function channelOf(s: GeoSource): Channel {
  if (AI_ENGINES.includes(s)) return 'ai_engine'
  if (s === 'search' || s === 'bing') return 'search'
  if (s === 'social' || s === 'producthunt') return 'social'
  if (s === 'referral') return 'referral'
  return 'direct'
}

function referrerHost(): string {
  try {
    const ref = document.referrer
    if (!ref) return ''
    const host = new URL(ref).hostname.toLowerCase()
    // Same-site referrer (in-page navigation) is not an acquisition source.
    if (host === location.hostname) return ''
    return host
  } catch {
    return ''
  }
}

let cached: Props | null = null

/** Derive the closed-enum session properties once per page load. Host-only, no PII. */
export function deriveSession(): Props {
  if (cached) return cached

  const params = new URLSearchParams(location.search)
  const utmRaw = (params.get('utm_source') || '').toLowerCase().trim()
  const host = referrerHost()

  let geo_source: GeoSource
  if (utmRaw && UTM_SOURCE[utmRaw]) {
    geo_source = UTM_SOURCE[utmRaw] // explicit UTM wins — most reliable
  } else if (host) {
    geo_source = HOST_SOURCE.find(([re]) => re.test(host))?.[1] ?? 'referral'
  } else {
    geo_source = utmRaw ? 'unknown' : 'direct'
  }

  const utm = (k: string): string => {
    const v = (params.get(k) || '').toLowerCase().trim()
    return v ? v.slice(0, 64) : 'none' // cap length; closed-ish, never raw PII
  }

  cached = {
    path: location.pathname,
    referrer: host || 'none', // host only, never full URL
    geo_source,
    channel: channelOf(geo_source),
    utm_source: utm('utm_source'),
    utm_medium: utm('utm_medium'),
    utm_campaign: utm('utm_campaign'),
    utm_content: utm('utm_content'),
  }
  return cached
}

/**
 * Attribution payload to PERSIST with a waitlist signup (server-side), so every
 * signup is traceable to a source. Closed enums + host-only referrer + UTM only —
 * deliberately excludes the email and any PII. The waitlist endpoint stores this
 * next to the (volunteered) email; analytics events never carry the email.
 */
export function getAttribution(): Props {
  return { ...deriveSession() }
}

/** Fire an event with session props merged in. No-op if no analytics script is loaded. */
export function track(event: EventName, props: Props = {}): void {
  if (typeof window === 'undefined' || typeof window.plausible !== 'function') return
  window.plausible(event, { props: { ...deriveSession(), ...props } })
}

/** Call once on mount: the landing_view event carrying GEO/channel attribution. Also fires
 *  the canonical `oss_surface_view` (the cross-property top-of-funnel "reached an OSS
 *  property" event) so the suite→agency dashboard can read trovex's reach. */
export function trackLandingView(): void {
  track('landing_view')
  track('oss_surface_view', { surface: 'trovex' })
}

/* ── Waitlist funnel (primary conversion under the private-beta GTM) ──────────
 * The waitlist CTA + form live in App.tsx (cro-lead's file); these helpers give
 * that surface a one-call hook so it's instrumented from birth:
 *   - on the "request beta access" CTA click → trackRequestAccessClick(location)
 *   - on a SUCCESSFUL waitlist submit         → trackWaitlistSubmitted()
 * waitlist_submitted carries only the source attribution (geo_source/channel/utm_*),
 * never the email. The email is volunteered PII and stays in the waitlist store. */

/** Fire when the "request beta access" CTA is clicked. */
export function trackRequestAccessClick(location: string): void {
  track('request_access_clicked', { location })
}

/** Fire on a successful waitlist submission. No email / no PII — source only. Also fires the
 *  canonical `oss_adopt{kind:waitlist}` (the cross-property adoption event). */
export function trackWaitlistSubmitted(location = 'waitlist'): void {
  track('waitlist_submitted', { location })
  trackOssAdopt('waitlist')
}

/** Fire on a genuinely NEW newsletter signup (server returns body.new). The shared hub
 *  (tsukumo.ch/api/newsletter) dedups; we only count a real insert so bots/duplicates don't
 *  inflate the funnel. No email / no PII — source attribution + location only. */
export function trackNewsletterSignup(location = 'footer'): void {
  track('newsletter_signup', { location })
}

/** Canonical cross-property adoption event. kind = how the dev adopted trovex. Call
 *  trackOssAdopt('install') from the command-copy / quickstart, 'discord' from a Discord join. */
export function trackOssAdopt(kind: 'install' | 'waitlist' | 'discord'): void {
  track('oss_adopt', { tool: 'trovex', kind })
}

/** Fire on a trovex→tsukumo crosslink click: the canonical `suite_to_agency_click` (so the
 *  agency side can attribute which OSS property drove the visit) + trovex's own
 *  `tsukumo_clicked`. `link_location` = where the link sits (consult-band | footer | …). */
export function trackTsukumoClick(link_location: string): void {
  track('tsukumo_clicked', { location: link_location })
  track('suite_to_agency_click', { from_tool: 'trovex', link_location })
}

/**
 * Scroll-depth: fire `section_viewed` once per landing section as it scrolls in.
 * Keys off each `<section>`'s id or first class token (a stable, closed-ish name),
 * so it needs no markup change in App.tsx (cro-lead owns that file). Powers the
 * scroll-depth / hero-pass / FAQ experiments (#7, #10 in the experiment backlog).
 * No-op if IntersectionObserver is unavailable. Returns a cleanup function.
 */
export function trackSectionViews(): () => void {
  if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
    return () => {}
  }
  const sections = Array.from(document.querySelectorAll('main section'))
  const seen = new Set<string>()
  const nameOf = (el: Element): string => {
    const raw = el.id || (el.className || '').toString().split(/\s+/)[0] || 'unknown'
    return raw.toLowerCase().slice(0, 32)
  }
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue
        const name = nameOf(e.target)
        if (seen.has(name)) continue
        seen.add(name)
        track('section_viewed', { section: name })
        io.unobserve(e.target)
      }
    },
    { threshold: 0.4 },
  )
  sections.forEach((s) => io.observe(s))
  return () => io.disconnect()
}

/* ── /savings token-savings calculator ───────────────────────────────────────
 * Helpers for the calculator surface (spec b9866d6a §5 + team-CTA f07e80b7).
 * All props are coarse + closed-enum — NEVER repo names, file paths, or raw
 * inputs. `result_pct` is a bucket, not the exact ratio. */

/** Bucket a 0–1 savings ratio into a coarse label so the event carries no fine-grained
 *  (re-identifiable) value — just the band. */
export function pctBucket(ratio: number): string {
  const p = Math.round(ratio * 100)
  if (p <= 0) return '0'
  if (p < 25) return '1-24'
  if (p < 50) return '25-49'
  if (p < 65) return '50-64'
  if (p < 80) return '65-79'
  return '80+'
}

/** Fire once when the calculator produces a result (debounced by the caller). Coarse only. */
export function trackCalculatorRun(resultBucket: string): void {
  track('calculator_run', { mode: 'inputs', result_pct: resultBucket })
}

/** "show the math" toggle opened. */
export function trackMathShown(): void {
  track('math_shown')
}

/** A share artifact was copied (link | tweet | badge). */
export function trackShareClicked(format: string): void {
  track('share_clicked', { format })
}

/** Install-intent (a "star on GitHub" / install CTA click) → github_clicked, segmented by
 *  `location` so the landing's install funnel reads apart from the calculator's (spec §5:
 *  one funnel, no parallel to_install_click). Defaults to 'savings_calculator' for the
 *  calculator call sites that pass nothing; landing CTAs pass their own location. */
export function trackInstallClick(location = 'savings_calculator'): void {
  track('github_clicked', { location })
}

/** The team-scale consulting micro-CTA rendered (honest threshold met). Measures show→click
 *  against the canonical suite_to_agency_click fired by trackTsukumoClick on the link. */
export function trackConsultSignalShown(trigger: string): void {
  track('consult_signal_shown', { location: 'savings_calculator', trigger })
}
