import { describe, it, expect } from '@jest/globals'
import { BaseEventHandler } from '../../../src/shared/domain/events'
import { EventEnvelope } from '../../../src/shared/domain/events'

interface TestPayload { id: string }
const testSource = { context: 'test', aggregateId: '550e8400-e29b-41d4-a716-446655440000', aggregateType: 'Test' }
const testMeta = { userId: 'u1', agentId: null, channel: 'api' as const }

function makeEnvelope(eventId: string): EventEnvelope<TestPayload> {
  return {
    eventId, eventType: 'test.v1.event', eventVersion: '1.0',
    timestamp: '2026-07-02T23:00:00Z', correlationId: 'cid', causationId: null,
    tenantId: 't1', source: testSource, payload: { id: '123' }, metadata: testMeta,
  }
}

describe('BaseEventHandler — dedup', () => {
  it('should process an event once', async () => {
    const calls: string[] = []
    class Handler extends BaseEventHandler<TestPayload> {
      readonly eventType = 'test.v1.event'
      protected async apply(env: EventEnvelope<TestPayload>) { calls.push(env.eventId) }
    }
    const h = new Handler()
    await h.handle(makeEnvelope('evt-1'))
    expect(calls).toEqual(['evt-1'])
  })

  it('should skip duplicate eventId', async () => {
    const calls: string[] = []
    class Handler extends BaseEventHandler<TestPayload> {
      readonly eventType = 'test.v1.event'
      protected async apply(env: EventEnvelope<TestPayload>) { calls.push(env.eventId) }
    }
    const h = new Handler()
    await h.handle(makeEnvelope('evt-2'))
    await h.handle(makeEnvelope('evt-2'))
    await h.handle(makeEnvelope('evt-3'))
    expect(calls).toEqual(['evt-2', 'evt-3'])
  })
})
