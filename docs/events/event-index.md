# ATHENA Event Index

Generated: 2026-07-03T03:11:13.250Z

| # | Event Type | Context | Payload Required Fields |
|---|---|---|---|
| 1 | `alert.triggered` | analytics | alertId, title, severity, triggeredAt |
| 2 | `anomaly.detected` | analytics | anomalyId, metric, detectedAt |
| 3 | `executive.digest.sent` | analytics | digestId, type, sentAt |
| 4 | `forecast.updated` | analytics | forecastId, metric, generatedAt |
| 5 | `trend.analyzed` | analytics | trendId, context, metric, analyzedAt |
| 6 | `media.added` | catalog | mediaId, productId, type, url |
| 7 | `product.published` | catalog | productId, title, status |
| 8 | `product.updated` | catalog | productId, changedFields |
| 9 | `variant.created` | catalog | variantId, productId, sku, attributes |
| 10 | `job.scheduled` | cnc-machining | jobId, machineId, programId, scheduledAt |
| 11 | `machine.downtime.ended` | cnc-machining | downtimeId, machineId, endedAt |
| 12 | `machine.downtime.started` | cnc-machining | downtimeId, machineId, reason, startedAt |
| 13 | `machining.completed` | cnc-machining | jobId, machineId, completedAt |
| 14 | `machining.started` | cnc-machining | jobId, machineId, startedAt |
| 15 | `program.uploaded` | cnc-machining | programId, machineId, fileName, uploadedAt |
| 16 | `quality.inspection.passed` | cnc-machining | inspectionId, jobId, inspectedAt |
| 17 | `tool.replaced` | cnc-machining | toolId, machineId, replacedAt |
| 18 | `tool.wear.alert` | cnc-machining | toolId, machineId, wearMicrons, thresholdMicrons, detectedAt |
| 19 | `churn.risk.detected` | customer | customerId, riskScore, detectedAt |
| 20 | `customer.registered` | customer | customerId, name, email, registeredAt |
| 21 | `customer.segmented` | customer | customerId, segment, segmentedAt |
| 22 | `tier.changed` | customer | customerId, previousTier, newTier, changedAt |
| 23 | `batch.completed` | injection-molding | batchId, runId, productId, completedAt |
| 24 | `cycle.completed` | injection-molding | cycleId, runId, machineId, cycleNumber, completedAt |
| 25 | `defect.detected` | injection-molding | defectId, runId, cycleId, defectType, detectedAt |
| 26 | `machine.stopped` | injection-molding | stopId, machineId, runId, reason, stoppedAt |
| 27 | `mold.change.completed` | injection-molding | changeId, machineId, oldMoldId, newMoldId, completedAt |
| 28 | `parameter.changed` | injection-molding | changeId, runId, machineId, changes, changedAt |
| 29 | `quality.check.passed` | injection-molding | checkId, batchId, checkedAt |
| 30 | `run.completed` | injection-molding | runId, machineId, moldId, completedAt |
| 31 | `run.started` | injection-molding | runId, machineId, moldId, productId, startedAt |
| 32 | `scrap.recorded` | injection-molding | scrapId, runId, productId, quantity, reason, recordedAt |
| 33 | `low.stock.alert` | inventory | sku, warehouseId, currentQuantity, reorderPoint, triggeredAt |
| 34 | `stock.adjusted` | inventory | adjustmentId, warehouseId, items, reason, adjustedAt |
| 35 | `stock.received` | inventory | movementId, warehouseId, items, receivedAt |
| 36 | `stock.reserved` | inventory | reservationId, orderId, items, reservedAt |
| 37 | `stock.shipped` | inventory | movementId, orderId, warehouseId, items, shippedAt |
| 38 | `channel.account.health` | marketplace-integration | channelAccountId, channel, checkedAt |
| 39 | `channel.order.received` | marketplace-integration | channelOrderId, channel, items, customer, totals, receivedAt |
| 40 | `competitor.price.changed` | marketplace-integration | sku, channel, competitorId, newPrice, detectedAt |
| 41 | `listing.published` | marketplace-integration | listingId, channel, productId, channelSku, publishedAt |
| 42 | `price.repriced` | marketplace-integration | listingId, channel, sku, oldPrice, newPrice, repricedAt |
| 43 | `sync.completed` | marketplace-integration | syncId, channel, syncType, completedAt |
| 44 | `cycle.limit.reached` | mold-making | moldId, currentCycles, maxCycles, detectedAt |
| 45 | `maintenance.performed` | mold-making | maintenanceId, moldId, performedAt |
| 46 | `maintenance.scheduled` | mold-making | maintenanceId, moldId, scheduledDate, type |
| 47 | `mold.delivered` | mold-making | moldId, deliveredTo, deliveredAt |
| 48 | `mold.designed` | mold-making | moldId, productId, cavityCount, steelType, designedAt |
| 49 | `mold.fabrication.completed` | mold-making | moldId, completedAt |
| 50 | `mold.failure.detected` | mold-making | moldId, failureType, detectedAt |
| 51 | `mold.inspection.completed` | mold-making | inspectionId, moldId, result, inspectedAt |
| 52 | `mold.installed` | mold-making | moldId, machineId, installedAt |
| 53 | `fulfillment.completed` | order-management | fulfillmentId, orderId, warehouseId, completedAt |
| 54 | `fulfillment.routed` | order-management | orderId, warehouseId, routedAt |
| 55 | `order.confirmed` | order-management | orderId, confirmedAt |
| 56 | `order.delivered` | order-management | orderId, deliveredAt |
| 57 | `order.placed` | order-management | orderId, channel, items, customerId, totals |
| 58 | `order.shipped` | order-management | orderId, carrierId, trackingCode, shippedAt |
| 59 | `return.requested` | order-management | returnId, orderId, reason, requestedAt |
| 60 | `batch.completed` | plastisol-processing | batchId, formulationId, productId, completedAt |
| 61 | `coating.spec.updated` | plastisol-processing | specId, productId, updatedAt |
| 62 | `curing.completed` | plastisol-processing | curingId, completedAt |
| 63 | `curing.started` | plastisol-processing | curingId, dippingId, ovenId, startedAt |
| 64 | `dipping.completed` | plastisol-processing | dippingId, completedAt |
| 65 | `dipping.started` | plastisol-processing | dippingId, formulationId, lineId, productId, quantity, startedAt |
| 66 | `formulation.mixed` | plastisol-processing | formulationId, productId, batchSizeL, mixedAt |
| 67 | `qc.result.recorded` | plastisol-processing | qcId, batchId, result, testedAt |
| 68 | `viscosity.adjusted` | plastisol-processing | formulationId, oldViscosityCp, newViscosityCp, adjustedAt |
| 69 | `discount.applied` | pricing | discountId, orderId, amount, appliedAt |
| 70 | `elasticity.analyzed` | pricing | analysisId, productId, coefficient, analyzedAt |
| 71 | `margin.alert` | pricing | alertId, productId, currentMarginPercent, thresholdPercent, triggeredAt |
| 72 | `price.rule.updated` | pricing | ruleId, updatedAt |
| 73 | `price.updated` | pricing | priceId, productId, newPrice, updatedAt |
| 74 | `promotion.created` | pricing | promotionId, name, type, startsAt, endsAt |
| 75 | `promotion.expired` | pricing | promotionId, expiredAt |
| 76 | `bom.updated` | product-engineering | bomId, productId, components |
| 77 | `product.archived` | product-engineering | productId, reason |
| 78 | `product.designed` | product-engineering | productId, sku, name, category, materials |
| 79 | `revision.approved` | product-engineering | revisionId, productId, revisionNumber, approvedBy |
| 80 | `inventory.counted` | retail-operations | countId, storeId, countedAt |
| 81 | `register.closed` | retail-operations | registerId, storeId, closedAt |
| 82 | `sale.completed` | retail-operations | saleId, storeId, items, totals, completedAt |
| 83 | `carrier.picked.up` | shipping | shipmentId, carrier, pickedUpAt |
| 84 | `carrier.selected` | shipping | shipmentId, carrier, cost, estimatedDays, selectedAt |
| 85 | `delivered` | shipping | shipmentId, deliveredAt |
| 86 | `delivery.failed` | shipping | shipmentId, reason, failedAt |
| 87 | `label.generated` | shipping | labelId, shipmentId, carrier, trackingCode, generatedAt |
| 88 | `rate.calculated` | shipping | rateId, shipmentId, calculatedAt |
| 89 | `return.label.generated` | shipping | returnLabelId, shipmentId, returnOrderId, trackingCode, generatedAt |
| 90 | `shipment.created` | shipping | shipmentId, orderId, items, createdAt |
| 91 | `tracking.updated` | shipping | shipmentId, trackingCode, status, location, updatedAt |
| 92 | `conversation.started` | telegram-commerce | chatId, telegramUserId, startedAt |
| 93 | `order.confirmed` | telegram-commerce | chatOrderId, telegramUserId, chatId, items, totals, confirmedAt |
| 94 | `payment.completed` | telegram-commerce | paymentId, chatOrderId, amount, method, completedAt |
