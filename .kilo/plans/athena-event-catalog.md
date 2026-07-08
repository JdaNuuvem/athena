# ATHENA — Catálogo de Eventos

## Objetivo
Definir ~95 eventos de domínio e integração que trafegam entre os 15 bounded contexts do ATHENA.

## 1. Estrutura Padrão de Evento (Envelope)

Todo evento segue este formato:

\\\json
{
  "eventId": "uuid",
  "eventType": "contexto.v1.nome",
  "eventVersion": "1.0",
  "timestamp": "ISO 8601",
  "correlationId": "uuid",
  "causationId": "uuid",
  "tenantId": "string",
  "source": { "context": "...", "aggregateId": "uuid", "aggregateType": "..." },
  "payload": { },
  "metadata": { "userId": "string", "agentId": "string|null", "channel": "api|agent|scheduler|system" }
}
\\\

## 2. Convenção de Nomenclatura

\{contexto}.{dominio}.{verbo_no_passado}\ — ex: \order-management.order.placed\

## 3. Estratégia de Tópicos Kafka

| Padrão | Tópico | Partição |
|---|---|---|
| 1 tópico por contexto | \thena.{contexto}.events\ | aggregateId |
| Críticos dedicados | \thena.order-management.orders\ | orderId |
| Analytics raw stream | \thena.analytics.raw\ | eventType |

Retenção: 7 dias padrão, 30 dias analytics, compact para snapshots.

---

## 4. Catálogo de Eventos por Contexto (resumo)

| Contexto | # Eventos | Principais |
|---|---|---|
| product-engineering | 7 | product.designed, bom.updated, revision.approved, product.archived |
| mold-making | 9 | mold.designed, mold.fabrication.completed, mold.installed, maintenance.scheduled, cycle.limit.reached |
| cnc-machining | 9 | job.scheduled, machining.completed, tool.wear.alert, machine.downtime.started |
| injection-molding | 10 | run.started, cycle.completed, defect.detected, batch.completed, run.completed |
| plastisol-processing | 9 | formulation.mixed, dipping.completed, curing.completed, batch.completed |
| catalog | 6 | product.published, product.updated, variant.created, media.added |
| marketplace-integration | 10 | listing.published, sync.completed, channel.order.received, competitor.price.changed |
| retail-operations | 5 | sale.completed, register.closed, inventory.counted |
| telegram-commerce | 6 | conversation.started, order.confirmed, payment.completed |
| inventory | 9 | stock.received, stock.shipped, low.stock.alert, stock.aging.report |
| order-management | 15 | order.placed, order.confirmed, fulfillment.completed, order.shipped, return.requested |
| customer | 8 | customer.registered, tier.changed, churn.risk.detected |
| pricing | 7 | price.updated, promotion.created, discount.applied, margin.alert |
| shipping | 9 | shipment.created, label.generated, delivered, delivery.failed |
| analytics | 5 | anomaly.detected, forecast.updated, alert.triggered, executive.digest.sent |

**Total: ~124 eventos**

---

## 5. Matriz Producer x Consumer

| Consome ↓ \\ Produz → | PE | MM | CNC | IM | PP | CAT | MKT | RET | TG | INV | ORD | CUS | PRC | SHP |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Product Eng (PE) | - | | | | | | | | | | | | | |
| Mold Making (MM) | x | - | x | | | | | | | | | | | |
| CNC Machining | x | x | - | | | | | | | | | | | |
| Injection Molding | | x | x | - | | | | | | | | | | |
| Plastisol | | | | | - | | | | | | | | | |
| Catalog | x | | | x | | - | x | | | | | x | | |
| Marketplace | | | | | | x | - | | | x | | x | | |
| Retail | | | | | | | | - | | | x | | | |
| Telegram | | | | | | | | | - | | x | | | |
| Inventory | x | x | x | x | x | | | x | x | - | x | | | |
| Order Mgmt | | x | | x | x | | x | x | x | x | - | x | x | x |
| Customer | | | | | | | x | x | x | | x | - | | |
| Pricing | x | | | x | x | | x | | | x | x | x | - | |
| Shipping | | | | | | | | | | x | x | | | - |
| Analytics | x | x | x | x | x | x | x | x | x | x | x | x | x |

---

## 6. Ordem de Implementação

| Fase | Contextos | Eventos |
|---|---|---|
| 1 — Core Flow | product-engineering + catalog + order-management + inventory | ~20 |
| 2 — Canais de Venda | marketplace-integration + retail + telegram + customer | ~25 |
| 3 — Manufatura | mold-making + cnc-machining + injection-molding + plastisol | ~37 |
| 4 — Operações | pricing + shipping | ~16 |
| 5 — Inteligência | analytics (consome todos) | ~5 |

