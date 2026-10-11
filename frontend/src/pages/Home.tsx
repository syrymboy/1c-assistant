import { useEffect, useState } from 'react'
import { api, keycloak } from '../auth'

interface Me { username: string; email: string | null; full_name: string | null; roles: string[] }

export default function Home({ authed }: { authed: boolean }) {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!authed) return
    api.get<Me>('/api/me').then((r) => setMe(r.data)).catch((e) => setError(String(e)))
  }, [authed])

  if (!authed) {
    return (
      <div className="card hero">
        <h1>Ассистент 1С</h1>
        <p className="muted">Задавайте вопросы об управленческих данных 1С обычным языком.</p>
        <button className="btn" onClick={() => keycloak.login()}>Войти</button>
      </div>
    )
  }
  if (error) return <p className="error">Ошибка: {error}</p>
  if (!me) return <p className="muted">Загрузка профиля…</p>

  const appRoles = me.roles.filter((r) => ['admin', 'analyst', 'manager'].includes(r))
  return (
    <div className="card">
      <h1>Здравствуйте, {me.full_name || me.username}</h1>
      <div className="info">
        <div><span>Роль</span>{appRoles.length ? appRoles.map((r) => <b key={r} className="badge">{r}</b>) : '—'}</div>
        <div><span>E-mail</span>{me.email || '—'}</div>
      </div>
      <div className="placeholder">Здесь будет чат с ассистентом 1С</div>
    </div>
  )
}
