import { v4 as uuidv4 } from 'uuid'
import { IEventPublisher } from '../../../../shared/application/ports/messaging'
import { EventEnvelope } from '../../../../shared/domain/events'
import * as E from '../../domain/events'
import * as S from '../../../../shared/domain/events/schemas/mold-making.schema'

function env<T>(e: {eventType:string;eventVersion:string;payload:T}, ctx:string, aggId:string, aggType:string, c: {tenantId:string;userId:string;agentId?:string|null;correlationId?:string;causationId?:string|null}): EventEnvelope<T> {
  return {eventId:uuidv4(),eventType:e.eventType,eventVersion:e.eventVersion,timestamp:new Date().toISOString(),correlationId:c.correlationId??uuidv4(),causationId:c.causationId??null,tenantId:c.tenantId,source:{context:ctx,aggregateId:aggId,aggregateType:aggType},payload:e.payload,metadata:{userId:c.userId,agentId:c.agentId??null,channel:c.agentId?'agent':'api'}}
}

type C = {tenantId:string;userId:string;agentId?:string|null;correlationId?:string;causationId?:string|null}

export class PublishMoldDesigned { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MoldDesignedPayload}){ const v=S.MoldDesignedPayload.parse(c.payload); const e=env(new E.MoldDesignedEvent(v),'mold-making',v.moldId,'Mold',c); await this.p.publish(e); return e } }
export class PublishMoldFabricationCompleted { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MoldFabricationCompletedPayload}){ const v=S.MoldFabricationCompletedPayload.parse(c.payload); const e=env(new E.MoldFabricationCompletedEvent(v),'mold-making',v.moldId,'Mold',c); await this.p.publish(e); return e } }
export class PublishMoldDelivered { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MoldDeliveredPayload}){ const v=S.MoldDeliveredPayload.parse(c.payload); const e=env(new E.MoldDeliveredEvent(v),'mold-making',v.moldId,'Mold',c); await this.p.publish(e); return e } }
export class PublishMoldInstalled { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MoldInstalledPayload}){ const v=S.MoldInstalledPayload.parse(c.payload); const e=env(new E.MoldInstalledEvent(v),'mold-making',v.moldId,'Mold',c); await this.p.publish(e); return e } }
export class PublishMaintenanceScheduled { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MaintenanceScheduledPayload}){ const v=S.MaintenanceScheduledPayload.parse(c.payload); const e=env(new E.MaintenanceScheduledEvent(v),'mold-making',v.maintenanceId,'Maintenance',c); await this.p.publish(e); return e } }
export class PublishMaintenancePerformed { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MaintenancePerformedPayload}){ const v=S.MaintenancePerformedPayload.parse(c.payload); const e=env(new E.MaintenancePerformedEvent(v),'mold-making',v.maintenanceId,'Maintenance',c); await this.p.publish(e); return e } }
export class PublishCycleLimitReached { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.CycleLimitReachedPayload}){ const v=S.CycleLimitReachedPayload.parse(c.payload); const e=env(new E.CycleLimitReachedEvent(v),'mold-making',v.moldId,'Mold',c); await this.p.publish(e); return e } }
export class PublishMoldFailureDetected { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MoldFailureDetectedPayload}){ const v=S.MoldFailureDetectedPayload.parse(c.payload); const e=env(new E.MoldFailureDetectedEvent(v),'mold-making',v.moldId,'Mold',c); await this.p.publish(e); return e } }
export class PublishMoldInspectionCompleted { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MoldInspectionCompletedPayload}){ const v=S.MoldInspectionCompletedPayload.parse(c.payload); const e=env(new E.MoldInspectionCompletedEvent(v),'mold-making',v.inspectionId,'Inspection',c); await this.p.publish(e); return e } }
