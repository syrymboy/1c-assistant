import { useEffect, useState } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import { hasRole, initAuth, keycloak } from './auth'
import Home from './pages/Home'
import Admin from './pages/Admin'

export default function App() {
  const [ready, setReady] = useState(false)
  const [authed, setAuthed] = useState(false)

  useEffect(() => {
    initAuth().then((a) => { setAuthed(a); setReady(true) })
  }, [])

  if (!ready) return <p style={{ padding: 24 }}>Загрузка…</p>

  return (
    <div style={{ fontFamily: 'sans-serif', maxWidth: 720, margin: '0 auto', padding: 24 }}>
      <header style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 24 }}>
        <strong>Ассистент 1С</strong>
        <Link to="/">Главная</Link>
        {authed && hasRole('admin') && <Link to="/admin">Админ</Link>}
        <span style={{ flex: 1 }} />
        {authed
          ? <button onClick={() => keycloak.logout({ redirectUri: window.location.origin })}>Выйти</button>
          : <button onClick={() => keycloak.login()}>Войти</button>}
      </header>
      <Routes>
        <Route path="/" element={<Home authed={authed} />} />
        <Route path="/admin" element={<Admin authed={authed} />} />
      </Routes>
    </div>
  )
}
