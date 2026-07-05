const MAX_REQUESTS = 200
const WINDOW_MS = 60000

interface RateWindow { count: number; resetAt: number }
const windows = new Map<string, RateWindow>()

setInterval(() => { const now = Date.now(); for (const [k, w] of windows) { if (now > w.resetAt) windows.delete(k) } }, 60000).unref()

export function checkRateLimit(ip: string, url: string): { allowed: boolean; retryAfter?: number } {
  const key = `${ip}:${url}`
  const now = Date.now()
  const w = windows.get(key)
  if (!w || now > w.resetAt) { windows.set(key, { count: 1, resetAt: now + WINDOW_MS }); return { allowed: true } }
  w.count++
  if (w.count > MAX_REQUESTS) return { allowed: false, retryAfter: Math.ceil((w.resetAt - now) / 1000) }
  return { allowed: true }
}

export function getRateLimitStats(): Array<{ key: string; count: number; resetAt: number }> {
  return [...windows.entries()].map(([k, w]) => ({ key: k, count: w.count, resetAt: w.resetAt }))
}
