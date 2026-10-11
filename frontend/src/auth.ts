import Keycloak from 'keycloak-js'
import axios from 'axios'

export const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL,
  realm: import.meta.env.VITE_KEYCLOAK_REALM,
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
})

let initPromise: Promise<boolean> | null = null
export function initAuth(): Promise<boolean> {
  // keycloak-js нельзя инициализировать дважды (React StrictMode вызывает эффекты повторно)
  initPromise ??= keycloak.init({ onLoad: 'check-sso', pkceMethod: 'S256', checkLoginIframe: false })
  return initPromise
}

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL })
api.interceptors.request.use(async (config) => {
  await keycloak.updateToken(30).catch(() => keycloak.login())
  config.headers.Authorization = `Bearer ${keycloak.token}`
  return config
})

export const hasRole = (role: string) => keycloak.hasRealmRole(role)
