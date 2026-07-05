const API_KEYS = new Set([
  process.env['INTERNAL_API_KEY'] ?? 'athena-internal-dev-key',
])

export function apiKeyAuth() {
  return async (req: { headers: Record<string, string | undefined> }, reply: { status: (n: number) => { send: (b: unknown) => void } }) => {
    const key = req.headers['x-api-key']
    if (!key || !API_KEYS.has(key)) {
      return reply.status(401).send({ error: 'Invalid API key' })
    }
  }
}
