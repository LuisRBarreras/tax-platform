import { useEffect, useState } from 'react'
import { api } from '../api'
import type { SheetInfo } from '../types'

/** Shortcut to the spreadsheet where every sent invoice appends a row. */
export default function SheetLink() {
  const [info, setInfo] = useState<SheetInfo | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    api
      .sheetInfo()
      .then(setInfo)
      .catch(() => setFailed(true))
  }, [])

  if (failed) {
    return (
      <p className="card sheet-link">
        No se pudo leer la configuración de la hoja de cálculo.
      </p>
    )
  }

  if (!info) return null

  return (
    <div className="card sheet-link">
      <div>
        <strong>Hoja de cálculo</strong>
        <span className="muted">
          {' '}
          · cada factura enviada escribe una fila en el tab <span className="mono">{info.tab}</span>
        </span>
        {!info.enabled && <span className="muted"> · sincronización desactivada</span>}
      </div>
      <a className="pdf-link" href={info.url} target="_blank" rel="noreferrer">
        Abrir Google Sheets ↗
      </a>
    </div>
  )
}
