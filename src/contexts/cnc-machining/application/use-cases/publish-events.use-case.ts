import { v4 as uuidv4 } from 'uuid'
import { IEventPublisher } from '../../../../shared/application/ports/messaging'
import { EventEnvelope } from '../../../../shared/domain/events'
import * as E from '../../domain/events'
import * as S from '../../../../shared/domain/events/schemas/cnc-machining.schema'

function env<T>(e:{eventType:string;eventVersion:string;payload:T},ctx:string,aggId:string,aggType:string,c:{tenantId:string;userId:string;agentId?:string|null;correlationId?:string;causationId?:string|null}):EventEnvelope<T>{
  return {eventId:uuidv4(),eventType:e.eventType,eventVersion:e.eventVersion,timestamp:new Date().toISOString(),correlationId:c.correlationId??uuidv4(),causationId:c.causationId??null,tenantId:c.tenantId,source:{context:ctx,aggregateId:aggId,aggregateType:aggType},payload:e.payload,metadata:{userId:c.userId,agentId:c.agentId??null,channel:c.agentId?'agent':'api'}}
}
type C={tenantId:string;userId:string;agentId?:string|null;correlationId?:string;causationId?:string|null}

export class PublishJobScheduled { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.JobScheduledPayload}){ const v=S.JobScheduledPayload.parse(c.payload); const e=env(new E.JobScheduledEvent(v),'cnc-machining',v.jobId,'Job',c); await this.p.publish(e); return e } }
export class PublishNCProgramUploaded { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.NCProgramUploadedPayload}){ const v=S.NCProgramUploadedPayload.parse(c.payload); const e=env(new E.NCProgramUploadedEvent(v),'cnc-machining',v.programId,'NCProgram',c); await this.p.publish(e); return e } }
export class PublishMachiningStarted { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MachiningStartedPayload}){ const v=S.MachiningStartedPayload.parse(c.payload); const e=env(new E.MachiningStartedEvent(v),'cnc-machining',v.jobId,'Job',c); await this.p.publish(e); return e } }
export class PublishMachiningCompleted { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MachiningCompletedPayload}){ const v=S.MachiningCompletedPayload.parse(c.payload); const e=env(new E.MachiningCompletedEvent(v),'cnc-machining',v.jobId,'Job',c); await this.p.publish(e); return e } }
export class PublishToolWearAlert { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.ToolWearAlertPayload}){ const v=S.ToolWearAlertPayload.parse(c.payload); const e=env(new E.ToolWearAlertEvent(v),'cnc-machining',v.toolId,'Tool',c); await this.p.publish(e); return e } }
export class PublishToolReplaced { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.ToolReplacedPayload}){ const v=S.ToolReplacedPayload.parse(c.payload); const e=env(new E.ToolReplacedEvent(v),'cnc-machining',v.toolId,'Tool',c); await this.p.publish(e); return e } }
export class PublishMachineDowntimeStarted { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MachineDowntimeStartedPayload}){ const v=S.MachineDowntimeStartedPayload.parse(c.payload); const e=env(new E.MachineDowntimeStartedEvent(v),'cnc-machining',v.downtimeId,'Downtime',c); await this.p.publish(e); return e } }
export class PublishMachineDowntimeEnded { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.MachineDowntimeEndedPayload}){ const v=S.MachineDowntimeEndedPayload.parse(c.payload); const e=env(new E.MachineDowntimeEndedEvent(v),'cnc-machining',v.downtimeId,'Downtime',c); await this.p.publish(e); return e } }
export class PublishQualityInspectionPassed { constructor(private p:IEventPublisher){} async execute(c:C&{payload:E.QualityInspectionPassedPayload}){ const v=S.QualityInspectionPassedPayload.parse(c.payload); const e=env(new E.QualityInspectionPassedEvent(v),'cnc-machining',v.inspectionId,'Inspection',c); await this.p.publish(e); return e } }
