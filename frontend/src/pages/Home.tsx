import { useEffect, useState } from 'react'
import { api, keycloak } from '../auth'

interface Me {
  username: string; email: string | null; full_name: string | null
  roles: string[]; last_login_at: string | null
}

const EXAMPLES: [string, string][] = [
  ['Выручка за сентябрь по филиалам', 'продажи'],
  ['Топ-10 клиентов по сумме отгрузок за квартал', 'клиенты'],
  ['Остатки товаров на складах на сегодня', 'склад'],
  ['Дебиторская задолженность свыше 30 дней', 'расчёты'],
]

const ROLE_NAMES: Record<string, string> = { admin: 'администратор', analyst: 'аналитик', manager: 'менеджер' }

function ExamplesPanel({ title }: { title: string }) {
  return (
    <div className="panel">
      <div className="panel-head">{title}<span className="count">{EXAMPLES.length}</span></div>
      <ul className="examples">
        {EXAMPLES.map(([q, tag]) => (
          <li key={q}><span className="dot" />{q}<span className="tagline">{tag}</span></li>
        ))}
      </ul>
    </div>
  )
}

export default function Home({ authed }: { authed: boolean }) {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!authed) return
    api.get<Me>('/api/me').then((r) => setMe(r.data)).catch((e) => setError(String(e)))
  }, [authed])

  if (!authed) {
    return (
      <>
        <div className="panel landing">
          <h1>Спросите 1С обычными словами</h1>
          <p>Напишите вопрос про продажи, склад или расчёты, а ассистент найдёт ответ в базе 1С. Для работы нужно войти под своей учётной записью.</p>
          <button className="btn" onClick={() => keycloak.login()}>Войти</button>
        </div>
        <ExamplesPanel title="О чём можно спросить" />
      </>
    )
  }
  if (error) return <p className="error">Не удалось загрузить профиль: {error}</p>
  if (!me) return <p className="note">Загрузка профиля…</p>

  const name = me.full_name || me.username
  const roles = me.roles.filter((r) => r in ROLE_NAMES)
  const lastLogin = me.last_login_at ? new Date(me.last_login_at).toLocaleString('ru-RU') : '—'

  return (
    <div className="layout">
      <aside className="panel profile">
        <div className="profile-top">
          <span className="avatar big">{name.slice(0, 1).toUpperCase()}</span>
          <div><h2>{name}</h2><div className="login">@{me.username}</div></div>
        </div>
        <ul className="facts">
          <li><span>Роль</span><span>{roles.length ? roles.map((r) => <span key={r} className="tag">{ROLE_NAMES[r]}</span>) : '—'}</span></li>
          <li><span>Почта</span><span>{me.email || '—'}</span></li>
          <li><span>Последний вход</span><span>{lastLogin}</span></li>
        </ul>
      </aside>
      <section>
        <div className="panel">
          <div className="panel-head">Чат с ассистентом</div>
          <div className="panel-body"><p className="note">Чат появится на следующем этапе. Пока можно посмотреть, какие вопросы он сможет разбирать.</p></div>
          <div className="chatbox"><input disabled placeholder="Например: выручка за сентябрь по филиалам" /><button className="btn" disabled>Спросить</button></div>
        </div>
        <ExamplesPanel title="Примеры вопросов" />
      </section>
    </div>
  )
}
