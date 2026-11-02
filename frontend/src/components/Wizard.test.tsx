import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Wizard from './Wizard'
import type { Invoice } from '../types'

const api = vi.hoisted(() => ({
  mailRecipients: vi.fn(),
  emailPreviewWithSubject: vi.fn(),
  createInvoice: vi.fn(),
  getInvoice: vi.fn(),
  uploadProof: vi.fn(),
  sendInvoice: vi.fn(),
}))

vi.mock('../api', () => ({
  api,
  invoiceProofUrl: (id: string) => `/api/invoices/${id}/proof`,
  invoiceHtmlUrl: (id: string) => `/api/invoices/${id}/html`,
  invoicePdfUrl: (id: string) => `/api/invoices/${id}/pdf`,
}))

function makeInvoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    'invoice-id': 'INV-1',
    'invoice-number': '455',
    'client-name': 'LoanPro Software, LLC',
    'client-email': 'billing@loanpro.io',
    'client-address': '',
    items: [{ description: 'Software Service', quantity: 1, 'unit-price': 500 }],
    subtotal: 500,
    tax: 0,
    total: 500,
    'due-date': '',
    date: '2026-11-15',
    'bank-info': '',
    status: 'created',
    'pdf-path': '.tmp/invoices/INV-1.pdf',
    'proof-path': null,
    'work-from': '2026-11-01',
    'work-to': '2026-11-15',
    'deposit-date': '2026-11-15',
    'exchange-rate': 18,
    pesos: null,
    'created-at': '2026-11-02T00:00:00Z',
    'sent-at': null,
    'sent-to': null,
    ...overrides,
  }
}

function getInput(label: string) {
  return screen.getByLabelText(new RegExp(`^${label}`, 'i')) as HTMLInputElement
}

function setValue(label: string, value: string) {
  fireEvent.change(getInput(label), { target: { value } })
}

async function reachConfirmStep() {
  setValue('No. de factura', '455')
  setValue('Fecha factura', '2026-11-15')
  setValue('Monto / Salary', '500')
  setValue('Tipo de cambio', '18')
  setValue('Trabajo desde', '2026-11-01')
  setValue('Trabajo hasta', '2026-11-15')
  setValue('Fecha depósito', '2026-11-15')

  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: /generar invoice/i }))
  await user.click(await screen.findByRole('button', { name: /continuar sin comprobante/i }))
  return user
}

describe('Wizard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.mailRecipients.mockResolvedValue({ recipients: ['lrbs0190@gmail.com'], 'dry-run': false })
    api.emailPreviewWithSubject.mockResolvedValue({
      to: 'lrbs0190@gmail.com',
      subject: 'Invoice 455 — 1 al 15 de Nov',
      attachments: ['invoice-455.pdf'],
      html: '<p>hola</p>',
    })
    api.createInvoice.mockResolvedValue({ success: true, 'invoice-id': 'INV-1' })
    api.getInvoice.mockResolvedValue(makeInvoice())
  })

  it('ends in a final step with the result and a fresh start', async () => {
    api.sendInvoice.mockResolvedValue({
      success: true,
      'dry-run': false,
      to: 'lrbs0190@gmail.com',
      subject: 'Invoice 455 — 1 al 15 de Nov',
      sheet: { status: 'appended', tab: 'Copy of 2026' },
    })

    render(<Wizard onCreated={() => {}} />)
    const user = await reachConfirmStep()

    await user.click(await screen.findByRole('button', { name: /confirmar y enviar/i }))

    expect(await screen.findByText(/correo enviado/i)).toBeInTheDocument()
    expect(screen.getByText(/lrbs0190@gmail\.com/)).toBeInTheDocument()
    expect(screen.getByText('Invoice 455 — 1 al 15 de Nov')).toBeInTheDocument()
    expect(screen.getByText('invoice-455.pdf')).toBeInTheDocument()
    expect(screen.getByText(/fila agregada en copy of 2026/i)).toBeInTheDocument()

    // The fourth step is the current one.
    expect(screen.getByText('Finalize')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /nuevo invoice/i }))

    // Back to step 1: the form is empty and the success is gone.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /generar invoice/i })).toBeInTheDocument(),
    )
    expect(screen.queryByText(/correo enviado/i)).not.toBeInTheDocument()
    // The stepper is back on step 1.
    expect(screen.getAllByRole('listitem')[0]).toHaveClass('current')
  })

  it('explains a spreadsheet that could not be written', async () => {
    api.sendInvoice.mockResolvedValue({
      success: true,
      'dry-run': false,
      to: 'lrbs0190@gmail.com',
      subject: 'Invoice 455 — 1 al 15 de Nov',
      sheet: { status: 'error', message: 'La cuenta de servicio no tiene permiso sobre la hoja.' },
    })

    render(<Wizard onCreated={() => {}} />)
    const user = await reachConfirmStep()
    await user.click(await screen.findByRole('button', { name: /confirmar y enviar/i }))

    expect(
      await screen.findByText(/la cuenta de servicio no tiene permiso sobre la hoja/i),
    ).toBeInTheDocument()
  })

  it('shows the dry-run notice instead of a sent message', async () => {
    api.sendInvoice.mockResolvedValue({
      success: true,
      'dry-run': true,
      to: 'lrbs0190@gmail.com',
      subject: 'Invoice 455 — 1 al 15 de Nov',
      path: '.tmp/outbox/INV-1.eml',
      sheet: { status: 'skipped', message: 'Modo prueba (SMTP_DRY_RUN=1)' },
    })

    render(<Wizard onCreated={() => {}} />)
    const user = await reachConfirmStep()
    await user.click(await screen.findByRole('button', { name: /confirmar y enviar/i }))

    expect(await screen.findByText(/modo prueba: correo guardado/i)).toBeInTheDocument()
    expect(screen.getByText(/modo prueba \(smtp_dry_run=1\)/i)).toBeInTheDocument()
  })
})
