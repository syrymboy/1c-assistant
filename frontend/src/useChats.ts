import { useCallback, useEffect, useRef, useState } from 'react'
import { api, keycloak } from './auth'

export interface ChatItem { id: number; title: string }
export interface TraceItem { tool: string; entity?: string; request?: string; rows?: number | null; error?: string }
export interface Msg { id?: number; role: 'user' | 'assistant'; content: string; trace?: TraceItem[] | null }

export function useChats(enabled: boolean) {
  const [chats, setChats] = useState<ChatItem[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Msg[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [limitHit, setLimitHit] = useState(false)
  const [status, setStatus] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  const loadChats = useCallback(
    () => api.get<ChatItem[]>('/api/chats').then((r) => setChats(r.data)).catch((e) => setError(String(e))),
    [],
  )
  useEffect(() => { if (enabled) loadChats() }, [enabled, loadChats])

  const newChat = useCallback(() => {
    if (busy) return
    setActiveId(null); setMessages([]); setError('')
  }, [busy])

  const open = useCallback(async (id: number) => {
    if (busy) return
    setError(''); setActiveId(id)
    try {
      const r = await api.get<{ messages: Msg[] }>(`/api/chats/${id}`)
      setMessages(r.data.messages)
    } catch (e) { setError(`Не удалось открыть диалог: ${e instanceof Error ? e.message : e}`) }
  }, [busy])

  const rename = useCallback(async (id: number, title: string) => {
    const t = title.trim()
    if (!t) return
    setChats((c) => c.map((x) => (x.id === id ? { ...x, title: t } : x)))
    try { await api.patch(`/api/chats/${id}`, { title: t }) } catch { loadChats() }
  }, [loadChats])

  const stop = useCallback(() => abortRef.current?.abort(), [])

  const remove = useCallback(async (id: number) => {
    if (busy) return
    await api.delete(`/api/chats/${id}`)
    if (id === activeId) { setActiveId(null); setMessages([]) }
    loadChats()
  }, [busy, activeId, loadChats])

  const send = useCallback(async (raw: string) => {
    const text = raw.trim()
    if (!text || busy) return
    setBusy(true); setError(''); setLimitHit(false); setStatus('')
    try {
      let id = activeId
      if (id === null) {
        id = (await api.post<ChatItem>('/api/chats')).data.id
        setActiveId(id)
      }
      setMessages((m) => [...m, { role: 'user', content: text }, { role: 'assistant', content: '' }])

      await keycloak.updateToken(30).catch(() => keycloak.login())
      const ctrl = new AbortController()
      abortRef.current = ctrl
      const resp = await fetch(`${import.meta.env.VITE_API_URL}/api/chats/${id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${keycloak.token}` },
        body: JSON.stringify({ content: text }),
        signal: ctrl.signal,
      })
      if (resp.status === 402) {
        // лимит тарифа исчерпан: убираем неотправленные пузыри и объясняем причину
        setMessages((m) => m.slice(0, -2))
        const d = await resp.json().catch(() => null)
        setError(d?.detail ?? 'Лимит вопросов тарифа исчерпан')
        setLimitHit(true)
        return
      }
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const frames = buf.split('\n\n')
        buf = frames.pop() ?? ''
        for (const f of frames) {
          if (!f.startsWith('data: ')) continue
          const ev = JSON.parse(f.slice(6))
          if (ev.tool) setStatus(ev.tool.entity ? `Запрашиваю данные 1С: ${ev.tool.entity.split('_').slice(1).join(' ')}…` : 'Запрашиваю данные 1С…')
          else if (ev.trace) {
            setMessages((m) => {
              const copy = m.slice()
              const last = copy[copy.length - 1]
              copy[copy.length - 1] = { ...last, trace: [...(last.trace ?? []), ev.trace] }
              return copy
            })
          } else if (ev.delta) {
            setStatus('')
            setMessages((m) => {
              const copy = m.slice()
              const last = copy[copy.length - 1]
              copy[copy.length - 1] = { ...last, content: last.content + ev.delta }
              return copy
            })
          } else if (ev.error) setError(ev.error)
        }
      }
      loadChats()
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') { loadChats(); return }
      setError(`Не удалось отправить вопрос: ${e instanceof Error ? e.message : e}`)
    } finally { abortRef.current = null; setBusy(false); setStatus('') }
  }, [activeId, busy, loadChats])

  return { chats, activeId, messages, busy, error, limitHit, status, newChat, open, remove, rename, stop, send }
}
