import { Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, FilePlus2, FileText, ClipboardCheck, ShoppingCart, Building2, History, Settings as Cog, ReceiptText } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import AddInvoice from './pages/AddInvoice'
import Invoices from './pages/Invoices'
import InvoiceDetail from './pages/InvoiceDetail'
import Review from './pages/Review'
import ReviewDetail from './pages/ReviewDetail'
import Pos from './pages/Pos'
import Vendors from './pages/Vendors'
import HistoryPage from './pages/History'
import RunView from './pages/RunView'
import SettingsPage from './pages/Settings'

const NAV = [['/', 'Dashboard', LayoutDashboard], ['/add', 'Add Invoice', FilePlus2], ['/invoices', 'All Invoices', FileText],
  ['/review', 'Review Queue', ClipboardCheck], ['/pos', 'Purchase Orders', ShoppingCart], ['/vendors', 'Vendors', Building2],
  ['/history', 'Processing History', History], ['/settings', 'Settings', Cog]] as const

export default function App() {
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex items-center gap-2 px-5 py-5"><div className="rounded-lg bg-brand-600 p-1.5 text-white"><ReceiptText className="h-5 w-5" /></div><span className="text-lg font-semibold">InvoiceAP</span></div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50'}`}>
              <Icon className="h-4 w-4" />{label}</NavLink>))}
        </nav>
        <div className="px-5 py-4 text-xs text-slate-400">Local build · localhost only</div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-6 backdrop-blur">
          <span className="text-sm text-slate-500">Accounts Payable Automation</span>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">AP Operator</span>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} /><Route path="/add" element={<AddInvoice />} />
            <Route path="/invoices" element={<Invoices />} /><Route path="/invoices/:id" element={<InvoiceDetail />} />
            <Route path="/review" element={<Review />} /><Route path="/review/:runId" element={<ReviewDetail />} />
            <Route path="/pos" element={<Pos />} /><Route path="/vendors" element={<Vendors />} />
            <Route path="/history" element={<HistoryPage />} /><Route path="/runs/:id" element={<RunView />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </div>)
}
