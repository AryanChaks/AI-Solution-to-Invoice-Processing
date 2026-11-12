import { useState } from 'react'
import { Link } from 'react-router-dom'
import { get, money } from '../api'
import { Badge, Card, ErrorBox, Input, PageHeader, Select, Table, useLoad } from '../ui'

export default function Invoices() {
  const [q, setQ] = useState(''); const [st, setSt] = useState('')
  const { data, err, loading } = useLoad(() => get(`/api/invoices?q=${encodeURIComponent(q)}&status=${st}`), [q, st])
  return (<><PageHeader title="All Invoices" sub="One row per vendor + normalised invoice number" />
    <Card><div className="mb-4 flex gap-3"><div className="w-72"><Input placeholder="Search invoice no. or vendor…" value={q} onChange={(e: any) => setQ(e.target.value)} /></div>
      <div className="w-56"><Select value={st} onChange={(e: any) => setSt(e.target.value)}><option value="">All statuses</option>{['AUTO_APPROVED_FOR_AP', 'REVIEW_REQUIRED', 'BLOCKED', 'APPROVED', 'REJECTED', 'PAID'].map(s => <option key={s}>{s}</option>)}</Select></div></div>
      <ErrorBox msg={err} />
      <Table head={['ID', 'Invoice no.', 'Vendor', 'Date', 'Total', 'Paid', 'Outstanding', 'Source', 'Status']} empty={!loading && !data?.length ? 'No invoices found.' : ''}>
        {(data || []).map((i: any) => <tr key={i.Invoice_ID} className="hover:bg-slate-50"><td className="px-3 py-2">{i.Invoice_ID}</td><td className="px-3 py-2"><Link className="font-medium text-brand-600" to={`/invoices/${i.Invoice_ID}`}>{i.Invoice_Number}</Link></td>
          <td className="px-3 py-2">{i.Vendor_Name}</td><td className="px-3 py-2">{i.Invoice_Date}</td><td className="px-3 py-2">{money(i.Total_Amount, i.Currency)}</td><td className="px-3 py-2">{money(i.Total_Paid, i.Currency)}</td>
          <td className="px-3 py-2">{money(i.Outstanding_Amount, i.Currency)}</td><td className="px-3 py-2">{i.Source_Type}</td><td className="px-3 py-2"><Badge v={i.Invoice_Status} /></td></tr>)}
      </Table></Card></>)
}
