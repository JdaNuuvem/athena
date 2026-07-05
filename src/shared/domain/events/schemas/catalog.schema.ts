import { z } from 'zod'

export const ProductPublishedPayload = z.object({
  productId: z.string().uuid(),
  sku: z.string().optional(),
  title: z.string().min(1),
  description: z.string().optional(),
  bulletPoints: z.array(z.string()).optional(),
  categoryId: z.string().optional(),
  brand: z.string().optional(),
  gtin: z.string().optional(),
  ncm: z.string().optional(),
  status: z.enum(['draft', 'published', 'archived']),
  seoMetadata: z.object({
    metaTitle: z.string().optional(),
    metaDescription: z.string().optional(),
    keywords: z.array(z.string()).optional(),
  }).optional(),
  publishedAt: z.string().datetime().optional(),
})

export const ProductUpdatedPayload = z.object({
  productId: z.string().uuid(),
  sku: z.string().optional(),
  changedFields: z.array(z.string()).min(1),
  newValues: z.object({
    title: z.string().optional(),
    description: z.string().optional(),
    price: z.number().optional(),
    categoryId: z.string().optional(),
    status: z.string().optional(),
  }).optional(),
})

export const VariantCreatedPayload = z.object({
  variantId: z.string().uuid(),
  productId: z.string().uuid(),
  sku: z.string().min(1),
  attributes: z.object({
    color: z.string().optional(),
    size: z.string().optional(),
    material: z.string().optional(),
    finish: z.string().optional(),
  }),
  price: z.number().nonnegative(),
  stockQuantity: z.number().int().nonnegative(),
  isDefault: z.boolean().optional(),
})

export const MediaAddedPayload = z.object({
  mediaId: z.string().uuid(),
  productId: z.string().uuid(),
  type: z.enum(['image', 'video', 'manual', 'spec_sheet', 'certificate']),
  url: z.string().url(),
  filename: z.string().optional(),
  sortOrder: z.number().int().optional(),
  tags: z.array(z.string()).optional(),
  isMain: z.boolean().optional(),
})
