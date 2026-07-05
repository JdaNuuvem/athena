import 'dotenv/config'
import { z } from 'zod'

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  PORT: z.coerce.number().default(3000),
  HOST: z.string().default('0.0.0.0'),

  DATABASE_URL: z.string().default('postgresql://athena:athena@localhost:5432/athena'),
  REDIS_URL: z.string().default('redis://localhost:6379'),
  QDRANT_URL: z.string().default('http://localhost:6333'),
  KAFKA_BROKERS: z.string().default('localhost:9092'),

  EVENT_BUS: z.enum(['redis', 'kafka', 'inmemory']).default('redis'),

  OPENAI_API_KEY: z.string().optional(),
  ANTHROPIC_API_KEY: z.string().optional(),
  GROQ_API_KEY: z.string().optional(),

  LLM_PROVIDER: z.enum(['openai', 'anthropic', 'groq', 'ollama']).default('openai'),
  LLM_MODEL: z.string().default('gpt-4o-mini'),
  LLM_TEMPERATURE: z.coerce.number().default(0.3),
  LLM_MAX_TOKENS: z.coerce.number().default(4096),

  JWT_SECRET: z.string().default('athena-dev-secret-change-in-production'),
  JWT_EXPIRES_IN: z.string().default('24h'),
  JWT_REFRESH_EXPIRES_IN: z.string().default('7d'),
})

export type AppConfig = z.infer<typeof envSchema>

let _config: AppConfig | null = null

export function loadConfig(): AppConfig {
  if (_config) return _config
  const result = envSchema.safeParse(process.env)
  if (!result.success) {
    console.error('Invalid environment config:', result.error.format())
    throw new Error('Invalid environment configuration')
  }
  _config = result.data
  return _config
}

export function getConfig(): AppConfig {
  if (!_config) return loadConfig()
  return _config
}
