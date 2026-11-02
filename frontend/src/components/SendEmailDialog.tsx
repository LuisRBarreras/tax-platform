import { useEffect, useState } from 'react'
import { api } from '../api'
import EmailConfirm from './EmailConfirm'
import { formatShortDate, formatWorkPeriod } from '../invoiceDefaults'
import type { Invoice, SheetResult } from '../types'

interface Props {
  invoice: Invoice
  onClose: () => void
  onSent: () => void
}

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

function pesos(invoice: Invoice): string {
  const value = invoice.pesos ?? invoice.total * (invoice['exchange-rate'] ?? 0)
  return money.format(value)
}

export default function SendEmailDialog({ invoice, onClose, onSent }: Props) {
  const [recipients, setRecipients] = useState<string[]>([])
  const [to, setTo] = useState('')
  const [dryRun, setDryRun] = useState(false)
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [sheet, setSheet] = useState<SheetResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    api
      .mailRecipients()
      .then((data) => {
        setRecipients(data.recipients)
        setTo(data.recipients[0] ?? '')
        setDryRun(data['dry-run'])
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Error'))
  }, [])

  async function handleSend() {
    setSending(true)
    setError(null)
    try {
      const res = await api.sendInvoice(invoice['invoice-id'], to)
      setResult(res['dry-run'] ? `Modo prueba: guardado en ${res.path}` : `Enviado a ${res.to}`)
      setSheet(res.sheet)
      onSent()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo enviar')
    } finally {
      setSending(false)
    }
  }

  const period = formatWorkPeriod(invoice['work-from'], invoice['work-to'])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-small" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <div>
            <strong>Enviar factura</strong>
            <span className="mono muted"> · {invoice['invoice-id']}</span>
          </div>
          <button type="button" className="ghost" onClick={onClose} aria-label="Cerrar">
            ✕
          </button>
        </header>

        <div className="modal-body">
          <table className="summary">
            <tbody>
              <tr>
                <th>Fecha trabajo</th>
                <td>{period || '—'}</td>
                <th>Fecha depósito</th>
                <td>{formatShortDate(invoice['deposit-date']) || '—'}</td>
              </tr>
              <tr>
                <th>Salary</th>
                <td>{money.format(invoice.total)}</td>
                <th>Pesos</th>
                <td>{pesos(invoice)}</td>
              </tr>
            </tbody>
          </table>

          <p className="attachments">
            Adjuntos: <strong>PDF</strong>
            {invoice['proof-path'] ? ' + comprobante' : ' (sin comprobante)'}
          </p>

          <label>
            Destinatario
            <select value={to} onChange={(e) => setTo(e.target.value)} disabled={sending || !!result}>
              {recipients.map((addr) => (
                <option key={addr} value={addr}>
                  {addr}
                </option>
              ))}
            </select>
          </label>

          {dryRun && (
            <p className="note">
              Modo prueba activo (<code>SMTP_DRY_RUN=1</code>): se escribe el <code>.eml</code> en
              <code>.tmp/outbox/</code> en lugar de enviarlo.
            </p>
          )}

          {result && <p className="ok">{result}</p>}
          {sheet?.status === 'appended' && (
            <p className="ok">Fila agregada al spreadsheet ({sheet.tab}).</p>
          )}
          {sheet?.status === 'error' && (
            <p className="note">
              El correo salió, pero no se pudo guardar en el spreadsheet: {sheet.message}
            </p>
          )}
          {error && <p className="error">{error}</p>}

          <div className="modal-footer">
            <button type="button" className="ghost" onClick={onClose}>
              Cerrar
            </button>
            <button
              type="button"
              onClick={() => setConfirming(true)}
              disabled={sending || !to || !!result}
            >
              Revisar y enviar
            </button>
          </div>
        </div>
      </div>

      {confirming && (
        <EmailConfirm
          invoice={invoice}
          to={to}
          sending={sending}
          onCancel={() => setConfirming(false)}
          onConfirm={() => void handleSend().then(() => setConfirming(false))}
        />
      )}
    </div>
  )
}
