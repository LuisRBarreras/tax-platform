import { describe, expect, it } from 'vitest'
import { formatShortDate, formatWorkPeriod, todayISO } from './invoiceDefaults'

describe('formatWorkPeriod', () => {
  it('collapses a range inside the same month', () => {
    expect(formatWorkPeriod('2026-10-16', '2026-10-31')).toBe('16 al 31 de Oct')
  })

  it('keeps both months when the range crosses them', () => {
    expect(formatWorkPeriod('2026-09-28', '2026-10-12')).toBe('28 Sep al 12 de Oct')
  })

  it('returns an empty string when a date is missing', () => {
    expect(formatWorkPeriod('', '2026-10-12')).toBe('')
    expect(formatWorkPeriod('2026-09-28', '')).toBe('')
  })

  it('returns an empty string for malformed dates', () => {
    expect(formatWorkPeriod('28/09/2026', '12/10/2026')).toBe('')
  })

  it('uses Spanish month abbreviations', () => {
    expect(formatWorkPeriod('2026-01-01', '2026-01-15')).toContain('Ene')
    expect(formatWorkPeriod('2026-12-01', '2026-12-15')).toContain('Dic')
  })
})

describe('formatShortDate', () => {
  it('formats a single date', () => {
    expect(formatShortDate('2026-10-30')).toBe('30 de Oct')
  })

  it('handles empty and malformed input', () => {
    expect(formatShortDate('')).toBe('')
    expect(formatShortDate('nope')).toBe('')
  })
})

describe('todayISO', () => {
  it('returns a YYYY-MM-DD string', () => {
    expect(todayISO()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('uses the local date, not UTC', () => {
    const local = new Date()
    const expected = [
      local.getFullYear(),
      String(local.getMonth() + 1).padStart(2, '0'),
      String(local.getDate()).padStart(2, '0'),
    ].join('-')
    expect(todayISO()).toBe(expected)
  })
})
