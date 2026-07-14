import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import type { IRoleRepository } from '../../domain/repositories/role-repository'
import type { Role, RoleWithPermissions } from '../../domain/entities'

type PrismaRole = Awaited<ReturnType<ReturnType<typeof getPrisma>['role']['findUnique']>>

export class PrismaRoleRepository implements IRoleRepository {
  async findById(id: string): Promise<Role | null> {
    const r = await getPrisma().role.findUnique({
      where: { id },
      include: { permissions: { include: { permission: true } }, users: true },
    })
    if (!r) return null
    return {
      id: r.id, name: r.name, description: r.description, active: r.active,
      isSystem: r.isSystem, createdAt: r.createdAt, updatedAt: r.updatedAt,
      permissions: this.extractPermissions(r),
      users: (r.users as Array<{ userId: string; roleId: string }>) ?? [],
    }
  }

  async findByName(name: string): Promise<Role | null> {
    const r = await getPrisma().role.findUnique({
      where: { name },
      include: { permissions: { include: { permission: true } }, users: true },
    })
    if (!r) return null
    return {
      id: r.id, name: r.name, description: r.description, active: r.active,
      isSystem: r.isSystem, createdAt: r.createdAt, updatedAt: r.updatedAt,
      permissions: this.extractPermissions(r),
      users: (r.users as Array<{ userId: string; roleId: string }>) ?? [],
    }
  }

  async findAll(includePermissions = false): Promise<RoleWithPermissions[]> {
    const roles = await getPrisma().role.findMany({
      include: includePermissions ? { permissions: { include: { permission: true } } } : undefined,
      orderBy: { name: 'asc' },
    })
    return roles.map(r => {
      const perms = this.extractPermissions(r)
      return {
        id: r.id, name: r.name, description: r.description, active: r.active,
        isSystem: r.isSystem, createdAt: r.createdAt, updatedAt: r.updatedAt,
        permissions: perms,
        permissionCodes: perms.map(p => p.code),
        users: [],
      }
    })
  }

  async save(role: Omit<Role, 'permissions' | 'users'>): Promise<Role> {
    const created = await getPrisma().role.create({ data: role })
    return { ...created, permissions: [], users: [] }
  }

  async update(id: string, data: Partial<Pick<Role, 'name' | 'description' | 'active'>>): Promise<Role> {
    const updated = await getPrisma().role.update({ where: { id }, data })
    return { ...updated, permissions: [], users: [] }
  }

  async delete(id: string): Promise<void> {
    await getPrisma().role.delete({ where: { id } })
  }

  async addPermissions(roleId: string, permissionIds: string[]): Promise<void> {
    await getPrisma().rolePermission.createMany({
      data: permissionIds.map(pid => ({ roleId, permissionId: pid })),
      skipDuplicates: true,
    })
  }

  async removePermissions(roleId: string, permissionIds: string[]): Promise<void> {
    await getPrisma().rolePermission.deleteMany({
      where: { roleId, permissionId: { in: permissionIds } },
    })
  }

  async setPermissions(roleId: string, permissionIds: string[]): Promise<void> {
    const p = getPrisma()
    await p.rolePermission.deleteMany({ where: { roleId } })
    if (permissionIds.length > 0) {
      await p.rolePermission.createMany({
        data: permissionIds.map(pid => ({ roleId, permissionId: pid })),
      })
    }
  }

  async getPermissionCodes(roleId: string): Promise<string[]> {
    const rows = await getPrisma().rolePermission.findMany({
      where: { roleId },
      include: { permission: { select: { code: true } } },
    })
    return rows.map(r => r.permission.code)
  }

  private extractPermissions(r: Record<string, unknown>) {
    const rps = r['permissions'] as Array<Record<string, unknown>> | undefined
    if (!rps) return []
    return rps.map(rp => {
      const perm = rp['permission'] as Record<string, unknown>
      return {
        id: perm['id'] as string,
        code: perm['code'] as string,
        module: perm['module'] as string,
        action: perm['action'] as string,
        description: perm['description'] as string | null,
        createdAt: perm['createdAt'] as Date,
      }
    })
  }
}
