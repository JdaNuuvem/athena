import { EventEmitter } from 'events'

type Handler = (payload: Record<string, unknown>) => void

class AthenaPubSub {
  private emitter = new EventEmitter()
  private listeners = new Map<string, Set<Handler>>()

  publish(topic: string, payload: Record<string, unknown>): void {
    this.emitter.emit(topic, payload)
  }

  subscribe(topic: string): AsyncIterableIterator<Record<string, unknown>> {
    const queue: Record<string, unknown>[] = []
    let resolve: ((v: IteratorResult<Record<string, unknown>>) => void) | null = null
    let done = false

    const handler = (payload: Record<string, unknown>) => {
      if (done) return
      if (resolve) {
        resolve({ value: payload, done: false })
        resolve = null
      } else {
        queue.push(payload)
      }
    }

    let handlers = this.listeners.get(topic)
    if (!handlers) { handlers = new Set(); this.listeners.set(topic, handlers) }
    handlers.add(handler)
    this.emitter.on(topic, handler)

    const unsubscribe = () => {
      done = true
      this.emitter.off(topic, handler)
      const h = this.listeners.get(topic)
      if (h) { h.delete(handler); if (h.size === 0) this.listeners.delete(topic) }
      if (resolve) resolve({ value: undefined, done: true })
    }

    const self = this
    return {
      [Symbol.asyncIterator]() { return this },
      next(): Promise<IteratorResult<Record<string, unknown>>> {
        if (done) return Promise.resolve({ value: undefined, done: true })
        if (queue.length > 0) return Promise.resolve({ value: queue.shift()!, done: false })
        return new Promise(r => { resolve = r })
      },
      return(): Promise<IteratorResult<Record<string, unknown>>> {
        unsubscribe()
        return Promise.resolve({ value: undefined, done: true })
      },
      throw(e: Error): Promise<IteratorResult<Record<string, unknown>>> {
        unsubscribe()
        return Promise.reject(e)
      },
    }
  }
}

export const athenaPubSub = new AthenaPubSub()
