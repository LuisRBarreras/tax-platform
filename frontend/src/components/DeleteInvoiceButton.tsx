import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Invoice } from '../types'

interface Props {
  invoice: Invoice
  onDeleted: () => void
}

/** "Borrar" link plus the confirmation that actually calls the API. */
export default function DeleteInvoiceButton({ invoice, onDeleted }: Props) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape' && !busy) setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, busy])

  async function remove() {
    setBusy(true)
    setError(null)
    try {
      await api.deleteInvoice(invoice['invoice-id'])
      setOpen(false)
      onDeleted()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo borrar la factura')
    } finally {
      setBusy(false)
    }
  }

  const label = invoice['invoice-number'] || invoice['invoice-id']
  const attachments = invoice['proof-path'] ? 'el PDF y el comprobante' : 'el PDF'

  return (
    <>
      <button type="button" className="link-button danger" onClick={() => setOpen(true)}>
        Borrar
      </button>

      {open && (
        <div className="modal-backdrop" onClick={() => !busy && setOpen(false)}>
          <div className="modal modal-small" onClick={(e) => e.stopPropagation()}>
            <header className="modal-head">
              <div>
                <strong>Borrar invoice</strong>
                <span className="mono muted"> · {label}</span>
              </div>
              <button
                type="button"
                className="ghost"
                onClick={() => setOpen(false)}
                disabled={busy}
                aria-label="Cerrar"
              >
                ✕
              </button>
            </header>

            <div className="modal-body">
              <p className="hint">
                Se borran la factura y sus archivos ({attachments}). No se puede deshacer.
              </p>

              {error && <p className="error">{error}</p>}

              <div className="modal-footer">
                <button type="button" className="ghost" onClick={() => setOpen(false)} disabled={busy}>
                  Cancelar
                </button>
                <button type="button" className="danger" onClick={() => void remove()} disabled={busy}>
                  {busy ? 'Borrando…' : 'Sí, borrar'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
