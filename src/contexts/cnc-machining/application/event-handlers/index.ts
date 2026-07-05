import { BaseEventHandler } from '../../../../shared/domain/events/base-event-handler'; import { EventEnvelope } from '../../../../shared/domain/events'
export class OnMoldDesigned extends BaseEventHandler { readonly eventType='mold-making.v1.mold.designed'; protected async apply(e:EventEnvelope){void e} }
export class OnMoldFabricationCompleted extends BaseEventHandler { readonly eventType='mold-making.v1.mold.fabrication.completed'; protected async apply(e:EventEnvelope){void e} }
export class OnMoldInstalled extends BaseEventHandler { readonly eventType='mold-making.v1.mold.installed'; protected async apply(e:EventEnvelope){void e} }
