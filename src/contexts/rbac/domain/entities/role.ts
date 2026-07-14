export interface Role {
  id: string
  name: string
  description: string | null
  active: boolean
  isSystem: boolean
  createdAt: Date
  updatedAt: Date
  permissions: Permission[]
  users: UserRole[]
}

export interface UserRole {
  userId: string
  roleId: string
}

export interface Permission {
  id: string
  code: string
  module: string
  action: string
  description: string | null
  createdAt: Date
}

export interface RoleWithPermissions extends Role {
  permissionCodes: string[]
}
