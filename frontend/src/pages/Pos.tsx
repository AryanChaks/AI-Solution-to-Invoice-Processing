import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import { get, post, put, money } from '../api'
import { Badge, Btn, Card, ErrorBox, Input, PageHeader, Select, Table, useLoad } from '../ui'

const line = () => ({ Item_Code: '', Description: '', Quantity: '1', Unit_Price: '0', Tax_Rate: '0' })
export default function Pos() {
  const { data, err, reload } = useLoad(() => get('/api/purchase-orders')); const vendors = useLoad(() => get('/api/vendors'))
  const [f, setF] = useState<any>(null); const [e2, setE2] = useState<string | null>(null); const [open, setOpen] = useState<any>(null)
  const save = async () => { setE2(null); try { await post('/api/purchase-orders', { ...f, Vendor_ID: Number(f.Vendor_ID), lines: f.lines.filter((l: any) => l.Description) }); setF(null); reload() } catch (x: any) { setE2(x.message) } }
  const setStatus = async (id: number, st: string) => { const d = await get(`/api/purchase-orders/${id}`)
    await put(`/api/purchase-orders/${id}`, { PO_Number: d.PO_Number, Vendor_ID: d.Vendor_ID, PO_Date: d.PO_Date, Currency: d.Currency, PO_Status: st, lines: d.lines.map((l: any) => ({ Item_Code: l.Item_Code, Description: l.Description, Quantity: String(l.Quantity), Unit_Price: String(l.Unit_Price), Tax_Rate: String(l.Tax_Rate) })) }); reload() }
  return (<><PageHeader title="Purchase Orders" sub="PO consumption = invoices already approved or awaiting review against the PO"><Btn onClick={() => setF({ PO_Number: '', Vendor_ID: '', PO_Date: '', Currency: 'INR', PO_Status: 'OPEN', lines: [line()] })}><Plus className="h-4 w-4" />New PO</Btn></PageHeader>
    <ErrorBox msg={err} />
    {f && <Card title="New purchase order" className="mb-5"><div className="grid gap-3 md:grid-cols-4">
      <Input label="PO number" value={f.PO_Number} onChange={(e: any) => setF({ ...f, PO_Number: e.target.value })} />
      <Select label="Vendor" value={f.Vendor_ID} onChange={(e: any) => setF({ ...f, Vendor_ID: e.target.value })}><option value="">Select…</option>{(vendors.data || []).map((v: any) => <option key={v.Vendor_ID} value={v.Vendor_ID}>{v.Vendor_Name}</option>)}</Select>
      <Input label="PO date" type="date" value={f.PO_Date} onChange={(e: any) => setF({ ...f, PO_Date: e.target.value })} />
      <Select label="Currency" value={f.Currency} onChange={(e: any) => setF({ ...f, Currency: e.target.value })}><option>INR</option><option>USD</option><option>EUR</option></Select></div>
      <h4 className="mb-2 mt-4 text-xs font-semibold uppercase text-slate-500">Lines</h4>
      {f.lines.map((l: any, i: number) => <div key={i} className="mb-2 grid grid-cols-12 items-end gap-2">{['Item_Code', 'Description', 'Quantity', 'Unit_Price', 'Tax_Rate'].map(k => <div key={k} className={k === 'Description' ? 'col-span-4' : 'col-span-2'}><Input placeholder={k.replace('_', ' ')} value={l[k]} onChange={(e: any) => setF({ ...f, lines: f.lines.map((x: any, j: number) => j === i ? { ...x, [k]: e.target.value } : x) })} /></div>)}
        <button className="pb-2 text-slate-400 hover:text-red-600" onClick={() => setF({ ...f, lines: f.lines.filter((_: any, j: number) => j !== i) })}><Trash2 className="h-4 w-4" /></button></div>)}
      <Btn variant="ghost" onClick={() => setF({ ...f, lines: [...f.lines, line()] })}>+ line</Btn>
      <div className="mt-3"><ErrorBox msg={e2} /></div><div className="mt-3 flex gap-2"><Btn onClick={save}>Create PO</Btn><Btn variant="ghost" onClick={() => setF(null)}>Cancel</Btn></div></Card>}
    <Card><Table head={['PO', 'Vendor', 'Date', 'Status', 'PO total', 'Invoiced', 'Remaining', 'Paid', 'Outstanding', '']}>{(data || []).map((p: any) => <Fragment key={p.PO_ID}>
      <tr className="hover:bg-slate-50"><td className="px-3 py-2 font-medium">{p.PO_Number}</td><td className="px-3 py-2">{p.Vendor_Name}</td><td className="px-3 py-2">{p.PO_Date}</td><td className="px-3 py-2"><Badge v={p.PO_Status} /></td>
        <td className="px-3 py-2">{money(p.PO_Total_Amount, p.Currency)}</td><td className="px-3 py-2">{money(p.summary.invoiced, p.Currency)}</td><td className="px-3 py-2 font-medium">{money(p.summary.remaining, p.Currency)}</td><td className="px-3 py-2">{money(p.summary.paid, p.Currency)}</td><td className="px-3 py-2">{money(p.summary.outstanding, p.Currency)}</td>
        <td className="space-x-3 whitespace-nowrap px-3 py-2 text-xs"><button className="text-brand-600" onClick={async () => setOpen(open?.PO_ID === p.PO_ID ? null : await get(`/api/purchase-orders/${p.PO_ID}`))}>Details</button>
          {p.PO_Status === 'OPEN' ? <button className="text-red-600" onClick={() => setStatus(p.PO_ID, 'CLOSED')}>Close</button> : <button className="text-emerald-600" onClick={() => setStatus(p.PO_ID, 'OPEN')}>Reopen</button>}</td></tr>
      {open?.PO_ID === p.PO_ID && <tr><td colSpan={10} className="bg-slate-50 px-6 py-3 text-sm"><b>Lines:</b> {open.lines.map((l: any) => `${l.Item_Code || ''} ${l.Description} ×${l.Quantity} @ ${l.Unit_Price}`).join(' · ')}<br /><b>Invoices:</b> {open.invoices.length ? open.invoices.map((i: any) => <span key={i.Invoice_ID} className="mr-3"><Link className="text-brand-600" to={`/invoices/${i.Invoice_ID}`}>{i.Invoice_Number}</Link> {money(i.Total_Amount)} <Badge v={i.Invoice_Status} /></span>) : 'none'}</td></tr>}</Fragment>)}</Table></Card></>)
}
