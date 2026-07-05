import { z } from 'zod'
import type { ToolDefinition, ToolRegistry } from './tool-registry'

export interface MCPBridgeConfig {
  readonly serverName: string
  readonly command: string
  readonly args: string[]
  readonly env?: Record<string, string>
}

export class MCPBridge {
  constructor(private registry: ToolRegistry) {}

  async connect(config: MCPBridgeConfig): Promise<void> {
    this.registry.register({
      name: `mcp.${config.serverName}.echo`,
      description: `MCP bridge tool for ${config.serverName}`,
      inputSchema: z.object({ message: z.string() }),
      outputSchema: z.object({ response: z.string() }),
      handler: async (input: unknown) => {
        const data = input as { message: string }
        return { response: `[${config.serverName}] echo: ${data.message}` }
      },
    })
    this.registry.register({
      name: `mcp.${config.serverName}.health`,
      description: `Health check for MCP server ${config.serverName}`,
      inputSchema: z.object({}),
      outputSchema: z.object({ status: z.string(), server: z.string() }),
      handler: async () => ({ status: 'connected', server: config.serverName }),
    })
  }
}
