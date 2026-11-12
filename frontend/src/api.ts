export async function api(path: string, opts: RequestInit = {}) {
  const isForm = opts.body instanceof FormData
  const r = await fetch(path, { ...opts, headers: opts.body && !isForm ? { 'Content-Type': 'application/json' } : undefined })
  if (!r.ok) {
    let msg = r.statusText
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j) } catch {}
    throw new Error(msg)
  }
  return r.json()
}
export const get = (p: string) => api(p)
export const post = (p: string, b?: any) => api(p, { method: 'POST', body: b === undefined ? undefined : (b instanceof FormData ? b : JSON.stringify(b)) })
export const put = (p: string, b: any) => api(p, { method: 'PUT', body: JSON.stringify(b) })
export const money = (v: any, cur = 'INR') => v === null || v === undefined || v === '' || isNaN(Number(v)) ? '—'
  : new Intl.NumberFormat('en-IN', { style: 'currency', currency: cur, maximumFractionDigits: 2 }).format(Number(v))
export const dt = (s: any) => s ? new Date(s.endsWith?.('Z') ? s : s + 'Z').toLocaleString('en-IN') : '—'
