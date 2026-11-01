import { useEffect, useRef, useState } from 'react'
import { api, invoiceProofUrl } from '../api'
import type { Invoice } from '../types'

interface Props {
  invoice: Invoice
  onClose: () => void
  onUploaded: () => void
}

export default function ProofPreview({ invoice, onClose, onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const id = invoice['invoice-id']
  const proofPath = invoice['proof-path'] ?? ''
  const isPdf = proofPath.toLowerCase().endsWith('.pdf')
  // The filename changes when replaced: doubles as a cache-buster.
  const src = `${invoiceProofUrl(id)}?v=${encodeURIComponent(proofPath)}`

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleFile(file: File | undefined) {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await api.uploadProof(id, file)
      onUploaded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo subir el comprobante')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <div>
            <strong>Comprobante de pago</strong>
            <span className="mono muted">
              {' '}
              · {invoice['invoice-number'] || invoice['invoice-id']}
            </span>
          </div>
          <div className="modal-actions">
            <input
              ref={inputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/heic,application/pdf"
              hidden
              onChange={(e) => void handleFile(e.target.files?.[0])}
            />
            <a className="pdf-link" href={src} target="_blank" rel="noreferrer">
              Abrir en pestaña
            </a>
            <button
              type="button"
              className="ghost"
              disabled={uploading}
              onClick={() => inputRef.current?.click()}
            >
              {uploading ? 'Subiendo…' : 'Reemplazar'}
            </button>
            <button type="button" className="ghost" onClick={onClose} aria-label="Cerrar">
              ✕
            </button>
          </div>
        </header>

        <div className="proof-view">
          {isPdf ? (
            <iframe className="pdf-frame" src={src} title="Comprobante" />
          ) : (
            <img className="proof-image" src={src} alt="Comprobante de pago" />
          )}
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    </div>
  )
}