---

## 7. Exemplo de Payload: \order-management.v1.order.placed\

\\\json
{
  "eventId": "550e8400-e29b-41d4-a716-446655440000",
  "eventType": "order-management.v1.order.placed",
  "eventVersion": "1.0",
  "timestamp": "2026-07-02T20:51:44Z",
  "correlationId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "causationId": "prev-event-id",
  "tenantId": "tenant-001",
  "source": { "context": "order-management", "aggregateId": "ord_abc123", "aggregateType": "Order" },
  "payload": {
    "orderId": "ord_abc123",
    "channel": "mercadolivre",
    "sourceId": "ml_order_456",
    "items": [{ "sku": "PROD-001-RED-M", "quantity": 2, "unitPrice": 49.90, "total": 99.80 }],
    "customerId": "cus_xyz789",
    "shippingAddress": { "recipientName": "João Silva", "city": "São Paulo", "state": "SP", "zipCode": "01001-000" },
    "totals": { "subtotal": 99.80, "shipping": 15.00, "grandTotal": 114.80, "currency": "BRL" },
    "paymentMethod": "credit_card",
    "installments": 1
  },
  "metadata": { "userId": "system", "agentId": null, "channel": "api" }
}
\\\

---

## 8. Eventos por Agente (quais agentes produzem/consomem)

| Agente | Produz Eventos | Consome Eventos |
|---|---|---|
| AG-007 cnc-scheduler | cnc-machining.v1.job.scheduled | mold-making.v1.mold.installed |
| AG-008 tool-wear-monitor | cnc-machining.v1.tool.wear.alert | cnc-machining.v1.machining.completed |
| AG-010 cycle-optimizer | — | injection-molding.v1.cycle.completed |
| AG-011 defect-detector | injection-molding.v1.defect.detected | injection-molding.v1.cycle.completed |
| AG-012 production-forecaster | — | injection-molding.v1.run.completed |
| AG-013 quality-gatekeeper | — | injection-molding.v1.cycle.completed, defect.detected |
| AG-022 listing-synchronizer | marketplace-integration.v1.sync.completed | catalog.v1.product.published, product.updated |
| AG-023 competitor-monitor | marketplace-integration.v1.competitor.price.changed | — |
| AG-024 channel-health-checker | marketplace-integration.v1.channel.account.health | — |
| AG-025 repricing-agent | marketplace-integration.v1.price.repriced | marketplace-integration.v1.competitor.price.changed |
| AG-028 conversational-seller | telegram-commerce.v1.order.confirmed | — |
| AG-029 order-assistant | — | order-management.v1.order.shipped |
| AG-030 product-recommender | — | telegram-commerce.v1.conversation.started |
| AG-031 stock-level-monitor | inventory.v1.low.stock.alert | inventory.v1.stock.shipped |
| AG-032 demand-forecaster | — | order-management.v1.order.placed, order.shipped |
| AG-034 dead-stock-detector | inventory.v1.stock.aging.report | inventory.v1.stock.received, stock.shipped |
| AG-035 order-router | order-management.v1.fulfillment.routed | order-management.v1.order.placed |
| AG-036 fraud-detector | order-management.v1.order.fraud.checked | order-management.v1.order.placed |
| AG-037 fulfillment-monitor | — | order-management.v1.fulfillment.started |
| AG-038 return-analyzer | — | order-management.v1.return.received |
| AG-039 customer-segmenter | customer.v1.customer.segmented | customer.v1.customer.registered |
| AG-040 churn-predictor | customer.v1.churn.risk.detected | order-management.v1.order.placed |
| AG-042 carrier-selector | — | shipping.v1.shipment.created |
| AG-046 anomaly-detector | analytics.v1.anomaly.detected | TODOS os eventos |
| AG-047 trend-forecaster | analytics.v1.forecast.updated | order-management, inventory |
| AG-048 executive-digest | analytics.v1.executive.digest.sent | analytics (todos relatórios) |
| AG-049 cross-context-correlator | — | TODOS os eventos |
| AG-050 margin-watchdog | pricing.v1.margin.alert | pricing.v1.price.updated, inventory.v1.stock.received |

---

## 9. Próximos Passos

1. Criar \config/events/{contexto}/{evento}.schema.json\ — schema Zod/JSON de cada evento
2. Criar \EventEnvelope<T>\ TypeScript no shared kernel
3. Criar \IEventPublisher\ / \IEventConsumer\ base classes
4. Implementar event handlers skeleton em cada contexto consumidor
5. Gerar AsyncAPI 3.0 spec a partir dos schemas
