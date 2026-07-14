import crypto from 'node:crypto'

export function hashPassword(password: string): string {
  const salt = crypto.randomBytes(16).toString('hex')
  const hash = crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512').toString('hex')
  return `${salt}:${hash}`
}

export function verifyPassword(password: string, stored: string): boolean {
  const [salt, hash] = stored.split(':')
  if (!salt || !hash) return false
  const computed = Buffer.from(crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512').toString('hex'))
  const expected = Buffer.from(hash)
  return computed.length === expected.length && crypto.timingSafeEqual(computed, expected)
}

import { getPrisma } from '../persistence/prisma-client'

export async function authenticateUser(
  email: string,
  password: string,
): Promise<{ sub: string; role: string; name: string; permissions: string[] } | null> {
  const user = await getPrisma().user.findUnique({
    where: { email },
    include: {
      userRoles: {
        include: {
          role: {
            include: {
              permissions: {
                include: { permission: { select: { code: true } } },
              },
            },
          },
        },
      },
    },
  }) as Record<string, unknown> | null

  if (!user || !user['active']) return null
  if (!verifyPassword(password, user['passwordHash'] as string)) return null

  const codes = new Set<string>()
  const userRoles = (user['userRoles'] as Array<Record<string, unknown>>) ?? []
  for (const ur of userRoles) {
    const role = ur['role'] as Record<string, unknown>
    if (!role['active']) continue
    const perms = (role['permissions'] as Array<Record<string, unknown>>) ?? []
    for (const rp of perms) {
      const perm = rp['permission'] as Record<string, unknown>
      codes.add(perm['code'] as string)
    }
  }

  const firstRole = userRoles[0]
  const roleName = ((firstRole?.['role'] as Record<string, unknown>)?.['name'] as string) ?? 'viewer'

  return {
    sub: user['id'] as string,
    role: roleName,
    name: user['name'] as string,
    permissions: [...codes],
  }
}
