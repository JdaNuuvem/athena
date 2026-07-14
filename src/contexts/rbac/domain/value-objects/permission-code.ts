const PERMISSION_PATTERN = /^[a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*:[a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*$/

export class PermissionCode {
  readonly module: string
  readonly action: string

  constructor(public readonly code: string) {
    if (!PERMISSION_PATTERN.test(code)) {
      throw new Error(`Invalid permission code: "${code}". Expected format: "module:action"`)
    }
    const [mod, act] = code.split(':') as [string, string]
    this.module = mod
    this.action = act
  }

  toString(): string { return this.code }

  static isValid(code: string): boolean {
    return PERMISSION_PATTERN.test(code)
  }

  static try(code: string): PermissionCode | null {
    try { return new PermissionCode(code) } catch { return null }
  }
}
