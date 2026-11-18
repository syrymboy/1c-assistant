import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { api, hasRole, keycloak } from '../auth'
import type { ChatItem } from '../useChats'
import type { Billing } from '../useBilling'

interface Me { username: string; full_name: string | null; email: string | null; roles: string[] }
const ROLE_NAMES: Record<string, string> = { admin: 'Администратор', analyst: 'Аналитик', manager: 'Менеджер' }

interface Props {
  chats: ChatItem[]
  activeId: number | null
  busy: boolean
  onNew: () => void
  onOpen: (id: number) => void
  onRemove: (id: number) => void
  onRename: (id: number, title: string) => void
  onNavigate: () => void
  billing: Billing | null
}

export default function Sidebar({ chats, activeId, busy, onNew, onOpen, onRemove, onRename, onNavigate, billing }: Props) {
  const [me, setMe] = useState<Me | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [draft, setDraft] = useState('')
  const navigate = useNavigate()

  useEffect(() => { api.get<Me>('/api/me').then((r) => setMe(r.data)).catch(() => {}) }, [])

  const name = me?.full_name || me?.username || ''
  const role = me?.roles.map((r) => ROLE_NAMES[r]).find(Boolean) ?? ''
  const go = (fn: () => void) => () => { navigate('/chat'); fn(); onNavigate() }

  return (
    <div className="sidebar-inner">
      <div className="brand"><span className="brand-logo">1С</span>Ассистент</div>
      <nav className="mainnav" aria-label="Разделы">
        <NavLink to="/" end onClick={onNavigate}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></svg>
          Источники данных
        </NavLink>
        <NavLink to="/billing" onClick={onNavigate}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18" /></svg>
          Тариф и оплата
        </NavLink>
      </nav>
      <button className="new-chat" onClick={go(onNew)} disabled={busy}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        Новый чат
      </button>

      <nav className="history" aria-label="История диалогов">
        {chats.length > 0 && <h2>История</h2>}
        <ul>
          {chats.map((c) => (
            <li key={c.id} className={c.id === activeId ? 'active' : ''}>
              {editId === c.id ? (
                <input
                  className="rename" autoFocus value={draft} maxLength={120} aria-label="Название диалога"
                  onChange={(e) => setDraft(e.target.value)}
                  onFocus={(e) => e.currentTarget.select()}
                  onBlur={() => { onRename(c.id, draft); setEditId(null) }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.nativeEvent.isComposing && e.keyCode !== 229) e.currentTarget.blur()
                    if (e.key === 'Escape') { setDraft(c.title); setEditId(null) }
                  }}
                />
              ) : confirmId === c.id ? (
                <div className="confirm">
                  <span>Удалить?</span>
                  <button className="link danger" onClick={() => { setConfirmId(null); onRemove(c.id) }}>Да</button>
                  <button className="link" onClick={() => setConfirmId(null)}>Нет</button>
                </div>
              ) : (
                <>
                  <button className="chat-title" onClick={go(() => onOpen(c.id))}
                    onDoubleClick={() => { setDraft(c.title); setEditId(c.id) }} title={c.title}>{c.title}</button>
                  <button className="chat-del" onClick={() => { setDraft(c.title); setEditId(c.id) }} aria-label={`Переименовать диалог «${c.title}»`} disabled={busy}>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16v4zM13 7l4 4" /></svg>
                  </button>
                  <button className="chat-del" onClick={() => setConfirmId(c.id)} aria-label={`Удалить диалог «${c.title}»`} disabled={busy}>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12h10l1-12M9 7V4h6v3" /></svg>
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      </nav>

      {billing && (
        <NavLink to="/billing" className="quota" onClick={onNavigate}>
          <span>{billing.plan.name}</span>
          <span className="muted">Осталось {Math.max(0, billing.limit - billing.used)} из {billing.limit}</span>
          <span className="meter"><i style={{ width: `${Math.min(100, (billing.used / billing.limit) * 100)}%` }} className={billing.used / billing.limit >= 0.9 ? 'hot' : ''} /></span>
        </NavLink>
      )}
      <div className="user">
        {hasRole('admin') && (
          <NavLink to="/admin" className="user-link" onClick={onNavigate}>Администрирование</NavLink>
        )}
        <div className="user-row">
          <span className="avatar">{name.slice(0, 1).toUpperCase()}</span>
          <div className="user-meta">
            <strong>{name || '…'}</strong>
            <span>{role || me?.email || ''}</span>
          </div>
          <button className="icon-btn" aria-label="Выйти" title="Выйти"
            onClick={() => keycloak.logout({ redirectUri: window.location.origin })}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4H5v16h4M16 8l4 4-4 4M20 12H9" /></svg>
          </button>
        </div>
      </div>
    </div>
  )
}
