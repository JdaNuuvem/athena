import type { IOrderRepository, IFulfillmentRepository } from '../../domain/repositories'
import { Order, OrderLine, Fulfillment } from '../../domain/entities'
import type { IEventBus } from '@shared/domain/events'

export class PlaceOrderUseCase {
  constructor(
    private orderRepo: IOrderRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(input: PlaceOrderInput): Promise<Order> {
    const lines: OrderLine[] = input.lines.map(l => ({ sku: l.sku, name: l.name, quantity: l.quantity, unitPrice: l.unitPrice }))
    const order = new Order(input.customerId, input.channel ?? 'manual', lines, 0, input.shippingAddress)
    order.place()
    await this.orderRepo.save(order)
    for (const event of order.pullDomainEvents()) await this.eventBus.publish(event)
    return order
  }
}

export interface PlaceOrderInput {
  customerId: string
  channel?: string
  lines: Array<{ sku: string; name: string; quantity: number; unitPrice: number }>
  shippingAddress?: Record<string, unknown>
}

export class ConfirmOrderUseCase {
  constructor(
    private orderRepo: IOrderRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(orderId: string): Promise<Order> {
    const order = await this.orderRepo.findById(orderId)
    if (!order) throw new Error('Order not found')
    order.confirm()
    await this.orderRepo.save(order)
    for (const event of order.pullDomainEvents()) await this.eventBus.publish(event)
    return order
  }
}

export class ShipOrderUseCase {
  constructor(
    private orderRepo: IOrderRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(orderId: string, trackingCode: string, carrierId: string): Promise<Order> {
    const order = await this.orderRepo.findById(orderId)
    if (!order) throw new Error('Order not found')
    order.ship(trackingCode, carrierId)
    await this.orderRepo.save(order)
    for (const event of order.pullDomainEvents()) await this.eventBus.publish(event)
    return order
  }
}

export class DeliverOrderUseCase {
  constructor(
    private orderRepo: IOrderRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(orderId: string): Promise<Order> {
    const order = await this.orderRepo.findById(orderId)
    if (!order) throw new Error('Order not found')
    order.deliver()
    await this.orderRepo.save(order)
    for (const event of order.pullDomainEvents()) await this.eventBus.publish(event)
    return order
  }
}

export class RouteFulfillmentUseCase {
  constructor(
    private fulfillmentRepo: IFulfillmentRepository,
    private eventBus: IEventBus,
  ) {}

  async execute(orderId: string, centerId: string): Promise<Fulfillment> {
    let fulfillment = await this.fulfillmentRepo.findByOrderId(orderId)
    if (!fulfillment) {
      fulfillment = new Fulfillment(orderId)
    }
    fulfillment.route(centerId)
    await this.fulfillmentRepo.save(fulfillment)
    for (const event of fulfillment.pullDomainEvents()) await this.eventBus.publish(event)
    return fulfillment
  }
}
