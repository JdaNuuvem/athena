import { z } from 'zod'

export const AgentConfigSchema = z.object({
  modelProvider: z.enum(['openai', 'anthropic', 'groq', 'ollama']).default('openai'),
  modelName: z.string().default('gpt-4o-mini'),
  temperature: z.number().min(0).max(2).default(0.3),
  maxTokens: z.number().int().positive().default(4096),
  retryPolicy: z.object({
    maxRetries: z.number().int().min(0).default(3),
    backoffMs: z.number().int().min(100).default(1000),
  }).default({ maxRetries: 3, backoffMs: 1000 }),
  timeout: z.number().int().min(1000).default(60000),
  schedule: z.string().optional(),
})

export const AgentDefinitionFileSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.enum(['observer', 'analyst', 'decision-maker', 'executor', 'coordinator']),
  context: z.string(),
  prompt: z.object({
    template: z.string().default('default'),
    variables: z.record(z.string()).optional(),
  }),
  config: AgentConfigSchema,
  capabilities: z.array(z.object({
    name: z.string(),
    description: z.string(),
    inputSchema: z.record(z.unknown()),
    outputSchema: z.record(z.unknown()),
  })).default([]),
  toolset: z.array(z.string()).default([]),
})

export type AgentConfig = z.infer<typeof AgentConfigSchema>
export type AgentDefinitionFile = z.infer<typeof AgentDefinitionFileSchema>

import { readFileSync } from 'fs'

export function loadAgentConfig(filePath: string): AgentDefinitionFile {
  const raw = readFileSync(filePath, 'utf-8')
  const parsed = JSON.parse(raw)
  return AgentDefinitionFileSchema.parse(parsed)
}

export function mergeWithEnv(config: AgentDefinitionFile, env: Record<string, string | undefined>): AgentDefinitionFile {
  const provider = env['ATHENA_LLM_PROVIDER'] ?? config.config.modelProvider
  const model = env['ATHENA_LLM_MODEL'] ?? config.config.modelName
  const key = env['ATHENA_LLM_API_KEY'] ?? ''

  return {
    ...config,
    config: {
      ...config.config,
      modelProvider: provider as AgentConfig['modelProvider'],
      modelName: model,
    },
  }
}
