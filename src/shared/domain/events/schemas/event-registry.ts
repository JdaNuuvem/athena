import { z } from 'zod'
import { eventEnvelopeSchema } from './envelope.schema'

import {
  ProductDesignedPayload, BOMUpdatedPayload,
  RevisionApprovedPayload, ProductArchivedPayload,
} from './product-engineering.schema'

import {
  ProductPublishedPayload, ProductUpdatedPayload,
  VariantCreatedPayload, MediaAddedPayload,
} from './catalog.schema'

import {
  OrderPlacedPayload, OrderConfirmedPayload, OrderShippedPayload,
  OrderDeliveredPayload, FulfillmentCompletedPayload,
  FulfillmentRoutedPayload, ReturnRequestedPayload,
} from './order-management.schema'

import {
  StockReceivedPayload, StockShippedPayload, StockReservedPayload,
  LowStockAlertPayload, StockAdjustedPayload,
} from './inventory.schema'

import {
  ListingPublishedPayload, SyncCompletedPayload,
  ChannelOrderReceivedPayload, CompetitorPriceChangedPayload,
  ChannelAccountHealthPayload, PriceRepricedPayload,
} from './marketplace-integration.schema'

import {
  SaleCompletedPayload, RegisterClosedPayload,
  InventoryCountedPayload,
} from './retail-operations.schema'

import {
  ConversationStartedPayload, OrderConfirmedViaChatPayload,
  PaymentCompletedPayload,
} from './telegram-commerce.schema'

import {
  CustomerRegisteredPayload, TierChangedPayload,
  ChurnRiskDetectedPayload, CustomerSegmentedPayload,
} from './customer.schema'

import {
  MoldDesignedPayload, MoldFabricationCompletedPayload, MoldDeliveredPayload,
  MoldInstalledPayload, MaintenanceScheduledPayload, MaintenancePerformedPayload,
  CycleLimitReachedPayload, MoldFailureDetectedPayload, MoldInspectionCompletedPayload,
} from './mold-making.schema'

import {
  JobScheduledPayload, NCProgramUploadedPayload, MachiningStartedPayload,
  MachiningCompletedPayload, ToolWearAlertPayload, ToolReplacedPayload,
  MachineDowntimeStartedPayload, MachineDowntimeEndedPayload, QualityInspectionPassedPayload,
} from './cnc-machining.schema'

import {
  RunStartedPayload, CycleCompletedPayload, DefectDetectedPayload,
  BatchCompletedPayload, RunCompletedPayload, MachineStoppedPayload,
  ParameterChangedPayload, QualityCheckPassedPayload, ScrapRecordedPayload,
  MoldChangeCompletedPayload,
} from './injection-molding.schema'

import {
  FormulationMixedPayload, DippingStartedPayload, DippingCompletedPayload,
  CuringStartedPayload, CuringCompletedPayload, BatchCompletedPayload as PPBatchCompletedPayload,
  QCResultRecordedPayload, ViscosityAdjustedPayload, CoatingSpecUpdatedPayload,
} from './plastisol-processing.schema'

import {
  PriceUpdatedPayload, PromotionCreatedPayload, PromotionExpiredPayload,
  DiscountAppliedPayload, MarginAlertPayload, PriceRuleUpdatedPayload,
  ElasticityAnalyzedPayload,
} from './pricing.schema'

import {
  ShipmentCreatedPayload, LabelGeneratedPayload, CarrierPickedUpPayload,
  DeliveredPayload, DeliveryFailedPayload, TrackingUpdatedPayload,
  CarrierSelectedPayload, ReturnLabelGeneratedPayload, RateCalculatedPayload,
} from './shipping.schema'

import {
  AnomalyDetectedPayload, ForecastUpdatedPayload, AlertTriggeredPayload,
  ExecutiveDigestSentPayload, TrendAnalyzedPayload,
} from './analytics.schema'

import { SpecificationValidatedPayload, RevisionCreatedPayload } from './product-engineering-extra.schema'
import { CategoryReorganizedPayload, SEOOptimizedPayload } from './catalog-extra.schema'
import { ListingUpdatedPayload, ListingClosedPayload, ChannelOrderShippedPayload, ChannelReturnReceivedPayload } from './marketplace-extra.schema'
import { RegisterOpenedPayload, ShiftReconciledPayload, ProductShownPayload, CartUpdatedPayload, CustomerBlockedPayload, StockAgingReportPayload, StockTransferredPayload, ReorderPointReachedPayload, StockCycleCountedPayload } from './retail-telegram-inventory-extra.schema'
import { FulfillmentStartedPayload, OrderCanceledPayload, InvoiceGeneratedPayload, PaymentReceivedPayload, OrderOnHoldPayload, ReturnReceivedPayload, OrderSplitPayload, OrderMergedPayload, ProfileUpdatedPayload, PointsEarnedPayload, InteractionRecordedPayload, LoyaltyRewardClaimedPayload } from './order-customer-extra.schema'

