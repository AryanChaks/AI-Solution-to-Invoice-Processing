import { useEffect, useRef, useState } from 'react'
import { get } from './api'

/** Renders the original document pages (server-side PyMuPDF rasterisation) and overlays extraction bounding boxes. */
export default function DocViewer({ runId, evidence, active }: { runId: number; evidence: any[]; active?: string | null }) {
  const [pages, setPages] = useState<any[] | null>(null); const [err, setErr] = useState<string | null>(null)
  const refs = useRef<Record<number, HTMLDivElement | null>>({})
  useEffect(() => { get(`/api/processing/runs/${runId}/pages`).then(setPages).catch(e => setErr(e.message)) }, [runId])
  const box = (e: any) => { if (!e.Bounding_Box || !e.Source_Page) return null; const [x0, y0, x1, y1] = e.Bounding_Box.split(',').map(Number); return { x0, y0, x1, y1 } }
  useEffect(() => {
    const e = evidence.find(x => x.Field_Name === active); if (e?.Source_Page) refs.current[e.Source_Page]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [active])
  if (err) return <p className="text-sm text-slate-500">Original document not available ({err}).</p>
  if (!pages) return <p className="text-sm text-slate-500">Loading document…</p>
  return <div className="space-y-4">{pages.map(p => (
    <div key={p.page} ref={el => (refs.current[p.page] = el)} className="relative overflow-hidden rounded-lg border border-slate-200 bg-white">
      <img src={`/api/processing/runs/${runId}/page/${p.page}.png`} className="block w-full" alt={`page ${p.page}`} />
      {evidence.filter(e => e.Source_Page === p.page).map(e => { const b = box(e); if (!b) return null; const on = e.Field_Name === active
        return <div key={e.Evidence_ID} title={`${e.Field_Name}: ${e.Corrected_Value || e.Extracted_Value}`}
          style={{ position: 'absolute', left: `${b.x0 / p.width * 100}%`, top: `${b.y0 / p.height * 100}%`, width: `${(b.x1 - b.x0) / p.width * 100}%`, height: `${(b.y1 - b.y0) / p.height * 100}%` }}
          className={on ? 'border-2 border-brand-600 bg-brand-500/30' : 'border border-amber-400/60 bg-amber-300/10'} /> })}
      <div className="absolute right-2 top-2 rounded bg-slate-900/60 px-2 py-0.5 text-xs text-white">p{p.page}</div>
    </div>))}</div>
}
