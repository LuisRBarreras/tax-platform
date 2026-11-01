import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import InvoiceList from './InvoiceList'
import type { Invoice } from '../types'

function makeInvoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    'invoice-id': 'INV-1',
    'invoice-number': '2026-010',
    'client-name': 'Client',
    'client-email': 'c@example.com',
    'client-address': '',
    items: [],
    subtotal: 4200,
    tax: 0,
    total: 4200,
    'due-date': '',
    date: '2026-10-31',
    'bank-info': '',
    status: 'created',
    'pdf-path': null,
    'proof-path': null,
    'work-from': '2026-10-16',
    'work-to': '2026-10-31',
    'deposit-date': '2026-10-30',
    'exchange-rate': 18.5,
    pesos: 77700,
    'created-at': '2026-11-01T15:05:53+00:00',
    'sent-at': null,
    'sent-to': null,
    ...overrides,
  }
}

const baseProps = {
  loading: false,
  onRefresh: vi.fn(),
  onPreview: vi.fn(),
  onProofUploaded: vi.fn(),
  onProofPreview: vi.fn(),
  onSend: vi.fn(),
  page: 1,
  pages: 3,
  total: 21,
  onPage: vi.fn(),
}

describe('InvoiceList', () => {
  it('renders the invoice number, date, amount and created timestamp', () => {
    render(<InvoiceList invoices={[makeInvoice()]} {...baseProps} />)

    expect(screen.getByText('2026-010')).toBeInTheDocument()
    expect(screen.getByText('2026-10-31')).toBeInTheDocument()
    expect(screen.getByText('$4,200.00')).toBeInTheDocument()
    expect(screen.getByText(/01 nov 2026/i)).toBeInTheDocument()
  })

  it('translates the stored status into Spanish', () => {
    const { rerender } = render(<InvoiceList invoices={[makeInvoice()]} {...baseProps} />)
    expect(screen.getByText('creada')).toBeInTheDocument()

    rerender(<InvoiceList invoices={[makeInvoice({ status: 'sent' })]} {...baseProps} />)
    expect(screen.getByText('enviada')).toBeInTheDocument()
  })

  it('shows the record range and page counter', () => {
    render(<InvoiceList invoices={[makeInvoice()]} {...baseProps} page={2} />)

    expect(screen.getByText('11–20 de 21')).toBeInTheDocument()
    expect(screen.getByText('Página 2 de 3')).toBeInTheDocument()
  })

  it('disables previous on the first page and next on the last one', () => {
    const { rerender } = render(<InvoiceList invoices={[makeInvoice()]} {...baseProps} page={1} />)
    expect(screen.getByRole('button', { name: /anterior/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /siguiente/i })).toBeEnabled()

    rerender(<InvoiceList invoices={[makeInvoice()]} {...baseProps} page={3} />)
    expect(screen.getByRole('button', { name: /anterior/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /siguiente/i })).toBeDisabled()
  })

  it('asks for the neighbouring page', async () => {
    const user = userEvent.setup()
    const onPage = vi.fn()
    render(<InvoiceList invoices={[makeInvoice()]} {...baseProps} page={2} onPage={onPage} />)

    await user.click(screen.getByRole('button', { name: /siguiente/i }))
    expect(onPage).toHaveBeenCalledWith(3)

    await user.click(screen.getByRole('button', { name: /anterior/i }))
    expect(onPage).toHaveBeenCalledWith(1)
  })

  it('shows the empty state when there are no invoices', () => {
    render(<InvoiceList invoices={[]} {...baseProps} total={0} pages={1} />)
    expect(screen.getByText(/todavía no hay facturas/i)).toBeInTheDocument()
    expect(screen.getByText(/sin registros/i)).toBeInTheDocument()
  })

  it('opens the proof preview only when a proof exists', async () => {
    const user = userEvent.setup()
    const onProofPreview = vi.fn()
    const { container } = render(
      <InvoiceList
        invoices={[makeInvoice({ 'proof-path': '.tmp/proofs/INV-1.png' })]}
        {...baseProps}
        onProofPreview={onProofPreview}
      />,
    )

    // The PDF column also has a "Ver" button; target the proof cell.
    const proofButton = container.querySelector('.proof-cell button')!
    await user.click(proofButton)

    expect(onProofPreview).toHaveBeenCalledTimes(1)
  })
})
