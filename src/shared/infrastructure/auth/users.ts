import { scryptSync, randomBytes, timingSafeEqual } from 'crypto'

export function hashPassword(password: string): string {
  const salt = randomBytes(16).toString('hex')
  const hash = scryptSync(password, salt, 64).toString('hex')
  return `${salt}:${hash}`
}

export function verifyPassword(password: string, stored: string): boolean {
  const [salt, hash] = stored.split(':')
  if (!salt || !hash) return false
  const computed = Buffer.from(scryptSync(password, salt, 64).toString('hex'))
  const expected = Buffer.from(hash)
  return computed.length === expected.length && timingSafeEqual(computed, expected)
}

const USERS: Record<string, { passwordHash: string; role: string; name: string }> = {
  admin: { passwordHash: hashPassword('athena-admin-2026'), role: 'admin', name: 'Administrator' },
  operator: { passwordHash: hashPassword('athena-op-2026'), role: 'operator', name: 'Operator' },
  viewer: { passwordHash: hashPassword('athena-view-2026'), role: 'viewer', name: 'Viewer' },
}

export function authenticateUser(username: string, password: string): { sub: string; role: string; name: string } | null {
  const user = USERS[username]
  if (!user) return null
  if (!verifyPassword(password, user.passwordHash)) return null
  return { sub: username, role: user.role, name: user.name }
}
