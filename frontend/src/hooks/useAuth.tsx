import { useState, createContext, useContext, useCallback, useEffect, type ReactNode } from 'react'

interface AuthState { token: string | null; role: string | null; name: string | null }
interface AuthCtx extends AuthState { login: (u: string, p: string) => Promise<boolean>; logout: () => void }
const AuthContext = createContext<AuthCtx>({ token: null, role: null, name: null, login: async () => false, logout: () => {} })

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => { const t = localStorage.getItem('athena_token'); const r = localStorage.getItem('athena_role'); const n = localStorage.getItem('athena_name'); return { token: t, role: r, name: n } })
  const login = useCallback(async (username: string, password: string) => {
    try { const r = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) }); const d = await r.json() as Record<string, string>; if (d['token']) { const s = { token: d['token'], role: d['role'] || '', name: d['name'] || '' }; setState(s); localStorage.setItem('athena_token', s.token!); localStorage.setItem('athena_role', s.role!); localStorage.setItem('athena_name', s.name!); return true } return false } catch { return false }
  }, [])
  const logout = useCallback(() => { setState({ token: null, role: null, name: null }); localStorage.clear() }, [])
  return <AuthContext.Provider value={{ ...state, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() { return useContext(AuthContext) }

export function useApi() {
  const { token } = useAuth()
  return useCallback(async <T = unknown,>(path: string, options?: RequestInit): Promise<T | null> => {
    try { const r = await fetch(path, { ...options, headers: { ...options?.headers, 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) } }); if (r.status === 401) { localStorage.clear(); window.location.href = '/login' } return r.json() as T } catch { return null }
  }, [token])
}

export function useWebSocket() {
  const [events, setEvents] = useState<Array<{ type: string; payload: Record<string, unknown>; timestamp: string }>>([])
  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws`)
    ws.onmessage = (e) => { const msg = JSON.parse(e.data); if (msg.type === 'history') setEvents(msg.payload.events as Array<{ type: string; payload: Record<string, unknown>; timestamp: string }> || []); else setEvents(prev => [msg, ...prev].slice(0, 200)) }
    ws.onclose = () => setTimeout(() => { /* reconnect handled by new effect */ }, 3000)
    return () => ws.close()
  }, [])
  return events
}
