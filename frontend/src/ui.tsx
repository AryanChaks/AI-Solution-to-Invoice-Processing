import React from 'react'
import { Loader2, AlertTriangle } from 'lucide-react'

const COLORS: Record<string, string> = {
  AUTO_APPROVED_FOR_AP: 'bg-emerald-100 text-emerald-700', APPROVED: 'bg-emerald-100 text-emerald-700', COMPLETED: 'bg-emerald-100 text-emerald-700',
  PAID: 'bg-teal-100 text-teal-700', VALID: 'bg-emerald-100 text-emerald-700', IMPORTED: 'bg-emerald-100 text-emerald-700',
  REVIEW_REQUIRED: 'bg-amber-100 text-amber-800', PENDING: 'bg-amber-100 text-amber-800', CLARIFICATION: 'bg-amber-100 text-amber-800', WARNING: 'bg-amber-100 text-amber-800', POTENTIAL_DUPLICATE: 'bg-amber-100 text-amber-800',
  BLOCKED: 'bg-red-100 text-red-700', REJECTED: 'bg-red-100 text-red-700', FAILED: 'bg-red-100 text-red-700', INVALID: 'bg-red-100 text-red-700', CONFIRMED_DUPLICATE: 'bg-red-100 text-red-700', ERROR: 'bg-red-100 text-red-700', HIGH: 'bg-red-100 text-red-700',
  RUNNING: 'bg-blue-100 text-blue-700', MEDIUM: 'bg-amber-100 text-amber-800', SUPERSEDED: 'bg-slate-100 text-slate-500', RECEIVED: 'bg-slate-100 text-slate-600', INFO: 'bg-slate-100 text-slate-600',
}
export const Badge = ({ v }: { v?: string | null }) => v ? <span className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${COLORS[v] || 'bg-slate-100 text-slate-700'}`}>{v.replace(/_/g, ' ')}</span> : <span className="text-slate-400">—</span>
export const Card = ({ title, right, children, className = '' }: any) => (
  <div className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
    {(title || right) && <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3"><h3 className="text-sm font-semibold text-slate-700">{title}</h3>{right}</div>}
    <div className="p-5">{children}</div>
  </div>)
export const Btn = ({ variant = 'primary', className = '', ...p }: any) => {
  const v: any = { primary: 'bg-brand-600 text-white hover:bg-brand-700', ghost: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
    danger: 'bg-red-600 text-white hover:bg-red-700', ok: 'bg-emerald-600 text-white hover:bg-emerald-700' }
  return <button {...p} className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:opacity-50 ${v[variant]} ${className}`} />
}
export const Input = React.forwardRef<HTMLInputElement, any>(({ label, className = '', ...p }, ref) => (
  <label className="block text-sm">{label && <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>}
    <input ref={ref} {...p} className={`w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 ${className}`} /></label>))
export const Select = ({ label, children, ...p }: any) => (
  <label className="block text-sm">{label && <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>}
    <select {...p} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100">{children}</select></label>)
export const Spinner = () => <div className="flex items-center gap-2 text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
export const ErrorBox = ({ msg }: { msg?: string | null }) => msg ? <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span className="whitespace-pre-wrap break-words">{msg}</span></div> : null
export const PageHeader = ({ title, sub, children }: any) => (
  <div className="mb-6 flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1>{sub && <p className="mt-1 text-sm text-slate-500">{sub}</p>}</div><div className="flex gap-2">{children}</div></div>)
export const Table = ({ head, children, empty }: any) => (
  <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
    {head.map((h: string) => <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">{h}</th>)}</tr></thead>
    <tbody className="divide-y divide-slate-100">{children}</tbody></table>{empty && <div className="py-8 text-center text-sm text-slate-400">{empty}</div>}</div>)
export const Stat = ({ label, value, sub, icon: Icon, tone = 'brand' }: any) => (
  <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center justify-between"><span className="text-xs font-medium text-slate-500">{label}</span>
    {Icon && <Icon className={`h-4 w-4 ${tone === 'red' ? 'text-red-500' : tone === 'amber' ? 'text-amber-500' : tone === 'green' ? 'text-emerald-500' : 'text-brand-500'}`} />}</div>
    <div className="mt-2 text-2xl font-semibold">{value}</div>{sub && <div className="mt-0.5 text-xs text-slate-400">{sub}</div>}</div>)
export function useLoad<T = any>(fn: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = React.useState<T | null>(null); const [err, setErr] = React.useState<string | null>(null); const [loading, setL] = React.useState(true)
  const reload = React.useCallback(() => { setL(true); fn().then(d => { setData(d); setErr(null) }).catch(e => setErr(e.message)).finally(() => setL(false)) }, deps)
  React.useEffect(reload, [reload])
  return { data, err, loading, reload, setData }
}
