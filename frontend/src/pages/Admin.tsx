import { useEffect, useState } from 'react'
import { api, hasRole } from '../auth'

export default function Admin({ authed }: { authed: boolean }) {
  const [pong, setPong] = useState('')
  const allowed = authed && hasRole('admin')

  useEffect(() => {
    if (allowed) api.get('/api/admin/ping').then((r) => setPong(JSON.stringify(r.data)))
  }, [allowed])

  if (!allowed) {
    return (
      <div className="panel landing">
        <h1>Нет доступа</h1>
        <p>Эта страница только для администраторов. Если она вам нужна, попросите выдать роль.</p>
      </div>
    )
  }
  return (
    <div className="panel">
      <div className="panel-head">Администрирование</div>
      <div className="panel-body"><p className="note">Ответ backend: <code>{pong || '…'}</code></p></div>
    </div>
  )
}
