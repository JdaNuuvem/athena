import { ApolloClient, InMemoryCache, split } from '@apollo/client'
import { HttpLink } from '@apollo/client/link/http'
import { GraphQLWsLink } from '@apollo/client/link/subscriptions'
import { getMainDefinition } from '@apollo/client/utilities'
import { createClient } from 'graphql-ws'

const httpUri = '/graphql'
const wsUri = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/graphql`

const httpLink = new HttpLink({ uri: httpUri })

const wsLink = new GraphQLWsLink(
  createClient({
    url: wsUri,
    retryAttempts: Infinity,
    shouldRetry: () => true,
  }),
)

const splitLink = split(
  ({ query }) => {
    const definition = getMainDefinition(query)
    return definition.kind === 'OperationDefinition' && definition.operation === 'subscription'
  },
  wsLink,
  httpLink,
)

export const client = new ApolloClient({
  link: splitLink,
  cache: new InMemoryCache(),
})
