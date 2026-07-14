import type { IPermissionRepository } from '../../domain/repositories/permission-repository'
import type { Permission } from '../../domain/entities'
import { PermissionCode } from '../../domain/value-objects/permission-code'

export class ManagePermissionsUseCase {
  constructor(private readonly permRepo: IPermissionRepository) {}

  async list(): Promise<Permission[]> {
    return this.permRepo.findAll()
  }

  async listByModule(module: string): Promise<Permission[]> {
    return this.permRepo.findByModule(module)
  }

  async getModules(): Promise<string[]> {
    const all = await this.permRepo.findAll()
    return [...new Set(all.map(p => p.module))].sort()
  }

  async create(data: { code: string; description?: string }): Promise<Permission> {
    if (!PermissionCode.isValid(data.code)) {
      throw new Error(`Invalid permission code: "${data.code}". Expected format: "module:action"`)
    }
    const existing = await this.permRepo.findByCode(data.code)
    if (existing) throw new Error(`Permission "${data.code}" already exists`)
    const pc = new PermissionCode(data.code)
    return this.permRepo.save({
      code: data.code, module: pc.module, action: pc.action,
      description: data.description ?? null,
    })
  }

  async delete(id: string): Promise<void> {
    await this.permRepo.delete(id)
  }
}
