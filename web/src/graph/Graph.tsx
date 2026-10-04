/**
 * "The codebase's brain" — a WebGL knowledge-graph view of the live trovex
 * index. Docs, code files, tickets and decisions are nodes; typed doc_links are
 * edges. The differentiator is the lenses: the same layout, repainted to show
 * lifecycle status, real agent-read heat, drift, or node type — an instant
 * reducer repaint, never a relayout.
 *
 * Rendering: sigma.js v3 (WebGL) + graphology. ForceAtlas2 runs in a worker so
 * the main thread stays at 60fps; Louvain finds communities we cluster and
 * label. Node SHAPE is a stable pictogram (kind); node COLOUR is the current
 * lens — the two never fight, which is what keeps it from reading like a
 * generic Obsidian blob.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import {
  SigmaContainer,
  useCamera,
  useLoadGraph,
  useRegisterEvents,
  useSetSettings,
  useSigma,
} from '@react-sigma/core'
import { MultiDirectedGraph } from 'graphology'
import forceAtlas2 from 'graphology-layout-forceatlas2'
import FA2Layout from 'graphology-layout-forceatlas2/worker'
import louvain from 'graphology-communities-louvain'
import { NodePictogramProgram } from '@sigma/node-image'
import { EdgeArrowProgram, EdgeLineProgram } from 'sigma/rendering'
import type { Settings } from 'sigma/settings'

import {
  type GraphNode,
  type GraphPayload,
  fetchGraph,
  syntheticPayload,
} from './api'
import {
  type LensId,
  EDGE_COLOR,
  KIND_PICTOGRAM,
  LENSES,
  LINEAGE_RELS,
  lensVisual,
} from './lenses'
import SidePanel from './SidePanel'
import { SelectBridge } from './selectBridge'

// ── shared view state ───────────────────────────────────────────────────────
interface GraphState {
  lens: LensId
  setLens: (l: LensId) => void
  selected: string | null
  setSelected: (id: string | null) => void
  maxReads7d: number
  maxReads30d: number
  driftCount: number
}
const Ctx = createContext<GraphState | null>(null)
const useGraphState = () => {
  const v = useContext(Ctx)
  if (!v) throw new Error('GraphState missing')
  return v
}

// ── graphology construction ──────────────────────────────────────────────────
function baseSize(degree: number): number {
  // unlinked docs stay small "corpus dust" so the wired knowledge structure is
  // what the eye lands on; linked nodes grow with their degree.
  if (degree === 0) return 2.4
  return Math.min(24, 5 + Math.sqrt(degree) * 1.9)
}

function buildGraphology(payload: GraphPayload): MultiDirectedGraph {
  const g = new MultiDirectedGraph()
  for (const n of payload.nodes) {
    if (g.hasNode(n.id)) continue
    g.addNode(n.id, {
      // layout seed — fa2 cannot start from an all-zero cloud
      x: Math.random(),
      y: Math.random(),
      label: n.title,
      type: 'pictogram',
      image: KIND_PICTOGRAM[n.kind],
      color: '#9aa6b8',
      size: 5,
      // domain attrs the lens reducer reads
      kind: n.kind,
      status: n.status,
      reads_7d: n.reads_7d,
      reads_30d: n.reads_30d,
      drift: n.drift,
      path: n.path,
    })
  }
  for (const e of payload.edges) {
    if (!g.hasNode(e.src) || !g.hasNode(e.dst)) continue
    const lineage = LINEAGE_RELS.has(e.kind)
    g.addEdge(e.src, e.dst, {
      // typed doc_links are drawn as directed arrows; the co-read backbone is a
      // thin undirected thread underneath.
      type: lineage ? 'arrow' : 'line',
      color: EDGE_COLOR[e.kind] ?? EDGE_COLOR.link,
      size: lineage ? 2.4 : 0.6,
      rel: e.kind,
      zIndex: lineage ? 3 : 1,
    })
  }
  // degree-driven base size (read before layout mutates nothing here)
  g.forEachNode((id) => {
    g.setNodeAttribute(id, 'size', baseSize(g.degree(id)))
  })
  // communities for clustering + labels
  try {
    louvain.assign(g, { nodeCommunityAttribute: 'community' })
  } catch {
    g.forEachNode((id) => g.setNodeAttribute(id, 'community', 0))
  }
  // seed each community in its own angular wedge so fa2 separates them fast
  const comms = new Set<number>()
  g.forEachNode((id) => comms.add(g.getNodeAttribute(id, 'community') as number))
  const order = [...comms]
  g.forEachNode((id) => {
    const c = g.getNodeAttribute(id, 'community') as number
    const a = (order.indexOf(c) / Math.max(1, order.length)) * Math.PI * 2
    const r = 2 + Math.random()
    g.setNodeAttribute(id, 'x', Math.cos(a) * r + Math.random() * 0.4)
    g.setNodeAttribute(id, 'y', Math.sin(a) * r + Math.random() * 0.4)
  })
  return g
}

// ── loader + forceatlas2 worker ──────────────────────────────────────────────
function Loader({ payload }: { payload: GraphPayload }) {
  const loadGraph = useLoadGraph()
  const sigma = useSigma()
  useEffect(() => {
    const g = buildGraphology(payload)
    loadGraph(g)
    if (g.order === 0) return
    const settings = forceAtlas2.inferSettings(g)
    const layout = new FA2Layout(g, {
      settings: {
        ...settings,
        barnesHutOptimize: g.order > 800,
        gravity: 0.6,
        scalingRatio: 12,
        slowDown: 1 + Math.log(g.order + 1),
        adjustSizes: true,
        outboundAttractionDistribution: true,
      },
    })
    layout.start()
    // let it breathe, then freeze — a settled layout is screenshot-worthy and
    // cheap to interact with.
    const ms = Math.min(9000, 2500 + g.order * 1.1)
    const stop = window.setTimeout(() => {
      layout.stop()
      sigma.getCamera().animatedReset({ duration: 400 })
    }, ms)
    return () => {
      window.clearTimeout(stop)
      layout.kill()
    }
  }, [payload, loadGraph, sigma])
  return null
}

// ── lens painter (instant repaint, no relayout) ──────────────────────────────
function LensPainter() {
  const setSettings = useSetSettings()
  const sigma = useSigma()
  const { lens, selected, maxReads7d, maxReads30d } = useGraphState()
  const pulse = useRef(0)

  useEffect(() => {
    const ctx = { maxReads7d, maxReads30d }
    const apply = (reduceExtra = 0) => {
      setSettings({
        nodeReducer: (node, data) => {
          const n: GraphNode = {
            id: node,
            title: data.label,
            path: data.path ?? '',
            kind: data.kind,
            status: data.status,
            reads_7d: data.reads_7d ?? 0,
            reads_30d: data.reads_30d ?? 0,
            drift: data.drift ?? 0,
          }
          const v = lensVisual(lens, n, ctx)
          let size = baseSize(sigma.getGraph().degree(node)) * v.sizeScale
          const color = v.color
          // drift lens pulses the drifted nodes so the eye catches them
          if (lens === 'drift' && n.drift > 0) {
            size *= 1 + 0.18 * reduceExtra
          }
          const res: Record<string, unknown> = { ...data, color, size, zIndex: v.glow > 0.5 ? 3 : 1 }
          if (selected) {
            const graph = sigma.getGraph()
            if (node === selected) {
              res.highlighted = true
              res.size = (size as number) * 1.5
              res.zIndex = 4
            } else if (graph.areNeighbors(selected, node)) {
              res.zIndex = 3
            } else {
              res.color = '#20262f'
              res.label = ''
              res.zIndex = 0
            }
          }
          return res
        },
        edgeReducer: (edge, data) => {
          if (!selected) return data
          const graph = sigma.getGraph()
          if (!graph.hasExtremity(edge, selected)) {
            return { ...data, hidden: true }
          }
          return { ...data, size: (data.size ?? 1) * 1.6, zIndex: 3 }
        },
      } as Partial<Settings>)
    }
    apply(0)

    // only pay for the pulse loop when the drift lens is actually showing drift
    // — and never when the viewer asked for reduced motion.
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const drifted = sigma.getGraph().filterNodes((_, a) => (a.drift ?? 0) > 0).length
    if (lens === 'drift' && drifted > 0 && !reduceMotion) {
      const id = window.setInterval(() => {
        pulse.current = pulse.current === 0 ? 1 : 0
        apply(pulse.current)
      }, 520)
      return () => window.clearInterval(id)
    }
  }, [lens, selected, maxReads7d, maxReads30d, setSettings, sigma])
  return null
}

// ── interactions: click to select, click stage to clear, drag nodes ──────────
function Interactions() {
  const registerEvents = useRegisterEvents()
  const sigma = useSigma()
  const { setSelected } = useGraphState()
  const dragged = useRef<string | null>(null)

  useEffect(() => {
    registerEvents({
      clickNode: (e) => setSelected(e.node),
      clickStage: () => setSelected(null),
      downNode: (e) => {
        dragged.current = e.node
        sigma.getGraph().setNodeAttribute(e.node, 'highlighted', true)
      },
      mousemovebody: (e) => {
        if (!dragged.current) return
        const p = sigma.viewportToGraph(e)
        sigma.getGraph().setNodeAttribute(dragged.current, 'x', p.x)
        sigma.getGraph().setNodeAttribute(dragged.current, 'y', p.y)
        e.preventSigmaDefault()
        e.original.preventDefault()
        e.original.stopPropagation()
      },
      mouseup: () => {
        if (dragged.current) {
          sigma.getGraph().removeNodeAttribute(dragged.current, 'highlighted')
          dragged.current = null
        }
      },
    })
  }, [registerEvents, sigma, setSelected])
  return null
}

// ── community labels — imperative overlay, repositioned each render ───────────
interface CommunityLabel {
  key: number
  gx: number
  gy: number
  text: string
  size: number
}
function CommunityLabels() {
  const sigma = useSigma()
  const registerEvents = useRegisterEvents()
  const boxRef = useRef<HTMLDivElement>(null)
  const [labels, setLabels] = useState<CommunityLabel[]>([])

  // compute once the layout is on screen
  useEffect(() => {
    const t = window.setTimeout(() => {
      const g = sigma.getGraph()
      const acc: Record<number, { x: number; y: number; n: number; top: string; deg: number }> = {}
      g.forEachNode((id, a) => {
        const c = (a.community ?? 0) as number
        const slot = (acc[c] ??= { x: 0, y: 0, n: 0, top: a.label as string, deg: -1 })
        slot.x += a.x as number
        slot.y += a.y as number
        slot.n += 1
        const d = g.degree(id)
        if (d > slot.deg) {
          slot.deg = d
          slot.top = a.label as string
        }
      })
      setLabels(
        Object.entries(acc)
          .filter(([, s]) => s.n >= 8)
          .sort((a, b) => b[1].n - a[1].n)
          .slice(0, 14)
          .map(([k, s]) => ({
            key: Number(k),
            gx: s.x / s.n,
            gy: s.y / s.n,
            text: s.top?.length > 26 ? s.top.slice(0, 25) + '…' : s.top,
            size: s.n,
          })),
      )
    }, 9500)
    return () => window.clearTimeout(t)
  }, [sigma])

  // reposition imperatively on every frame — cheap, no React re-render
  useEffect(() => {
    const place = () => {
      const box = boxRef.current
      if (!box) return
      const children = box.children
      labels.forEach((l, i) => {
        const el = children[i] as HTMLElement | undefined
        if (!el) return
        const p = sigma.graphToViewport({ x: l.gx, y: l.gy })
        el.style.transform = `translate(-50%,-50%) translate(${p.x}px,${p.y}px)`
      })
    }
    registerEvents({ afterRender: place })
    place()
  }, [labels, sigma, registerEvents])

  return (
    <div ref={boxRef} className="community-layer" aria-hidden>
      {labels.map((l) => (
        <span key={l.key} className="community-label">
          {l.text}
          <small>{l.size}</small>
        </span>
      ))}
    </div>
  )
}

// ── search box: fly the camera to a node ──────────────────────────────────────
function SearchBox({ nodes }: { nodes: GraphNode[] }) {
  const { gotoNode } = useCamera({ duration: 650 })
  const { setSelected } = useGraphState()
  const [q, setQ] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // ⌘K / Ctrl-K focuses the search — a real shortcut, not a decorative hint.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const matches = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return []
    return nodes
      .filter((n) => n.title.toLowerCase().includes(s) || n.path.toLowerCase().includes(s))
      .slice(0, 8)
  }, [q, nodes])

  const fly = (id: string) => {
    gotoNode(id)
    setSelected(id)
    setQ('')
  }

  return (
    <div className="search">
      <input
        ref={inputRef}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && matches[0]) fly(matches[0].id)
          if (e.key === 'Escape') setQ('')
        }}
        placeholder="Search the brain…  ⌘K"
        aria-label="Search nodes by title or path"
        spellCheck={false}
      />
      {matches.length > 0 && (
        <ul className="search-results">
          {matches.map((m) => (
            <li key={m.id}>
              <button onClick={() => fly(m.id)}>
                <span className={`dot k-${m.kind}`} />
                <span className="st">{m.title}</span>
                <span className="sp">{m.path}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── perf HUD — live render fps from sigma's own frame events ──────────────────
function PerfHud({ bench }: { bench: boolean }) {
  const sigma = useSigma()
  const registerEvents = useRegisterEvents()
  const frames = useRef<number[]>([])
  const [fps, setFps] = useState(0)
  const [worst, setWorst] = useState(0)

  useEffect(() => {
    registerEvents({ afterRender: () => frames.current.push(performance.now()) })
    const id = window.setInterval(() => {
      const now = performance.now()
      const recent = frames.current.filter((t) => t > now - 1000)
      frames.current = recent
      if (recent.length > 2) {
        const deltas = recent.slice(1).map((t, i) => t - recent[i])
        const maxDelta = Math.max(...deltas)
        setFps(Math.round(recent.length))
        setWorst(Math.round(maxDelta * 10) / 10)
      } else {
        setFps(0)
      }
    }, 500)
    return () => window.clearInterval(id)
  }, [registerEvents])

  return (
    <div className={`perf-hud ${bench ? 'bench' : ''}`}>
      <strong>{fps || '—'}</strong> fps
      <span>{sigma.getGraph().order.toLocaleString()} nodes</span>
      {worst > 0 && <span>worst frame {worst} ms</span>}
    </div>
  )
}

// ── bench orbiter — drives the camera so the HUD reads *interactive* fps ──────
function Orbiter() {
  const sigma = useSigma()
  useEffect(() => {
    const cam = sigma.getCamera()
    const base = cam.getState()
    let raf = 0
    const t0 = performance.now()
    const tick = () => {
      const t = (performance.now() - t0) / 1000
      cam.setState({
        x: base.x + Math.sin(t * 0.7) * 0.12,
        y: base.y + Math.cos(t * 0.5) * 0.12,
        ratio: base.ratio * (1 + 0.35 * Math.sin(t * 0.9)),
        angle: Math.sin(t * 0.25) * 0.25,
      })
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [sigma])
  return null
}

// ── lens toggle + legend ──────────────────────────────────────────────────────
function LensBar() {
  const { lens, setLens, driftCount } = useGraphState()
  return (
    <div className="lensbar">
      <div className="lens-tabs" role="tablist" aria-label="Engineering lenses">
        {LENSES.map((l) => (
          <button
            key={l.id}
            role="tab"
            aria-selected={lens === l.id}
            className={lens === l.id ? 'on' : ''}
            onClick={() => setLens(l.id)}
            title={l.hint}
          >
            {l.label}
            {l.id === 'drift' && driftCount > 0 && <em>{driftCount}</em>}
          </button>
        ))}
      </div>
      <p className="lens-hint">{LENSES.find((l) => l.id === lens)?.hint}</p>
    </div>
  )
}

// ── top-level ─────────────────────────────────────────────────────────────────
function readSynthetic(): number {
  const n = Number(new URLSearchParams(window.location.search).get('synthetic'))
  return Number.isFinite(n) && n > 0 ? Math.min(n, 20000) : 0
}

export default function Graph() {
  const synthetic = readSynthetic()
  const [payload, setPayload] = useState<GraphPayload | null>(() =>
    synthetic ? syntheticPayload(synthetic) : null,
  )
  const [error, setError] = useState<string | null>(null)
  const [lens, setLens] = useState<LensId>('status')
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    if (synthetic) return
    fetchGraph()
      .then(setPayload)
      .catch((e) => setError(String(e)))
  }, [synthetic])

  const stats = useMemo(() => {
    const ns = payload?.nodes ?? []
    return {
      maxReads7d: ns.reduce((m, n) => Math.max(m, n.reads_7d), 0),
      maxReads30d: ns.reduce((m, n) => Math.max(m, n.reads_30d), 0),
      driftCount: ns.filter((n) => n.drift > 0).length,
    }
  }, [payload])

  const value: GraphState = {
    lens,
    setLens,
    selected,
    setSelected: useCallback((id: string | null) => setSelected(id), []),
    ...stats,
  }

  const settings = useMemo<Partial<Settings>>(
    () => ({
      allowInvalidContainer: true,
      defaultNodeType: 'pictogram',
      nodeProgramClasses: { pictogram: NodePictogramProgram },
      edgeProgramClasses: { line: EdgeLineProgram, arrow: EdgeArrowProgram },
      defaultEdgeType: 'line',
      labelFont: "'Fira Code', ui-monospace, monospace",
      labelColor: { color: '#c3ccd9' },
      labelSize: 11,
      labelWeight: '500',
      labelDensity: 0.5,
      labelGridCellSize: 140,
      labelRenderedSizeThreshold: 10,
      renderEdgeLabels: false,
      zIndex: true,
      hideEdgesOnMove: true,
      hideLabelsOnMove: false,
    }),
    [],
  )

  return (
    <Ctx.Provider value={value}>
     <SelectBridge.Provider value={(id: string) => setSelected(id)}>
      <div className="brain">
        <header className="brain-head">
          <div className="title">
            <span className="mark">◆</span> the codebase&rsquo;s brain
            <span className="sub">
              {payload ? `${payload.nodes.length} nodes · ${payload.edges.length} links` : 'loading index…'}
            </span>
          </div>
        </header>

        {error && <div className="brain-error">couldn&rsquo;t reach the local index. is <code>trovex serve</code> running? ({error})</div>}

        {payload && payload.nodes.length > 0 && (
          <SigmaContainer className="stage" settings={settings} graph={MultiDirectedGraph}>
            <Loader payload={payload} />
            <LensPainter />
            <Interactions />
            <CommunityLabels />
            <LensBar />
            <SearchBox nodes={payload.nodes} />
            <PerfHud bench={synthetic > 0} />
            {synthetic > 0 && <Orbiter />}
          </SigmaContainer>
        )}

        {payload && payload.nodes.length === 0 && !error && (
          <div className="brain-empty">the index is empty. run <code>trovex index</code> first.</div>
        )}

        <SidePanel id={selected} onClose={() => setSelected(null)} />
      </div>
     </SelectBridge.Provider>
    </Ctx.Provider>
  )
}
