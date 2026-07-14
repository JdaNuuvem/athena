import { AuthorizationService } from '../../../contexts/rbac/application/services/authorization-service'

const authService = new AuthorizationService()

export class RbacGuard {
  static async can(userId: string, permissionCode: string): Promise<boolean> {
    return authService.hasPermission(userId, permissionCode)
  }

  static async canAny(userId: string, permissionCodes: string[]): Promise<boolean> {
    return authService.hasAnyPermission(userId, permissionCodes)
  }

  static async getPermissions(userId: string): Promise<string[]> {
    return authService.getUserPermissions(userId)
  }

  static async getRoles(userId: string): Promise<string[]> {
    return authService.getUserRoles(userId)
  }

  static async assignRole(userId: string, roleId: string): Promise<void> {
    return authService.assignRole(userId, roleId)
  }

  static async assignRoles(userId: string, roleIds: string[]): Promise<void> {
    return authService.setUserRoles(userId, roleIds)
  }

  static async revokeRole(userId: string, roleId: string): Promise<void> {
    return authService.revokeRole(userId, roleId)
  }
}
