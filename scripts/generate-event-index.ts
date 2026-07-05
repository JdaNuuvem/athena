/**
 * Gera um indice de eventos markdown para documentacao.
 * Uso: npx ts-node scripts/generate-event-index.ts
 */
import * as fs from 'fs'
import * as path from 'path'

const EVENTS_DIR = path.resolve(__dirname, '..', 'config', 'events')
const OUTPUT = path.resolve(__dirname, '..', 'docs', 'events', 'event-index.md')

interface EventSchema { '$id': string; title: string; properties?: { payload?: { required?: string[] } } }

function generate(): string {
  const lines: string[] = ['# ATHENA Event Index', '', `Generated: ${new Date().toISOString()}`, '', '| # | Event Type | Context | Payload Required Fields |', '|---|---|---|---|']

  const entries = fs.readdirSync(EVENTS_DIR, { withFileTypes: true })
  let idx = 0

  for (const entry of entries) {
    if (!entry.isDirectory()) continue
    const contextDir = path.join(EVENTS_DIR, entry.name)
    const files = fs.readdirSync(contextDir).filter(f => f.endsWith('.schema.json'))

    for (const file of files) {
      idx++
      const raw = JSON.parse(fs.readFileSync(path.join(contextDir, file), 'utf-8')) as EventSchema
      const eventType = raw['$id']?.split('/').pop() ?? file.replace('.schema.json', '')
      const requiredFields = raw.properties?.payload?.required?.join(', ') ?? ''
      lines.push(`| ${idx} | \`${eventType}\` | ${entry.name} | ${requiredFields} |`)
    }
  }

  return lines.join('\n') + '\n'
}

const outputDir = path.dirname(OUTPUT)
if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true })
fs.writeFileSync(OUTPUT, generate())
console.log(`Event index written to ${OUTPUT}`)
