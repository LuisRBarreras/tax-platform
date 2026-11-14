import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Payable, Receipt } from '../types'

interface Props {
  payable: Payable
  onClose: () => void
  onPaid: () => void
}

interface Preview {
  to: string
  subject: string
  text: string
  html: string
  attachments: string[]
}

const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' })

/**
 * Two steps: pick the receipt, then read the reply before it goes out.
 * The body is editable, so a one-off note does not need a code change.
 */
export default function PayDialog({ payable, onClose, onPaid }: Props) {
  const [receipts, setReceipts] = useState<Receipt[]>([])
  const [folder, setFolder] = useState('')
  const [chosen, setChosen] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const [preview, setPreview] = useState<Preview | null>(null)
  const [message, setMessage] = useState('')
  const [loadingPreview, setLoadingPreview] = useState(false)

  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .receipts()
      .then((data) => {
        setReceipts(data.receipts)
        setFolder(data.directory)
        setChosen(data.receipts[0]?.name ?? '')
      })
      .catch(() => setReceipts([]))
  }, [])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape' && !sending) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, sending])

  async function review() {
    setLoadingPreview(true)
    setError(null)
    try {
      const data = await api.payablePreview(payable.id, file ? file.name : chosen)
      setPreview(data)
      setMessage(data.text)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo generar el previo')
    } finally {
      setLoadingPreview(false)
    }
  }

  async function submit() {
    setSending(true)
    setError(null)
    try {
      const res = await api.payPayable(
        payable.id,
        file ?? undefined,
        file ? undefined : chosen,
        message,
      )
      setResult(
        res['dry-run']
          ? `Modo prueba: respuesta guardada en ${res.path}`
          : `Respuesta enviada a ${res.to}`,
      )
      onPaid()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo enviar la respuesta')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={() => !sending && onClose()}>
      <div className="modal modal-small" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <div>
            <strong>Pagar factura {payable.folio}</strong>
            <span className="mono muted">
              {' '}
              · {preview ? 'revisar el correo' : 'elegir el comprobante'}
            </span>
          </div>
          <button type="button" className="ghost" onClick={onClose} disabled={sending} aria-label="Cerrar">
            ✕
          </button>
        </header>

        <div className="modal-body">
          {!preview ? (
            <>
              <table className="summary">
                <tbody>
                  <tr>
                    <th>Factura</th>
                    <td className="mono">{payable.folio || '—'}</td>
                    <th>Monto</th>
                    <td>{payable.total ? money.format(payable.total) : '—'}</td>
                  </tr>
                </tbody>
              </table>

              {receipts.length > 0 && (
                <label>
                  Comprobante de la carpeta
                  <select
                    value={file ? '' : chosen}
                    onChange={(e) => {
                      setChosen(e.target.value)
                      setFile(null)
                    }}
                    disabled={sending}
                  >
                    {file && <option value="">(usando el archivo elegido abajo)</option>}
                    {receipts.map((item) => (
                      <option key={item.name} value={item.name}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                  <small className="hint mono">{folder}</small>
                </label>
              )}

              <label>
                {receipts.length > 0 ? '…o subir otro archivo' : 'Comprobante de pago'}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/heic,application/pdf"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  disabled={sending}
                />
              </label>

              {error && <p className="error">{error}</p>}

              <div className="modal-footer">
                <button type="button" className="ghost" onClick={onClose}>
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void review()}
                  disabled={loadingPreview || (!file && !chosen)}
                >
                  {loadingPreview ? 'Generando…' : 'Revisar correo'}
                </button>
              </div>
            </>
          ) : result ? (
            <>
              <p className="ok">{result}</p>
              <div className="modal-footer">
                <button type="button" onClick={onClose}>
                  Cerrar
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="email-meta">
                <div>
                  <span className="meta-label">Para</span>
                  <span>{preview.to}</span>
                </div>
                <div>
                  <span className="meta-label">Asunto</span>
                  <span>{preview.subject}</span>
                </div>
                <div>
                  <span className="meta-label">Adjuntos</span>
                  <span>{preview.attachments.join(', ') || '—'}</span>
                </div>
              </div>

              <label>
                Mensaje
                <textarea
                  className="message-input"
                  rows={9}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  disabled={sending}
                />
              </label>

              {error && <p className="error">{error}</p>}

              <div className="modal-footer">
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setPreview(null)
                    setError(null)
                  }}
                  disabled={sending}
                >
                  Atrás
                </button>
                <button
                  type="button"
                  onClick={() => void submit()}
                  disabled={sending || !message.trim()}
                >
                  {sending ? 'Enviando…' : 'Enviar y marcar pagada'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
