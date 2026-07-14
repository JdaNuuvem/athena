import type { FastifyRequest, FastifyReply } from 'fastify'
import { AuthorizationService } from '../../../contexts/rbac/application/services/authorization-service'

const authService = new AuthorizationService()

export function requirePermission(...permissionCodes: string[]) {
  return async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    const userId = req.user?.sub
    if (!userId) {
      reply.status(401).send({ error: 'Authentication required' })
      return
    }

    if (permissionCodes.length === 0) return

    const hasAccess = await authService.hasAnyPermission(userId, permissionCodes)
    if (!hasAccess) {
      reply.status(403).send({ error: `Missing required permission: ${permissionCodes.join(' or ')}` })
    }
  }
}
