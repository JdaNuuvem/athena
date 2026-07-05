const typeDefs = /* GraphQL */ `
  type Query {
    # Health
    health: Health!

    # Orders
    orders(status: String, channel: String): [Order!]!
    order(id: String!): Order
    ordersByStatus: [OrderStatusCount!]!

    # Products
    products(status: String, category: String): [Product!]!
    product(id: String!): Product
    productBySku(sku: String!): Product

    # Catalog
    catalogEntries(status: String): [CatalogEntry!]!
    catalogEntry(productId: String!): CatalogEntry

    # Inventory
    stockItems(warehouseId: String): [StockItem!]!
    stockItem(sku: String!, warehouseId: String!): StockItem
    stockMovements(sku: String, type: String, limit: Int): [StockMovement!]!

    # Customers
    customers(tier: String): [Customer!]!
    customer(id: String!): Customer
    customerSegments(customerId: String): [CustomerSegment!]!

    # Shipping
    shipments(status: String): [Shipment!]!
    shipment(id: String!): Shipment
    trackingEvents(shipmentId: String): [TrackingEvent!]!

    # Manufacturing
    molds(status: String): [Mold!]!
    mold(id: String!): Mold
    productionRuns(status: String, moldId: String): [ProductionRun!]!
    cncJobs(status: String): [CNCJob!]!

    # Analytics / KPI
    kpiSummary: KPISummary!
    anomalies(severity: String, acknowledged: Boolean): [Anomaly!]!
  }

  type Health {
    status: String!
    timestamp: String!
    env: String!
    uptime: Float!
  }

  type Order {
    id: String!
    channel: String!
    customerId: String!
    customer: Customer!
    status: String!
    items: [OrderItem!]!
    totals: OrderTotals!
    fulfillment: FulfillmentDetail
    shippingAddress: JSON
    correlationId: String
    createdAt: String!
    updatedAt: String!
  }

  type FulfillmentDetail {
    id: String!
    orderId: String!
    type: String!
    centerId: String
    status: String!
    estimatedDays: Int!
    trackingCode: String
    carrierId: String
    shippedAt: String
    deliveredAt: String
    createdAt: String!
    updatedAt: String!
  }

  type OrderItem {
    sku: String!
    quantity: Int!
    unitPrice: Float!
    total: Float!
  }

  type OrderTotals {
    subtotal: Float!
    shipping: Float!
    discount: Float!
    grandTotal: Float!
    currency: String!
  }

  type OrderStatusCount {
    status: String!
    count: Int!
  }

  type Product {
    id: String!
    sku: String!
    name: String!
    description: String
    category: String!
    status: String!
    materials: [Material!]!
    dimensions: Dimensions
    bom: BOMDetail
    revisions: [RevisionDetail!]!
    createdAt: String!
  }

  type Material {
    materialId: String!
    name: String!
    type: String!
  }

  type Dimensions {
    lengthMm: Float!
    widthMm: Float!
    heightMm: Float!
    weightG: Float!
  }

  type BOMDetail {
    id: String!
    productId: String!
    revision: String!
    components: JSON!
    validated: Boolean!
    validatedAt: String
    validatedBy: String
    createdAt: String!
    updatedAt: String!
  }

  type RevisionDetail {
    id: String!
    productId: String!
    revisionNumber: String!
    changes: String
    approvedBy: String
    approvedAt: String
    cadFileHash: String
    status: String!
    createdAt: String!
  }

  type CatalogEntry {
    id: String!
    productId: String!
    sku: String!
    title: String!
    description: String!
    category: String!
    status: String!
    materials: [String!]!
    variants: [CatalogVariant!]!
    media: [CatalogMedia!]!
    createdAt: String!
    updatedAt: String!
  }

  type CatalogVariant {
    variantId: String!
    sku: String!
    attributes: JSON!
    price: Float!
    stockQuantity: Int!
  }

  type CatalogMedia {
    mediaId: String!
    type: String!
    url: String!
    isMain: Boolean!
  }

  type StockItem {
    id: String!
    sku: String!
    warehouseId: String!
    location: String!
    quantity: Int!
    reserved: Int!
    available: Int!
    reorderPoint: Int!
    safetyStock: Int!
    unitCost: Float!
    updatedAt: String!
  }

  type StockMovement {
    id: String!
    type: String!
    sku: String!
    warehouseId: String!
    quantity: Int!
    reference: String!
    timestamp: String!
  }

  type Customer {
    id: String!
    name: String!
    email: String!
    phone: String
    channelOrigin: String!
    tier: String!
    loyaltyPoints: Int!
    totalOrders: Int!
    lifetimeValue: Float!
    registeredAt: String!
  }

  type CustomerSegment {
    id: String!
    customerId: String!
    segment: String!
    recency: Int!
    frequency: Int!
    monetary: Float!
    totalScore: Int!
    segmentedAt: String!
  }

  type Shipment {
    id: String!
    orderId: String!
    carrier: String
    trackingCode: String
    status: String!
    shippingCost: Float
    estimatedDeliveryDate: String
    deliveredAt: String
    createdAt: String!
    updatedAt: String!
  }

  type TrackingEvent {
    id: String!
    shipmentId: String!
    trackingCode: String!
    status: String!
    statusDetail: String
    location: String!
    city: String
    state: String
    updatedAt: String!
  }

  type Mold {
    id: String!
    moldCode: String!
    productId: String!
    cavityCount: Int!
    steelType: String!
    cycleLife: Int!
    currentCycles: Int!
    status: String!
    installedMachineId: String
    createdAt: String!
  }

  type ProductionRun {
    id: String!
    machineId: String!
    moldId: String!
    productId: String!
    status: String!
    totalCycles: Int!
    totalPartsProduced: Int!
    totalDefectives: Int!
    totalMaterialKg: Float!
    oee: Float!
    qualityChecks: [QualityCheckDetail!]!
    startedAt: String!
    completedAt: String
  }

  type QualityCheckDetail {
    id: String!
    runId: String!
    passed: Boolean!
    defects: [String!]!
    parameters: JSON!
    createdAt: String!
  }

  type CNCJob {
    id: String!
    machineId: String!
    programId: String!
    materialType: String!
    status: String!
    partsProduced: Int!
    partsDefective: Int!
    scheduledAt: String!
    completedAt: String
  }

  type KPISummary {
    totalOrders: Int!
    totalRevenue: Float!
    totalProduction: Int!
    defectRate: Float!
    oee: Float!
    shippingOnTimeRate: Float!
  }

  type Anomaly {
    id: String!
    context: String!
    metric: String!
    deviationPercent: Float!
    severity: String!
    detectedAt: String!
    acknowledged: Boolean!
  }

  scalar JSON

  type Subscription {
    orderUpdated: Order!
    orderPlaced: Order!
    productionProgress(runId: String): ProductionRun!
    inventoryChanged(warehouseId: String): StockItem!
    moldStatusChanged(moldId: String): Mold!
    kpiSnapshot: KPISummary!
    anomalyAlert(severity: String): Anomaly!
    shipmentStatusChanged(shipmentId: String): Shipment!
  }
`

export { typeDefs }
