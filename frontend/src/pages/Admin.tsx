import { useEffect, useState } from 'react'
import { api, hasRole } from '../auth'

export default function Admin({ authed }: { authed: boolean }) {
  const [pong, setPong] = useState('')
  const allowed = authed && hasRole('admin')

  useEffect(() => {
    if (allowed) api.get('/api/admin/ping').then((r) => setPong(JSON.stringify(r.data)))
  }, [allowed])

  if (!allowed) return <p>Нет доступа</p>
  return (
    <div>
      <h1>Администрирование</h1>
      <p>Ответ backend: {pong || '…'}</p>
    </div>
  )
}
