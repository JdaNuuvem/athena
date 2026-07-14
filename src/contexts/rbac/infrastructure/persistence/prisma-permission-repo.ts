import { getPrisma } from '../../../../shared/infrastructure/persistence/prisma-client'
import type { IPermissionRepository } from '../../domain/repositories/permission-repository'
import type { Permission } from '../../domain/entities'

export class PrismaPermissionRepository implements IPermissionRepository {
  async findById(id: string): Promise<Permission | null> {
    return getPrisma().permission.findUnique({ where: { id } })
  }

  async findByCode(code: string): Promise<Permission | null> {
    return getPrisma().permission.findUnique({ where: { code } })
  }

  async findAll(): Promise<Permission[]> {
    return getPrisma().permission.findMany({ orderBy: [{ module: 'asc' }, { action: 'asc' }] })
  }

  async findByModule(module: string): Promise<Permission[]> {
    return getPrisma().permission.findMany({ where: { module }, orderBy: { action: 'asc' } })
  }

  async save(permission: Omit<Permission, 'id' | 'createdAt'>): Promise<Permission> {
    return getPrisma().permission.create({ data: permission })
  }

  async delete(id: string): Promise<void> {
    await getPrisma().permission.delete({ where: { id } })
  }
}
