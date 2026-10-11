import { useEffect, useState } from 'react'
import { api } from '../auth'

interface Me { username: string; email: string | null; full_name: string | null; roles: string[] }

export default function Home({ authed }: { authed: boolean }) {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!authed) return
    api.get<Me>('/api/me').then((r) => setMe(r.data)).catch((e) => setError(String(e)))
  }, [authed])

  if (!authed) return <p>Для работы с ассистентом необходимо войти.</p>
  if (error) return <p style={{ color: 'crimson' }}>Ошибка: {error}</p>
  if (!me) return <p>Загрузка профиля…</p>

  const appRoles = me.roles.filter((r) => ['admin', 'analyst', 'manager'].includes(r))
  return (
    <div>
      <h1>Здравствуйте, {me.full_name || me.username}</h1>
      <p>Роль: {appRoles.join(', ') || '—'}</p>
      <p>E-mail: {me.email || '—'}</p>
      <div style={{ border: '1px dashed #999', padding: 24, borderRadius: 8, color: '#666' }}>
        Здесь будет чат с ассистентом 1С
      </div>
    </div>
  )
}