export const EventSchemas = {
  'product-engineering.v1.product.designed': eventEnvelopeSchema(ProductDesignedPayload),
  'product-engineering.v1.bom.updated': eventEnvelopeSchema(BOMUpdatedPayload),
  'product-engineering.v1.revision.approved': eventEnvelopeSchema(RevisionApprovedPayload),
  'product-engineering.v1.product.archived': eventEnvelopeSchema(ProductArchivedPayload),

  'catalog.v1.product.published': eventEnvelopeSchema(ProductPublishedPayload),
  'catalog.v1.product.updated': eventEnvelopeSchema(ProductUpdatedPayload),
  'catalog.v1.variant.created': eventEnvelopeSchema(VariantCreatedPayload),
  'catalog.v1.media.added': eventEnvelopeSchema(MediaAddedPayload),

  'order-management.v1.order.placed': eventEnvelopeSchema(OrderPlacedPayload),
  'order-management.v1.order.confirmed': eventEnvelopeSchema(OrderConfirmedPayload),
  'order-management.v1.order.shipped': eventEnvelopeSchema(OrderShippedPayload),
  'order-management.v1.order.delivered': eventEnvelopeSchema(OrderDeliveredPayload),
  'order-management.v1.fulfillment.completed': eventEnvelopeSchema(FulfillmentCompletedPayload),
  'order-management.v1.fulfillment.routed': eventEnvelopeSchema(FulfillmentRoutedPayload),
  'order-management.v1.return.requested': eventEnvelopeSchema(ReturnRequestedPayload),

  'inventory.v1.stock.received': eventEnvelopeSchema(StockReceivedPayload),
  'inventory.v1.stock.shipped': eventEnvelopeSchema(StockShippedPayload),
  'inventory.v1.stock.reserved': eventEnvelopeSchema(StockReservedPayload),
  'inventory.v1.low.stock.alert': eventEnvelopeSchema(LowStockAlertPayload),
  'inventory.v1.stock.adjusted': eventEnvelopeSchema(StockAdjustedPayload),

  'marketplace-integration.v1.listing.published': eventEnvelopeSchema(ListingPublishedPayload),
  'marketplace-integration.v1.sync.completed': eventEnvelopeSchema(SyncCompletedPayload),
  'marketplace-integration.v1.channel.order.received': eventEnvelopeSchema(ChannelOrderReceivedPayload),
  'marketplace-integration.v1.competitor.price.changed': eventEnvelopeSchema(CompetitorPriceChangedPayload),
  'marketplace-integration.v1.channel.account.health': eventEnvelopeSchema(ChannelAccountHealthPayload),
  'marketplace-integration.v1.price.repriced': eventEnvelopeSchema(PriceRepricedPayload),

  'retail-operations.v1.sale.completed': eventEnvelopeSchema(SaleCompletedPayload),
  'retail-operations.v1.register.closed': eventEnvelopeSchema(RegisterClosedPayload),
  'retail-operations.v1.inventory.counted': eventEnvelopeSchema(InventoryCountedPayload),

  'telegram-commerce.v1.conversation.started': eventEnvelopeSchema(ConversationStartedPayload),
  'telegram-commerce.v1.order.confirmed': eventEnvelopeSchema(OrderConfirmedViaChatPayload),
  'telegram-commerce.v1.payment.completed': eventEnvelopeSchema(PaymentCompletedPayload),

  'customer.v1.customer.registered': eventEnvelopeSchema(CustomerRegisteredPayload),
  'customer.v1.tier.changed': eventEnvelopeSchema(TierChangedPayload),
  'customer.v1.churn.risk.detected': eventEnvelopeSchema(ChurnRiskDetectedPayload),
  'customer.v1.customer.segmented': eventEnvelopeSchema(CustomerSegmentedPayload),

  'mold-making.v1.mold.designed': eventEnvelopeSchema(MoldDesignedPayload),
  'mold-making.v1.mold.fabrication.completed': eventEnvelopeSchema(MoldFabricationCompletedPayload),
  'mold-making.v1.mold.delivered': eventEnvelopeSchema(MoldDeliveredPayload),
  'mold-making.v1.mold.installed': eventEnvelopeSchema(MoldInstalledPayload),
  'mold-making.v1.maintenance.scheduled': eventEnvelopeSchema(MaintenanceScheduledPayload),
  'mold-making.v1.maintenance.performed': eventEnvelopeSchema(MaintenancePerformedPayload),
  'mold-making.v1.cycle.limit.reached': eventEnvelopeSchema(CycleLimitReachedPayload),
  'mold-making.v1.mold.failure.detected': eventEnvelopeSchema(MoldFailureDetectedPayload),
  'mold-making.v1.mold.inspection.completed': eventEnvelopeSchema(MoldInspectionCompletedPayload),

  'cnc-machining.v1.job.scheduled': eventEnvelopeSchema(JobScheduledPayload),
  'cnc-machining.v1.program.uploaded': eventEnvelopeSchema(NCProgramUploadedPayload),
  'cnc-machining.v1.machining.started': eventEnvelopeSchema(MachiningStartedPayload),
  'cnc-machining.v1.machining.completed': eventEnvelopeSchema(MachiningCompletedPayload),
  'cnc-machining.v1.tool.wear.alert': eventEnvelopeSchema(ToolWearAlertPayload),
  'cnc-machining.v1.tool.replaced': eventEnvelopeSchema(ToolReplacedPayload),
  'cnc-machining.v1.machine.downtime.started': eventEnvelopeSchema(MachineDowntimeStartedPayload),
  'cnc-machining.v1.machine.downtime.ended': eventEnvelopeSchema(MachineDowntimeEndedPayload),
  'cnc-machining.v1.quality.inspection.passed': eventEnvelopeSchema(QualityInspectionPassedPayload),

  'injection-molding.v1.run.started': eventEnvelopeSchema(RunStartedPayload),
  'injection-molding.v1.cycle.completed': eventEnvelopeSchema(CycleCompletedPayload),
  'injection-molding.v1.defect.detected': eventEnvelopeSchema(DefectDetectedPayload),
  'injection-molding.v1.batch.completed': eventEnvelopeSchema(BatchCompletedPayload),
  'injection-molding.v1.run.completed': eventEnvelopeSchema(RunCompletedPayload),
  'injection-molding.v1.machine.stopped': eventEnvelopeSchema(MachineStoppedPayload),
  'injection-molding.v1.parameter.changed': eventEnvelopeSchema(ParameterChangedPayload),
  'injection-molding.v1.quality.check.passed': eventEnvelopeSchema(QualityCheckPassedPayload),
  'injection-molding.v1.scrap.recorded': eventEnvelopeSchema(ScrapRecordedPayload),
  'injection-molding.v1.mold.change.completed': eventEnvelopeSchema(MoldChangeCompletedPayload),

  'plastisol-processing.v1.formulation.mixed': eventEnvelopeSchema(FormulationMixedPayload),
  'plastisol-processing.v1.dipping.started': eventEnvelopeSchema(DippingStartedPayload),
  'plastisol-processing.v1.dipping.completed': eventEnvelopeSchema(DippingCompletedPayload),
  'plastisol-processing.v1.curing.started': eventEnvelopeSchema(CuringStartedPayload),
  'plastisol-processing.v1.curing.completed': eventEnvelopeSchema(CuringCompletedPayload),
  'plastisol-processing.v1.batch.completed': eventEnvelopeSchema(PPBatchCompletedPayload),
  'plastisol-processing.v1.qc.result.recorded': eventEnvelopeSchema(QCResultRecordedPayload),
  'plastisol-processing.v1.viscosity.adjusted': eventEnvelopeSchema(ViscosityAdjustedPayload),
  'plastisol-processing.v1.coating.spec.updated': eventEnvelopeSchema(CoatingSpecUpdatedPayload),

  'pricing.v1.price.updated': eventEnvelopeSchema(PriceUpdatedPayload),
  'pricing.v1.promotion.created': eventEnvelopeSchema(PromotionCreatedPayload),
  'pricing.v1.promotion.expired': eventEnvelopeSchema(PromotionExpiredPayload),
  'pricing.v1.discount.applied': eventEnvelopeSchema(DiscountAppliedPayload),
  'pricing.v1.margin.alert': eventEnvelopeSchema(MarginAlertPayload),
  'pricing.v1.price.rule.updated': eventEnvelopeSchema(PriceRuleUpdatedPayload),
  'pricing.v1.elasticity.analyzed': eventEnvelopeSchema(ElasticityAnalyzedPayload),

  'shipping.v1.shipment.created': eventEnvelopeSchema(ShipmentCreatedPayload),
  'shipping.v1.label.generated': eventEnvelopeSchema(LabelGeneratedPayload),
  'shipping.v1.carrier.picked.up': eventEnvelopeSchema(CarrierPickedUpPayload),
  'shipping.v1.delivered': eventEnvelopeSchema(DeliveredPayload),
  'shipping.v1.delivery.failed': eventEnvelopeSchema(DeliveryFailedPayload),
  'shipping.v1.tracking.updated': eventEnvelopeSchema(TrackingUpdatedPayload),
  'shipping.v1.carrier.selected': eventEnvelopeSchema(CarrierSelectedPayload),
  'shipping.v1.return.label.generated': eventEnvelopeSchema(ReturnLabelGeneratedPayload),
  'shipping.v1.rate.calculated': eventEnvelopeSchema(RateCalculatedPayload),

  'analytics.v1.anomaly.detected': eventEnvelopeSchema(AnomalyDetectedPayload),
  'analytics.v1.forecast.updated': eventEnvelopeSchema(ForecastUpdatedPayload),
  'analytics.v1.alert.triggered': eventEnvelopeSchema(AlertTriggeredPayload),
  'analytics.v1.executive.digest.sent': eventEnvelopeSchema(ExecutiveDigestSentPayload),
  'analytics.v1.trend.analyzed': eventEnvelopeSchema(TrendAnalyzedPayload),

  'product-engineering.v1.specification.validated': eventEnvelopeSchema(SpecificationValidatedPayload),
  'product-engineering.v1.revision.created': eventEnvelopeSchema(RevisionCreatedPayload),
  'product-engineering.v1.specification.approved': eventEnvelopeSchema(SpecificationValidatedPayload),

  'catalog.v1.category.reorganized': eventEnvelopeSchema(CategoryReorganizedPayload),
  'catalog.v1.seo.optimized': eventEnvelopeSchema(SEOOptimizedPayload),

  'marketplace-integration.v1.listing.updated': eventEnvelopeSchema(ListingUpdatedPayload),
  'marketplace-integration.v1.listing.closed': eventEnvelopeSchema(ListingClosedPayload),
  'marketplace-integration.v1.channel.order.shipped': eventEnvelopeSchema(ChannelOrderShippedPayload),
  'marketplace-integration.v1.channel.return.received': eventEnvelopeSchema(ChannelReturnReceivedPayload),

  'retail-operations.v1.register.opened': eventEnvelopeSchema(RegisterOpenedPayload),
  'retail-operations.v1.shift.reconciled': eventEnvelopeSchema(ShiftReconciledPayload),

  'telegram-commerce.v1.product.shown': eventEnvelopeSchema(ProductShownPayload),
  'telegram-commerce.v1.cart.updated': eventEnvelopeSchema(CartUpdatedPayload),
  'telegram-commerce.v1.customer.blocked': eventEnvelopeSchema(CustomerBlockedPayload),

  'inventory.v1.stock.aging.report': eventEnvelopeSchema(StockAgingReportPayload),
  'inventory.v1.stock.transferred': eventEnvelopeSchema(StockTransferredPayload),
  'inventory.v1.reorder.point.reached': eventEnvelopeSchema(ReorderPointReachedPayload),
  'inventory.v1.stock.cycle.counted': eventEnvelopeSchema(StockCycleCountedPayload),

  'order-management.v1.fulfillment.started': eventEnvelopeSchema(FulfillmentStartedPayload),
  'order-management.v1.order.canceled': eventEnvelopeSchema(OrderCanceledPayload),
  'order-management.v1.invoice.generated': eventEnvelopeSchema(InvoiceGeneratedPayload),
  'order-management.v1.payment.received': eventEnvelopeSchema(PaymentReceivedPayload),
  'order-management.v1.order.on.hold': eventEnvelopeSchema(OrderOnHoldPayload),
  'order-management.v1.return.received': eventEnvelopeSchema(ReturnReceivedPayload),
  'order-management.v1.order.split': eventEnvelopeSchema(OrderSplitPayload),
  'order-management.v1.order.merged': eventEnvelopeSchema(OrderMergedPayload),

  'customer.v1.profile.updated': eventEnvelopeSchema(ProfileUpdatedPayload),
  'customer.v1.points.earned': eventEnvelopeSchema(PointsEarnedPayload),
  'customer.v1.interaction.recorded': eventEnvelopeSchema(InteractionRecordedPayload),
  'customer.v1.loyalty.reward.claimed': eventEnvelopeSchema(LoyaltyRewardClaimedPayload),
} as const

export type KnownEventType = keyof typeof EventSchemas

export function validateEvent(raw: unknown) {
  if (typeof raw !== 'object' || raw === null) {
    return { success: false as const, error: new z.ZodError([]) }
  }
  const eventType = (raw as Record<string, unknown>)['eventType']
  if (typeof eventType !== 'string' || !(eventType in EventSchemas)) {
    return { success: false as const, error: new z.ZodError([]) }
  }
  const schema = EventSchemas[eventType as KnownEventType]
  return schema.safeParse(raw)
}
