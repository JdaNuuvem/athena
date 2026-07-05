export type AgentId = string
export type AgentRole = 'observer' | 'analyst' | 'decision-maker' | 'executor' | 'coordinator'
export type AgentStatus = 'idle' | 'running' | 'paused' | 'stopped' | 'error'

export interface AgentCapability {
  readonly name: string
  readonly description: string
  readonly inputSchema: Record<string, unknown>
  readonly outputSchema: Record<string, unknown>
}

export interface AgentDefinition {
  readonly id: AgentId
  readonly name: string
  readonly role: AgentRole
  readonly context: string
  readonly capabilities: AgentCapability[]
  readonly systemPrompt: string
  readonly config: AgentConfig
}

export interface AgentConfig {
  modelProvider: 'openai' | 'anthropic' | 'groq' | 'ollama'
  modelName: string
  temperature: number
  maxTokens: number
  retryPolicy: { maxRetries: number; backoffMs: number }
  schedule?: string
  timeout: number
}
