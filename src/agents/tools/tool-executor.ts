import type { ToolDefinition } from './tool-registry'

export interface ToolResult {
  readonly toolName: string
  readonly success: boolean
  readonly data?: unknown
  readonly error?: string
  readonly duration: number
  readonly retries: number
}

export class ToolExecutor {
  constructor(private registry: { get(name: string): ToolDefinition | undefined }) {}

  async execute(toolName: string, input: unknown): Promise<ToolResult> {
    const startedAt = Date.now()
    const tool = this.registry.get(toolName)
    if (!tool) return { toolName, success: false, error: `Tool "${toolName}" not found`, duration: Date.now() - startedAt, retries: 0 }

    const parsed = tool.inputSchema.safeParse(input)
    if (!parsed.success) return { toolName, success: false, error: parsed.error.message, duration: Date.now() - startedAt, retries: 0 }

    const maxRetries = tool.retryCount ?? 0
    let lastError: unknown
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const output = await this.withTimeout(tool.handler(parsed.data), tool.timeout ?? 30000)
        return { toolName, success: true, data: output, duration: Date.now() - startedAt, retries: attempt }
      } catch (err) {
        lastError = err
      }
    }
    return { toolName, success: false, error: String(lastError), duration: Date.now() - startedAt, retries: maxRetries }
  }

  private withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => setTimeout(() => reject(new Error('Tool execution timed out')), ms)),
    ])
  }
}
