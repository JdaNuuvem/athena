/**
 * Gera especificacao AsyncAPI 3.0 a partir dos schemas JSON de eventos.
 * Uso: npx ts-node scripts/generate-asyncapi.ts > athena/docs/api/asyncapi.json
 */
import * as fs from 'fs'
import * as path from 'path'

const EVENTS_DIR = path.resolve(__dirname, '..', 'config', 'events')
const OUTPUT_DIR = path.resolve(__dirname, '..', 'docs', 'api')

interface AsyncAPI30 {
  asyncapi: string
  id: string
  info: { title: string; version: string; description: string }
  defaultContentType: string
  servers: Record<string, { protocol: string; url: string; description: string }>
  channels: Record<string, {
    address: string
    messages: Record<string, { $ref: string }>
    description: string
  }>
  components: {
    messages: Record<string, {
      name: string
      title: string
      summary: string
      contentType: string
      payload: { $ref: string }
    }>
    schemas: Record<string, unknown>
  }
}

function extractEventType(raw: Record<string, unknown>): string {
  const $id = raw['$id'] as string ?? ''
  const match = $id.match(/athena:\/\/events\/(.+)/)
  if (match) return match[1]!.replace(/\//g, '.').replace(/\.v1\./, '.v1.')
  const props = raw['properties'] as Record<string, unknown> | undefined
  const et = props?.['eventType'] as Record<string, unknown> | undefined
  return (et?.['const'] as string) ?? 'unknown'
}

function collectSchemas(dir: string): Array<{ filePath: string; content: unknown }> {
  const result: Array<{ filePath: string; content: unknown }> = []
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  for (const entry of entries) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      result.push(...collectSchemas(full))
    } else if (entry.name.endsWith('.schema.json')) {
      result.push({ filePath: full, content: JSON.parse(fs.readFileSync(full, 'utf-8')) })
    }
  }
  return result
}

function buildSpec(): AsyncAPI30 {
  const schemas = collectSchemas(EVENTS_DIR)

  const channels: AsyncAPI30['channels'] = {}
  const messages: AsyncAPI30['components']['messages'] = {}
  const asyncapiSchemas: AsyncAPI30['components']['schemas'] = {}

  for (const s of schemas) {
    const raw = s.content as Record<string, unknown>
    const eventType = extractEventType(raw)
    const [context, , namePart] = eventType.split('.')

    const address = `athena.${context}.events`
    const messageKey = `${context}.${namePart}`

    channels[address] = channels[address] ?? {
      address,
      description: `${context} context events`,
      messages: {},
    }
    channels[address]!.messages[messageKey] = { $ref: `#/components/messages/${messageKey}` }

    messages[messageKey] = {
      name: messageKey,
      title: raw['title'] as string ?? messageKey,
      summary: `${context} — ${namePart}`,
      contentType: 'application/json',
      payload: { $ref: `#/components/schemas/${messageKey}` },
    }

    asyncapiSchemas[messageKey] = raw
  }

  return {
    asyncapi: '3.0.0',
    id: 'urn:athena:event-catalog',
    info: {
      title: 'ATHENA Event Catalog — AsyncAPI 3.0',
      version: '0.1.0',
      description: 'Catalog of domain events flowing between ATHENA bounded contexts (Phase 1). Generated from config/events/.',
    },
    defaultContentType: 'application/json',
    servers: {
      kafka: {
        protocol: 'kafka',
        url: 'kafka.athena.local:9092',
        description: 'Kafka broker — development environment',
      },
    },
    channels,
    components: {
      messages,
      schemas: asyncapiSchemas,
    },
  }
}

const spec = buildSpec()
if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true })
fs.writeFileSync(path.join(OUTPUT_DIR, 'asyncapi.json'), JSON.stringify(spec, null, 2))
console.log(`AsyncAPI 3.0 generated at ${path.join(OUTPUT_DIR, 'asyncapi.json')} (${Object.keys(spec.channels).length} channels, ${Object.keys(spec.components.messages).length} messages)`)
