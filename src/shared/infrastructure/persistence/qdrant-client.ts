import { QdrantClient } from '@qdrant/js-client-rest'
import { getConfig } from '../config/app-config'

let qdrant: QdrantClient | null = null

export function getQdrant(): QdrantClient {
  if (qdrant) return qdrant
  const config = getConfig()
  qdrant = new QdrantClient({ url: config.QDRANT_URL })
  return qdrant
}

export async function ensureCollection(name: string, vectorSize = 1536): Promise<void> {
  const client = getQdrant()
  const collections = await client.getCollections()
  const exists = collections.collections.some(c => c.name === name)
  if (!exists) {
    await client.createCollection(name, {
      vectors: { size: vectorSize, distance: 'Cosine' },
    })
  }
}
