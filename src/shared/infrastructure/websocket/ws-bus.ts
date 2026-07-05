import { EventEmitter } from 'events'
import type { WebSocket } from 'ws'

export interface WSEvent {
  type: string
  payload: Record<string, unknown>
  timestamp: string
}

export class WebSocketEventBus {
  private clients = new Set<WebSocket>()
  public readonly events = new EventEmitter()
  private history: WSEvent[] = []

  constructor(private maxHistory = 200) {}

  addClient(ws: WebSocket): void {
    this.clients.add(ws)
    ws.on('close', () => this.clients.delete(ws))
    ws.on('error', () => this.clients.delete(ws))
    this.sendHistory(ws)
  }

  broadcast(type: string, payload: Record<string, unknown>): void {
    const event: WSEvent = { type, payload, timestamp: new Date().toISOString() }
    this.history.push(event)
    if (this.history.length > this.maxHistory) this.history = this.history.slice(-this.maxHistory)

    const msg = JSON.stringify(event)
    for (const ws of this.clients) {
      try { if (ws.readyState === ws.OPEN) ws.send(msg) } catch { this.clients.delete(ws) }
    }
    this.events.emit('event', event)
  }

  private sendHistory(ws: WebSocket): void {
    try {
      ws.send(JSON.stringify({ type: 'history', payload: { events: this.history }, timestamp: new Date().toISOString() }))
    } catch { /* ignore */ }
  }

  getClientsCount(): number { return this.clients.size }
  getHistory(): WSEvent[] { return [...this.history] }
}

export const wsBus = new WebSocketEventBus()
