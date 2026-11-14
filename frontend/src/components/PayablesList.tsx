import { useEffect, useState } from 'react'
import DeletePayableButton from './DeletePayableButton'
import { api, payablePdfUrl } from '../api'
import type { Payable } from '../types'

const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' })

const MONTHS_ES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

/** '2026-10' -> 'Octubre 2026'. The invoice is issued for the previous month. */
function periodLabel(period: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(period ?? '')
  if (!match) return '—'
  const month = MONTHS_ES[Number(match[2]) - 1]
  if (!month) return '—'
  return `${month.charAt(0).toUpperCase()}${month.slice(1)} ${match[1]}`
}

const receivedFmt = new Intl.DateTimeFormat('es-MX', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

function formatDay(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : receivedFmt.format(parsed)
}

interface Props {
  onPay: (payable: Payable) => void
}

/** Invoices that arrive by mail from the billing address, pending vs answered. */
export default function PayablesList({ onPay }: Props) {
  const [payables, setPayables] = useState<Payable[]>([])
  const [sender, setSender] = useState('')
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    try {
      const data = await api.payables()
      setPayables(data.payables)
      setSender(data.sender)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo leer la lista')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function sync() {
    setSyncing(true)
    setError(null)
    setNotice(null)
    try {
      const result = await api.syncPayables()
      const parts = [`${result.new} nueva${result.new === 1 ? '' : 's'}`]
      if (result['marked-paid']) parts.push(`${result['marked-paid']} marcada(s) pagada(s)`)
      setNotice(`Correo revisado: ${parts.join(', ')}`)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo revisar el correo')
    } finally {
      setSyncing(false)
    }
  }

  const pending = payables.filter((item) => item.status === 'pending').length

  return (
    <section className="card">
      <div className="list-header">
        <h2>
          Honorarios por pagar
          {pending > 0 && <span className="count">{pending}</span>}
        </h2>
        <div className="list-actions">
          <span className="muted mono">{sender}</span>
          <button type="button" className="ghost" onClick={() => void sync()} disabled={syncing || loading}>
            {syncing ? 'Revisando…' : 'Revisar correo'}
          </button>
        </div>
      </div>

      {notice && <p className="ok">{notice}</p>}
      {error && <p className="error">{error}</p>}

      {payables.length === 0 && !loading ? (
        <p className="empty">Sin facturas registradas. Pulsa «Revisar correo» para leer el buzón.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Factura</th>
              <th>Corresponde a</th>
              <th>Recibida</th>
              <th>Emisor</th>
              <th className="right">Monto</th>
              <th>Estado</th>
              <th className="right">PDF</th>
              <th className="right"></th>
              <th className="right"></th>
            </tr>
          </thead>
          <tbody>
            {payables.map((item) => (
              <tr key={item.id}>
                <td className="mono">{item.folio || '—'}</td>
                <td>{periodLabel(item.period)}</td>
                <td className="created">{formatDay(item['received-at'])}</td>
                <td title={item['issuer-rfc']}>{item['issuer-name'] || '—'}</td>
                <td className="right">
                  {item.total ? money.format(item.total) : '—'}
                </td>
                <td>
                  <span className={`badge badge-${item.status === 'paid' ? 'sent' : 'created'}`}>
                    {item.status === 'paid' ? 'pagada' : 'pendiente'}
                  </span>
                </td>
                <td className="right">
                  <a className="pdf-link" href={payablePdfUrl(item.id)}>
                    Descargar
                  </a>
                </td>
                <td className="right">
                  {item.status === 'pending' ? (
                    <button type="button" className="link-button" onClick={() => onPay(item)}>
                      Pagar y responder
                    </button>
                  ) : (
                    <span className="muted mono">{formatDay(item['paid-at'] ?? '')}</span>
                  )}
                </td>
                <td className="right">
                  <DeletePayableButton payable={item} onDeleted={() => void load()} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
