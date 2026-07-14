import type { FastifyInstance } from 'fastify'
import { authenticateUser } from '../../shared/infrastructure/auth/users'
import { generateTokens } from '../../shared/infrastructure/auth/jwt'
import { authMiddleware, requirePermission } from '../../shared/infrastructure/auth'
import { PrismaRoleRepository } from '../../contexts/rbac/infrastructure/persistence/prisma-role-repo'
import { PrismaPermissionRepository } from '../../contexts/rbac/infrastructure/persistence/prisma-permission-repo'
import { ManageRolesUseCase } from '../../contexts/rbac/application/use-cases/manage-roles'
import { ManagePermissionsUseCase } from '../../contexts/rbac/application/use-cases/manage-permissions'
import { AuthorizationService } from '../../contexts/rbac/application/services/authorization-service'
import { RbacGuard } from '../../shared/infrastructure/auth/rbac-guard'

const roleRepo = new PrismaRoleRepository()
const permRepo = new PrismaPermissionRepository()
const manageRoles = new ManageRolesUseCase(roleRepo)
const managePerms = new ManagePermissionsUseCase(permRepo)
const authService = new AuthorizationService()

export function registerRbacRoutes(server: FastifyInstance): void {
  // ─── AUTH ────────────────────────────────────────────────────────

  server.post<{ Body: { email: string; password: string } }>('/api/auth/login', async (req, reply) => {
    const { email, password } = req.body
    if (!email || !password) {
      return reply.status(400).send({ error: 'Email and password required' })
    }

    const user = await authenticateUser(email, password)
    if (!user) {
      return reply.status(401).send({ error: 'Invalid credentials' })
    }

    const tokens = generateTokens({ sub: user.sub, email, role: user.role, permissions: user.permissions })

    return {
      token: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      expiresIn: tokens.expiresIn,
      user: { id: user.sub, name: user.name, role: user.role },
      permissions: user.permissions,
    }
  })

  server.get('/api/auth/me', { preHandler: [authMiddleware(null)] }, async (req) => {
    const userId = req.user!.sub
    const permissions = await RbacGuard.getPermissions(userId)
    const roles = await RbacGuard.getRoles(userId)
    return {
      id: userId,
      name: req.user!.email,
      role: req.user!.role,
      roles,
      permissions,
    }
  })

  // ─── ROLES ───────────────────────────────────────────────────────

  server.get('/api/roles', { preHandler: [authMiddleware(null), requirePermission('roles:view')] }, async () => {
    const roles = await manageRoles.list()
    return { roles: roles.map(r => ({ id: r.id, name: r.name, description: r.description, active: r.active, isSystem: r.isSystem, permissionCodes: r.permissionCodes, createdAt: r.createdAt })) }
  })

  server.get<{ Params: { id: string } }>('/api/roles/:id', { preHandler: [authMiddleware(null), requirePermission('roles:view')] }, async (req) => {
    const role = await manageRoles.getById(req.params.id)
    if (!role) return { error: 'Role not found', statusCode: 404 }
    const codes = await roleRepo.getPermissionCodes(role.id)
    return { id: role.id, name: role.name, description: role.description, active: role.active, isSystem: role.isSystem, permissionCodes: codes, createdAt: role.createdAt }
  })

  server.post<{ Body: { name: string; description?: string } }>('/api/roles', { preHandler: [authMiddleware(null), requirePermission('roles:create')] }, async (req, reply) => {
    try {
      const role = await manageRoles.create({ name: req.body.name, description: req.body.description })
      return { role }
    } catch (e) {
      return reply.status(409).send({ error: (e as Error).message })
    }
  })

  server.put<{ Params: { id: string }; Body: { name?: string; description?: string; active?: boolean } }>('/api/roles/:id', { preHandler: [authMiddleware(null), requirePermission('roles:edit')] }, async (req, reply) => {
    try {
      const role = await manageRoles.update(req.params.id, req.body)
      return { role }
    } catch (e) {
      return reply.status(400).send({ error: (e as Error).message })
    }
  })

  server.delete<{ Params: { id: string } }>('/api/roles/:id', { preHandler: [authMiddleware(null), requirePermission('roles:delete')] }, async (req, reply) => {
    try {
      await manageRoles.delete(req.params.id)
      return { status: 'deleted' }
    } catch (e) {
      return reply.status(400).send({ error: (e as Error).message })
    }
  })

  server.put<{ Params: { id: string }; Body: { permissionIds: string[] } }>('/api/roles/:id/permissions', { preHandler: [authMiddleware(null), requirePermission('roles:manage')] }, async (req) => {
    await roleRepo.setPermissions(req.params.id, req.body.permissionIds)
    const codes = await roleRepo.getPermissionCodes(req.params.id)
    return { roleId: req.params.id, permissionCodes: codes }
  })

  // ─── PERMISSIONS ─────────────────────────────────────────────────

  server.get('/api/permissions', { preHandler: [authMiddleware(null), requirePermission('roles:view')] }, async () => {
    const permissions = await managePerms.list()
    return { permissions }
  })

  server.get('/api/permissions/modules', { preHandler: [authMiddleware(null)] }, async () => {
    const modules = await managePerms.getModules()
    return { modules }
  })

  server.post<{ Body: { code: string; description?: string } }>('/api/permissions', { preHandler: [authMiddleware(null), requirePermission('roles:create')] }, async (req, reply) => {
    try {
      const perm = await managePerms.create({ code: req.body.code, description: req.body.description })
      return { permission: perm }
    } catch (e) {
      return reply.status(409).send({ error: (e as Error).message })
    }
  })

  server.delete<{ Params: { id: string } }>('/api/permissions/:id', { preHandler: [authMiddleware(null), requirePermission('roles:delete')] }, async () => {
    // soft block: cannot delete permissions via API unless explicitly allowed
    return { error: 'Permission deletion is restricted. Use the database admin interface.' }
  })

  // ─── USER ROLES ──────────────────────────────────────────────────

  server.get<{ Params: { id: string } }>('/api/users/:id/roles', { preHandler: [authMiddleware(null), requirePermission('users:view')] }, async (req) => {
    const roles = await authService.getUserRoles(req.params.id)
    const permissions = await authService.getUserPermissions(req.params.id)
    return { userId: req.params.id, roles, permissions }
  })

  server.put<{ Params: { id: string }; Body: { roleIds: string[] } }>('/api/users/:id/roles', { preHandler: [authMiddleware(null), requirePermission('users:manage')] }, async (req) => {
    await authService.setUserRoles(req.params.id, req.body.roleIds)
    const roles = await authService.getUserRoles(req.params.id)
    return { userId: req.params.id, roles }
  })
}
