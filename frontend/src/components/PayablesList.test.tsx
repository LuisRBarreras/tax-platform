import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PayablesList from './PayablesList'
import type { Payable } from '../types'

const api = vi.hoisted(() => ({ payables: vi.fn(), syncPayables: vi.fn() }))

vi.mock('../api', () => ({
  api,
  payablePdfUrl: (id: string) => `/api/payables/${id}/pdf`,
}))

function makePayable(overrides: Partial<Payable> = {}): Payable {
  return {
    id: 'HON-1',
    'message-id': '<3133@outlook.com>',
    subject: 'Factura 3133',
    sender: 'Carla Velez <carlavelezfacturacion@hotmail.com>',
    'received-at': '2026-11-13T19:17:39+00:00',
    folio: '3133',
    total: 2320,
    subtotal: 2000,
    currency: 'MXN',
    'cfdi-fecha': '2026-11-12',
    period: '2026-10',
    'cfdi-uuid': 'UUID',
    'issuer-name': 'ROSA MARIA VELEZ ESCALANTE ALLEGRE',
    'issuer-rfc': 'VEAR540818TJ1',
    'pdf-path': '.tmp/payables/HON-1.pdf',
    'xml-path': null,
    status: 'pending',
    'replied-at': null,
    'reply-message-id': null,
    'paid-at': null,
    'proof-path': null,
    'created-at': '2026-11-14T00:00:00Z',
    ...overrides,
  }
}

describe('PayablesList', () => {
  beforeEach(() => {
    api.payables.mockReset()
    api.syncPayables.mockReset()
    api.payables.mockResolvedValue({
      payables: [makePayable()],
      counts: { pending: 1 },
      sender: 'carlavelezfacturacion@hotmail.com',
    })
  })

  it('lists pending invoices with amount and download link', async () => {
    render(<PayablesList onPay={vi.fn()} />)

    expect(await screen.findByText('3133')).toBeInTheDocument()
    expect(screen.getByText('pendiente')).toBeInTheDocument()
    expect(screen.getByText('Descargar')).toHaveAttribute('href', '/api/payables/HON-1/pdf')
    expect(screen.getByRole('button', { name: /pagar y responder/i })).toBeInTheDocument()
  })

  it('syncs the mailbox and reloads', async () => {
    api.syncPayables.mockResolvedValue({ success: true, new: 2, 'marked-paid': 1, counts: {} })

    const user = userEvent.setup()
    render(<PayablesList onPay={vi.fn()} />)
    await screen.findByText('3133')

    await user.click(screen.getByRole('button', { name: /revisar correo/i }))

    await waitFor(() => expect(api.syncPayables).toHaveBeenCalled())
    expect(await screen.findByText(/2 nuevas, 1 marcada/i)).toBeInTheDocument()
    expect(api.payables).toHaveBeenCalledTimes(2)
  })
})
