import { z, ZodSchema } from 'zod'

export interface ToolDefinition<TInput = unknown, TOutput = unknown> {
  readonly name: string
  readonly description: string
  readonly inputSchema: ZodSchema<TInput>
  readonly outputSchema: ZodSchema<TOutput>
  readonly handler: (input: TInput) => Promise<TOutput>
  readonly timeout?: number
  readonly retryCount?: number
}

export interface ToolRegistry {
  register<TInput, TOutput>(tool: ToolDefinition<TInput, TOutput>): void
  unregister(name: string): void
  get(name: string): ToolDefinition | undefined
  list(): ToolDefinition[]
  listByCapability(capability: string): ToolDefinition[]
}

export class DefaultToolRegistry implements ToolRegistry {
  private tools = new Map<string, ToolDefinition>()

  register<TInput, TOutput>(tool: ToolDefinition<TInput, TOutput>): void {
    this.tools.set(tool.name, tool as ToolDefinition)
  }

  unregister(name: string): void {
    this.tools.delete(name)
  }

  get(name: string): ToolDefinition | undefined {
    return this.tools.get(name)
  }

  list(): ToolDefinition[] {
    return [...this.tools.values()]
  }

  listByCapability(capability: string): ToolDefinition[] {
    return [...this.tools.values()].filter(t => t.name.includes(capability) || t.description.includes(capability))
  }
}
