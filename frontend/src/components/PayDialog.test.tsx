import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PayDialog from './PayDialog'
import type { Payable } from '../types'

const api = vi.hoisted(() => ({
  receipts: vi.fn(),
  payablePreview: vi.fn(),
  payPayable: vi.fn(),
}))

vi.mock('../api', () => ({ api }))

const payable: Payable = {
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
  'pdf-path': null,
  'xml-path': null,
  status: 'pending',
  'replied-at': null,
  'reply-message-id': null,
  'paid-at': null,
  'proof-path': null,
  'created-at': '2026-11-14T00:00:00Z',
}

describe('PayDialog', () => {
  beforeEach(() => {
    api.receipts.mockReset()
    api.payablePreview.mockReset()
    api.payPayable.mockReset()
    api.receipts.mockResolvedValue({
      receipts: [{ name: 'octubre.jpeg', size: 10, modified: '2026-11-14T00:00:00Z' }],
      directory: '/receipts',
      available: true,
    })
    api.payablePreview.mockResolvedValue({
      to: 'carlavelezfacturacion@hotmail.com',
      subject: 'Re: Factura 3133',
      text: 'Buen día,\n\nAdjunto el comprobante.',
      html: '<p>Buen día,</p>',
      attachments: ['comprobante-3133-12-nov.jpeg'],
    })
  })

  it('shows the reply before sending it', async () => {
    const user = userEvent.setup()
    render(<PayDialog payable={payable} onClose={() => {}} onPaid={() => {}} />)

    await user.click(await screen.findByRole('button', { name: /revisar correo/i }))

    expect(await screen.findByText('Re: Factura 3133')).toBeInTheDocument()
    expect(screen.getByText('comprobante-3133-12-nov.jpeg')).toBeInTheDocument()
    expect(screen.getByDisplayValue(/Adjunto el comprobante/)).toBeInTheDocument()
    expect(api.payPayable).not.toHaveBeenCalled()
  })

  it('sends the edited message', async () => {
    api.payPayable.mockResolvedValue({
      success: true,
      payable: { ...payable, status: 'paid' },
      'dry-run': false,
      to: 'carlavelezfacturacion@hotmail.com',
      subject: 'Re: Factura 3133',
    })

    const user = userEvent.setup()
    render(<PayDialog payable={payable} onClose={() => {}} onPaid={() => {}} />)

    await user.click(await screen.findByRole('button', { name: /revisar correo/i }))
    const box = await screen.findByDisplayValue(/Adjunto el comprobante/)
    await user.clear(box)
    await user.type(box, 'Ya quedó el pago de noviembre.')
    await user.click(screen.getByRole('button', { name: /enviar y marcar pagada/i }))

    expect(api.payPayable).toHaveBeenCalledWith(
      'HON-1',
      undefined,
      'octubre.jpeg',
      'Ya quedó el pago de noviembre.',
    )
  })

  it('can go back and pick another receipt', async () => {
    const user = userEvent.setup()
    render(<PayDialog payable={payable} onClose={() => {}} onPaid={() => {}} />)

    await user.click(await screen.findByRole('button', { name: /revisar correo/i }))
    await screen.findByText('Re: Factura 3133')
    await user.click(screen.getByRole('button', { name: 'Atrás' }))

    expect(screen.queryByText('Re: Factura 3133')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /revisar correo/i })).toBeInTheDocument()
  })
})
