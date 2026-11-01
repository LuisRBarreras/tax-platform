import ProofUpload from './ProofUpload'
import type { Invoice } from '../types'

interface Props {
  invoices: Invoice[]
  loading: boolean
  onRefresh: () => void
  onPreview: (invoice: Invoice) => void
  onProofUploaded: () => void
  onProofPreview: (invoice: Invoice) => void
  onSend: (invoice: Invoice) => void
  page: number
  pages: number
  total: number
  onPage: (page: number) => void
}

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

/** Statuses are stored in English; the UI shows them in Spanish. */
const STATUS_LABEL: Record<string, string> = {
  created: 'creada',
  sent: 'enviada',
  paid: 'pagada',
}

function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status
}

/** 2026-11-01T15:05:53+00:00 -> "01 nov 2026, 08:05" (local time) */
const createdFmt = new Intl.DateTimeFormat('es-MX', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function formatCreated(value: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : createdFmt.format(parsed)
}

/** Show the captured number; otherwise the tail of the internal id. */
function displayNumber(invoice: Invoice): string {
  if (invoice['invoice-number']) return invoice['invoice-number']
  const id = invoice['invoice-id']
  return id.length > 16 ? `…${id.slice(-12)}` : id
}

export default function InvoiceList({
  invoices,
  loading,
  onRefresh,
  onPreview,
  onProofUploaded,
  onProofPreview,
  onSend,
  page,
  pages,
  total,
  onPage,
}: Props) {
  return (
    <section className="card">
      <div className="list-header">
        <h2>Invoices</h2>
        <div className="list-actions">
          <span className="count" title="Total de registros">{total}</span>
          <button type="button" className="ghost" onClick={onRefresh} disabled={loading}>
            {loading ? 'Cargando…' : 'Actualizar'}
          </button>
        </div>
      </div>

      {invoices.length === 0 && !loading ? (
        <p className="empty">Todavía no hay facturas.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Factura</th>
              <th>Fecha</th>
              <th>Creada</th>
              <th className="right">Monto</th>
              <th>Estado</th>
              <th className="right">PDF</th>
              <th>Comprobante</th>
              <th className="right">Correo</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => (
              <tr key={invoice['invoice-id']}>
                <td className="mono" title={invoice['invoice-id']}>
                  {displayNumber(invoice)}
                </td>
                <td>{invoice.date}</td>
                <td className="created">{formatCreated(invoice['created-at'])}</td>
                <td className="right">{money.format(invoice.total)}</td>
                <td>
                  <span className={`badge badge-${invoice.status}`}>{statusLabel(invoice.status)}</span>
                </td>
                <td className="right">
                  <button type="button" className="link-button" onClick={() => onPreview(invoice)}>
                    Ver
                  </button>
                </td>
                <td>
                  <ProofUpload invoice={invoice} onUploaded={onProofUploaded} onPreview={onProofPreview} />
                </td>
                <td className="right">
                  <button type="button" className="link-button" onClick={() => onSend(invoice)}>
                    {invoice['sent-at'] ? 'Reenviar' : 'Enviar'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <footer className="pager">
        <span className="pager-info">
          {total === 0
            ? 'Sin registros'
            : `${(page - 1) * 10 + 1}–${Math.min(page * 10, total)} de ${total}`}
        </span>
        <div className="pager-controls">
          <button type="button" className="ghost" onClick={() => onPage(page - 1)} disabled={page <= 1 || loading}>
            ← Anterior
          </button>
          <span className="pager-page">
            Página {page} de {pages}
          </span>
          <button type="button" className="ghost" onClick={() => onPage(page + 1)} disabled={page >= pages || loading}>
            Siguiente →
          </button>
        </div>
      </footer>
    </section>
  )
}
