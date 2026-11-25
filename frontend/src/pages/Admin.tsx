import { useEffect, useState } from 'react'
import { api, hasRole } from '../auth'

interface Report { total: number; added: string[]; updated: string[]; removed: string[] }

export default function Admin() {
  const [pong, setPong] = useState('')
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState('')
  async function sync() {
    setBusy(true); setError(''); setReport(null)
    try { setReport((await api.post<Report>('/api/sources/sync')).data) }
    catch (e: any) { setError(e?.response?.data?.detail ?? 'Не удалось обновить каталог') }
    finally { setBusy(false) }
  }
  const allowed = hasRole('admin')

  useEffect(() => {
    if (allowed) api.get('/api/admin/ping').then((r) => setPong(JSON.stringify(r.data)))
  }, [allowed])

  return (
    <div className="page">
      <div className="column">
        {allowed ? (
          <>
            <h1>Администрирование</h1>
            <section className="group">
              <div className="group-head"><h2>Подключение к 1С</h2></div>
              <p className="muted">Каталог источников берётся из метаданных 1С (OData). Названия, описания и роли хранятся в приложении и при обновлении не меняются; новые объекты доступны только администратору.</p>
              <button className="primary small" onClick={sync} disabled={busy}>{busy ? 'Обновляем…' : 'Обновить каталог из 1С'}</button>
              {error && <p className="error" role="alert">{error}</p>}
              {report && (
                <p className="muted" role="status">
                  Объектов в 1С: {report.total}. Добавлено: {report.added.length}, обновлено: {report.updated.length}, снято с публикации: {report.removed.length}.
                </p>
              )}
            </section>
            <div className="card"><span className="muted">Ответ backend</span><code>{pong || '…'}</code></div>
          </>
        ) : (
          <div className="empty-state">
            <h1>Нет доступа</h1>
            <p className="muted">Эта страница только для администраторов. Если она вам нужна, попросите выдать роль.</p>
          </div>
        )}
      </div>
    </div>
  )
}
