export interface CatalogEntry {
  id: string
  productId: string
  sku: string
  title: string
  description: string
  category: string
  materials: string[]
  status: 'draft' | 'published' | 'archived'
  variants: CatalogVariant[]
  media: CatalogMedia[]
  createdAt: string
  updatedAt: string
}

export interface CatalogVariant {
  variantId: string
  sku: string
  attributes: Record<string, string>
  price: number
  stockQuantity: number
}

export interface CatalogMedia {
  mediaId: string
  type: string
  url: string
  isMain: boolean
}
