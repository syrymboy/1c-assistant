import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { hasRole, initAuth, keycloak } from './auth'
import Home from './pages/Home'
import Admin from './pages/Admin'

export default function App() {
  const [ready, setReady] = useState(false)
  const [authed, setAuthed] = useState(false)

  useEffect(() => {
    initAuth().then((a) => { setAuthed(a); setReady(true) })
  }, [])

  if (!ready) return <div className="container note">Загрузка…</div>

  const claims = keycloak.tokenParsed as { preferred_username?: string } | undefined
  const username = claims?.preferred_username ?? ''

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand"><span className="brand-logo">1С</span>Ассистент</div>
          <nav className="nav">
            <NavLink to="/" end>Главная</NavLink>
            {authed && hasRole('admin') && <NavLink to="/admin">Администрирование</NavLink>}
          </nav>
          <span className="spacer" />
          {authed && <span className="avatar">{username.slice(0, 1).toUpperCase()}</span>}
          {authed
            ? <button className="btn ghost" onClick={() => keycloak.logout({ redirectUri: window.location.origin })}>Выйти</button>
            : <button className="btn" onClick={() => keycloak.login()}>Войти</button>}
        </div>
      </header>
      <main className="container">
        <Routes>
          <Route path="/" element={<Home authed={authed} />} />
          <Route path="/admin" element={<Admin authed={authed} />} />
        </Routes>
      </main>
    </>
  )
}
