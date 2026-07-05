import { DomainEvent, EventEnvelope } from '@shared/domain/events'

abstract class E<T> implements DomainEvent<T> { readonly eventVersion='1.0'; constructor(readonly payload:T){} abstract readonly eventType:string; toEnvelope(p:Omit<EventEnvelope<T>,'eventType'|'eventVersion'|'payload'>):EventEnvelope<T>{return {...p,eventType:this.eventType,eventVersion:this.eventVersion,payload:this.payload as T}}}

export interface JobScheduledPayload { jobId:string;machineId:string;machineName?:string;programId:string;programCode?:string;materialType?:string;materialBlock?:string;estimatedMachiningTimeMin?:number;priority:string;scheduledAt:string;scheduledBy?:string }
export class JobScheduledEvent extends E<JobScheduledPayload> { readonly eventType='cnc-machining.v1.job.scheduled' }
export interface NCProgramUploadedPayload { programId:string;machineId:string;fileName:string;fileHash?:string;toolCount:number;estimatedRuntimeMin?:number;validationStatus:string;uploadedAt:string;uploadedBy?:string }
export class NCProgramUploadedEvent extends E<NCProgramUploadedPayload> { readonly eventType='cnc-machining.v1.program.uploaded' }
export interface MachiningStartedPayload { jobId:string;machineId:string;programId?:string;operatorId?:string;stockMaterial?:string;initialToolCount?:number;startedAt:string }
export class MachiningStartedEvent extends E<MachiningStartedPayload> { readonly eventType='cnc-machining.v1.machining.started' }
export interface MachiningCompletedPayload { jobId:string;machineId:string;programId?:string;actualDurationMin?:number;estimatedDurationMin?:number;partsProduced:number;partsDefective:number;toolWearSummary?:Array<{toolId:string;toolNumber:number;wearMicrons:number;cyclesRemaining:number}>;completedAt:string;operatorId?:string }
export class MachiningCompletedEvent extends E<MachiningCompletedPayload> { readonly eventType='cnc-machining.v1.machining.completed' }
export interface ToolWearAlertPayload { toolId:string;toolNumber?:number;toolName?:string;machineId:string;wearMicrons:number;thresholdMicrons:number;currentJobId?:string;cyclesCompleted?:number;estimatedCyclesRemaining?:number;severity:string;detectedAt:string }
export class ToolWearAlertEvent extends E<ToolWearAlertPayload> { readonly eventType='cnc-machining.v1.tool.wear.alert' }
export interface ToolReplacedPayload { toolId:string;toolNumber?:number;toolName?:string;machineId:string;oldToolCycles?:number;newToolId?:string;replacedAt:string;replacedBy?:string;cost?:number }
export class ToolReplacedEvent extends E<ToolReplacedPayload> { readonly eventType='cnc-machining.v1.tool.replaced' }
export interface MachineDowntimeStartedPayload { downtimeId:string;machineId:string;reason:string;detail?:string;startedAt:string;reportedBy?:string }
export class MachineDowntimeStartedEvent extends E<MachineDowntimeStartedPayload> { readonly eventType='cnc-machining.v1.machine.downtime.started' }
export interface MachineDowntimeEndedPayload { downtimeId:string;machineId:string;downtimeDurationMin?:number;actionTaken?:string;endedAt:string;resolvedBy?:string;machineRestarted?:boolean }
export class MachineDowntimeEndedEvent extends E<MachineDowntimeEndedPayload> { readonly eventType='cnc-machining.v1.machine.downtime.ended' }
export interface QualityInspectionPassedPayload { inspectionId:string;jobId:string;partsInspected?:number;partsPassed?:number;partsFailed?:number;dimensionalToleranceOk?:boolean;surfaceFinishOk?:boolean;inspectedAt:string;inspectedBy?:string }
export class QualityInspectionPassedEvent extends E<QualityInspectionPassedPayload> { readonly eventType='cnc-machining.v1.quality.inspection.passed' }
