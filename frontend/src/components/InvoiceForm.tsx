import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { formatShortDate, formatWorkPeriod, todayISO } from '../invoiceDefaults'
import type { CreateInvoicePayload } from '../types'

interface Props {
  onSubmit: (payload: CreateInvoicePayload) => Promise<void>
  /** Inside the wizard the form does not render its own card. */
  embedded?: boolean
}

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const money3 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 })

export default function InvoiceForm({ onSubmit, embedded = false }: Props) {
  const [invoiceNumber, setInvoiceNumber] = useState('')
  const [date, setDate] = useState(todayISO)
  const [amount, setAmount] = useState('')
  const [workFrom, setWorkFrom] = useState('')
  const [workTo, setWorkTo] = useState('')
  const [depositDate, setDepositDate] = useState('')
  const [rate, setRate] = useState('')
  const [pesosInput, setPesosInput] = useState('')
  const [pesosManual, setPesosManual] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const parsedAmount = Number(amount)
  const parsedRate = Number(rate)
  const valid =
    amount.trim() !== '' &&
    Number.isFinite(parsedAmount) &&
    parsedAmount > 0 &&
    rate.trim() !== '' &&
    Number.isFinite(parsedRate) &&
    parsedRate > 0 &&
    invoiceNumber.trim() !== '' &&
    workFrom !== '' &&
    workTo !== '' &&
    depositDate !== ''

  const sugerido = parsedAmount > 0 && parsedRate > 0 ? parsedAmount * parsedRate : 0

  useEffect(() => {
    if (!pesosManual) setPesosInput(sugerido > 0 ? sugerido.toFixed(2) : '')
  }, [sugerido, pesosManual])

  const parsedPesos = Number(pesosInput)
  const pesos = Number.isFinite(parsedPesos) && parsedPesos > 0 ? parsedPesos : sugerido
  const period = formatWorkPeriod(workFrom, workTo)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!valid || submitting) return

    setSubmitting(true)
    setError(null)
    try {
      await onSubmit({
        'invoice-number': invoiceNumber.trim(),
        'client-name': '',
        'client-email': '',
        'client-address': '',
        date,
        'work-from': workFrom,
        'work-to': workTo,
        'deposit-date': depositDate,
        'exchange-rate': parsedRate,
        'pesos': Number(pesos.toFixed(2)),
        items: [{ description: 'Software Service', quantity: 1, 'unit-price': parsedAmount }],
        'due-date': '',
        'bank-info': '',
      })
      setAmount('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo generar la factura')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className={embedded ? 'wizard-form' : 'card'} onSubmit={handleSubmit}>
      {!embedded && <h2>Nuevo invoice</h2>}

      <div className="grid">
        <p className="group-label">Datos del invoice</p>
        <label>
          No. de factura
          <input
            required
            placeholder="2026-010"
            value={invoiceNumber}
            onChange={(e) => setInvoiceNumber(e.target.value)}
          />
        </label>
        <label>
          Fecha factura
          <input required type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <p className="group-label">Periodo trabajado</p>
        <label>
          Trabajo desde
          <input required type="date" value={workFrom} onChange={(e) => setWorkFrom(e.target.value)} />
        </label>
        <label>
          Trabajo hasta
          <input required type="date" value={workTo} onChange={(e) => setWorkTo(e.target.value)} />
        </label>
        <label>
          Fecha depósito
          <input
            required
            type="date"
            value={depositDate}
            onChange={(e) => setDepositDate(e.target.value)}
          />
        </label>
        <p className="group-label">Montos</p>
        <label>
          Monto / Salary (USD)
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            inputMode="decimal"
            placeholder="4083.33"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <label>
          Tipo de cambio
          <input
            required
            type="number"
            min="0.001"
            step="0.001"
            inputMode="decimal"
            placeholder="18.760"
            value={rate}
            onChange={(e) => setRate(e.target.value)}
          />
        </label>
        <label>
          Pesos (MXN)
          <span className="input-with-action">
            <input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              placeholder="Automático"
              value={pesosInput}
              onChange={(e) => {
                setPesosManual(true)
                setPesosInput(e.target.value)
              }}
            />
            {pesosManual && (
              <button
                type="button"
                className="ghost mini"
                title="Volver al cálculo automático"
                onClick={() => setPesosManual(false)}
              >
                ↻
              </button>
            )}
          </span>
        </label>
      </div>

      {valid && (
        <div className="totals">
          <span>{period}</span>
          <span>{formatShortDate(depositDate)}</span>
          <strong>{money.format(parsedAmount)}</strong>
          <span>{money3.format(parsedRate)}</span>
          <strong>{money.format(pesos)}</strong>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <button type="submit" disabled={!valid || submitting}>
        {submitting ? 'Generando PDF…' : 'Generar invoice'}
      </button>
    </form>
  )
}
