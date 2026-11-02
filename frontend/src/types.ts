/** Mirrors the JSON returned by the FastAPI backend (kebab-case keys). */

export interface InvoiceItem {
  description: string
  quantity: number
  'unit-price': number
}

export interface Invoice {
  'invoice-id': string
  'invoice-number': string
  'client-name': string
  'client-email': string
  'client-address': string
  items: InvoiceItem[]
  subtotal: number
  tax: number
  total: number
  'due-date': string
  date: string
  'bank-info': string
  status: string
  'pdf-path': string | null
  'proof-path': string | null
  'work-from': string
  'work-to': string
  'deposit-date': string
  'exchange-rate': number | null
  'pesos': number | null
  'created-at': string
  'sent-at': string | null
  'sent-to': string | null
}

export interface CreateInvoicePayload {
  'invoice-number': string
  'client-name': string
  'client-email': string
  'client-address': string
  items: InvoiceItem[]
  date: string
  'work-from': string
  'work-to': string
  'deposit-date': string
  'exchange-rate': number | null
  'pesos': number | null
  'due-date': string
  'bank-info': string
}

export interface CreateInvoiceResponse {
  success: boolean
  'invoice-id': string
  message: string
  'pdf-size': number
}

/** Result of appending the sent invoice to the Google Sheets tracker. */
export interface SheetResult {
  status: 'appended' | 'skipped' | 'disabled' | 'error'
  message?: string
  range?: string
  tab?: string
  url?: string
  to?: string
}

export interface SendInvoiceResponse {
  success: boolean
  'dry-run': boolean
  to: string
  subject: string
  path?: string
  sheet: SheetResult
}
