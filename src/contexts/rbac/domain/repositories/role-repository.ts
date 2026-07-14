import type { Role, RoleWithPermissions } from '../entities'

export interface IRoleRepository {
  findById(id: string): Promise<Role | null>
  findByName(name: string): Promise<Role | null>
  findAll(includePermissions?: boolean): Promise<RoleWithPermissions[]>
  save(role: Omit<Role, 'permissions' | 'users'>): Promise<Role>
  update(id: string, data: Partial<Pick<Role, 'name' | 'description' | 'active'>>): Promise<Role>
  delete(id: string): Promise<void>
  addPermissions(roleId: string, permissionIds: string[]): Promise<void>
  removePermissions(roleId: string, permissionIds: string[]): Promise<void>
  setPermissions(roleId: string, permissionIds: string[]): Promise<void>
  getPermissionCodes(roleId: string): Promise<string[]>
}
