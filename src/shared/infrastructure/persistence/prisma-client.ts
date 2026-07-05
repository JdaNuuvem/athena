import { PrismaClient } from '@prisma/client'

let prisma: PrismaClient | null = null

export function getPrisma(): PrismaClient {
  if (prisma) return prisma
  try {
    prisma = new PrismaClient()
    return prisma
  } catch {
    prisma = new Proxy({} as PrismaClient, {
      get: () => {
        return new Proxy(() => {}, {
          get: () => async () => { throw new Error('Prisma unavailable') },
          apply: () => async () => { throw new Error('Prisma unavailable') },
        })
      },
    })
    return prisma
  }
}

export async function disconnectPrisma(): Promise<void> {
  if (prisma) {
    await prisma.$disconnect()
    prisma = null
  }
}
