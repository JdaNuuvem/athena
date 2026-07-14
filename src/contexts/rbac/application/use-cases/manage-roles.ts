import type { IRoleRepository } from '../../domain/repositories/role-repository'
import type { Role, RoleWithPermissions } from '../../domain/entities'

export class ManageRolesUseCase {
  constructor(private readonly roleRepo: IRoleRepository) {}

  async list(): Promise<RoleWithPermissions[]> {
    return this.roleRepo.findAll(true)
  }

  async getById(id: string): Promise<Role | null> {
    return this.roleRepo.findById(id)
  }

  async create(data: { name: string; description?: string }): Promise<Role> {
    const existing = await this.roleRepo.findByName(data.name)
    if (existing) throw new Error(`Role "${data.name}" already exists`)
    return this.roleRepo.save({
      id: '', name: data.name, description: data.description ?? null,
      active: true, isSystem: false, createdAt: new Date(), updatedAt: new Date(),
    })
  }

  async update(id: string, data: { name?: string; description?: string; active?: boolean }): Promise<Role> {
    const role = await this.roleRepo.findById(id)
    if (!role) throw new Error('Role not found')
    if (role.isSystem) throw new Error('Cannot edit system roles')
    return this.roleRepo.update(id, data)
  }

  async delete(id: string): Promise<void> {
    const role = await this.roleRepo.findById(id)
    if (!role) throw new Error('Role not found')
    if (role.isSystem) throw new Error('Cannot delete system roles')
    await this.roleRepo.delete(id)
  }

  async setPermissions(roleId: string, permissionIds: string[]): Promise<void> {
    await this.roleRepo.setPermissions(roleId, permissionIds)
  }

  async getPermissionCodes(roleId: string): Promise<string[]> {
    return this.roleRepo.getPermissionCodes(roleId)
  }
}
