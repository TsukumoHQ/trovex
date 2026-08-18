/**
 * Savings-receipt data layer — types, fetch, and the honesty resolver.
 *
 * Consumes trovex-backend's 4 additive REST endpoints (feat/savings-receipt),
 * served same-origin by `trovex serve`. This is a LOCAL dashboard reading the
 * running instance's REAL measured savings — not the client-side estimate at
 * trovex.dev/savings, and not a public page. No analytics, nothing phones home.
 *
 * The honesty rules (CTO brief) are the product's core claim, so they live here
 * as pure, tested functions rather than scattered through JSX:
 *   1. every number carries its `assumption` string;
 *   2. precision=null  → show RAW `saved` with an "unverified routing" caveat,
 *      and never render saved_at_precision (it isn't meaningful yet);
 *      precision set   → LEAD with saved_at_precision, raw is secondary;
 *   3. the `tokenizer` is always stated (o200k_base vs the chars/4 fallback);
 *   4. under-claim — no inflation.
 */

// The trovex server hosts this bundle same-origin with the API, so every fetch
// is a relative /api/* path — no base, no CORS, no injected host seam (that
// decoupled-deploy seam is deliberately deferred; add it only if hosts split).

/** Shape of /api/savings and /api/savings/lifetime. */
export type SavingsTotals = {
  queries: number
  would_have_read: number
  actual_read: number
  response_tokens: number
  saved: number
  ratio: number
  tokenizer: string
  /** null until measured routing precision exists for this instance. */
  precision: number | null
  precision_measured_at: number | null
  /** Only meaningful when precision !== null. */
  saved_at_precision: number | null
  assumption: string
  /** Backend-authored honesty caveat. Non-null ONLY when precision is null. */
  caveat: string | null
}

/** Row of /api/savings/agents. */
export type AgentRow = {
  agent: string
  sessions: number
  queries: number
  would_have_read: number
  saved: number
  saved_at_precision: number | null
  ratio: number
  last_seen: number
}

/** Row of /api/savings/sessions. */
export type SessionRow = {
  session: string
  agent: string
  queries: number
  saved: number
  saved_at_precision: number | null
  would_have_read: number
  last_seen: number
}

export class ApiError extends Error {}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, {
    signal,
    headers: { accept: 'application/json' },
  })
  if (!res.ok) throw new ApiError(`${path} → HTTP ${res.status}`)
  return (await res.json()) as T
}

export const fetchTotals = (days: number, signal?: AbortSignal) =>
  getJson<SavingsTotals>(`/api/savings?days=${days}`, signal)

export const fetchLifetime = (signal?: AbortSignal) =>
  getJson<SavingsTotals>(`/api/savings/lifetime`, signal)

export const fetchAgents = (days: number, signal?: AbortSignal) =>
  getJson<AgentRow[]>(`/api/savings/agents?days=${days}`, signal)

export const fetchSessions = (days: number, signal?: AbortSignal) =>
  getJson<SessionRow[]>(`/api/savings/sessions?days=${days}`, signal)

// ── Honesty resolver ────────────────────────────────────────────────────────

export type Headline = {
  /** true when routing precision was measured — the figure is verified. */
  verified: boolean
  /** The number to show big. */
  saved: number
  /** Human label for the big number. */
  label: string
  /** Secondary figure (the other of raw / at-precision), or null. */
  secondary: { saved: number; label: string } | null
  /** Shown only when NOT verified — the honest caveat. Never hidden. */
  caveat: string | null
}

/**
 * Resolve which savings figure leads and how it must be qualified.
 * The single source of truth for honesty rule #2, so the UI can't drift from it.
 */
export function resolveHeadline(t: SavingsTotals): Headline {
  const verified = t.precision != null && t.saved_at_precision != null
  if (verified) {
    return {
      verified: true,
      saved: t.saved_at_precision as number,
      label: 'tokens saved · routing verified',
      secondary: { saved: t.saved, label: 'raw model estimate' },
      caveat: null,
    }
  }
  return {
    verified: false,
    saved: t.saved,
    label: 'tokens saved · raw model estimate',
    secondary: null,
    // Prefer the backend-authored caveat (SSOT); fall back only if it's absent.
    caveat:
      t.caveat ??
      'Unverified routing: this is the model estimate, not measured against ground-truth precision. ' +
        'The verified figure appears once precision is measured for this instance.',
  }
}

/** Whether a row's at-precision figure may be shown (governed by the run's precision). */
export function showAtPrecision(t: SavingsTotals): boolean {
  return t.precision != null
}
