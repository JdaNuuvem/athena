import { z } from 'zod'

export const EventSourceSchema = z.object({
  context: z.string().min(1),
  aggregateId: z.string().uuid(),
  aggregateType: z.string().min(1),
})

export const EventMetadataSchema = z.object({
  userId: z.string().min(1),
  agentId: z.string().nullable(),
  channel: z.enum(['api', 'agent', 'scheduler', 'system']),
})

export function eventEnvelopeSchema<T extends z.ZodTypeAny>(payloadSchema: T) {
  return z.object({
    eventId: z.string().uuid(),
    eventType: z.string().min(1),
    eventVersion: z.string().regex(/^\d+\.\d+$/),
    timestamp: z.string().datetime(),
    correlationId: z.string().uuid(),
    causationId: z.string().uuid().nullable(),
    tenantId: z.string().min(1),
    source: EventSourceSchema,
    payload: payloadSchema,
    metadata: EventMetadataSchema,
  })
}

export type EventEnvelopeParsed<T = Record<string, unknown>> = z.infer<ReturnType<typeof eventEnvelopeSchema<z.ZodType<T>>>>
