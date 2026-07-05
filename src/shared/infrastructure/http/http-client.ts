export interface HttpClientConfig {
  baseURL: string
  timeout: number
  retries: number
  retryDelay: number
  headers?: Record<string, string>
}

export interface HttpResponse<T = unknown> {
  status: number
  data: T
  headers: Record<string, string>
}

export interface CircuitBreakerState {
  failures: number
  lastFailure: number
  state: 'closed' | 'open' | 'half-open'
}

export class HttpClient {
  private breaker: Map<string, CircuitBreakerState> = new Map()
  private readonly breakerThreshold = 5
  private readonly breakerResetMs = 30000

  constructor(private config: HttpClientConfig) {}

  async get<T = unknown>(path: string, headers?: Record<string, string>): Promise<HttpResponse<T>> {
    return this.request<T>('GET', path, undefined, headers)
  }

  async post<T = unknown>(path: string, body?: unknown, headers?: Record<string, string>): Promise<HttpResponse<T>> {
    return this.request<T>('POST', path, body, headers)
  }

  async put<T = unknown>(path: string, body?: unknown, headers?: Record<string, string>): Promise<HttpResponse<T>> {
    return this.request<T>('PUT', path, body, headers)
  }

  async delete<T = unknown>(path: string, headers?: Record<string, string>): Promise<HttpResponse<T>> {
    return this.request<T>('DELETE', path, undefined, headers)
  }

  private async request<T>(method: string, path: string, body?: unknown, extraHeaders?: Record<string, string>): Promise<HttpResponse<T>> {
    const key = `${method}:${this.config.baseURL}${path}`
    this.checkBreaker(key)

    const url = `${this.config.baseURL}${path}`
    const mergedHeaders = { ...this.config.headers, ...extraHeaders, 'Content-Type': 'application/json' }

    let lastError: Error | null = null
    for (let attempt = 0; attempt <= this.config.retries; attempt++) {
      try {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), this.config.timeout)

        const response = await fetch(url, {
          method,
          headers: mergedHeaders,
          body: body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        })

        clearTimeout(timer)
        const responseData = await response.json().catch(() => null) as T
        const responseHeaders: Record<string, string> = {}
        response.headers.forEach((v, k) => { responseHeaders[k] = v })

        if (!response.ok) {
          const err = new Error(`HTTP ${response.status}: ${response.statusText}`)
          ;(err as unknown as Record<string, unknown>)['status'] = response.status
          ;(err as unknown as Record<string, unknown>)['data'] = responseData
          throw err
        }

        this.recordSuccess(key)
        return { status: response.status, data: responseData, headers: responseHeaders }
      } catch (err) {
        lastError = err as Error
        if (attempt < this.config.retries) {
          await new Promise(r => setTimeout(r, this.config.retryDelay * (attempt + 1)))
        }
      }
    }

    this.recordFailure(key)
    throw lastError ?? new Error('HTTP request failed')
  }

  private checkBreaker(key: string): void {
    const state = this.breaker.get(key)
    if (!state) return
    if (state.state === 'open') {
      if (Date.now() - state.lastFailure > this.breakerResetMs) {
        state.state = 'half-open'
      } else {
        throw new Error(`Circuit breaker open for ${key}`)
      }
    }
  }

  private recordSuccess(key: string): void {
    this.breaker.delete(key)
  }

  private recordFailure(key: string): void {
    const state = this.breaker.get(key) ?? { failures: 0, lastFailure: 0, state: 'closed' as const }
    state.failures++
    state.lastFailure = Date.now()
    if (state.failures >= this.breakerThreshold) {
      state.state = 'open'
    }
    this.breaker.set(key, state)
  }

  getBreakerStates(): ReadonlyMap<string, CircuitBreakerState> {
    return this.breaker
  }
}

export const httpClient = new HttpClient({
  baseURL: '',
  timeout: 30000,
  retries: 3,
  retryDelay: 1000,
})
