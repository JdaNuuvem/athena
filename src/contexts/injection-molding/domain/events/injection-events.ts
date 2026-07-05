import { DomainEvent, EventEnvelope } from '@shared/domain/events'

abstract class E<T> implements DomainEvent<T> { readonly eventVersion='1.0'; constructor(readonly payload:T){} abstract readonly eventType:string; toEnvelope(p:Omit<EventEnvelope<T>,'eventType'|'eventVersion'|'payload'>):EventEnvelope<T>{return {...p,eventType:this.eventType,eventVersion:this.eventVersion,payload:this.payload as T}}}

export interface RunStartedPayload { runId:string;machineId:string;machineName?:string;moldId:string;productId:string;materialLot?:string;targetCycles?:number;startedAt:string;operatorId?:string;initialParameters?:{meltTempC?:number;moldTempC?:number;injectionPressureBar?:number;holdingPressureBar?:number;coolingTimeSec?:number;cycleTimeSec?:number} }
export class RunStartedEvent extends E<RunStartedPayload> { readonly eventType='injection-molding.v1.run.started' }
export interface CycleCompletedPayload { cycleId:string;runId:string;machineId:string;cycleNumber:number;cycleTimeSec?:number;shotWeightG?:number;meltTempC?:number;injectionPressureBar?:number;cushionMm?:number;partsProduced:number;defectsDetected?:boolean;completedAt:string }
export class CycleCompletedEvent extends E<CycleCompletedPayload> { readonly eventType='injection-molding.v1.cycle.completed' }
export interface DefectDetectedPayload { defectId:string;runId:string;cycleId:string;machineId?:string;moldId?:string;defectType:string;severity:string;quantity:number;possibleCause?:string;photoUrl?:string;detectedAt:string;detectedBy?:string }
export class DefectDetectedEvent extends E<DefectDetectedPayload> { readonly eventType='injection-molding.v1.defect.detected' }
export interface BatchCompletedPayload { batchId:string;runId:string;productId:string;totalCycles?:number;totalPartsProduced?:number;defectiveParts?:number;scrapRatePercent?:number;materialUsedKg?:number;avgCycleTimeSec?:number;oee?:number;completedAt:string;qualityStatus?:string }
export class BatchCompletedEvent extends E<BatchCompletedPayload> { readonly eventType='injection-molding.v1.batch.completed' }
export interface RunCompletedPayload { runId:string;machineId:string;moldId:string;totalBatches?:number;totalCycles?:number;totalPartsProduced?:number;totalDefectives?:number;totalScrapRatePercent?:number;totalMaterialKg?:number;durationHours?:number;avgOEE?:number;completedAt:string;moldCycleCountAtEnd?:number }
export class RunCompletedEvent extends E<RunCompletedPayload> { readonly eventType='injection-molding.v1.run.completed' }
export interface MachineStoppedPayload { stopId:string;machineId:string;runId:string;reason:string;detail?:string;productionStopped?:boolean;stoppedAt:string;stoppedBy?:string }
export class MachineStoppedEvent extends E<MachineStoppedPayload> { readonly eventType='injection-molding.v1.machine.stopped' }
export interface ParameterChangedPayload { changeId:string;runId:string;machineId:string;changes:Array<{parameter:string;oldValue:number;newValue:number}>;reason?:string;changedAt:string;changedBy?:string }
export class ParameterChangedEvent extends E<ParameterChangedPayload> { readonly eventType='injection-molding.v1.parameter.changed' }
export interface QualityCheckPassedPayload { checkId:string;batchId:string;samplesChecked?:number;samplesPassed?:number;tests?:Array<{testName:string;result:string;measuredValue?:number;toleranceMin?:number;toleranceMax?:number}>;checkedAt:string;checkedBy?:string }
export class QualityCheckPassedEvent extends E<QualityCheckPassedPayload> { readonly eventType='injection-molding.v1.quality.check.passed' }
export interface ScrapRecordedPayload { scrapId:string;runId:string;batchId?:string;productId:string;quantity:number;weightKg?:number;reason:string;recyclable?:boolean;recordedAt:string }
export class ScrapRecordedEvent extends E<ScrapRecordedPayload> { readonly eventType='injection-molding.v1.scrap.recorded' }
export interface MoldChangeCompletedPayload { changeId:string;machineId:string;oldMoldId:string;newMoldId:string;downtimeMin?:number;setupVerified?:boolean;completedAt:string;completedBy?:string }
export class MoldChangeCompletedEvent extends E<MoldChangeCompletedPayload> { readonly eventType='injection-molding.v1.mold.change.completed' }
