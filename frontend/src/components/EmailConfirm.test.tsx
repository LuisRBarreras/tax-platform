import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EmailConfirm from './EmailConfirm'
import type { Invoice } from '../types'

const emailPreview = vi.fn()

vi.mock('../api', () => ({
  api: { emailPreview: (...args: unknown[]) => emailPreview(...args) },
  invoiceProofUrl: (id: string) => `/api/invoices/${id}/proof`,
}))

function makeInvoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    'invoice-id': 'INV-1',
    'invoice-number': '455',
    'client-name': 'Client',
    'client-email': 'c@example.com',
    'client-address': '',
    items: [],
    subtotal: 500,
    tax: 0,
    total: 500,
    'due-date': '',
    date: '2026-11-15',
    'bank-info': '',
    status: 'created',
    'pdf-path': '.tmp/invoices/INV-1.pdf',
    'proof-path': '.tmp/proofs/INV-1.jpg',
    'work-from': '2026-11-01',
    'work-to': '2026-11-15',
    'deposit-date': '2026-11-15',
    'exchange-rate': 18,
    pesos: 9000,
    'created-at': '2026-11-02T00:00:00Z',
    'sent-at': null,
    'sent-to': null,
    ...overrides,
  }
}

function renderConfirm(invoice = makeInvoice()) {
  return render(
    <EmailConfirm
      invoice={invoice}
      to="lrbs0190@gmail.com"
      onCancel={() => {}}
      onConfirm={() => {}}
      sending={false}
    />,
  )
}

describe('EmailConfirm', () => {
  beforeEach(() => {
    emailPreview.mockReset()
  })

  it('shows the attachment names the recipient will get', async () => {
    emailPreview.mockResolvedValue({
      to: 'lrbs0190@gmail.com',
      subject: 'Invoice 455',
      from: 'me@example.com',
      attachments: ['invoice-455.pdf', 'comprobante-15-nov.jpg'],
      html: '<p>hola</p>',
    })

    renderConfirm()

    expect(await screen.findByText('invoice-455.pdf')).toBeInTheDocument()
    expect(await screen.findByText('comprobante-15-nov.jpg')).toBeInTheDocument()
  })

  it('falls back to the invoice number while the preview loads', () => {
    emailPreview.mockReturnValue(new Promise(() => {}))

    renderConfirm()

    expect(screen.getByText('455')).toBeInTheDocument()
    expect(screen.getByText('comprobante')).toBeInTheDocument()
  })

  it('says so when there is no proof', async () => {
    emailPreview.mockResolvedValue({
      to: 'lrbs0190@gmail.com',
      subject: 'Invoice 455',
      from: 'me@example.com',
      attachments: ['invoice-455.pdf'],
      html: '<p>hola</p>',
    })

    renderConfirm(makeInvoice({ 'proof-path': null }))

    expect(await screen.findByText('Sin comprobante')).toBeInTheDocument()
    expect(screen.queryByText('comprobante')).not.toBeInTheDocument()
  })
})
