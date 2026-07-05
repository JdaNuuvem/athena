import type { FastifyInstance } from 'fastify'
import mercurius from 'mercurius'
import { typeDefs } from './schema'
import { resolvers } from './resolvers'
import { athenaPubSub } from './pubsub'

export async function registerGraphQL(server: FastifyInstance, registry: unknown, orchestrator: unknown): Promise<void> {
  await server.register(mercurius, {
    schema: typeDefs,
    resolvers,
    graphiql: true,
    subscription: true,
    context: () => ({ registry, orchestrator, pubsub: athenaPubSub }),
  })
}

export { athenaPubSub }
