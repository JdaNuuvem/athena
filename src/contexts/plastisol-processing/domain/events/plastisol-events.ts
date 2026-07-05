import { DomainEvent, EventEnvelope } from '@shared/domain/events'
abstract class E<T> implements DomainEvent<T> { readonly eventVersion='1.0'; constructor(readonly payload:T){} abstract readonly eventType:string; toEnvelope(p:Omit<EventEnvelope<T>,'eventType'|'eventVersion'|'payload'>):EventEnvelope<T>{return {...p,eventType:this.eventType,eventVersion:this.eventVersion,payload:this.payload as T}}}
export interface FormulationMixedPayload { formulationId:string;productId:string;batchSizeL:number;components:Array<{name:string;type:string;quantityL:number;lotNumber:string}>;targetViscosityCp?:number;actualViscosityCp?:number;mixedAt:string;mixedBy?:string }
export class FormulationMixedEvent extends E<FormulationMixedPayload> { readonly eventType='plastisol-processing.v1.formulation.mixed' }
export interface DippingStartedPayload { dippingId:string;formulationId:string;lineId:string;productId:string;quantity:number;moldType?:string;preheatTempC?:number;startedAt:string;operatorId?:string }
export class DippingStartedEvent extends E<DippingStartedPayload> { readonly eventType='plastisol-processing.v1.dipping.started' }
export interface DippingCompletedPayload { dippingId:string;gelThicknessMm?:number;coatingUniformityOk?:boolean;visualInspectionOk?:boolean;completedAt:string }
export class DippingCompletedEvent extends E<DippingCompletedPayload> { readonly eventType='plastisol-processing.v1.dipping.completed' }
export interface CuringStartedPayload { curingId:string;dippingId:string;ovenId:string;targetTempC?:number;targetDurationMin?:number;curingProfile?:string;startedAt:string }
export class CuringStartedEvent extends E<CuringStartedPayload> { readonly eventType='plastisol-processing.v1.curing.started' }
export interface CuringCompletedPayload { curingId:string;actualDurationMin?:number;maxTempReachedC?:number;tempProfileOk?:boolean;hardnessShoreA?:number;completedAt:string }
export class CuringCompletedEvent extends E<CuringCompletedPayload> { readonly eventType='plastisol-processing.v1.curing.completed' }
export interface BatchCompletedPayload { batchId:string;formulationId:string;productId:string;quantityProduced?:number;defectives?:number;firstPassYieldPercent?:number;materialUsageL?:number;avgGelThicknessMm?:number;avgHardnessShoreA?:number;completedAt:string;qualityStatus?:string }
export class BatchCompletedEvent extends E<BatchCompletedPayload> { readonly eventType='plastisol-processing.v1.batch.completed' }
export interface QCResultRecordedPayload { qcId:string;batchId:string;result:string;tests?:Array<{testType:string;passed:boolean;measured:number;specMin?:number;specMax?:number}>;notes?:string;testedAt:string;testedBy?:string }
export class QCResultRecordedEvent extends E<QCResultRecordedPayload> { readonly eventType='plastisol-processing.v1.qc.result.recorded' }
export interface ViscosityAdjustedPayload { formulationId:string;oldViscosityCp:number;newViscosityCp:number;adjustmentMethod?:string;additiveUsed?:string;quantityAddedL?:number;adjustedAt:string;adjustedBy?:string }
export class ViscosityAdjustedEvent extends E<ViscosityAdjustedPayload> { readonly eventType='plastisol-processing.v1.viscosity.adjusted' }
export interface CoatingSpecUpdatedPayload { specId:string;productId:string;changes?:Array<{field:string;oldValue:string;newValue:string}>;updatedAt:string;updatedBy?:string }
export class CoatingSpecUpdatedEvent extends E<CoatingSpecUpdatedPayload> { readonly eventType='plastisol-processing.v1.coating.spec.updated' }
