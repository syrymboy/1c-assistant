import { useEffect, useState } from 'react'
import { api, hasRole } from '../auth'

export default function Admin({ authed }: { authed: boolean }) {
  const [pong, setPong] = useState('')
  const allowed = authed && hasRole('admin')

  useEffect(() => {
    if (allowed) api.get('/api/admin/ping').then((r) => setPong(JSON.stringify(r.data)))
  }, [allowed])

  if (!allowed) {
    return <div className="card hero"><h1>Нет доступа</h1><p className="muted">Эта страница доступна только администраторам.</p></div>
  }
  return (
    <div className="card">
      <h1>Администрирование</h1>
      <p className="muted">Ответ backend: <code>{pong || '…'}</code></p>
    </div>
  )
}
