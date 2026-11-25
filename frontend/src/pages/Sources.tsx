import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Source } from '../useSources'

interface Props {
  name: string
  sources: Source[]
  loaded: boolean
  error: string
  onToggle: (ids: number[], on: boolean) => void
}

export default function Sources({ name, sources, loaded, error, onToggle }: Props) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<number | null>(null)

  const sections = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const map = new Map<string, Source[]>()
    for (const s of sources) {
      if (needle && !`${s.title} ${s.description} ${s.kind}`.toLowerCase().includes(needle)) continue
      map.set(s.section, [...(map.get(s.section) ?? []), s])
    }
    return [...map.entries()]
  }, [sources, q])

  const chosen = sources.filter((s) => s.enabled).length

  return (
    <div className="page">
      <div className="column wide">
        <header className="page-head">
          <h1>Источники данных</h1>
          <p className="muted">
            Отметьте, к каким данным 1С ассистент сможет обращаться. Он только читает: ничего не изменяет и не проводит.
            Показаны объекты, разрешённые вашей роли.
          </p>
          <p className="notice">Каталог загружен из 1С через OData. Сейчас подключена тестовая заглушка с демонстрационными данными.</p>
        </header>

        <div className="toolbar">
          <label className="search">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
            <span className="sr">Поиск по источникам</span>
            <input type="search" placeholder="Найти источник…" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
        </div>

        {error && <p className="error" role="alert">{error}</p>}
        {!loaded && <p className="muted">Загрузка…</p>}
        {loaded && sections.length === 0 && <p className="muted">Ничего не найдено.</p>}

        {sections.map(([section, items]) => {
          const allOn = items.every((s) => s.enabled)
          return (
            <section key={section} className="group">
              <div className="group-head">
                <h2>{section}</h2>
                <button className="link" onClick={() => onToggle(items.map((s) => s.id), !allOn)}>
                  {allOn ? 'Снять все' : 'Выбрать все'}
                </button>
              </div>
              <ul className="cards">
                {items.map((s) => (
                  <li key={s.id} className={`source${s.enabled ? ' on' : ''}`}>
                    <div className="source-top">
                      <span className="kind">{s.kind}</span>
                      <button
                        role="switch" aria-checked={s.enabled} className="switch"
                        aria-label={`Разрешить ассистенту «${s.title}»`}
                        onClick={() => onToggle([s.id], !s.enabled)}
                      ><i /></button>
                    </div>
                    <h3>{s.title}</h3>
                    <p>{s.description}</p>
                    <button className="link muted-link" aria-expanded={open === s.id}
                      onClick={() => setOpen(open === s.id ? null : s.id)}>
                      {open === s.id ? 'Скрыть поля' : `Поля (${s.fields.length})`}
                    </button>
                    {open === s.id && <p className="fields">{s.fields.join(' · ')}</p>}
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>

      <div className="dock">
        <div className="dock-inner">
          <span>{chosen === 0 ? 'Ничего не выбрано' : `Выбрано: ${chosen} из ${sources.length}`}</span>
          <Link to="/chat" className="primary small">Перейти к чату →</Link>
        </div>
      </div>
    </div>
  )
}
