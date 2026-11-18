import { useEffect, useState } from 'react'
import { api, hasRole } from '../auth'

export default function Admin() {
  const [pong, setPong] = useState('')
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
            <p className="muted">Здесь появятся подключения к 1С и настройки ассистента.</p>
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
