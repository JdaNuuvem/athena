import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'
import { EventEnvelope } from '../../../../shared/domain/events'

interface Payload { customerId: string; name: string; email: string; channelOrigin: string; registeredAt: string }

export class OnCustomerRegisteredHandler extends BaseEventHandler<Payload> {
  readonly eventType = 'customer.v1.customer.registered'
  protected async apply(env: EventEnvelope<Payload>) {
    void env.payload.customerId
  }
}
