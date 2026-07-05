import { DomainEvent, EventEnvelope } from '@shared/domain/events'

export abstract class BaseDomainEvent<T> implements DomainEvent<T> {
  abstract readonly eventType: string
  readonly eventVersion = '1.0'
  constructor(readonly payload: T) {}
  toEnvelope(props: Omit<EventEnvelope<T>, 'eventType' | 'eventVersion' | 'payload'>): EventEnvelope<T> {
    return { ...props, eventType: this.eventType, eventVersion: this.eventVersion, payload: this.payload as T }
  }
}

export interface MoldDesignedPayload { moldId:string; productId:string; moldCode?:string; cavityCount:number; steelType:string; coolingConfig?:string; ejectorType?:string; estimatedCycleLife?:number; estimatedCycleTimeSec?:number; cadFileHash?:string; designedAt:string; designedBy?:string }
export class MoldDesignedEvent extends BaseDomainEvent<MoldDesignedPayload> { readonly eventType = 'mold-making.v1.mold.designed' }
export interface MoldFabricationCompletedPayload { moldId:string; fabricationDurationDays?:number; actualSteelType?:string; actualCavityCount?:number; fabricatorName?:string; qualityCheckResult?:string; completedAt:string }
export class MoldFabricationCompletedEvent extends BaseDomainEvent<MoldFabricationCompletedPayload> { readonly eventType = 'mold-making.v1.mold.fabrication.completed' }
export interface MoldDeliveredPayload { moldId:string; deliveredTo:string; deliveryLocation?:string; deliveredAt:string; receivedBy?:string }
export class MoldDeliveredEvent extends BaseDomainEvent<MoldDeliveredPayload> { readonly eventType = 'mold-making.v1.mold.delivered' }
export interface MoldInstalledPayload { moldId:string; machineId:string; machineName?:string; installedAt:string; installedBy?:string; setupSheetId?:string }
export class MoldInstalledEvent extends BaseDomainEvent<MoldInstalledPayload> { readonly eventType = 'mold-making.v1.mold.installed' }
export interface MaintenanceScheduledPayload { maintenanceId:string; moldId:string; type:string; scheduledDate:string; reason?:string; currentCycleCount?:number; cycleCountAtSchedule?:number; assignedTechnician?:string }
export class MaintenanceScheduledEvent extends BaseDomainEvent<MaintenanceScheduledPayload> { readonly eventType = 'mold-making.v1.maintenance.scheduled' }
export interface MaintenancePerformedPayload { maintenanceId:string; moldId:string; type?:string; findings?:string; actionsTaken?:string; partsReplaced?:string[]; downtimeHours?:number; cost?:number; performedAt:string; performedBy?:string; nextMaintenanceCycles?:number }
export class MaintenancePerformedEvent extends BaseDomainEvent<MaintenancePerformedPayload> { readonly eventType = 'mold-making.v1.maintenance.performed' }
export interface CycleLimitReachedPayload { moldId:string; currentCycles:number; maxCycles:number; overPercent?:number; materialProcessedKg?:number; detectedAt:string; actionRequired?:string }
export class CycleLimitReachedEvent extends BaseDomainEvent<CycleLimitReachedPayload> { readonly eventType = 'mold-making.v1.cycle.limit.reached' }
export interface MoldFailureDetectedPayload { moldId:string; machineId?:string; failureType:string; severity:string; cyclesAtFailure?:number; detectedAt:string; immediateAction?:string }
export class MoldFailureDetectedEvent extends BaseDomainEvent<MoldFailureDetectedPayload> { readonly eventType = 'mold-making.v1.mold.failure.detected' }
export interface MoldInspectionCompletedPayload { inspectionId:string; moldId:string; result:string; findings?:string[]; dimensionalCheck?:boolean; surfaceFinishCheck?:boolean; coolingChannelCheck?:boolean; inspectedAt:string; inspectedBy?:string }
export class MoldInspectionCompletedEvent extends BaseDomainEvent<MoldInspectionCompletedPayload> { readonly eventType = 'mold-making.v1.mold.inspection.completed' }
