import { Pool } from 'pg'

const pool = new Pool({ connectionString: process.env['DATABASE_URL'] ?? 'postgresql://athena:athena@localhost:5433/athena', max: 5 })

async function query(text: string, params?: unknown[]) {
  const result = await pool.query(text, params)
  return result.rows
}

export interface SettingRow {
  key: string
  value: string
  group: string
  secure: boolean
  updatedAt: string
}

// ponytail: CREATE TABLE IF NOT EXISTS — idempotent, no migration tool needed
const INIT_SQL = `
  CREATE TABLE IF NOT EXISTS "Setting" (
    "key" TEXT PRIMARY KEY,
    "value" TEXT NOT NULL DEFAULT '',
    "group" TEXT NOT NULL DEFAULT 'general',
    "secure" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "updatedAt" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
  );
  CREATE INDEX IF NOT EXISTS "idx_setting_group" ON "Setting"("group");
`

const DEFAULT_SETTINGS: Array<{ key: string; value: string; group: string; secure: boolean }> = [
  { key: 'SHOPEE_PARTNER_ID', value: '', group: 'shopee', secure: false },
  { key: 'SHOPEE_PARTNER_KEY', value: '', group: 'shopee', secure: true },
  { key: 'SHOPEE_SHOP_ID', value: '', group: 'shopee', secure: false },
  { key: 'SHOPEE_ACCESS_TOKEN', value: '', group: 'shopee', secure: true },
  { key: 'SHOPEE_SANDBOX', value: 'true', group: 'shopee', secure: false },
  { key: 'SHOPEE_REGION', value: 'br', group: 'shopee', secure: false },
  { key: 'EVOLUTION_API_URL', value: 'http://localhost:8080', group: 'whatsapp', secure: false },
  { key: 'EVOLUTION_API_KEY', value: 'athena-evolution-key', group: 'whatsapp', secure: true },
  { key: 'EVOLUTION_INSTANCE_NAME', value: 'athena', group: 'whatsapp', secure: false },
  { key: 'TELEGRAM_BOT_TOKEN', value: '', group: 'telegram', secure: true },
  { key: 'EVENT_BUS', value: 'redis', group: 'system', secure: false },
  { key: 'REDIS_URL', value: 'redis://localhost:6380/0', group: 'system', secure: true },
  { key: 'DATABASE_URL', value: 'postgresql://athena:athena@localhost:5433/athena', group: 'system', secure: true },
]

export async function initSettingsTable(): Promise<void> {
  try {
    await query(INIT_SQL)
    for (const def of DEFAULT_SETTINGS) {
      await query(`INSERT INTO "Setting" ("key", "value", "group", "secure") VALUES ($1, $2, $3, $4) ON CONFLICT ("key") DO NOTHING`, [def.key, def.value, def.group, def.secure])
    }
  } catch (err) {
    console.warn('[Settings] init failed:', err)
  }
}

export async function getAllSettings(): Promise<SettingRow[]> {
  return query(`SELECT "key", "value", "group", "secure", "updatedAt" FROM "Setting" ORDER BY "group", "key"`)
}

export async function getSetting(key: string): Promise<string | undefined> {
  const rows = await query(`SELECT "value" FROM "Setting" WHERE "key"=$1`, [key])
  return rows[0]?.value
}

export async function setSetting(key: string, value: string): Promise<void> {
  await query(`INSERT INTO "Setting" ("key", "value") VALUES ($1, $2) ON CONFLICT ("key") DO UPDATE SET "value"=$2, "updatedAt"=NOW()`, [key, value])
}

export async function setSettingsBatch(entries: Array<{ key: string; value: string }>): Promise<void> {
  for (const e of entries) {
    await setSetting(e.key, e.value)
  }
}

// ponytail: load DB settings into process.env on startup so adapters can use them
export async function loadSettingsToEnv(): Promise<void> {
  try {
    const rows = await getAllSettings()
    for (const r of rows) {
      if (r.value && !process.env[r.key]) {
        process.env[r.key] = r.value
      }
    }
  } catch {
    // settings table might not exist yet
  }
}
