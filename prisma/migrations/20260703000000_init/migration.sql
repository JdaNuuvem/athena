-- CreateTable
CREATE TABLE "Agent" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "context" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'idle',
    "systemPrompt" TEXT NOT NULL,
    "modelProvider" TEXT NOT NULL DEFAULT 'openai',
    "modelName" TEXT NOT NULL DEFAULT 'gpt-4o-mini',
    "temperature" DOUBLE PRECISION NOT NULL DEFAULT 0.3,
    "maxTokens" INTEGER NOT NULL DEFAULT 4096,
    "startedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Agent_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "EpisodicEvent" (
    "id" TEXT NOT NULL DEFAULT gen_random_uuid(),
    "agentId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "data" JSONB NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "EpisodicEvent_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "EpisodicEvent_agentId_timestamp_idx" ON "EpisodicEvent"("agentId", "timestamp");
CREATE INDEX "EpisodicEvent_type_idx" ON "EpisodicEvent"("type");

CREATE TABLE "AuditTrail" (
    "id" TEXT NOT NULL DEFAULT gen_random_uuid(),
    "agentId" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "input" JSONB,
    "output" JSONB,
    "error" TEXT,
    "duration" INTEGER NOT NULL DEFAULT 0,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "AuditTrail_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "AuditTrail_agentId_timestamp_idx" ON "AuditTrail"("agentId", "timestamp");

CREATE TABLE "Task" (
    "id" TEXT NOT NULL DEFAULT gen_random_uuid(),
    "agentId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "input" JSONB NOT NULL,
    "output" JSONB,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "priority" INTEGER NOT NULL DEFAULT 0,
    "retries" INTEGER NOT NULL DEFAULT 0,
    "maxRetries" INTEGER NOT NULL DEFAULT 3,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Task_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "Task_agentId_status_idx" ON "Task"("agentId", "status");
CREATE INDEX "Task_status_idx" ON "Task"("status");

CREATE TABLE "Workflow" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "steps" JSONB NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'running',
    "onError" TEXT NOT NULL DEFAULT 'stop',
    "maxRetries" INTEGER NOT NULL DEFAULT 3,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),
    CONSTRAINT "Workflow_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "WorkflowExecution" (
    "id" TEXT NOT NULL DEFAULT gen_random_uuid(),
    "workflowId" TEXT NOT NULL,
    "stepId" TEXT NOT NULL,
    "agentId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "input" JSONB NOT NULL,
    "output" JSONB,
    "error" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    CONSTRAINT "WorkflowExecution_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "WorkflowExecution_workflowId_idx" ON "WorkflowExecution"("workflowId");

CREATE TABLE "Product" (
    "id" TEXT NOT NULL,
    "sku" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "category" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "revision" TEXT NOT NULL DEFAULT '1.0',
    "cadFileHash" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Product_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "Product_sku_key" ON "Product"("sku");
CREATE INDEX "Product_status_idx" ON "Product"("status");
CREATE INDEX "Product_category_idx" ON "Product"("category");

CREATE TABLE "BOM" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "revision" TEXT NOT NULL DEFAULT '1.0',
    "components" JSONB NOT NULL,
    "validated" BOOLEAN NOT NULL DEFAULT false,
    "validatedAt" TIMESTAMP(3),
    "validatedBy" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "BOM_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "BOM_productId_key" ON "BOM"("productId");

CREATE TABLE "Component" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL,
    "materialSpec" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Component_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "Component_productId_idx" ON "Component"("productId");

CREATE TABLE "Revision" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "revisionNumber" TEXT NOT NULL,
    "changes" TEXT,
    "approvedBy" TEXT,
    "approvedAt" TIMESTAMP(3),
    "cadFileHash" TEXT,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Revision_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "Revision_productId_idx" ON "Revision"("productId");
CREATE INDEX "Revision_status_idx" ON "Revision"("status");

CREATE TABLE "StockItem" (
    "id" TEXT NOT NULL,
    "sku" TEXT NOT NULL,
    "warehouseId" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL DEFAULT 0,
    "reorderPoint" INTEGER NOT NULL DEFAULT 10,
    "reservedQty" INTEGER NOT NULL DEFAULT 0,
    "unit" TEXT NOT NULL DEFAULT 'units',
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "StockItem_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "StockItem_sku_warehouseId_key" ON "StockItem"("sku", "warehouseId");
CREATE INDEX "StockItem_sku_idx" ON "StockItem"("sku");
CREATE INDEX "StockItem_warehouseId_idx" ON "StockItem"("warehouseId");

CREATE TABLE "Warehouse" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "state" TEXT NOT NULL,
    "active" BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT "Warehouse_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "Warehouse_active_idx" ON "Warehouse"("active");

CREATE TABLE "StockMovement" (
    "id" TEXT NOT NULL DEFAULT gen_random_uuid(),
    "sku" TEXT NOT NULL,
    "warehouseId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL,
    "referenceId" TEXT,
    "reason" TEXT,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "StockMovement_sku_warehouseId_idx" ON "StockMovement"("sku", "warehouseId");
CREATE INDEX "StockMovement_type_idx" ON "StockMovement"("type");
CREATE INDEX "StockMovement_timestamp_idx" ON "StockMovement"("timestamp");

CREATE TABLE "Order" (
    "id" TEXT NOT NULL,
    "customerId" TEXT NOT NULL,
    "channel" TEXT NOT NULL DEFAULT 'manual',
    "status" TEXT NOT NULL DEFAULT 'draft',
    "totalAmount" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "shippingAddress" JSONB,
    "correlationId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Order_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "Order_customerId_idx" ON "Order"("customerId");
CREATE INDEX "Order_status_idx" ON "Order"("status");
CREATE INDEX "Order_channel_idx" ON "Order"("channel");

CREATE TABLE "OrderLine" (
    "id" TEXT NOT NULL DEFAULT gen_random_uuid(),
    "orderId" TEXT NOT NULL,
    "sku" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL DEFAULT 1,
    "unitPrice" DOUBLE PRECISION NOT NULL DEFAULT 0,
    CONSTRAINT "OrderLine_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "OrderLine_orderId_idx" ON "OrderLine"("orderId");

CREATE TABLE "Fulfillment" (
    "id" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "type" TEXT NOT NULL DEFAULT 'warehouse',
    "centerId" TEXT,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "estimatedDays" INTEGER NOT NULL DEFAULT 3,
    "trackingCode" TEXT,
    "carrierId" TEXT,
    "shippedAt" TIMESTAMP(3),
    "deliveredAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Fulfillment_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "Fulfillment_orderId_key" ON "Fulfillment"("orderId");
CREATE INDEX "Fulfillment_status_idx" ON "Fulfillment"("status");

CREATE TABLE "Return" (
    "id" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "reason" TEXT NOT NULL,
    "items" JSONB NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'requested',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Return_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "Return_status_idx" ON "Return"("status");

CREATE TABLE "Customer" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "phone" TEXT,
    "document" TEXT,
    "tier" TEXT NOT NULL DEFAULT 'bronze',
    "loyaltyPoints" INTEGER NOT NULL DEFAULT 0,
    "rfmScore" JSONB,
    "tags" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Customer_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "Customer_email_key" ON "Customer"("email");
CREATE INDEX "Customer_tier_idx" ON "Customer"("tier");

CREATE TABLE "Shipment" (
    "id" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "carrierId" TEXT NOT NULL,
    "trackingCode" TEXT NOT NULL,
    "cost" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "estimatedDays" INTEGER NOT NULL DEFAULT 3,
    "status" TEXT NOT NULL DEFAULT 'created',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Shipment_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "Shipment_orderId_key" ON "Shipment"("orderId");
CREATE INDEX "Shipment_status_idx" ON "Shipment"("status");

CREATE TABLE "PriceListItem" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "price" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "cost" DOUBLE PRECISION,
    "currency" TEXT NOT NULL DEFAULT 'BRL',
    "active" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "PriceListItem_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "PriceListItem_productId_key" ON "PriceListItem"("productId");

CREATE TABLE "ProductCard" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "categoryId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "description" TEXT,
    "images" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "videos" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "attributes" JSONB DEFAULT '{}',
    "seoTitle" TEXT,
    "seoDescription" TEXT,
    "seoKeywords" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "variants" JSONB DEFAULT '[]',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "ProductCard_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ProductCard_productId_key" ON "ProductCard"("productId");
CREATE INDEX "ProductCard_categoryId_idx" ON "ProductCard"("categoryId");
CREATE INDEX "ProductCard_status_idx" ON "ProductCard"("status");

CREATE TABLE "Mold" (
    "id" TEXT NOT NULL,
    "moldCode" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'design',
    "cavities" INTEGER NOT NULL DEFAULT 1,
    "steelType" TEXT NOT NULL,
    "cycleLife" INTEGER NOT NULL,
    "coolingConfig" TEXT,
    "ejectorType" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Mold_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "Mold_moldCode_key" ON "Mold"("moldCode");
CREATE INDEX "Mold_status_idx" ON "Mold"("status");
CREATE INDEX "Mold_productId_idx" ON "Mold"("productId");

CREATE TABLE "MaintenanceRecord" (
    "id" TEXT NOT NULL,
    "moldId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "cost" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "performedAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "MaintenanceRecord_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "CNCJob" (
    "id" TEXT NOT NULL,
    "partNumber" TEXT NOT NULL,
    "estimatedHours" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "priority" INTEGER NOT NULL DEFAULT 1,
    "status" TEXT NOT NULL DEFAULT 'scheduled',
    "machineId" TEXT,
    "programId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "CNCJob_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "CNCJob_status_idx" ON "CNCJob"("status");

CREATE TABLE "ProductionRun" (
    "id" TEXT NOT NULL,
    "moldId" TEXT NOT NULL,
    "machineId" TEXT NOT NULL,
    "productSku" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'scheduled',
    "targetQuantity" INTEGER NOT NULL DEFAULT 0,
    "producedQuantity" INTEGER NOT NULL DEFAULT 0,
    "scrapQuantity" INTEGER NOT NULL DEFAULT 0,
    "defectRate" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "ProductionRun_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "ProductionRun_status_idx" ON "ProductionRun"("status");
CREATE INDEX "ProductionRun_moldId_idx" ON "ProductionRun"("moldId");

CREATE TABLE "QualityCheck" (
    "id" TEXT NOT NULL,
    "runId" TEXT NOT NULL,
    "passed" BOOLEAN NOT NULL DEFAULT false,
    "defects" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "parameters" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "QualityCheck_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "PlastisolFormulation" (
    "id" TEXT NOT NULL,
    "formulaCode" TEXT NOT NULL,
    "components" JSONB NOT NULL,
    "viscosity" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "gelTemperature" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "curingProfile" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "PlastisolFormulation_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "PlastisolFormulation_formulaCode_key" ON "PlastisolFormulation"("formulaCode");

CREATE TABLE "CuringCycle" (
    "id" TEXT NOT NULL,
    "formulationId" TEXT NOT NULL,
    "lineId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'started',
    "targetTemperature" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "targetDuration" INTEGER NOT NULL DEFAULT 0,
    "actualTemperature" DOUBLE PRECISION,
    "actualDuration" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "CuringCycle_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "ChannelListing" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "channel" TEXT NOT NULL,
    "price" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "stock" INTEGER NOT NULL DEFAULT 0,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "channelSku" TEXT,
    "lastSyncAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "ChannelListing_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ChannelListing_productId_channel_key" ON "ChannelListing"("productId", "channel");
CREATE INDEX "ChannelListing_channel_idx" ON "ChannelListing"("channel");

CREATE TABLE "SaleTransaction" (
    "id" TEXT NOT NULL,
    "storeId" TEXT NOT NULL,
    "items" JSONB NOT NULL,
    "totalAmount" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "paymentMethod" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "SaleTransaction_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "Store" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "state" TEXT NOT NULL,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Store_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "ChatOrder" (
    "id" TEXT NOT NULL,
    "telegramUserId" TEXT NOT NULL,
    "items" JSONB NOT NULL,
    "totalAmount" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "status" TEXT NOT NULL DEFAULT 'browsing',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "ChatOrder_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "ChatSession" (
    "id" TEXT NOT NULL,
    "telegramUserId" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "state" JSONB DEFAULT '{}',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "ChatSession_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ChatSession_telegramUserId_key" ON "ChatSession"("telegramUserId");

CREATE TABLE "Report" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "period" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'generating',
    "data" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Report_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "Metric" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "value" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "unit" TEXT NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Metric_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "Metric_name_key" ON "Metric"("name");

CREATE TABLE "Insight" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "context" TEXT NOT NULL,
    "severity" TEXT NOT NULL DEFAULT 'info',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Insight_pkey" PRIMARY KEY ("id")
);

-- Foreign Keys
ALTER TABLE "EpisodicEvent" ADD CONSTRAINT "EpisodicEvent_agentId_fkey" FOREIGN KEY ("agentId") REFERENCES "Agent"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "AuditTrail" ADD CONSTRAINT "AuditTrail_agentId_fkey" FOREIGN KEY ("agentId") REFERENCES "Agent"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Task" ADD CONSTRAINT "Task_agentId_fkey" FOREIGN KEY ("agentId") REFERENCES "Agent"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "WorkflowExecution" ADD CONSTRAINT "WorkflowExecution_workflowId_fkey" FOREIGN KEY ("workflowId") REFERENCES "Workflow"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "BOM" ADD CONSTRAINT "BOM_productId_fkey" FOREIGN KEY ("productId") REFERENCES "Product"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Component" ADD CONSTRAINT "Component_productId_fkey" FOREIGN KEY ("productId") REFERENCES "Product"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Revision" ADD CONSTRAINT "Revision_productId_fkey" FOREIGN KEY ("productId") REFERENCES "Product"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "OrderLine" ADD CONSTRAINT "OrderLine_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "Order"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Fulfillment" ADD CONSTRAINT "Fulfillment_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "Order"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Return" ADD CONSTRAINT "Return_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "Order"("id") ON DELETE CASCADE ON UPDATE CASCADE;
