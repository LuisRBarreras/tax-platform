import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import InvoiceForm from './InvoiceForm'

function getInput(label: string) {
  return screen.getByLabelText(new RegExp(`^${label}`, 'i')) as HTMLInputElement
}

/** Date and number inputs are set directly: typing into a prefilled date is brittle. */
function setValue(label: string, value: string) {
  fireEvent.change(getInput(label), { target: { value } })
}

function fillValidForm() {
  setValue('No. de factura', '2026-010')
  setValue('Fecha factura', '2026-10-31')
  setValue('Monto / Salary', '4200')
  setValue('Tipo de cambio', '18.5')
  setValue('Trabajo desde', '2026-11-01')
  setValue('Trabajo hasta', '2026-11-15')
  setValue('Fecha depósito', '2026-11-14')
}

describe('InvoiceForm', () => {
  it('renders every field grouped in sections', () => {
    render(<InvoiceForm onSubmit={vi.fn()} />)

    expect(screen.getByRole('heading', { name: /nuevo invoice/i })).toBeInTheDocument()
    expect(screen.getByText(/datos del invoice/i)).toBeInTheDocument()
    expect(screen.getByText(/periodo trabajado/i)).toBeInTheDocument()
    expect(screen.getByText(/^montos$/i)).toBeInTheDocument()

    for (const label of [
      'No. de factura',
      'Fecha factura',
      'Trabajo desde',
      'Trabajo hasta',
      'Fecha depósito',
      'Monto / Salary',
      'Tipo de cambio',
      'Pesos',
    ]) {
      expect(getInput(label)).toBeInTheDocument()
    }
  })

  it('keeps submit disabled until the form is valid', async () => {
    const user = userEvent.setup()
    render(<InvoiceForm onSubmit={vi.fn()} />)

    const submit = screen.getByRole('button', { name: /generar invoice/i })
    expect(submit).toBeDisabled()

    await user.type(getInput('Monto / Salary'), '100')
    expect(submit).toBeDisabled() // still missing the rest

    fillValidForm()
    expect(submit).toBeEnabled()
  })

  it('auto-computes the MXN amount from salary and rate', async () => {
    const user = userEvent.setup()
    render(<InvoiceForm onSubmit={vi.fn()} />)

    await user.type(getInput('Monto / Salary'), '4200')
    await user.type(getInput('Tipo de cambio'), '18.5')

    expect(getInput('Pesos')).toHaveValue(77700)
  })

  it('stops recomputing once the MXN amount is edited manually', async () => {
    const user = userEvent.setup()
    render(<InvoiceForm onSubmit={vi.fn()} />)

    await user.type(getInput('Monto / Salary'), '4200')
    await user.type(getInput('Tipo de cambio'), '18.5')

    const pesos = getInput('Pesos')
    await user.clear(pesos)
    await user.type(pesos, '78000')

    await user.clear(getInput('Tipo de cambio'))
    await user.type(getInput('Tipo de cambio'), '19')

    expect(getInput('Pesos')).toHaveValue(78000)
  })

  it('restores automatic calculation with the reset button', async () => {
    const user = userEvent.setup()
    render(<InvoiceForm onSubmit={vi.fn()} />)

    await user.type(getInput('Monto / Salary'), '4200')
    await user.type(getInput('Tipo de cambio'), '18.5')
    await user.clear(getInput('Pesos'))
    await user.type(getInput('Pesos'), '1')

    await user.click(screen.getByTitle(/volver al cálculo automático/i))

    expect(getInput('Pesos')).toHaveValue(77700)
  })

  it('submits the payload the backend expects', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<InvoiceForm onSubmit={onSubmit} />)

    fillValidForm()
    await user.click(screen.getByRole('button', { name: /generar invoice/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const payload = onSubmit.mock.calls[0][0]

    expect(payload['invoice-number']).toBe('2026-010')
    expect(payload.date).toBe('2026-10-31')
    expect(payload['work-from']).toBe('2026-11-01')
    expect(payload['work-to']).toBe('2026-11-15')
    expect(payload['deposit-date']).toBe('2026-11-14')
    expect(payload['exchange-rate']).toBe(18.5)
    expect(payload.pesos).toBe(77700)
    expect(payload.items[0]).toMatchObject({ quantity: 1, 'unit-price': 4200 })
  })

  it('shows the error when the request fails and keeps the data', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockRejectedValue(new Error('La API explotó'))
    render(<InvoiceForm onSubmit={onSubmit} />)

    fillValidForm()
    await user.click(screen.getByRole('button', { name: /generar invoice/i }))

    expect(await screen.findByText('La API explotó')).toBeInTheDocument()
    expect(getInput('Monto / Salary')).toHaveValue(4200)
  })
})
