import { useRef, useState } from 'react'
import { api } from '../api'
import type { Invoice } from '../types'

interface Props {
  invoice: Invoice
  onUploaded: () => void
  onPreview: (invoice: Invoice) => void
}

export default function ProofUpload({ invoice, onUploaded, onPreview }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const hasProof = Boolean(invoice['proof-path'])

  async function handleFile(file: File | undefined) {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await api.uploadProof(invoice['invoice-id'], file)
      onUploaded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo subir el comprobante')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <span className="proof-cell">
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/heic,application/pdf"
        hidden
        onChange={(e) => void handleFile(e.target.files?.[0])}
      />

      {hasProof ? (
        <button type="button" className="link-button" onClick={() => onPreview(invoice)}>
          Ver
        </button>
      ) : (
        <button
          type="button"
          className="link-button"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
        >
          {uploading ? 'Subiendo…' : 'Subir'}
        </button>
      )}

      {error && (
        <span className="proof-error" title={error}>
          ⚠
        </span>
      )}
    </span>
  )
}
