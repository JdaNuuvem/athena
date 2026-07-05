import { gql } from '@apollo/client'

export const KPI_SUMMARY = gql`
  query KpiSummary {
    kpiSummary {
      totalOrders
      totalRevenue
      totalProduction
      defectRate
      oee
      shippingOnTimeRate
    }
  }
`

export const ORDERS_BY_STATUS = gql`
  query OrdersByStatus {
    ordersByStatus {
      status
      count
    }
  }
`

export const RECENT_ORDERS = gql`
  query RecentOrders {
    orders {
      id
      channel
      status
      totals {
        grandTotal
        currency
      }
      customer {
        id
        name
        tier
      }
      createdAt
    }
  }
`

export const ORDERS = gql`
  query Orders($status: String, $channel: String) {
    orders(status: $status, channel: $channel) {
      id
      channel
      status
      customer {
        id
        name
        tier
      }
      items {
        sku
        quantity
        unitPrice
        total
      }
      totals {
        subtotal
        shipping
        discount
        grandTotal
        currency
      }
      fulfillment {
        id
        status
        trackingCode
        carrierId
        shippedAt
        deliveredAt
      }
      shippingAddress
      createdAt
      updatedAt
    }
  }
`

export const ORDER_DETAIL = gql`
  query OrderDetail($id: String!) {
    order(id: $id) {
      id
      channel
      status
      customer {
        id
        name
        email
        phone
        tier
      }
      items {
        sku
        quantity
        unitPrice
        total
      }
      totals {
        subtotal
        shipping
        discount
        grandTotal
        currency
      }
      fulfillment {
        id
        status
        trackingCode
        carrierId
        shippedAt
        deliveredAt
      }
      shippingAddress
      createdAt
      updatedAt
    }
  }
`

export const STOCK_ITEMS = gql`
  query StockItems {
    stockItems {
      id
      sku
      warehouseId
      quantity
      reserved
      available
      reorderPoint
      safetyStock
      updatedAt
    }
  }
`

export const STOCK_MOVEMENTS = gql`
  query StockMovements {
    stockMovements {
      id
      type
      sku
      warehouseId
      quantity
      reference
      timestamp
    }
  }
`

export const CUSTOMERS = gql`
  query Customers {
    customers {
      id
      name
      email
      phone
      channelOrigin
      tier
      loyaltyPoints
      totalOrders
      lifetimeValue
      registeredAt
    }
  }
`

export const CUSTOMER_SEGMENTS = gql`
  query CustomerSegments {
    customerSegments {
      id
      customerId
      segment
      recency
      frequency
      monetary
      totalScore
      segmentedAt
    }
  }
`

export const PRODUCTION_RUNS = gql`
  query ProductionRuns {
    productionRuns {
      id
      machineId
      moldId
      productId
      status
      totalCycles
      totalPartsProduced
      totalDefectives
      totalMaterialKg
      oee
      qualityChecks {
        id
        runId
        passed
        defects
        createdAt
      }
      startedAt
      completedAt
    }
  }
`

export const MOLDS = gql`
  query Molds {
    molds {
      id
      moldCode
      productId
      cavityCount
      steelType
      cycleLife
      currentCycles
      status
      installedMachineId
      createdAt
    }
  }
`

export const SHIPMENTS = gql`
  query Shipments {
    shipments {
      id
      orderId
      carrier
      trackingCode
      status
      shippingCost
      estimatedDeliveryDate
      deliveredAt
      createdAt
      updatedAt
    }
  }
`

export const SHOPEE_PRODUCTS = gql`
  query ShopeeProducts {
    shopeeProducts {
      itemId
      itemSku
      itemName
      itemStatus
      stock
      reservedStock
      hasModel
      price
      lastSyncedAt
    }
  }
`

export const SYNC_SHOPEE = gql`
  mutation SyncShopeeStock {
    syncShopeeStock {
      count
      errors
    }
  }
`
