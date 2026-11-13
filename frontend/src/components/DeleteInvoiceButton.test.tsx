import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DeleteInvoiceButton from './DeleteInvoiceButton'
import type { Invoice } from '../types'

const api = vi.hoisted(() => ({ deleteInvoice: vi.fn() }))

vi.mock('../api', () => ({ api }))

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

describe('DeleteInvoiceButton', () => {
  beforeEach(() => {
    api.deleteInvoice.mockReset()
  })

  it('asks before deleting', async () => {
    const user = userEvent.setup()
    render(<DeleteInvoiceButton invoice={makeInvoice()} onDeleted={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Borrar' }))

    expect(screen.getByText(/no se puede deshacer/i)).toBeInTheDocument()
    expect(api.deleteInvoice).not.toHaveBeenCalled()
  })

  it('deletes after confirming', async () => {
    const onDeleted = vi.fn()
    api.deleteInvoice.mockResolvedValue({ success: true, 'invoice-id': 'INV-1', 'files-removed': [] })

    const user = userEvent.setup()
    render(<DeleteInvoiceButton invoice={makeInvoice()} onDeleted={onDeleted} />)

    await user.click(screen.getByRole('button', { name: 'Borrar' }))
    await user.click(screen.getByRole('button', { name: 'Sí, borrar' }))

    await waitFor(() => expect(api.deleteInvoice).toHaveBeenCalledWith('INV-1'))
    expect(onDeleted).toHaveBeenCalled()
  })

  it('cancel leaves the invoice alone', async () => {
    const user = userEvent.setup()
    render(<DeleteInvoiceButton invoice={makeInvoice()} onDeleted={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Borrar' }))
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(screen.queryByText(/no se puede deshacer/i)).not.toBeInTheDocument()
    expect(api.deleteInvoice).not.toHaveBeenCalled()
  })

  it('reports a failure and keeps the dialog open', async () => {
    api.deleteInvoice.mockRejectedValue(new Error('Factura no encontrada'))

    const user = userEvent.setup()
    render(<DeleteInvoiceButton invoice={makeInvoice()} onDeleted={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Borrar' }))
    await user.click(screen.getByRole('button', { name: 'Sí, borrar' }))

    expect(await screen.findByText('Factura no encontrada')).toBeInTheDocument()
    expect(screen.getByText(/no se puede deshacer/i)).toBeInTheDocument()
  })
})
