import { useCallback, useEffect, useState } from 'react'
import { api, invoiceProofUrl } from '../api'
import { formatWorkPeriod } from '../invoiceDefaults'
import InvoiceForm from './InvoiceForm'
import PdfPreview from './PdfPreview'
import ProofPreview from './ProofPreview'
import type { CreateInvoicePayload, Invoice, SendInvoiceResponse, SheetResult } from '../types'

interface Props {
  onCreated: () => void
}

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

type Step = 1 | 2 | 3 | 4

const STEPS: { id: Step; label: string }[] = [
  { id: 1, label: 'Invoice' },
  { id: 2, label: 'Comprobante' },
  { id: 3, label: 'Enviar' },
  { id: 4, label: 'Finalize' },
]

function sheetMessage(sheet: SheetResult | undefined): string {
  if (!sheet) return 'Sin información del spreadsheet'
  switch (sheet.status) {
    case 'appended':
      return `Fila agregada en ${sheet.tab ?? 'el spreadsheet'}`
    case 'skipped':
      return sheet.message ?? 'No se escribe en modo prueba'
    case 'disabled':
      return 'Desactivado (GOOGLE_SHEETS_ENABLED=0)'
    default:
      return sheet.message ?? 'No se pudo guardar la fila'
  }
}

export default function Wizard({ onCreated }: Props) {
  const [step, setStep] = useState<Step>(1)
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [error, setError] = useState<string | null>(null)

  // step 2
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)

  // step 3
  const [recipients, setRecipients] = useState<string[]>([])
  const [to, setTo] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [result, setResult] = useState<SendInvoiceResponse | null>(null)
  const [previewAttachments, setPreviewAttachments] = useState<string[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const [subject, setSubject] = useState('')
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewSubject, setPreviewSubject] = useState('')
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [showPdf, setShowPdf] = useState(false)
  const [showProof, setShowProof] = useState(false)

  useEffect(() => {
    api
      .mailRecipients()
      .then((data) => {
        setRecipients(data.recipients)
        setTo(data.recipients[0] ?? '')
      })
      .catch(() => setRecipients([]))
  }, [])

  useEffect(() => {
    if (step !== 3 || !invoice || !to) return
    let alive = true
    setLoadingPreview(true)
    api
      .emailPreviewWithSubject(invoice['invoice-id'], to)
      .then((data) => {
        if (!alive) return
        setPreviewHtml(data.html)
        setPreviewSubject(data.subject)
        setPreviewAttachments(data.attachments)
        // preload the subject only once
        setSubject((prev) => prev || data.subject)
      })
      .catch((err) => alive && setError(err instanceof Error ? err.message : 'Error'))
      .finally(() => alive && setLoadingPreview(false))
    return () => {
      alive = false
    }
  }, [step, invoice, to])

  const createInvoice = useCallback(
    async (payload: CreateInvoicePayload) => {
      setError(null)
      const created = await api.createInvoice(payload)
      const full = await api.getInvoice(created['invoice-id'])
      setInvoice(full)
      onCreated()
      setStep(2)
    },
    [onCreated],
  )

  async function uploadProof(file: File | undefined) {
    if (!file || !invoice) return
    setUploading(true)
    setError(null)
    try {
      await api.uploadProof(invoice['invoice-id'], file)
      const refreshed = await api.getInvoice(invoice['invoice-id'])
      setInvoice(refreshed)
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo subir el comprobante')
    } finally {
      setUploading(false)
    }
  }

  async function sendInvoice() {
    if (!invoice) return
    setSending(true)
    setError(null)
    try {
      const res = await api.sendInvoice(invoice['invoice-id'], to, subject || previewSubject)
      setResult(res)
      setSent(true)
      onCreated()
      if (res['dry-run']) setNotice(`Modo prueba: guardado en ${res.path}`)
      setStep(4)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo enviar')
    } finally {
      setSending(false)
    }
  }

  function reset() {
    setInvoice(null)
    setSent(false)
    setResult(null)
    setPreviewAttachments([])
    setError(null)
    setNotice(null)
    setSubject('')
    setPreviewHtml('')
    setStep(1)
  }

  const period = invoice ? formatWorkPeriod(invoice['work-from'], invoice['work-to']) : ''

  return (
    <section className="card wizard">
      <ol className="stepper">
        {STEPS.map(({ id, label }) => (
          <li
            key={id}
            className={`step ${step === id ? 'current' : ''} ${step > id ? 'done' : ''}`}
          >
            <span className="step-num">{step > id ? '✓' : id}</span>
            <span className="step-label">{label}</span>
          </li>
        ))}
      </ol>

      {step === 1 && <InvoiceForm onSubmit={createInvoice} embedded />}

      {step === 2 && invoice && (
        <div className="wizard-body">
          <p className="wizard-summary">
            Invoice <strong>{invoice['invoice-number'] || invoice['invoice-id']}</strong> ·{' '}
            {period || invoice.date} · <strong>{money.format(invoice.total)}</strong>
          </p>

          <label
            className={`dropzone ${dragging ? 'dragging' : ''}`}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              void uploadProof(e.dataTransfer.files?.[0])
            }}
          >
            <input
              type="file"
              hidden
              accept="image/png,image/jpeg,image/webp,image/heic,application/pdf"
              onChange={(e) => void uploadProof(e.target.files?.[0])}
            />
            {uploading ? (
              <span>Subiendo…</span>
            ) : invoice['proof-path'] ? (
              <img
                className="dropzone-thumb"
                src={`${invoiceProofUrl(invoice['invoice-id'])}?v=${encodeURIComponent(invoice['proof-path'])}`}
                alt="Comprobante"
              />
            ) : (
              <span>
                Arrastra el comprobante aquí o <u>haz clic</u> para elegirlo
                <small>PNG, JPG, WEBP, HEIC o PDF · máx. 10 MB</small>
              </span>
            )}
          </label>

          {invoice['proof-path'] && (
            <p className="hint">Comprobante cargado. Puedes reemplazarlo arrastrando otro archivo.</p>
          )}

          <div className="wizard-actions">
            <button type="button" onClick={() => setStep(3)}>
              {invoice['proof-path'] ? 'Continuar' : 'Continuar sin comprobante'}
            </button>
          </div>
        </div>
      )}

      {step === 3 && invoice && (
        <div className="wizard-body">
          <div className="email-meta compose">
            <div>
              <span className="meta-label">Para</span>
              <select
                value={to}
                onChange={(e) => setTo(e.target.value)}
                disabled={sending || sent}
              >
                {recipients.map((addr) => (
                  <option key={addr} value={addr}>
                    {addr}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <span className="meta-label">Asunto</span>
              <input
                className="subject-input"
                value={subject}
                placeholder={previewSubject}
                onChange={(e) => setSubject(e.target.value)}
                disabled={sending || sent}
              />
            </div>
            <div>
              <span className="meta-label">Adjuntos</span>
              <span className="attachments-row">
                <button type="button" className="attachment" onClick={() => setShowPdf(true)}>
                  <span className="attachment-icon">PDF</span>
                  <span className="attachment-name">
                    {invoice['invoice-number'] || invoice['invoice-id']}
                  </span>
                </button>
                {invoice['proof-path'] && (
                  <button type="button" className="attachment" onClick={() => setShowProof(true)}>
                    <span className="attachment-name">Comprobante</span>
                  </button>
                )}
              </span>
            </div>
          </div>

          {loadingPreview && !previewHtml ? (
            <p className="hint email-loading">Generando vista previa…</p>
          ) : (
            <iframe className="email-frame inline" title="Vista previa del correo" srcDoc={previewHtml} sandbox="" />
          )}

          {notice && <p className="note">{notice}</p>}
          {error && <p className="error">{error}</p>}

          <div className="wizard-actions">
            <button type="button" className="ghost" onClick={() => setStep(2)} disabled={sending}>
              Atrás
            </button>
            <button type="button" onClick={sendInvoice} disabled={sending || !to}>
              {sending ? 'Enviando…' : 'Confirmar y enviar'}
            </button>
          </div>
        </div>
      )}


      {step === 4 && invoice && result && (
        <div className="wizard-body finalize">
          <div className="finalize-badge" aria-hidden="true">
            ✓
          </div>

          <div className="finalize-text">
            <h3 className="finalize-title">
              {result['dry-run'] ? 'Modo prueba: correo guardado' : 'Correo enviado'}
            </h3>
            <p className="hint">
              Invoice <strong>{invoice['invoice-number'] || invoice['invoice-id']}</strong> ·{' '}
              {result.to}
            </p>
          </div>

          <dl className="finalize-list">
            <dt>Asunto</dt>
            <dd>{result.subject}</dd>
            <dt>Adjuntos</dt>
            <dd>{previewAttachments.join(' + ') || '—'}</dd>
            <dt>Spreadsheet</dt>
            <dd>{sheetMessage(result.sheet)}</dd>
          </dl>

          {notice && <p className="note">{notice}</p>}

          <div className="wizard-actions">
            <button type="button" onClick={reset}>
              Nuevo invoice
            </button>
          </div>
        </div>
      )}

      {showPdf && <PdfPreview invoice={invoice!} onClose={() => setShowPdf(false)} />}
      {showProof && invoice && (
        <ProofPreview invoice={invoice} onClose={() => setShowProof(false)} onUploaded={() => {}} />
      )}
    </section>
  )
}
