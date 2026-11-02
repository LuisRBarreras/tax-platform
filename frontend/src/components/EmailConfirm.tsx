import { useEffect, useState } from 'react'
import { api, invoiceProofUrl } from '../api'
import PdfPreview from './PdfPreview'
import ProofPreview from './ProofPreview'
import type { Invoice } from '../types'

interface Preview {
  to: string
  subject: string
  from: string
  attachments: string[]
  html: string
}

interface Props {
  invoice: Invoice
  to: string
  onCancel: () => void
  onConfirm: () => void
  sending: boolean
}

export default function EmailConfirm({ invoice, to, onCancel, onConfirm, sending }: Props) {
  const [preview, setPreview] = useState<Preview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showPdf, setShowPdf] = useState(false)
  const [showProof, setShowProof] = useState(false)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape' && !sending) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel, sending])

  // Names as the recipient will see them, straight from the backend.
  const [pdfName, proofName] = preview?.attachments ?? []

  useEffect(() => {
    let alive = true
    setPreview(null)
    setError(null)
    api
      .emailPreview(invoice['invoice-id'], to)
      .then((data) => alive && setPreview(data))
      .catch((err) => alive && setError(err instanceof Error ? err.message : 'Error'))
    return () => {
      alive = false
    }
  }, [invoice, to])

  return (
    <div className="modal-backdrop" onClick={() => !sending && onCancel()}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <div>
            <strong>Confirmar envío</strong>
            <span className="mono muted"> · revisa el correo antes de enviarlo</span>
          </div>
          <button type="button" className="ghost" onClick={onCancel} disabled={sending} aria-label="Cerrar">
            ✕
          </button>
        </header>

        <div className="email-meta">
          <div>
            <span className="meta-label">Para</span>
            <span>{preview?.to ?? to}</span>
          </div>
          <div>
            <span className="meta-label">Asunto</span>
            <span>{preview?.subject ?? '—'}</span>
          </div>
          <div>
            <span className="meta-label">Adjuntos</span>
            <span className="attachments-row">
              <button
                type="button"
                className="attachment"
                onClick={() => setShowPdf(true)}
                title="Ver la factura adjunta"
              >
                <span className="attachment-icon">PDF</span>
                <span className="attachment-name">
                  {pdfName || invoice['invoice-number'] || invoice['invoice-id']}
                </span>
              </button>

              {invoice['proof-path'] ? (
                <button
                  type="button"
                  className="attachment"
                  onClick={() => setShowProof(true)}
                  title="Ver el comprobante adjunto"
                >
                  <img
                    className="attachment-thumb"
                    src={`${invoiceProofUrl(invoice['invoice-id'])}?v=${encodeURIComponent(invoice['proof-path'])}`}
                    alt="Comprobante"
                  />
                  <span className="attachment-name">
                    {proofName ?? 'comprobante'}
                  </span>
                </button>
              ) : (
                <span className="attachment muted-attachment">Sin comprobante</span>
              )}

            </span>
          </div>
        </div>

        {error && <p className="error">{error}</p>}

        {preview ? (
          <iframe
            className="email-frame"
            title="Vista previa del correo"
            srcDoc={preview.html}
            sandbox=""
          />
        ) : (
          !error && <p className="hint email-loading">Generando vista previa…</p>
        )}

        <div className="modal-footer">
          <button type="button" className="ghost" onClick={onCancel} disabled={sending}>
            Cancelar
          </button>
          <button type="button" onClick={onConfirm} disabled={sending || !preview}>
            {sending ? 'Enviando…' : 'Confirmar y enviar'}
          </button>
        </div>
      </div>

      {showPdf && <PdfPreview invoice={invoice} onClose={() => setShowPdf(false)} />}
      {showProof && (
        <ProofPreview
          invoice={invoice}
          onClose={() => setShowProof(false)}
          onUploaded={() => setShowProof(false)}
        />
      )}
    </div>
  )
}
