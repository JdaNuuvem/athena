import crypto from 'node:crypto'
import { getConfig } from '../config/app-config'

export interface TokenPayload {
  sub: string
  email: string
  role: string
  iat?: number
  exp?: number
}

export interface TokenPair {
  accessToken: string
  refreshToken: string
  expiresIn: number
}

export type AuthRole = 'admin' | 'operator' | 'viewer'
export type Role = AuthRole
export const ROLES: readonly AuthRole[] = ['admin', 'operator', 'viewer']

export interface AuthenticatedUser {
  id: string
  email: string
  name: string
  role: AuthRole
}

function base64url(str: string): string { return Buffer.from(str).toString('base64url') }

function sign(payload: TokenPayload, secret: string, expiresIn: string): string {
  const header = base64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const now = Math.floor(Date.now() / 1000)
  const seconds = parseDuration(expiresIn)
  const body = base64url(JSON.stringify({ ...payload, iat: now, exp: now + seconds }))
  const signature = crypto.createHmac('sha256', secret).update(`${header}.${body}`).digest('base64url')
  return `${header}.${body}.${signature}`
}

export function verifyToken(token: string): TokenPayload | null {
  try {
    const config = getConfig()
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const [header, body, signature] = parts
    const expected = crypto.createHmac('sha256', config.JWT_SECRET).update(`${header}.${body}`).digest('base64url')
    if (signature !== expected) return null
    const payload = JSON.parse(Buffer.from(body!, 'base64url').toString('utf8')) as TokenPayload
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) return null
    return payload
  } catch { return null }
}

export const verifyAccessToken = verifyToken
export const verifyRefreshToken = verifyToken

export function extractToken(header: string): string | null {
  if (!header || !header.startsWith('Bearer ')) return null
  return header.slice(7)
}

function parseDuration(str: string): number {
  const match = str.match(/^(\d+)(s|m|h|d)$/)
  if (!match) return 86400
  const value = Number(match[1])
  switch (match[2]) {
    case 's': return value
    case 'm': return value * 60
    case 'h': return value * 3600
    case 'd': return value * 86400
    default: return 86400
  }
}

export function generateTokens(payload: Omit<TokenPayload, 'iat' | 'exp'>): TokenPair {
  const config = getConfig()
  const accessToken = sign(payload as TokenPayload, config.JWT_SECRET, config.JWT_EXPIRES_IN)
  const refreshToken = sign(payload as TokenPayload, config.JWT_SECRET, config.JWT_REFRESH_EXPIRES_IN)
  return { accessToken, refreshToken, expiresIn: parseDuration(config.JWT_EXPIRES_IN) }
}

export function createToken(sub: string, role: string): { token: string; expiresAt: Date } {
  const config = getConfig()
  const seconds = parseDuration(config.JWT_EXPIRES_IN)
  const token = sign({ sub, email: '', role, iat: 0, exp: 0 }, config.JWT_SECRET, config.JWT_EXPIRES_IN)
  return { token, expiresAt: new Date(Date.now() + seconds * 1000) }
}

export function authenticateUser(username: string, password: string): { sub: string; role: AuthRole; name: string } | null {
  if (username === 'admin' && password === 'admin') return { sub: 'user-admin', role: 'admin', name: 'Administrator' }
  if (username === 'operator' && password === 'operator') return { sub: 'user-op', role: 'operator', name: 'Operator' }
  return null
}

export function hashPassword(password: string): string {
  const salt = crypto.randomBytes(16).toString('hex')
  const hash = crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512').toString('hex')
  return `${salt}:${hash}`
}

export function verifyPassword(password: string, storedHash: string): boolean {
  const [salt, hash] = storedHash.split(':')
  if (!salt || !hash) return false
  const computed = crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512').toString('hex')
  return crypto.timingSafeEqual(Buffer.from(hash), Buffer.from(computed))
}
