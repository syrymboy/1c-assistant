import { useEffect, useState } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { initAuth, keycloak } from './auth'
import { useChats } from './useChats'
import { useSources } from './useSources'
import Sources from './pages/Sources'
import Billing from './pages/Billing'
import Pay from './pages/Pay'
import { useBilling } from './useBilling'
import Sidebar from './components/Sidebar'
import Chat from './pages/Chat'
import Admin from './pages/Admin'
import Landing from './pages/Landing'

export default function App() {
  const [ready, setReady] = useState(false)
  const [authed, setAuthed] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()
  const chats = useChats(authed)
  const src = useSources(authed)
  const bill = useBilling(authed)

  useEffect(() => { initAuth().then((a) => { setAuthed(a); setReady(true) }) }, [])
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  if (!ready) return <div className="splash" role="status">Загрузка…</div>
  if (!authed) return <Landing />
  if (pathname.startsWith('/pay/')) return (
    <Routes><Route path="/pay/:id" element={<Pay />} /></Routes>
  )

  const claims = keycloak.tokenParsed as { name?: string; preferred_username?: string } | undefined
  const name = claims?.name || claims?.preferred_username || ''

  return (
    <div className={`app${menuOpen ? ' menu-open' : ''}`}>
      <aside className="sidebar" id="sidebar">
        <Sidebar
          chats={chats.chats} activeId={chats.activeId} busy={chats.busy}
          onNew={chats.newChat} onOpen={chats.open} onRemove={chats.remove} onRename={chats.rename}
          onNavigate={() => setMenuOpen(false)} billing={bill.billing}
        />
      </aside>
      <div className="scrim" onClick={() => setMenuOpen(false)} />
      <main className="main">
        <header className="mobilebar">
          <button className="icon-btn" aria-label="Меню" aria-controls="sidebar" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
          </button>
          <strong>Ассистент 1С</strong>
        </header>
        <Routes>
          <Route path="/" element={<Sources name={name} sources={src.sources} loaded={src.loaded} error={src.error} onToggle={src.setMany} />} />
          <Route path="/chat" element={<Chat name={name} messages={chats.messages} busy={chats.busy} error={chats.error} limitHit={chats.limitHit} status={chats.status} sources={src.sources} onSend={async (t) => { await chats.send(t); bill.refresh() }} onStop={chats.stop} />} />
          <Route path="/billing" element={<Billing billing={bill.billing} refresh={bill.refresh} />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </main>
    </div>
  )
}
