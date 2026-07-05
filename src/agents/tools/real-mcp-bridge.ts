import { spawn, ChildProcess } from 'child_process'
import { z } from 'zod'
import type { ToolRegistry } from './tool-registry'

export interface MCPBridgeConfig {
  readonly serverName: string
  readonly command: string
  readonly args: string[]
  readonly env?: Record<string, string>
}

interface MCPTool {
  name: string
  description?: string
  inputSchema: Record<string, unknown>
}

export class RealMCPBridge {
  private processes = new Map<string, ChildProcess>()

  constructor(private registry: ToolRegistry) {}

  async connect(config: MCPBridgeConfig): Promise<void> {
    const proc = spawn(config.command, config.args, {
      env: { ...process.env, ...config.env },
      stdio: ['pipe', 'pipe', 'pipe'],
    })

    this.processes.set(config.serverName, proc)

    proc.on('exit', code => console.log(`[MCP:${config.serverName}] exited with code ${code}`))
    proc.on('error', err => console.error(`[MCP:${config.serverName}] error:`, err))

    const tools = await this.listTools(proc, config.serverName)

    for (const tool of tools) {
      this.registry.register({
        name: `mcp.${config.serverName}.${tool.name}`,
        description: tool.description ?? `MCP tool ${tool.name} from ${config.serverName}`,
        inputSchema: z.object(tool.inputSchema as Record<string, z.ZodTypeAny> ?? {}),
        outputSchema: z.object({}),
        handler: async (input: unknown) => {
          return this.callTool(proc, config.serverName, tool.name, input)
        },
      })
    }
  }

  private async listTools(proc: ChildProcess, serverName: string): Promise<MCPTool[]> {
    const request = JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list', params: {} })
    return new Promise<MCPTool[]>((resolve) => {
      const timeout = setTimeout(() => { resolve([]) }, 5000)
      let buffer = ''
      proc.stdout?.on('data', (chunk: Buffer) => {
        buffer += chunk.toString()
        try {
          const response = JSON.parse(buffer)
          clearTimeout(timeout)
          resolve((response.result?.tools as MCPTool[]) ?? [])
        } catch { /* wait for more data */ }
      })
      proc.stdin?.write(request + '\n')
    })
  }

  private async callTool(proc: ChildProcess, serverName: string, toolName: string, input: unknown): Promise<unknown> {
    const request = JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method: 'tools/call', params: { name: toolName, arguments: input } })
    return new Promise<unknown>((resolve, reject) => {
      const timeout = setTimeout(() => { reject(new Error(`MCP tool ${toolName} timed out`)) }, 30000)
      let buffer = ''
      const handler = (chunk: Buffer) => {
        buffer += chunk.toString()
        try {
          const response = JSON.parse(buffer)
          clearTimeout(timeout)
          proc.stdout?.removeListener('data', handler)
          if (response.error) reject(new Error(response.error.message))
          else resolve(response.result)
        } catch { /* wait for more data */ }
      }
      proc.stdout?.on('data', handler)
      proc.stdin?.write(request + '\n')
    })
  }

  disconnect(serverName: string): void {
    const proc = this.processes.get(serverName)
    if (proc) {
      proc.kill()
      this.processes.delete(serverName)
    }
  }

  disconnectAll(): void {
    for (const [name, proc] of this.processes) {
      proc.kill()
      console.log(`[MCP:${name}] disconnected`)
    }
    this.processes.clear()
  }
}
