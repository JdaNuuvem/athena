import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'; import { EventEnvelope } from '../../../../shared/domain/events'
export class OnMoldInstalled extends BaseEventHandler { readonly eventType='mold-making.v1.mold.installed'; protected async apply(e:EventEnvelope){void e} }
export class OnMachiningCompleted extends BaseEventHandler { readonly eventType='cnc-machining.v1.machining.completed'; protected async apply(e:EventEnvelope){void e} }
