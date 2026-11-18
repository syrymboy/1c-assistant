import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../auth'
import { money, type Billing as B, type PaymentItem } from '../useBilling'

const date = (s: string) => new Date(s).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
const STATUS: Record<string, string> = { succeeded: 'Оплачен', failed: 'Отклонён' }
const brandName = (b: string | null) => (b === 'mastercard' ? 'Mastercard' : b === 'visa' ? 'Visa' : 'Карта')

export default function Billing({ billing, refresh }: { billing: B | null; refresh: () => Promise<unknown> }) {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [banner, setBanner] = useState<{ kind: 'ok' | 'err' | 'wait'; text: string } | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const paymentId = params.get('payment')

  // Возврат со страницы оплаты: статус приходит вебхуком, поэтому опрашиваем платёж
  useEffect(() => {
    if (!paymentId) return
    let stop = false
    setBanner({ kind: 'wait', text: 'Проверяем платёж…' })
    ;(async () => {
      for (let i = 0; i < 15 && !stop; i++) {
        try {
          const { data } = await api.get<PaymentItem>(`/api/billing/payments/${paymentId}`)
          if (data.status === 'succeeded') { setBanner({ kind: 'ok', text: `Оплата прошла, тариф «${data.plan}» подключён.` }); await refresh(); return }
          if (data.status === 'failed') { setBanner({ kind: 'err', text: `Платёж отклонён: ${data.failure_reason ?? 'банк не подтвердил операцию'}.` }); await refresh(); return }
        } catch { /* повторим */ }
        await new Promise((r) => setTimeout(r, 1000))
      }
      if (!stop) setBanner({ kind: 'wait', text: 'Платёж ещё обрабатывается. Обновите страницу чуть позже.' })
    })()
    return () => { stop = true }
  }, [paymentId, refresh])

  if (!billing) return <div className="page"><div className="column"><p className="muted">Загрузка…</p></div></div>

  const pct = Math.min(100, Math.round((billing.used / billing.limit) * 100))
  const left = Math.max(0, billing.limit - billing.used)

  async function choose(code: string) {
    setBusy(code); setError('')
    try {
      const { data } = await api.post<{ checkout_url: string }>('/api/billing/checkout', { plan_code: code })
      navigate(data.checkout_url)
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Не удалось начать оплату')
    } finally { setBusy('') }
  }
  async function toggleCancel() {
    setBusy('cancel'); setError('')
    try { await api.post(billing!.cancel_at_period_end ? '/api/billing/resume' : '/api/billing/cancel'); await refresh() }
    catch { setError('Не удалось изменить подписку') } finally { setBusy('') }
  }

  return (
    <div className="page">
      <div className="column wide">
        <header className="page-head">
          <h1>Тариф и оплата</h1>
          <p className="notice">Тестовый режим: деньги не списываются. Для оплаты используйте тестовые карты.</p>
        </header>

        {banner && (
          <div className={`banner ${banner.kind}`} role="status">
            <span>{banner.text}</span>
            {banner.kind !== 'wait' && <button className="link" onClick={() => { setBanner(null); setParams({}) }}>Закрыть</button>}
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}

        <section className="current">
          <div>
            <span className="kind">Текущий тариф</span>
            <h2>{billing.plan.name}</h2>
            <p className="muted">
              {billing.paid
                ? billing.cancel_at_period_end
                  ? `Подписка отменена, доступ сохранится до ${date(billing.period_end)}.`
                  : `Следующее списание ${date(billing.period_end)}${billing.card ? ` · ${brandName(billing.card.brand)} •••• ${billing.card.last4}` : ''}.`
                : `Лимит обновится ${date(billing.period_end)}.`}
            </p>
            {billing.paid && (
              <button className="link" onClick={toggleCancel} disabled={busy === 'cancel'}>
                {billing.cancel_at_period_end ? 'Возобновить подписку' : 'Отменить подписку'}
              </button>
            )}
          </div>
          <div className="usage">
            <div className="usage-head"><span>Вопросов использовано</span><strong>{billing.used} из {billing.limit}</strong></div>
            <div className="meter" role="progressbar" aria-valuenow={billing.used} aria-valuemin={0} aria-valuemax={billing.limit}>
              <i style={{ width: `${pct}%` }} className={pct >= 90 ? 'hot' : ''} />
            </div>
            <span className="muted small">Осталось {left}</span>
          </div>
        </section>

        <ul className="plans">
          {billing.plans.map((p) => {
            const current = p.code === billing.plan.code
            return (
              <li key={p.code} className={`plan${current ? ' current-plan' : ''}${p.code === 'pro' ? ' featured' : ''}`}>
                {p.code === 'pro' && <span className="flag">Популярный</span>}
                <h3>{p.name}</h3>
                <p className="price"><strong>{money(p.price, p.currency)}</strong>{p.price > 0 && <span className="muted"> / месяц</span>}</p>
                <ul className="feat">{p.features.map((f) => <li key={f}>{f}</li>)}</ul>
                {current && !billing.cancel_at_period_end
                  ? <button className="btn-outline" disabled>Ваш тариф</button>
                  : p.price === 0
                    ? <button className="btn-outline" disabled>{billing.paid ? 'После окончания подписки' : 'Ваш тариф'}</button>
                    : <button className="primary small" onClick={() => choose(p.code)} disabled={busy === p.code}>
                        {billing.paid ? 'Перейти' : 'Подключить'}
                      </button>}
              </li>
            )
          })}
        </ul>

        <section className="group">
          <div className="group-head"><h2>История платежей</h2></div>
          {billing.payments.length === 0
            ? <p className="muted">Платежей пока нет.</p>
            : (
              <div className="table-wrap">
                <table className="history-table">
                  <thead><tr><th>Дата</th><th>Описание</th><th>Карта</th><th>Сумма</th><th>Статус</th></tr></thead>
                  <tbody>
                    {billing.payments.map((p) => (
                      <tr key={p.id}>
                        <td>{date(p.created_at)}</td>
                        <td>{p.kind === 'renewal' ? 'Автопродление' : 'Оплата'}: «{p.plan}»</td>
                        <td>{p.card_last4 ? `${brandName(p.card_brand)} •••• ${p.card_last4}` : '—'}</td>
                        <td>{money(p.amount, p.currency)}</td>
                        <td><span className={`status ${p.status}`} title={p.failure_reason ?? undefined}>{STATUS[p.status] ?? p.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </section>
      </div>
    </div>
  )
}
