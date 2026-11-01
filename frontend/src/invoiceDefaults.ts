/** Fixed invoice data (not captured by the form). */

/** Single billable concept. */
export const DEFAULT_DESCRIPTION = 'Software Service'

/** Today's date in local time (not UTC), YYYY-MM-DD. */
export function todayISO(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

/** Short Spanish month names, used for "16 al 31 de Oct". */
const MONTHS_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

/** "2026-10-16" + "2026-10-31" -> "16 al 31 de Oct" ("28 Sep al 12 Oct" across months). */
export function formatWorkPeriod(from: string, to: string): string {
  if (!from || !to) return ''
  const [fy, fm, fd] = from.split('-').map(Number)
  const [ty, tm, td] = to.split('-').map(Number)
  if (!fy || !fm || !fd || !ty || !tm || !td) return ''

  const fromLabel = fm === tm ? String(fd) : `${fd} ${MONTHS_ES[fm - 1]}`
  return `${fromLabel} al ${td} de ${MONTHS_ES[tm - 1]}`
}

/** "2026-10-30" -> "30 de Oct" */
export function formatShortDate(value: string): string {
  if (!value) return ''
  const [, month, day] = value.split('-').map(Number)
  if (!month || !day) return ''
  return `${day} de ${MONTHS_ES[month - 1]}`
}
