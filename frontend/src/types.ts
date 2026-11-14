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

/** An invoice that arrived by mail and still has to be paid ("honorarios"). */
export interface Payable {
  id: string
  'message-id': string
  subject: string
  sender: string
  'received-at': string
  folio: string
  total: number | null
  subtotal: number | null
  currency: string
  'cfdi-fecha': string
  /** Month the invoice covers: '2026-10'. */
  period: string
  'cfdi-uuid': string
  'issuer-name': string
  'issuer-rfc': string
  'pdf-path': string | null
  'xml-path': string | null
  status: 'pending' | 'paid'
  'replied-at': string | null
  'reply-message-id': string | null
  'paid-at': string | null
  'proof-path': string | null
  'created-at': string
}

export interface PayablesResponse {
  payables: Payable[]
  counts: Record<string, number>
  sender: string
}

/** A file in the mounted receipts folder. */
export interface Receipt {
  name: string
  size: number
  modified: string
}

/** Where the sent invoices are logged. */
export interface SheetInfo {
  url: string
  tab: string
  enabled: boolean
}
