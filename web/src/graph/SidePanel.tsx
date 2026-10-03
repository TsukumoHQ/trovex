/**
 * Click a node → this panel. It renders the doc (server-rendered markdown from
 * the local index, same renderer as the Jinja doc page), the typed in/out links
 * with their relation as context, and a one-click "open in trovex_read" that
 * copies the exact MCP call an agent would make. Navigating a link re-selects
 * that node, so the panel doubles as a link walker.
 */
import { useContext, useEffect, useState } from 'react'
import type { DocDetail, EdgeKind, NodeKind } from './api'
import { KIND_LABEL, STATUS_COLOR } from './lenses'
import { SelectBridge } from './selectBridge'

interface LinkRow {
  id: string
  title: string
  path: string
  kind: NodeKind
  rel: EdgeKind
}
interface FullDetail extends DocDetail {
  kind: NodeKind
  status: string
  drift: number
  drift_reason: string | null
  reads_7d?: number
  out_links: LinkRow[]
  in_links: LinkRow[]
  ext_id: string | null
}

export default function SidePanel({ id, onClose }: { id: string | null; onClose: () => void }) {
  const select = useContext(SelectBridge)
  const [detail, setDetail] = useState<FullDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!id) return
    let live = true
    const load = async () => {
      setLoading(true)
      setCopied(false)
      try {
        const r = await fetch(`/api/graph/node/${encodeURIComponent(id)}`)
        const d = r.ok ? await r.json() : null
        if (live) setDetail(d)
      } catch {
        if (live) setDetail(null)
      } finally {
        if (live) setLoading(false)
      }
    }
    void load()
    return () => {
      live = false
    }
  }, [id])

  if (!id) return null

  const ref = detail?.ext_id || detail?.path || id
  const readCall = `trovex_read(doc_id="${ref}")`
  const copy = () => {
    void navigator.clipboard?.writeText(readCall)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }

  const linkList = (rows: LinkRow[], dir: 'out' | 'in') =>
    rows.length === 0 ? (
      <p className="muted">none</p>
    ) : (
      <ul className="links">
        {rows.map((l) => (
          <li key={`${dir}-${l.rel}-${l.id}`}>
            <button onClick={() => select(l.id)}>
              <span className="rel">{l.rel}</span>
              <span className={`dot k-${l.kind}`} />
              <span className="lt">{l.title}</span>
            </button>
          </li>
        ))}
      </ul>
    )

  return (
    <aside className="panel" aria-live="polite">
      <button className="panel-x" onClick={onClose} aria-label="Close">
        ×
      </button>
      {loading && <div className="panel-loading">reading…</div>}
      {detail && (
        <>
          <div className="panel-head">
            <span className="kind-badge" data-kind={detail.kind}>
              {KIND_LABEL[detail.kind]}
            </span>
            <span className="status-chip" style={{ ['--c' as string]: STATUS_COLOR[detail.status as keyof typeof STATUS_COLOR] ?? STATUS_COLOR.unknown }}>
              {detail.status}
            </span>
            {detail.drift > 0 && <span className="drift-chip">drift</span>}
          </div>
          <h2 className="panel-title">{detail.title}</h2>
          <code className="panel-path">{detail.path}</code>

          {detail.drift_reason && <p className="drift-reason">⟳ {detail.drift_reason}</p>}

          <button className={`read-cta ${copied ? 'ok' : ''}`} onClick={copy}>
            {copied ? 'copied ✓' : `open in trovex_read`}
          </button>

          <section>
            <h3>Out-links</h3>
            {linkList(detail.out_links, 'out')}
          </section>
          <section>
            <h3>In-links (backlinks)</h3>
            {linkList(detail.in_links, 'in')}
          </section>

          <section className="doc-render">
            <h3>Document</h3>
            {/* Server-rendered markdown from the local index (trusted, same
                renderer as the Jinja doc page). Private local view only. */}
            <div className="doc-body" dangerouslySetInnerHTML={{ __html: detail.html }} />
          </section>
        </>
      )}
      {!loading && !detail && <div className="panel-loading">not found</div>}
    </aside>
  )
}
