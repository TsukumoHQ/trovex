/**
 * Data contract for the knowledge-graph view.
 *
 * Mirrors the server's `GET /api/graph` endpoint (server.py, next to
 * /api/map). The graph is the real trovex index: docs, code files, tickets
 * and decisions as nodes; typed doc_links as edges. Everything is read
 * same-origin from the running `trovex serve` process — no modelling, no
 * synthetic data (the perf receipt uses a separate synthetic generator).
 */

/** A node's kind drives its SHAPE (a stable pictogram), never its colour. */
export type NodeKind = 'doc' | 'code' | 'ticket' | 'decision'

/**
 * Canonical lifecycle status from the doc provenance envelope. Drives colour
 * under the "status" lens.
 */
export type NodeStatus =
  | 'canonical'
  | 'plan'
  | 'stale'
  | 'superseded'
  | 'duplicate'
  | 'unknown'

/** Typed doc_links kinds (L2/L3). `supersedes` is drawn as a lineage arrow. */
export type EdgeKind =
  | 'supersedes'
  | 'verdict-of'
  | 'decided-in'
  | 'resume-of'
  | 'co-read'
  | 'relates'
  | 'link'

export interface GraphNode {
  id: string
  title: string
  path: string
  kind: NodeKind
  status: NodeStatus
  /** Real agent reads (results surfaced into an agent's context) over 7 / 30 days. */
  reads_7d: number
  reads_30d: number
  /** 0..1 — docs whose cited code changed since (L5). >0 => drifted. */
  drift: number
}

export interface GraphEdge {
  src: string
  dst: string
  kind: EdgeKind
  weight: number
}

export interface GraphPayload {
  nodes: GraphNode[]
  edges: GraphEdge[]
  /** Echoed query, so the UI can show what slice it is looking at. */
  meta?: { source: string | null; focus: string | null; depth: number }
}

export interface GraphQuery {
  source?: string
  focus?: string
  depth?: number
}

function qs(q: GraphQuery): string {
  const p = new URLSearchParams()
  if (q.source) p.set('source', q.source)
  if (q.focus) p.set('focus', q.focus)
  if (q.depth != null) p.set('depth', String(q.depth))
  const s = p.toString()
  return s ? `?${s}` : ''
}

/**
 * A deterministic synthetic graph for the perf receipt — n nodes, ~4 edges
 * each (so n=5000 ⇒ ~20k edges, the stated budget). NOT real data; only used
 * when the page is opened with ?synthetic=<n>, so the perf number is honest
 * about its source.
 */
export function syntheticPayload(n: number): GraphPayload {
  const kinds: NodeKind[] = ['doc', 'code', 'ticket', 'decision']
  const statuses: NodeStatus[] = ['canonical', 'plan', 'stale', 'superseded', 'duplicate']
  const nodes: GraphNode[] = []
  const clusters = Math.max(4, Math.round(Math.sqrt(n) / 3))
  for (let i = 0; i < n; i++) {
    nodes.push({
      id: String(i),
      title: `node-${i}`,
      path: `src/mod${i % clusters}/file-${i}.ts`,
      kind: kinds[i % kinds.length],
      status: statuses[i % statuses.length],
      reads_7d: Math.floor(Math.random() * 40),
      reads_30d: Math.floor(Math.random() * 120),
      drift: Math.random() < 0.08 ? Math.random() : 0,
    })
  }
  const edges: GraphEdge[] = []
  const rels: EdgeKind[] = ['relates', 'supersedes', 'verdict-of', 'decided-in']
  for (let i = 0; i < n; i++) {
    const base = Math.floor(i / clusters) * clusters
    for (let k = 0; k < 4; k++) {
      const dst = base + Math.floor(Math.random() * clusters)
      if (dst !== i && dst < n) {
        edges.push({ src: String(i), dst: String(dst), kind: rels[k % rels.length], weight: 1 })
      }
    }
  }
  return { nodes, edges, meta: { source: 'synthetic', focus: null, depth: 0 } }
}

export async function fetchGraph(q: GraphQuery = {}): Promise<GraphPayload> {
  const res = await fetch(`/api/graph${qs(q)}`, {
    headers: { accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`/api/graph ${res.status}`)
  }
  return (await res.json()) as GraphPayload
}

/** The rendered doc body for the side panel, reusing the server's doc route. */
export interface DocDetail {
  id: string
  title: string
  path: string
  html: string
}

export async function fetchDoc(id: string): Promise<DocDetail | null> {
  const res = await fetch(`/api/graph/doc/${encodeURIComponent(id)}`, {
    headers: { accept: 'application/json' },
  })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`/api/graph/doc ${res.status}`)
  return (await res.json()) as DocDetail
}
