import { useCallback, useEffect, useState } from 'react'
import { api } from './auth'

export interface Source {
  id: number; section: string; kind: string; title: string
  description: string; fields: string[]; enabled: boolean
}

export function useSources(enabled: boolean) {
  const [sources, setSources] = useState<Source[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!enabled) return
    api.get<Source[]>('/api/sources')
      .then((r) => setSources(r.data))
      .catch((e) => setError(`Не удалось загрузить источники: ${e instanceof Error ? e.message : e}`))
      .finally(() => setLoaded(true))
  }, [enabled])

  const setMany = useCallback(async (ids: number[], on: boolean) => {
    const prev = sources
    setSources((s) => s.map((x) => (ids.includes(x.id) ? { ...x, enabled: on } : x)))
    try {
      await Promise.all(ids.map((id) => api.put(`/api/sources/${id}`, { enabled: on })))
      setError('')
    } catch {
      setSources(prev)
      setError('Не удалось сохранить выбор, попробуйте ещё раз')
    }
  }, [sources])

  return { sources, loaded, error, setMany }
}
