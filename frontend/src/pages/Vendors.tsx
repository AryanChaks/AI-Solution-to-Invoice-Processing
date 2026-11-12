import { useState } from 'react'
import { Link } from 'react-router-dom'
import { get, post, put, money } from '../api'
import { Badge, Btn, Card, ErrorBox, Input, PageHeader, Table, useLoad } from '../ui'

const blank = { Vendor_Name: '', Tax_ID: '', Vendor_Code: '', Primary_Address: '', Email: '', Contact_Number: '', Is_Approved: false, Is_Active: true, aliases: '' }
export default function Vendors() {
  const { data, err, reload } = useLoad(() => get('/api/vendors')); const [f, setF] = useState<any>(null); const [id, setId] = useState<number | null>(null); const [e2, setE2] = useState<string | null>(null)
  const [open, setOpen] = useState<any>(null)
  const save = async () => {
    setE2(null)
    try { const body = { ...f, aliases: String(f.aliases || '').split(',').map((s: string) => s.trim()).filter(Boolean), Tax_ID: f.Tax_ID || null }
      id ? await put(`/api/vendors/${id}`, body) : await post('/api/vendors', body); setF(null); setId(null); reload() } catch (x: any) { setE2(x.message) }
  }
  const toggle = async (v: any, k: string) => { await put(`/api/vendors/${v.Vendor_ID}`, { ...v, [k]: !v[k], Tax_ID: v.Tax_ID || null }); reload() }
  return (<><PageHeader title="Vendors" sub="Vendors are matched by GSTIN / exact name / registered alias — never fuzzy matching alone"><Btn onClick={() => { setF({ ...blank }); setId(null) }}>New vendor</Btn></PageHeader>
    <ErrorBox msg={err} />
    {f && <Card title={id ? 'Edit vendor' : 'New vendor'} className="mb-5"><div className="grid gap-3 md:grid-cols-3">
      {['Vendor_Name', 'Tax_ID', 'Vendor_Code', 'Primary_Address', 'Email', 'Contact_Number'].map(k => <Input key={k} label={k.replace('_', ' ')} value={f[k] || ''} onChange={(e: any) => setF({ ...f, [k]: e.target.value })} />)}
      <Input label="Aliases (comma separated)" value={f.aliases} onChange={(e: any) => setF({ ...f, aliases: e.target.value })} />
      <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={f.Is_Approved} onChange={e => setF({ ...f, Is_Approved: e.target.checked })} />Approved</label>
      <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={f.Is_Active} onChange={e => setF({ ...f, Is_Active: e.target.checked })} />Active</label></div>
      <div className="mt-3"><ErrorBox msg={e2} /></div><div className="mt-3 flex gap-2"><Btn onClick={save}>Save</Btn><Btn variant="ghost" onClick={() => setF(null)}>Cancel</Btn></div></Card>}
    <Card><Table head={['Name', 'GSTIN', 'Code', 'Aliases', 'Approved', 'Active', '']}>{(data || []).map((v: any) => <>
      <tr key={v.Vendor_ID} className="hover:bg-slate-50"><td className="px-3 py-2 font-medium">{v.Vendor_Name}</td><td className="px-3 py-2 font-mono text-xs">{v.Tax_ID}</td><td className="px-3 py-2">{v.Vendor_Code}</td><td className="px-3 py-2 text-xs">{v.aliases.join(', ')}</td>
        <td className="px-3 py-2"><button onClick={() => toggle(v, 'Is_Approved')}><Badge v={v.Is_Approved ? 'APPROVED' : 'REJECTED'} /></button></td><td className="px-3 py-2"><button onClick={() => toggle(v, 'Is_Active')}><Badge v={v.Is_Active ? 'COMPLETED' : 'FAILED'} /></button></td>
        <td className="space-x-3 px-3 py-2 text-xs"><button className="text-brand-600" onClick={() => { setId(v.Vendor_ID); setF({ ...v, aliases: v.aliases.join(', ') }) }}>Edit</button>
          <button className="text-brand-600" onClick={async () => setOpen(open?.Vendor_ID === v.Vendor_ID ? null : await get(`/api/vendors/${v.Vendor_ID}`))}>Invoices</button></td></tr>
      {open?.Vendor_ID === v.Vendor_ID && <tr key={'x' + v.Vendor_ID}><td colSpan={7} className="bg-slate-50 px-6 py-3 text-sm">{open.invoices.length ? open.invoices.map((i: any) => <div key={i.Invoice_ID}><Link className="text-brand-600" to={`/invoices/${i.Invoice_ID}`}>{i.Invoice_Number}</Link> · {money(i.Total_Amount)} · <Badge v={i.Invoice_Status} /></div>) : 'No invoices'}</td></tr>}</>)}</Table></Card></>)
}
