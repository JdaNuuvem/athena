import { getPrisma, disconnectPrisma } from '../src/shared/infrastructure/persistence/prisma-client'

const prisma = getPrisma()

async function main() {
  console.log('🌱 Seeding ATHENA OS...\n')

  // === Warehouses ===
  await prisma.warehouse.createMany({
    data: [
      { id: 'FUL-001', name: 'CD São Paulo', city: 'São Paulo', state: 'SP', active: true },
      { id: 'FUL-002', name: 'CD Recife', city: 'Recife', state: 'PE', active: true },
      { id: 'FUL-003', name: 'CD Manaus', city: 'Manaus', state: 'AM', active: true },
      { id: 'FUL-004', name: 'CD Curitiba', city: 'Curitiba', state: 'PR', active: true },
    ],
    skipDuplicates: true,
  })
  console.log('  4 warehouses')

  // === Products ===
  const products = [
    { id: 'PROD-001', sku: 'PP-BALDE-20L', name: 'Balde Plástico 20L PP', description: 'Balde industrial em polipropileno 20 litros com alça metálica', category: 'utilidades', status: 'active', revision: '2.1' },
    { id: 'PROD-002', sku: 'PEAD-TAMPA-110MM', name: 'Tampa PEAD 110mm', description: 'Tampa rosca em polietileno de alta densidade para frascos', category: 'acessorios', status: 'active', revision: '1.3' },
    { id: 'PROD-003', sku: 'PVC-MANGUEIRA-1/2', name: 'Mangueira Cristal PVC 1/2"', description: 'Mangueira flexível em PVC cristal reforçado', category: 'mangueiras', status: 'active', revision: '3.0' },
    { id: 'PROD-004', sku: 'PP-CAIXA-ORG', name: 'Caixa Organizadora PP 30L', description: 'Caixa organizadora em polipropileno com tampa', category: 'utilidades', status: 'active', revision: '1.0' },
    { id: 'PROD-005', sku: 'ABS-CARCACA-TOOL', name: 'Carcaça Ferramenta ABS', description: 'Carcaça injetada em ABS para ferramenta elétrica', category: 'industriais', status: 'active', revision: '2.4' },
    { id: 'PROD-006', sku: 'PEBD-SACO-100L', name: 'Saco PEBD 100L', description: 'Saco plástico em polietileno de baixa densidade 100 litros', category: 'embalagens', status: 'active', revision: '1.0' },
    { id: 'PROD-007', sku: 'PLAST-PISO-BRANCO', name: 'Piso Plastisol Branco 2mm', description: 'Revestimento de piso em plastisol branco 2mm', category: 'revestimentos', status: 'active', revision: '1.5' },
    { id: 'PROD-008', sku: 'PLAST-TAPETE-PRETO', name: 'Tapete Plastisol Preto 3mm', description: 'Tapete automotivo em plastisol preto 3mm', category: 'revestimentos', status: 'active', revision: '2.0' },
  ]
  for (const p of products) {
    await prisma.product.upsert({ where: { sku: p.sku }, create: p, update: {} })
  }
  console.log('  8 products')

  // === BOM + Components ===
  const boms = [
    { productId: 'PROD-001', components: [{ name: 'Polipropileno PP CP 442 XP', quantity: 0.85, unit: 'kg' }, { name: 'Masterbatch Branco', quantity: 0.02, unit: 'kg' }, { name: 'Alça Metálica Galvanizada', quantity: 1, unit: 'un' }] },
    { productId: 'PROD-005', components: [{ name: 'ABS Terluran GP-35', quantity: 0.45, unit: 'kg' }, { name: 'Masterbatch Preto', quantity: 0.01, unit: 'kg' }, { name: 'Parafuso M3x12', quantity: 4, unit: 'un' }] },
    { productId: 'PROD-002', components: [{ name: 'PEAD Braskem HS5502', quantity: 0.03, unit: 'kg' }, { name: 'Masterbatch Azul', quantity: 0.001, unit: 'kg' }] },
    { productId: 'PROD-003', components: [{ name: 'PVC Flexível K70', quantity: 0.25, unit: 'kg/m' }, { name: 'Plastificante DOP', quantity: 0.08, unit: 'kg/m' }] },
  ]
  for (const b of boms) {
    await prisma.bOM.upsert({
      where: { productId: b.productId },
      create: { id: `BOM-${b.productId}`, productId: b.productId, revision: '1.0', components: b.components, validated: true, validatedAt: new Date(), validatedBy: 'eng-001' },
      update: {},
    })
    for (const c of b.components as Array<{ name: string }>) {
      await prisma.component.create({
        data: { id: `CMP-${b.productId}-${c.name.replace(/\s+/g, '-')}`, productId: b.productId, name: c.name, quantity: 1 },
      })
    }
  }
  console.log('  4 BOMs')

  // === Revisions ===
  for (const p of products.slice(0, 5)) {
    await prisma.revision.create({
      data: { id: `REV-${p.id}-2`, productId: p.id, revisionNumber: '2.0', changes: 'Ajuste dimensional conforme ECN-2026-042', approvedBy: 'eng-001', approvedAt: new Date('2026-06-15'), status: 'approved' },
    })
  }
  console.log('  5 revisions')

  // === Stock Items ===
  await prisma.$executeRawUnsafe(`DELETE FROM "StockItem"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "StockItem" (id, sku, "warehouseId", quantity, "reorderPoint", "reservedQty", unit) VALUES
    ('STK-001', 'PP-BALDE-20L', 'FUL-001', 5200, 1000, 200, 'un'),
    ('STK-002', 'PP-BALDE-20L', 'FUL-002', 1800, 500, 0, 'un'),
    ('STK-003', 'PP-BALDE-20L', 'FUL-003', 450, 300, 0, 'un'),
    ('STK-004', 'PEAD-TAMPA-110MM', 'FUL-001', 12000, 2000, 500, 'un'),
    ('STK-005', 'PVC-MANGUEIRA-1/2', 'FUL-001', 850, 500, 0, 'un'),
    ('STK-006', 'PVC-MANGUEIRA-1/2', 'FUL-004', 3200, 800, 0, 'un'),
    ('STK-007', 'PP-CAIXA-ORG', 'FUL-001', 2100, 500, 0, 'un'),
    ('STK-008', 'ABS-CARCACA-TOOL', 'FUL-001', 340, 100, 150, 'un'),
    ('STK-009', 'ABS-CARCACA-TOOL', 'FUL-004', 1200, 300, 0, 'un'),
    ('STK-010', 'PEBD-SACO-100L', 'FUL-001', 8000, 2000, 0, 'un'),
    ('STK-011', 'PLAST-PISO-BRANCO', 'FUL-001', 650, 200, 0, 'un'),
    ('STK-012', 'PLAST-TAPETE-PRETO', 'FUL-001', 430, 150, 0, 'un')
  `)
  console.log('  12 stock items')

  // === Customers ===
  await prisma.$executeRawUnsafe(`DELETE FROM "Customer"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "Customer" (id, name, email, phone, document, tier, "loyaltyPoints", tags) VALUES
    ('CUST-001', 'Distribuidora Plásticos Nordeste Ltda', 'compras@dpn.com.br', '81 3456-7890', '12.345.678/0001-90', 'ouro', 12500, '{atacado,recorrente}'),
    ('CUST-002', 'Casa das Embalagens SP', 'vendas@casadasembalagens.com', '11 2345-6789', '98.765.432/0001-10', 'prata', 4800, '{varejo}'),
    ('CUST-003', 'Indústria Metalúrgica ABC', 'suprimentos@metalurgicaabc.com.br', '19 3456-1234', '55.123.456/0001-78', 'bronze', 1200, '{industria}'),
    ('CUST-004', 'Mega Construção Ltda', 'orcamentos@megaconstrucao.com', '11 4567-8901', '33.444.555/0001-66', 'ouro', 8900, '{atacado,construcao}'),
    ('CUST-005', 'João Silva ME', 'joao@silvaembalagens.com', '41 98765-4321', '111.222.333-44', 'bronze', 350, '{varejo,pf}')
  `)
  console.log('  5 customers')

  // === Orders + Lines + Fulfillment ===
  await prisma.$executeRawUnsafe(`DELETE FROM "Fulfillment"`)
  await prisma.$executeRawUnsafe(`DELETE FROM "OrderLine"`)
  await prisma.$executeRawUnsafe(`DELETE FROM "Return"`)
  await prisma.$executeRawUnsafe(`DELETE FROM "Order"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "Order" (id, "customerId", channel, status, subtotal, "shippingCost", discount, "grandTotal", currency, "createdAt") VALUES
    ('ORD-2026-001', 'CUST-001', 'b2b', 'delivered', 8450.00, 350.00, 0, 8800.00, 'BRL', '2026-06-20'),
    ('ORD-2026-002', 'CUST-002', 'shopee', 'shipped', 1250.50, 45.00, 125.00, 1170.50, 'BRL', '2026-06-28'),
    ('ORD-2026-003', 'CUST-003', 'b2b', 'confirmed', 3200.00, 180.00, 0, 3380.00, 'BRL', '2026-07-01'),
    ('ORD-2026-004', 'CUST-004', 'manual', 'placed', 15600.00, 520.00, 0, 16120.00, 'BRL', '2026-07-02'),
    ('ORD-2026-005', 'CUST-005', 'mercadolivre', 'delivered', 89.90, 0, 0, 89.90, 'BRL', '2026-06-25')
  `)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "OrderLine" (id, "orderId", sku, name, quantity, "unitPrice") VALUES
    ('OL-001A', 'ORD-2026-001', 'PP-BALDE-20L', 'Balde Plástico 20L PP', 500, 16.90),
    ('OL-002A', 'ORD-2026-002', 'PEAD-TAMPA-110MM', 'Tampa PEAD 110mm', 200, 1.85),
    ('OL-002B', 'ORD-2026-002', 'PP-CAIXA-ORG', 'Caixa Organizadora PP 30L', 50, 17.60),
    ('OL-003A', 'ORD-2026-003', 'ABS-CARCACA-TOOL', 'Carcaça Ferramenta ABS', 800, 4.00),
    ('OL-004A', 'ORD-2026-004', 'PLAST-PISO-BRANCO', 'Piso Plastisol Branco 2mm', 300, 52.00),
    ('OL-005A', 'ORD-2026-005', 'PEBD-SACO-100L', 'Saco PEBD 100L', 10, 8.99)
  `)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "Fulfillment" (id, "orderId", type, "centerId", status, "estimatedDays", "carrierId", "trackingCode", "shippedAt", "deliveredAt") VALUES
    ('FUL-001', 'ORD-2026-001', 'warehouse', 'FUL-001', 'delivered', 3, 'JADLOG', 'JDL-12345678', '2026-06-21', '2026-06-23'),
    ('FUL-002', 'ORD-2026-002', 'warehouse', 'FUL-001', 'shipped', 5, 'Correios', 'BR-98765432', '2026-06-29', NULL),
    ('FUL-003', 'ORD-2026-005', 'marketplace', 'FUL-001', 'delivered', 2, 'Mercado Envios', 'ME-55512345', '2026-06-26', '2026-06-28')
  `)
  console.log('  5 orders + 6 lines + 3 fulfillments')

  // === Molds + Maintenance ===
  await prisma.$executeRawUnsafe(`DELETE FROM "MaintenanceRecord"`)
  await prisma.$executeRawUnsafe(`DELETE FROM "Mold"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "Mold" (id, "moldCode", "productId", status, cavities, "steelType", "cycleLife") VALUES
    ('MOLD-001', 'M-BALDE-20L-A', 'PROD-001', 'active', 4, 'P20', 500000),
    ('MOLD-002', 'M-TAMPA-110-A', 'PROD-002', 'active', 8, 'H13', 300000),
    ('MOLD-003', 'M-CARC-TOOL-A', 'PROD-005', 'active', 2, '420SS', 200000),
    ('MOLD-004', 'M-CX-ORG-A', 'PROD-004', 'maintenance', 1, 'NAK80', 400000)
  `)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "MaintenanceRecord" (id, "moldId", type, description, cost, "performedAt") VALUES
    ('MAINT-001', 'MOLD-001', 'preventiva', 'Limpeza de canais e troca de vedações', 850.00, '2026-06-10'),
    ('MAINT-002', 'MOLD-002', 'corretiva', 'Reparo de inserto cavidade #3', 2400.00, '2026-05-28'),
    ('MAINT-003', 'MOLD-004', 'preventiva', 'Polimento de superfície e ajuste de extração', 1200.00, '2026-07-01')
  `)
  console.log('  4 molds + 3 maintenance records')

  // === CNC ===
  await prisma.$executeRawUnsafe(`DELETE FROM "CNCJob"`)
  await prisma.$executeRawUnsafe(`DELETE FROM "CNCTool"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "CNCJob" (id, "partNumber", "estimatedHours", priority, status, "machineId", "programId") VALUES
    ('CNC-001', 'INSERT-MOLD-001-CAV1', 12.5, 1, 'completed', 'CNC-DMU50', 'NC-4421'),
    ('CNC-002', 'INSERT-MOLD-002-CAV5', 8.0, 1, 'running', 'CNC-DMU50', 'NC-4450'),
    ('CNC-003', 'BASE-MOLD-004', 24.0, 2, 'scheduled', NULL, 'NC-4462')
  `)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "CNCTool" (id, "toolNumber", "machineId", name, "wearMicrons", "thresholdMicrons", "cyclesCompleted", "estimatedCyclesRemaining", status) VALUES
    ('TOOL-001', 1, 'CNC-DMU50', 'Fresa Topo Ø10mm', 12, 25, 4500, 8000, 'active'),
    ('TOOL-002', 2, 'CNC-DMU50', 'Fresa Topo Ø6mm', 22, 20, 3200, 500, 'warning'),
    ('TOOL-003', 3, 'CNC-DMU50', 'Broca Ø8mm', 5, 30, 1100, 12000, 'active')
  `)
  console.log('  3 CNC jobs + 3 tools')

  // === Production Runs ===
  await prisma.$executeRawUnsafe(`DELETE FROM "QualityCheck"`)
  await prisma.$executeRawUnsafe(`DELETE FROM "ProductionRun"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "ProductionRun" (id, "moldId", "machineId", "productSku", status, "targetQuantity", "producedQuantity", "scrapQuantity", "defectRate") VALUES
    ('RUN-001', 'MOLD-001', 'INJ-HAITIAN-300', 'PP-BALDE-20L', 'completed', 5000, 4950, 50, 1.0),
    ('RUN-002', 'MOLD-002', 'INJ-ARBURG-200', 'PEAD-TAMPA-110MM', 'running', 10000, 4500, 30, 0.67),
    ('RUN-003', 'MOLD-003', 'INJ-ENGEL-500', 'ABS-CARCACA-TOOL', 'running', 2000, 1200, 18, 1.5)
  `)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "QualityCheck" (id, "runId", passed, defects, parameters) VALUES
    ('QC-001', 'RUN-001', true, '{}', '{"temp":210,"pressure":85,"cycleTime":28.5}'),
    ('QC-002', 'RUN-001', false, '{rebarba,queima}', '{"temp":225,"pressure":90,"cycleTime":27.0}'),
    ('QC-003', 'RUN-002', true, '{}', '{"temp":195,"pressure":70,"cycleTime":12.3}'),
    ('QC-004', 'RUN-003', true, '{}', '{"temp":245,"pressure":95,"cycleTime":35.0}')
  `)
  console.log('  3 production runs + 4 quality checks')

  // === Plastisol ===
  await prisma.$executeRawUnsafe(`DELETE FROM "CuringCycle"`)
  await prisma.$executeRawUnsafe(`DELETE FROM "PlastisolFormulation"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "PlastisolFormulation" (id, "formulaCode", components, viscosity, "gelTemperature") VALUES
    ('FORM-001', 'PLAST-BRANCO-STD', '{"PVC Resin":"100 phr","DOP":"60 phr","TiO2":"5 phr","Stabilizer":"3 phr","CaCO3":"20 phr"}', 3200, 180),
    ('FORM-002', 'PLAST-PRETO-AUTO', '{"PVC Resin":"100 phr","DINP":"55 phr","Carbon Black":"3 phr","Stabilizer":"4 phr","CaCO3":"30 phr"}', 4500, 190)
  `)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "CuringCycle" (id, "formulationId", "lineId", status, "targetTemperature", "targetDuration", "actualTemperature", "actualDuration") VALUES
    ('CURE-001', 'FORM-001', 'LINE-1', 'completed', 200, 180, 198, 185),
    ('CURE-002', 'FORM-002', 'LINE-2', 'started', 210, 240, 205, NULL)
  `)
  console.log('  2 formulations + 2 curing cycles')

  // === Product Cards ===
  await prisma.$executeRawUnsafe(`DELETE FROM "ProductCard"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "ProductCard" (id, "productId", name, "categoryId", status, description, images, attributes, "seoTitle", variants) VALUES
    ('CARD-001', 'PROD-001', 'Balde Plástico 20L PP Industrial', 'utilidades', 'published', 'Balde industrial em polipropileno virgem', '{https://cdn.athena.io/prod-001-01.jpg}', '{"cor":"Branco","capacidade":"20L"}', 'Balde Plástico 20L PP', '[{"variantId":"V-001","sku":"PP-BALDE-20L","price":16.90}]'),
    ('CARD-005', 'PROD-005', 'Carcaça para Ferramenta Elétrica ABS', 'industriais', 'published', 'Carcaça injetada em ABS', '{https://cdn.athena.io/prod-005-01.jpg}', '{"cor":"Preto"}', 'Carcaça Ferramenta ABS', '[{"variantId":"V-005","sku":"ABS-CARCACA-TOOL","price":4.50}]'),
    ('CARD-007', 'PROD-007', 'Piso Plastisol Branco 2mm', 'revestimentos', 'published', 'Revestimento de piso em plastisol branco', '{https://cdn.athena.io/prod-007-01.jpg}', '{}', 'Piso Plastisol Branco', '[{"variantId":"V-007","sku":"PLAST-PISO-BRANCO","price":52.00}]')
  `)
  console.log('  3 product cards')

  // === Prices ===
  await prisma.$executeRawUnsafe(`DELETE FROM "PriceListItem"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "PriceListItem" (id, "productId", price, cost, currency) VALUES
    ('PR-001','PROD-001',16.90,8.50,'BRL'),('PR-002','PROD-002',1.85,0.60,'BRL'),
    ('PR-003','PROD-003',4.50,1.80,'BRL'),('PR-004','PROD-004',17.60,7.20,'BRL'),
    ('PR-005','PROD-005',4.50,1.90,'BRL'),('PR-006','PROD-006',8.99,2.50,'BRL'),
    ('PR-007','PROD-007',52.00,18.00,'BRL'),('PR-008','PROD-008',35.00,12.00,'BRL')
  `)
  console.log('  8 prices')

  // === KPIs ===
  await prisma.$executeRawUnsafe(`DELETE FROM "Metric"`)
  await prisma.$executeRawUnsafe(`DELETE FROM "KPIMetric"`)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "Metric" (id, name, value, unit) VALUES
    ('MET-OEE','oee',87.5,'%'),('MET-DEFECT','defect_rate',1.2,'%'),
    ('MET-ON_TIME','shipping_on_time',94.3,'%'),('MET-REVENUE','monthly_revenue',28450.40,'BRL')
  `)
  await prisma.$executeRawUnsafe(`
    INSERT INTO "KPIMetric" (id, name, value, target, unit, period, "recordedAt") VALUES
    ('KPI-001','OEE',87.5,90,'%','daily',NOW()),
    ('KPI-002','DefectRate',1.2,1.0,'%','daily',NOW()),
    ('KPI-003','OnTimeDelivery',94.3,95,'%','daily',NOW())
  `)
  console.log('  4 metrics + 3 KPI targets')

  // === Users === (RBAC seed handles users via seed-rbac.ts)

  console.log('\n✅ Seed completo — ATHENA OS com dados reais.\n')
}

main()
  .catch(console.error)
  .finally(async () => { await disconnectPrisma() })
