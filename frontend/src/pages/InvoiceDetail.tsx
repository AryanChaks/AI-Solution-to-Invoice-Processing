import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { get, post, money, dt } from '../api'
import DocViewer from '../DocViewer'
import { Badge, Btn, Card, ErrorBox, Input, PageHeader, Spinner, Table, useLoad } from '../ui'

export default function InvoiceDetail() {
  const { id } = useParams(); const { data, err, reload } = useLoad(() => get(`/api/invoices/${id}`), [id])
  const [active, setActive] = useState<string | null>(null); const [pay, setPay] = useState<any>({ amount: '', date: '', ref: '', method: 'UPI' }); const [perr, setPerr] = useState<string | null>(null)
  if (err) return <ErrorBox msg={err} />; if (!data) return <Spinner />
  const { invoice: i, vendor, po, lines, payments, decision, evidence, audit, runs } = data
  const addPay = async () => { setPerr(null); try { await post(`/api/invoices/${id}/payments`, pay); setPay({ amount: '', date: '', ref: '', method: 'UPI' }); reload() } catch (e: any) { setPerr(e.message) } }
  return (<>
    <PageHeader title={`Invoice ${i.Invoice_Number}`} sub={`${vendor.Vendor_Name} · ${i.Source_Type} · created ${dt(i.Created_At)}`}><Badge v={i.Invoice_Status} /></PageHeader>
    <div className="grid gap-5 xl:grid-cols-2">
      <div>{data.has_file ? <Card title="Original document"><DocViewer runId={data.latest_run_id} evidence={evidence} active={active} /></Card> : <Card title="Original document"><p className="text-sm text-slate-500">No file for this invoice (entered manually or imported from a spreadsheet).</p></Card>}</div>
      <div className="space-y-5">
        <Card title="Financials"><dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {[['Invoice date', i.Invoice_Date], ['Due date', i.Due_Date], ['Currency', i.Currency], ['PO', po ? <span>{po.PO_Number} <Badge v={po.PO_Status} /></span> : '—'], ['Subtotal', money(i.Subtotal, i.Currency)], ['Tax', money(i.Tax_Amount, i.Currency)],
            ['Discount', money(i.Discount_Amount, i.Currency)], ['Other charges', money(i.Other_Charges, i.Currency)], ['Total', <b>{money(i.Total_Amount, i.Currency)}</b>], ['Paid', money(i.Total_Paid, i.Currency)], ['Outstanding', <b>{money(i.Outstanding_Amount, i.Currency)}</b>]].map(([k, v]: any) => <div key={k} className="flex justify-between border-b border-slate-100 py-1"><dt className="text-slate-500">{k}</dt><dd>{v || '—'}</dd></div>)}</dl></Card>
        {decision && <Card title="Latest decision" right={<Badge v={decision.decision?.status} />}><p className="text-sm">{decision.decision?.explanation}</p>
          {decision.decision?.failed?.length > 0 && <ul className="mt-2 list-disc pl-5 text-sm text-red-700">{decision.decision.failed.map((f: string, k: number) => <li key={k}>{f}</li>)}</ul>}
          <p className="mt-2 text-sm text-slate-600"><b>Next action:</b> {decision.decision?.next_action}</p></Card>}
        {evidence.length > 0 && <Card title="Extraction evidence (click to locate)"><Table head={['Field', 'Value', 'Conf.', 'Page', 'Method', 'Check']}>{evidence.map((e: any) => <tr key={e.Evidence_ID} onClick={() => setActive(e.Field_Name)} className={`cursor-pointer hover:bg-brand-50 ${active === e.Field_Name ? 'bg-brand-50' : ''}`}>
          <td className="px-3 py-1.5 font-medium">{e.Field_Name}</td><td className="px-3 py-1.5">{e.Corrected_Value ? <span><s className="text-slate-400">{e.Extracted_Value}</s> → {e.Corrected_Value}</span> : e.Extracted_Value}</td>
          <td className="px-3 py-1.5">{e.Confidence_Score != null ? `${(e.Confidence_Score * 100).toFixed(0)}%` : '—'}</td><td className="px-3 py-1.5">{e.Source_Page || '—'}</td><td className="px-3 py-1.5 text-xs">{e.Extraction_Method}</td><td className="px-3 py-1.5"><Badge v={e.Validation_Status} /></td></tr>)}</Table></Card>}
        <Card title="Line items"><Table head={['Description', 'Code', 'Qty', 'Unit price', 'Tax %', 'Line total']} empty={lines.length ? '' : 'No line items'}>{lines.map((l: any) => <tr key={l.Line_Item_ID}><td className="px-3 py-1.5">{l.Description}</td><td className="px-3 py-1.5">{l.Item_Code}</td><td className="px-3 py-1.5">{l.Quantity}</td><td className="px-3 py-1.5">{money(l.Unit_Price)}</td><td className="px-3 py-1.5">{l.Tax_Rate}</td><td className="px-3 py-1.5">{money(l.Line_Total)}</td></tr>)}</Table></Card>
        <Card title="Payments"><Table head={['Date', 'Amount', 'Method', 'Reference', 'Source']} empty={payments.length ? '' : 'No payments recorded'}>{payments.map((p: any) => <tr key={p.Payment_ID}><td className="px-3 py-1.5">{p.Payment_Date}</td><td className="px-3 py-1.5">{money(p.Payment_Amount)}</td><td className="px-3 py-1.5">{p.Payment_Method}</td><td className="px-3 py-1.5 font-mono text-xs">{p.Ref_Number}</td><td className="px-3 py-1.5">{p.Source_Type}</td></tr>)}</Table>
          <div className="mt-4 grid grid-cols-5 items-end gap-2"><Input label="Amount" value={pay.amount} onChange={(e: any) => setPay({ ...pay, amount: e.target.value })} /><Input label="Date" type="date" value={pay.date} onChange={(e: any) => setPay({ ...pay, date: e.target.value })} />
            <Input label="UTR / ref" value={pay.ref} onChange={(e: any) => setPay({ ...pay, ref: e.target.value })} /><Input label="Method" value={pay.method} onChange={(e: any) => setPay({ ...pay, method: e.target.value })} /><Btn onClick={addPay}>Add payment</Btn></div>
          <div className="mt-2"><ErrorBox msg={perr} /></div></Card>
        <Card title="Processing runs"><ul className="space-y-1 text-sm">{runs.map((r: any) => <li key={r.Run_ID}><Link className="text-brand-600" to={`/runs/${r.Run_ID}`}>Run #{r.Run_ID}</Link> · {r.Source_Type} · {dt(r.Started_At)} · <Badge v={r.Final_Decision} /></li>)}</ul></Card>
        <Card title="Audit trail"><Table head={['When', 'Action', 'Actor', 'Reason / change']} empty={audit.length ? '' : 'No entries'}>{audit.map((a: any) => <tr key={a.Audit_ID}><td className="whitespace-nowrap px-3 py-1.5 text-xs">{dt(a.Created_At)}</td><td className="px-3 py-1.5">{a.Action}</td><td className="px-3 py-1.5">{a.Actor}</td><td className="max-w-md break-words px-3 py-1.5 text-xs text-slate-600">{a.Reason || ''} {a.New_Value ? <code>{String(a.New_Value).slice(0, 160)}</code> : null}</td></tr>)}</Table></Card>
      </div></div></>)
}
