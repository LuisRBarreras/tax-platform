import type {
  CreateInvoicePayload,
  CreateInvoiceResponse,
  Invoice,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE ?? '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      // no JSON body: keep the status code
    }
    throw new Error(detail)
  }

  return res.json() as Promise<T>
}

/** URL of the generated PDF (download). */
export function invoicePdfUrl(id: string): string {
  return `${BASE_URL}/invoices/${id}/pdf`
}

/** URL of the uploaded payment proof. */
export function invoiceProofUrl(id: string): string {
  return `${BASE_URL}/invoices/${id}/proof`
}

/**
 * Preview URL (same template, served as HTML).
 * Used instead of the PDF inside the iframe because some browsers do not
 * render embedded PDFs and just show a blank area.
 */
export function invoiceHtmlUrl(id: string): string {
  return `${BASE_URL}/invoices/${id}/html`
}

export const api = {
  listInvoices: (page = 1, perPage = 10) =>
    request<{
      invoices: Invoice[]
      total: number
      page: number
      per_page: number
      pages: number
    }>(`/invoices?page=${page}&per_page=${perPage}`),

  getInvoice: (id: string) => request<Invoice>(`/invoices/${id}`),

  createInvoice: (payload: CreateInvoicePayload) =>
    request<CreateInvoiceResponse>('/invoices', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  mailRecipients: () =>
    request<{ recipients: string[]; 'dry-run': boolean }>('/mail/recipients'),

  emailPreview: (id: string, to: string) =>
    request<{
      to: string
      subject: string
      from: string
      attachments: string[]
      html: string
      text: string
    }>(`/invoices/${id}/email-preview?to=${encodeURIComponent(to)}`),

  sendInvoice: (id: string, to: string, subject?: string) =>
    request<{ success: boolean; 'dry-run': boolean; to: string; subject: string; path?: string }>(
      `/invoices/${id}/send`,
      { method: 'POST', body: JSON.stringify({ to, subject: subject ?? '' }) },
    ),

  emailPreviewWithSubject: (id: string, to: string, subject = '') =>
    request<{ subject: string; to: string; attachments: string[]; html: string }>(
      `/invoices/${id}/email-preview?to=${encodeURIComponent(to)}&subject=${encodeURIComponent(subject)}`,
    ),

  /** multipart: do NOT set Content-Type, the browser adds the boundary. */
  uploadProof: async (id: string, file: File) => {
    const form = new FormData()
    form.append('proof', file)

    const res = await fetch(`${BASE_URL}/invoices/${id}/upload-proof`, {
      method: 'POST',
      body: form,
    })

    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        if (typeof body?.detail === 'string') detail = body.detail
      } catch {
        // no JSON body
      }
      throw new Error(detail)
    }

    return res.json()
  },
}
