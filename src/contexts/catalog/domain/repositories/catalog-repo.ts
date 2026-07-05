import type { ProductCard } from '../entities'
export interface ICatalogRepository { save(card: ProductCard): Promise<void>; findById(id: string): Promise<ProductCard | null>; findByProductId(productId: string): Promise<ProductCard | null>; findByCategory(categoryId: string): Promise<ProductCard[]>; findPublished(): Promise<ProductCard[]>; delete(id: string): Promise<void> }
