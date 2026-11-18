import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import axios from 'axios'
import { api } from '../auth'
import { money } from '../useBilling'

// Страница оплаты провайдера (симулятор). Приложение сюда не передаёт ничего, кроме id платёжной сессии,
// и не видит данных карты — результат придёт ему вебхуком.
const psp = axios.create({ baseURL: `${import.meta.env.VITE_API_URL}/api/psp` })

interface Info { id: string; plan_code: string; status: string; amount: number; currency: string; description: string; merchant: string; return_url: string; card: { brand: string; last4: string } | null }

const TEST_CARDS = [
  ['4242 4242 4242 4242', 'Успешная оплата'],
  ['4000 0027 6000 3184', 'Подтверждение 3-D Secure'],
  ['4000 0000 0000 0002', 'Отказ банка'],
  ['4000 0000 0000 9995', 'Недостаточно средств'],
]

const fmtNumber = (v: string) => v.replace(/\D/g, '').slice(0, 19).replace(/(.{4})/g, '$1 ').trim()
const fmtExp = (v: string) => { const d = v.replace(/\D/g, '').slice(0, 4); return d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d }

export default function Pay() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [info, setInfo] = useState<Info | null>(null)
  const [fatal, setFatal] = useState('')
  const [number, setNumber] = useState('')
  const [exp, setExp] = useState('')
  const [cvc, setCvc] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [threeDs, setThreeDs] = useState(false)
  const [declined, setDeclined] = useState(false)

  useEffect(() => {
    psp.get<Info>(`/checkout/${id}`)
      .then((r) => {
        setInfo(r.data)
        if (r.data.status === 'requires_action') setThreeDs(true)
        else if (r.data.status !== 'open') navigate(r.data.return_url, { replace: true })
      })
      .catch((e) => setFatal(e?.response?.data?.detail ?? 'Платёжная сессия не найдена'))
  }, [id, navigate])

  const done = (url: string) => navigate(url, { replace: true })

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try {
      const { data } = await psp.post(`/checkout/${id}/pay`, { number, exp, cvc, name })
      if (data.status === 'requires_action') setThreeDs(true)
      else if (data.status === 'succeeded') done(data.return_url)
      else { setError(data.message ?? 'Платёж отклонён'); setDeclined(true); setBusy(false); return }
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Не удалось выполнить платёж')
    }
    setBusy(false)
  }

  // Отказ закрывает платёжную сессию (как в реальных провайдерах) — для новой попытки создаём новую
  async function retry() {
    setBusy(true)
    try {
      const { data } = await api.post<{ checkout_url: string }>('/api/billing/checkout', { plan_code: info!.plan_code })
      setDeclined(false); setError(''); setNumber(''); setExp(''); setCvc('')
      navigate(data.checkout_url, { replace: true })
    } catch { setError('Не удалось начать новую попытку') }
    setBusy(false)
  }

  async function authenticate(approve: boolean) {
    setBusy(true)
    try { const { data } = await psp.post(`/checkout/${id}/authenticate`, { approve }); done(data.return_url) }
    catch (err: any) { setError(err?.response?.data?.detail ?? 'Ошибка подтверждения'); setBusy(false) }
  }

  if (fatal) return <div className="pay-wrap"><div className="pay-card center"><h1>Оплата недоступна</h1><p className="muted">{fatal}</p><Link to="/billing" className="primary small">К тарифам</Link></div></div>
  if (!info) return <div className="splash" role="status">Загрузка…</div>

  return (
    <div className="pay-wrap">
      <div className="pay-card">
        <aside className="pay-summary">
          <Link to="/billing" className="back">← Вернуться в {info.merchant}</Link>
          <span className="test-badge">Тестовый режим</span>
          <p className="muted">{info.description}</p>
          <p className="amount">{money(info.amount, info.currency)}</p>
          <div className="test-cards">
            <strong>Тестовые карты</strong>
            <p className="muted small">Срок — любой будущий, CVC — любые 3 цифры.</p>
            <ul>
              {TEST_CARDS.map(([n, d]) => (
                <li key={n}><button type="button" className="link" onClick={() => { setNumber(n); setExp('12/34'); setCvc('123'); setName('TEST USER') }}>{n}</button><span className="muted small">{d}</span></li>
              ))}
            </ul>
          </div>
        </aside>

        {threeDs ? (
          <div className="pay-form">
            <h1>Подтверждение в банке</h1>
            <p className="muted">Банк запросил подтверждение платежа{info.card ? ` по карте •••• ${info.card.last4}` : ''}. В тестовом режиме решение выбираете вы.</p>
            {error && <p className="error" role="alert">{error}</p>}
            <div className="row">
              <button className="primary" disabled={busy} onClick={() => authenticate(true)}>Подтвердить</button>
              <button className="btn-outline" disabled={busy} onClick={() => authenticate(false)}>Отклонить</button>
            </div>
          </div>
        ) : (
          <form className="pay-form" onSubmit={submit} autoComplete="off">
            <h1>Оплата картой</h1>
            <label>Номер карты
              <input inputMode="numeric" autoComplete="off" placeholder="4242 4242 4242 4242" value={number} onChange={(e) => setNumber(fmtNumber(e.target.value))} required />
            </label>
            <div className="row">
              <label>Срок
                <input inputMode="numeric" autoComplete="off" placeholder="ММ/ГГ" value={exp} onChange={(e) => setExp(fmtExp(e.target.value))} required />
              </label>
              <label>CVC
                <input inputMode="numeric" autoComplete="off" placeholder="123" maxLength={4} value={cvc} onChange={(e) => setCvc(e.target.value.replace(/\D/g, ''))} required />
              </label>
            </div>
            <label>Имя на карте
              <input autoComplete="off" placeholder="IVAN PETROV" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            {error && <p className="error" role="alert">{error}</p>}
            {declined
              ? <button type="button" className="primary" disabled={busy} onClick={retry}>Попробовать снова</button>
              : <button className="primary" disabled={busy}>{busy ? 'Обработка…' : `Оплатить ${money(info.amount, info.currency)}`}</button>}
            <p className="muted small">Это учебный симулятор платёжной системы. Не вводите данные реальной карты.</p>
          </form>
        )}
      </div>
    </div>
  )
}
