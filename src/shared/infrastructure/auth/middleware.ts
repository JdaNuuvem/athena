import type { FastifyRequest, FastifyReply } from 'fastify'
import { verifyToken, extractToken } from './jwt'

export type AuthRole = 'admin' | 'operator' | 'viewer'

declare module 'fastify' {
  interface FastifyRequest { user?: { sub: string; role: string; iat: number; exp: number } }
}

export function authMiddleware(requiredRole: AuthRole | null) {
  return async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    const publicPaths = ['/api/health', '/api/auth/login']
    if (publicPaths.includes(req.url)) return

    const t = extractToken(req.headers.authorization ?? '')
    if (!t) { reply.status(401).send({ error: 'Missing auth token' }); return }

    const payload = verifyToken(t)
    if (!payload) { reply.status(401).send({ error: 'Invalid or expired token' }); return }

    req.user = { sub: payload.sub, role: payload.role, iat: payload.iat ?? 0, exp: payload.exp ?? 0 }

    if (requiredRole) {
      const roleHierarchy: Record<string, number> = { viewer: 1, operator: 2, admin: 3 }
      if ((roleHierarchy[payload.role] ?? 0) < (roleHierarchy[requiredRole] ?? 9)) {
        reply.status(403).send({ error: `Requires ${requiredRole} role` }); return
      }
    }
  }
}
