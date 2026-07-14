import type { Permission } from '../entities'

export interface IPermissionRepository {
  findById(id: string): Promise<Permission | null>
  findByCode(code: string): Promise<Permission | null>
  findAll(): Promise<Permission[]>
  findByModule(module: string): Promise<Permission[]>
  save(permission: Omit<Permission, 'id' | 'createdAt'>): Promise<Permission>
  delete(id: string): Promise<void>
}
