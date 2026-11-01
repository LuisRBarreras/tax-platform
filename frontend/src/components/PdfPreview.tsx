import { useEffect } from 'react'
import { invoiceHtmlUrl, invoicePdfUrl } from '../api'
import type { Invoice } from '../types'

interface Props {
  invoice: Invoice
  onClose: () => void
}

export default function PdfPreview({ invoice, onClose }: Props) {
  const id = invoice['invoice-id']
  const htmlUrl = invoiceHtmlUrl(id)
  const pdfUrl = invoicePdfUrl(id)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <div>
            <strong>Factura {invoice.date}</strong>
            <span className="mono muted"> · {id}</span>
          </div>
          <div className="modal-actions">
            <a className="pdf-link" href={htmlUrl} target="_blank" rel="noreferrer">
              Abrir en pestaña
            </a>
            <a className="pdf-link" href={pdfUrl} download={`${id}.pdf`}>
              Descargar PDF
            </a>
            <button type="button" className="ghost" onClick={onClose} aria-label="Cerrar">
              ✕
            </button>
          </div>
        </header>
        <iframe
          className="pdf-frame"
          src={htmlUrl}
          title={`Vista previa ${id}`}
          sandbox=""
        />
      </div>
    </div>
  )
}
