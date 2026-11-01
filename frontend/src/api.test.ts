import { describe, expect, it } from 'vitest'
import { invoiceHtmlUrl, invoicePdfUrl, invoiceProofUrl } from './api'

describe('URL helpers', () => {
  it('builds the pdf url', () => {
    expect(invoicePdfUrl('INV-1')).toBe('/api/invoices/INV-1/pdf')
  })

  it('builds the proof url', () => {
    expect(invoiceProofUrl('INV-1')).toBe('/api/invoices/INV-1/proof')
  })

  it('builds the preview url', () => {
    expect(invoiceHtmlUrl('INV-1')).toBe('/api/invoices/INV-1/html')
  })

  it('keeps ids untouched (no encoding of the prefix)', () => {
    expect(invoicePdfUrl('INV-abc-123')).toBe('/api/invoices/INV-abc-123/pdf')
  })
})
