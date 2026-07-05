export interface AgentMessage {
  readonly senderId: string
  readonly recipientId: string | null
  readonly type: 'command' | 'query' | 'event' | 'response'
  readonly payload: Record<string, unknown>
  readonly correlationId: string
  readonly timestamp: Date
}

export interface AgentProtocol {
  send(message: AgentMessage): Promise<void>
  broadcast(message: Omit<AgentMessage, 'recipientId'>): Promise<void>
  onMessage(handler: (message: AgentMessage) => void): void
}

export class InMemoryAgentProtocol implements AgentProtocol {
  private handlers: Array<(message: AgentMessage) => void> = []

  async send(message: AgentMessage): Promise<void> {
    for (const handler of this.handlers) handler(message)
  }

  async broadcast(message: Omit<AgentMessage, 'recipientId'>): Promise<void> {
    for (const handler of this.handlers) {
      handler({ ...message, recipientId: null })
    }
  }

  onMessage(handler: (message: AgentMessage) => void): void {
    this.handlers.push(handler)
  }
}
