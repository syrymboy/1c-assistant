import { useCallback, useEffect, useState } from 'react'
import { api } from './auth'

export interface Plan { code: string; name: string; price: number; currency: string; questions: number; features: string[] }
export interface PaymentItem {
  id: string; plan: string; kind: string; amount: number; currency: string; status: string
  card_brand: string | null; card_last4: string | null; failure_reason: string | null; created_at: string
}
export interface Billing {
  plan: Plan; period_end: string; used: number; limit: number; paid: boolean
  cancel_at_period_end: boolean; card: { brand: string | null; last4: string } | null
  plans: Plan[]; payments: PaymentItem[]
}

export const money = (minor: number, cur = 'KZT') =>
  minor === 0 ? 'Бесплатно' : new Intl.NumberFormat('ru-RU', { style: 'currency', currency: cur, maximumFractionDigits: 0 }).format(minor / 100)

export function useBilling(enabled: boolean) {
  const [billing, setBilling] = useState<Billing | null>(null)
  const refresh = useCallback(
    () => api.get<Billing>('/api/billing').then((r) => setBilling(r.data)).catch(() => {}),
    [],
  )
  useEffect(() => { if (enabled) refresh() }, [enabled, refresh])
  return { billing, refresh }
}
