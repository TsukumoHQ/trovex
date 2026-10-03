/**
 * Engineering lenses — the differentiator. Each lens is a pure function from a
 * node (+ a global max, for normalisation) to a colour + size multiplier.
 * Shape (the pictogram) always encodes the node KIND and never changes with
 * the lens; only colour/size/glow do, so a lens switch is an instant reducer
 * repaint with no relayout.
 */
import type { GraphNode, NodeKind, NodeStatus } from './api'

export type LensId = 'status' | 'heat' | 'drift' | 'type'

export interface LensDef {
  id: LensId
  label: string
  hint: string
}

export const LENSES: LensDef[] = [
  { id: 'status', label: 'Status', hint: 'canonical · plan · stale · superseded · duplicate' },
  { id: 'heat', label: 'Agent heat', hint: 'glow by what agents actually read (7d) · dead docs dimmed' },
  { id: 'drift', label: 'Drift', hint: 'docs whose cited code changed since, pulsing red' },
  { id: 'type', label: 'Node type', hint: 'doc · code · ticket · decision' },
]

// Brand palette (from web/src/index.css :root). Kept in sync by hand; these
// are the same hexes the Jinja app and landing use.
export const STATUS_COLOR: Record<NodeStatus, string> = {
  canonical: '#22c55e',
  plan: '#60a5fa',
  stale: '#ef4444',
  superseded: '#a78bfa',
  duplicate: '#f59e0b',
  unknown: '#5a6577',
}

export const KIND_COLOR: Record<NodeKind, string> = {
  doc: '#22c55e',
  code: '#60a5fa',
  ticket: '#f59e0b',
  decision: '#a78bfa',
}

export const KIND_LABEL: Record<NodeKind, string> = {
  doc: 'Doc',
  code: 'Code file',
  ticket: 'Ticket',
  decision: 'Decision',
}

const DIM = '#2b323f' // dead / never-read

/** Mix two #rrggbb colours; t=0 => a, t=1 => b. */
function mix(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16))
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16))
  const p = pa.map((x, i) => Math.round(x + (pb[i] - x) * t))
  return '#' + p.map((x) => x.toString(16).padStart(2, '0')).join('')
}

export interface LensVisual {
  color: string
  /** size multiplier applied on top of the degree-derived base size */
  sizeScale: number
  /** 0..1 — drives an additive halo; heat/drift use it */
  glow: number
}

export interface LensContext {
  maxReads7d: number
  maxReads30d: number
}

export function lensVisual(lens: LensId, n: GraphNode, ctx: LensContext): LensVisual {
  switch (lens) {
    case 'status':
      return { color: STATUS_COLOR[n.status] ?? STATUS_COLOR.unknown, sizeScale: 1, glow: 0 }

    case 'type':
      return { color: KIND_COLOR[n.kind], sizeScale: 1, glow: 0 }

    case 'heat': {
      const max = ctx.maxReads7d || 1
      const t = Math.min(1, n.reads_7d / max)
      if (n.reads_7d === 0) return { color: DIM, sizeScale: 0.7, glow: 0 }
      // cold -> hot: muted blue to trovex green to warm amber
      const color = t < 0.5 ? mix('#3b82f6', '#22c55e', t * 2) : mix('#22c55e', '#fbbf24', (t - 0.5) * 2)
      return { color, sizeScale: 1 + t * 0.9, glow: t }
    }

    case 'drift': {
      if (n.drift <= 0) return { color: '#334155', sizeScale: 0.85, glow: 0 }
      const t = Math.min(1, n.drift)
      return { color: mix('#f59e0b', '#ef4444', t), sizeScale: 1 + t * 0.6, glow: t }
    }
  }
}

// ---- Pictograms: one crisp mono SVG per kind, tinted at render time by the
// node `color` (NodePictogramProgram, drawingMode:'color'). Shape == kind. ----
function dataUri(svg: string): string {
  return 'data:image/svg+xml;base64,' + btoa(svg)
}

const SVG_DOC = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="#fff"/></svg>`
const SVG_CODE = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="3.5" y="3.5" width="17" height="17" rx="2.5" fill="#fff"/></svg>`
const SVG_TICKET = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 2.5 L21.5 20 L2.5 20 Z" fill="#fff"/></svg>`
const SVG_DECISION = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 2 L22 12 L12 22 L2 12 Z" fill="#fff"/></svg>`

export const KIND_PICTOGRAM: Record<NodeKind, string> = {
  doc: dataUri(SVG_DOC),
  code: dataUri(SVG_CODE),
  ticket: dataUri(SVG_TICKET),
  decision: dataUri(SVG_DECISION),
}

/** Edge colour by link kind. Typed doc_links are the loud lineage overlay;
 *  co-read is the faint agent-usage backbone underneath. */
export const EDGE_COLOR: Record<string, string> = {
  supersedes: '#a78bfa',
  'verdict-of': '#22c55e',
  'decided-in': '#60a5fa',
  'resume-of': '#f59e0b',
  'co-read': 'rgba(120,140,170,0.09)',
  relates: 'rgba(148,163,184,0.18)',
  link: 'rgba(148,163,184,0.18)',
}

/** True for the explicit, typed doc_links we want drawn loud on top. */
export const LINEAGE_RELS = new Set(['supersedes', 'verdict-of', 'decided-in', 'resume-of'])
