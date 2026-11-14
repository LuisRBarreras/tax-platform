import { useCallback, useEffect, useState } from 'react'
import Wizard from './components/Wizard'
import InvoiceList from './components/InvoiceList'
import PayablesList from './components/PayablesList'
import PayDialog from './components/PayDialog'
import PdfPreview from './components/PdfPreview'
import SendEmailDialog from './components/SendEmailDialog'
import ProofPreview from './components/ProofPreview'
import { api } from './api'
import type { Invoice, Payable } from './types'

export default function App() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<Invoice | null>(null)
  const [sendTo, setSendTo] = useState<Invoice | null>(null)
  const [proofPreview, setProofPreview] = useState<Invoice | null>(null)
  const [tab, setTab] = useState<'invoices' | 'payables'>('invoices')
  const [paying, setPaying] = useState<Payable | null>(null)
  const [payablesRefresh, setPayablesRefresh] = useState(0)

  const loadInvoices = useCallback(async (target = page) => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.listInvoices(target, 10)
      setInvoices(data.invoices)
      setPage(data.page)
      setPages(data.pages)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    void loadInvoices(page)
  }, [loadInvoices, page])

  return (
    <div className="app">
      <header>
        <h1>Invoice Automation</h1>
        <p>Registra el periodo trabajado, el tipo de cambio y los pesos.</p>
      </header>

      {error && <p className="error">{error}</p>}

      <nav className="tabs">
        <button
          type="button"
          className={`tab ${tab === 'invoices' ? 'active' : ''}`}
          onClick={() => setTab('invoices')}
        >
          Facturar
        </button>
        <button
          type="button"
          className={`tab ${tab === 'payables' ? 'active' : ''}`}
          onClick={() => setTab('payables')}
        >
          Honorarios
        </button>
      </nav>

      <main>
        {tab === 'invoices' ? (
          <>
            <Wizard onCreated={() => void loadInvoices(1)} />
            <InvoiceList
              invoices={invoices}
              loading={loading}
              onRefresh={() => void loadInvoices(page)}
              onPreview={setPreview}
              onProofUploaded={() => void loadInvoices(page)}
              onSend={setSendTo}
              onProofPreview={setProofPreview}
              page={page}
              pages={pages}
              total={total}
              onPage={(p) => setPage(p)}
            />
          </>
        ) : (
          <PayablesList key={payablesRefresh} onPay={setPaying} />
        )}
      </main>

      {preview && <PdfPreview invoice={preview} onClose={() => setPreview(null)} />}
      {proofPreview && (
        <ProofPreview
          invoice={proofPreview}
          onClose={() => setProofPreview(null)}
          onUploaded={() => void loadInvoices()}
        />
      )}
      {paying && (
        <PayDialog
          payable={paying}
          onClose={() => setPaying(null)}
          onPaid={() => setPayablesRefresh((n) => n + 1)}
        />
      )}
      {sendTo && (
        <SendEmailDialog
          invoice={sendTo}
          onClose={() => setSendTo(null)}
          onSent={() => void loadInvoices(page)}
        />
      )}
    </div>
  )
}
