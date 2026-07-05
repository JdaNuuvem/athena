import { gql } from '@apollo/client'

export const ORDER_UPDATED = gql`
  subscription OrderUpdated {
    orderUpdated {
      id
      status
      customer {
        name
      }
      totals {
        grandTotal
      }
    }
  }
`

export const INVENTORY_CHANGED = gql`
  subscription InventoryChanged {
    inventoryChanged {
      id
      sku
      warehouseId
      quantity
      available
      updatedAt
    }
  }
`

export const PRODUCTION_PROGRESS = gql`
  subscription ProductionProgress {
    productionProgress {
      id
      status
      totalPartsProduced
      totalDefectives
      oee
    }
  }
`

export const MOLD_STATUS_CHANGED = gql`
  subscription MoldStatusChanged {
    moldStatusChanged {
      id
      moldCode
      status
      currentCycles
      cycleLife
    }
  }
`

export const KPI_SNAPSHOT = gql`
  subscription KpiSnapshot {
    kpiSnapshot {
      totalOrders
      totalRevenue
      totalProduction
      defectRate
      oee
      shippingOnTimeRate
    }
  }
`
