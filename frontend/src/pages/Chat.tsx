import { useEffect, useMemo, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Link } from 'react-router-dom'
import type { Msg, TraceItem } from '../useChats'
import type { Source } from '../useSources'

const DEFAULT_SUGGESTIONS = [
  'Выручка за сентябрь по филиалам',
  'Топ-10 клиентов по сумме отгрузок за квартал',
  'Остатки товаров на складах на сегодня',
  'Дебиторская задолженность свыше 30 дней',
]
// Подсказки под разделы включённых источников
const BY_SECTION: Record<string, string[]> = {
  'Продажи': ['Выручка за прошлый месяц по филиалам', 'Топ-10 клиентов по сумме отгрузок за квартал'],
  'Склад': ['Остатки товаров на складах на сегодня', 'Какие товары заканчиваются на складе?'],
  'Расчёты': ['Дебиторская задолженность свыше 30 дней', 'Кто из поставщиков ждёт оплаты?'],
  'Справочники': ['Сколько у нас активных контрагентов?'],
  'Персонал': ['Фонд оплаты труда за последний месяц'],
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  return (
    <button className="icon-btn small-btn" aria-label={done ? 'Скопировано' : 'Копировать ответ'} title="Копировать"
      onClick={() => navigator.clipboard.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500) }).catch(() => {})}>
      {done
        ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l5 5 9-10" /></svg>
        : <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 012-2h9" /></svg>}
    </button>
  )
}

const TOOL_LABEL: Record<string, string> = { query_1c: 'Чтение строк', aggregate_1c: 'Подсчёт итогов', find_reference: 'Поиск в справочнике' }

function Trace({ trace }: { trace: TraceItem[] }) {
  return (
    <details className="trace">
      <summary>Как получен ответ · {trace.length} {trace.length === 1 ? 'запрос' : 'запроса к 1С'}</summary>
      <ol>
        {trace.map((t, i) => (
          <li key={i} className={t.error ? 'bad' : ''}>
            <b>{TOOL_LABEL[t.tool] ?? t.tool}</b>
            {t.rows != null && !t.error && <span className="muted"> · {t.rows} {t.tool === 'aggregate_1c' ? 'групп' : 'строк'}</span>}
            {t.request && <code>GET {t.request}</code>}
            {t.error && <span className="err-text">{t.error}</span>}
          </li>
        ))}
      </ol>
      <p className="muted small">Только чтение: ассистент не изменяет данные в 1С.</p>
    </details>
  )
}

interface Props {
  name: string
  messages: Msg[]
  busy: boolean
  error: string
  limitHit: boolean
  status: string
  sources: Source[]
  onSend: (text: string) => void
  onStop: () => void
}

export default function Chat({ name, messages, busy, error, limitHit, status, sources, onSend, onStop }: Props) {
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const areaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [messages])
  useEffect(() => { if (!busy) areaRef.current?.focus() }, [busy])

  const chosen = sources.filter((x) => x.enabled)
  const suggestions = useMemo(() => {
    const picked = chosen.map((x) => x.section).filter((v, i, a) => a.indexOf(v) === i).flatMap((sec) => BY_SECTION[sec] ?? [])
    return picked.length ? picked.slice(0, 4) : DEFAULT_SUGGESTIONS
  }, [chosen])

  const submit = () => {
    if (!input.trim() || busy) return
    onSend(input)
    setInput('')
  }

  return (
    <div className="chat">
      <div className="scroll">
        <div className="column">
          {messages.length === 0 ? (
            <div className="hello">
              <h1>Здравствуйте{name ? `, ${name.split(' ')[0]}` : ''}</h1>
              <p>Спросите о продажах, складе или расчётах обычными словами.</p>
              <div className="chips">
                {suggestions.map((q) => (
                  <button key={q} className="chip" onClick={() => onSend(q)} disabled={busy}>{q}</button>
                ))}
              </div>
            </div>
          ) : (
            <ol className="messages">
              {messages.map((m, i) => (
                <li key={m.id ?? i} className={`msg ${m.role}`}>
                  {m.role === 'assistant' && <span className="bot" aria-hidden="true">1С</span>}
                  <div className="bubble">
                    {m.role === 'user' ? m.content : m.content ? (
                      <>
                        <div className="md"><Markdown remarkPlugins={[remarkGfm]} components={{ a: (p) => <a {...p} target="_blank" rel="noopener noreferrer" /> }}>{m.content}</Markdown></div>
                        {m.trace && m.trace.length > 0 && !(busy && i === messages.length - 1) && <Trace trace={m.trace} />}
                        {!(busy && i === messages.length - 1) && <div className="actions"><CopyButton text={m.content} /></div>}
                      </>
                    ) : busy && i === messages.length - 1
                      ? <span className="typing" role="status" aria-label="Ассистент печатает"><i /><i /><i />{status && <em className="status-line">{status}</em>}</span>
                      : null}
                  </div>
                </li>
              ))}
            </ol>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="composer-wrap">
        <div className="column">
          <div className="scope">
            {chosen.length === 0
              ? <span>Источники не выбраны. <Link to="/">Выбрать</Link></span>
              : <>
                  <span className="muted">Отвечаю по:</span>
                  {chosen.slice(0, 3).map((x) => <span key={x.id} className="pill">{x.title}</span>)}
                  {chosen.length > 3 && <span className="pill">+{chosen.length - 3}</span>}
                  <Link to="/">Изменить</Link>
                </>}
          </div>
          {error && <p className="error" role="alert">{error}{limitHit && <> <Link to="/billing">Выбрать тариф</Link></>}</p>}
          <form className="composer" onSubmit={(e) => { e.preventDefault(); submit() }}>
            <label htmlFor="q" className="sr">Ваш вопрос</label>
            <textarea
              id="q" ref={areaRef} rows={1} value={input} maxLength={4000}
              placeholder="Задайте вопрос по данным 1С…"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  // Enter подтверждает ввод в IME — отправлять в этот момент нельзя
                  if (e.nativeEvent.isComposing || e.keyCode === 229) return
                  submit()
                }
              }}
            />
            {busy
              ? <button type="button" className="send stop" onClick={onStop} aria-label="Остановить ответ"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" /></svg></button>
              : <button className="send" disabled={!input.trim()} aria-label="Отправить"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg></button>}
          </form>
          <p className="hint">Enter — отправить, Shift+Enter — новая строка</p>
        </div>
      </div>
    </div>
  )
}
