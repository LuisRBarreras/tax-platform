import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Payable } from '../types'

interface Props {
  payable: Payable
  onDeleted: () => void
}

/** "Borrar" for a payable: hides the row and drops the cached files. */
export default function DeletePayableButton({ payable, onDeleted }: Props) {
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
      await api.deletePayable(payable.id)
      setOpen(false)
      onDeleted()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo borrar')
    } finally {
      setBusy(false)
    }
  }

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
                <strong>Borrar factura</strong>
                <span className="mono muted"> · {payable.folio || payable.id}</span>
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
                Se oculta de la lista y se borran sus archivos. El correo sigue en tu buzón,
                así que se queda marcada como descartada para que no vuelva a aparecer al
                revisar el correo.
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
