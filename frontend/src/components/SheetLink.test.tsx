import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SheetLink from './SheetLink'

const api = vi.hoisted(() => ({ sheetInfo: vi.fn() }))

vi.mock('../api', () => ({ api }))

describe('SheetLink', () => {
  beforeEach(() => {
    api.sheetInfo.mockReset()
  })

  it('links to the configured tab', async () => {
    api.sheetInfo.mockResolvedValue({
      url: 'https://docs.google.com/spreadsheets/d/abc/edit#gid=1',
      tab: '2026',
      enabled: true,
    })

    render(<SheetLink />)

    const link = await screen.findByRole('link', { name: /abrir google sheets/i })
    expect(link).toHaveAttribute('href', 'https://docs.google.com/spreadsheets/d/abc/edit#gid=1')
    expect(screen.getByText('2026')).toBeInTheDocument()
    expect(screen.queryByText(/desactivada/i)).not.toBeInTheDocument()
  })

  it('says so when the sync is off', async () => {
    api.sheetInfo.mockResolvedValue({ url: 'https://x', tab: '2026', enabled: false })

    render(<SheetLink />)

    expect(await screen.findByText(/desactivada/i)).toBeInTheDocument()
  })
})
