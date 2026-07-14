import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'

export class AuthorizationService {
  async getUserPermissions(userId: string): Promise<string[]> {
    const userRoles = await getPrisma().userRole.findMany({
      where: { userId },
      include: {
        role: {
          include: {
            permissions: {
              include: { permission: { select: { code: true } } },
            },
          },
        },
      },
    })

    const codes = new Set<string>()
    for (const ur of userRoles) {
      if (!ur.role?.active) continue
      for (const rp of ur.role?.permissions ?? []) {
        codes.add(rp.permission.code)
      }
    }
    return [...codes]
  }

  async getUserRoles(userId: string): Promise<string[]> {
    const userRoles = await getPrisma().userRole.findMany({
      where: { userId },
      include: { role: { select: { name: true, active: true } } },
    })
    return userRoles.filter(ur => ur.role.active).map(ur => ur.role.name)
  }

  async hasPermission(userId: string, permissionCode: string): Promise<boolean> {
    const count = await getPrisma().userRole.count({
      where: {
        userId,
        role: {
          active: true,
          permissions: {
            some: { permission: { code: permissionCode } },
          },
        },
      },
    })
    return count > 0
  }

  async hasAnyPermission(userId: string, permissionCodes: string[]): Promise<boolean> {
    const count = await getPrisma().userRole.count({
      where: {
        userId,
        role: {
          active: true,
          permissions: {
            some: { permission: { code: { in: permissionCodes } } },
          },
        },
      },
    })
    return count > 0
  }

  async assignRole(userId: string, roleId: string): Promise<void> {
    await getPrisma().userRole.create({ data: { userId, roleId } })
  }

  async revokeRole(userId: string, roleId: string): Promise<void> {
    await getPrisma().userRole.deleteMany({ where: { userId, roleId } })
  }

  async setUserRoles(userId: string, roleIds: string[]): Promise<void> {
    const p = getPrisma()
    await p.userRole.deleteMany({ where: { userId } })
    if (roleIds.length > 0) {
      await p.userRole.createMany({
        data: roleIds.map(rid => ({ userId, roleId: rid })),
      })
    }
  }
}
