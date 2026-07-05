-- ATHENA OS SEED v2 — matches actual DB columns
BEGIN;

DELETE FROM "OrderLine"; DELETE FROM "Fulfillment"; DELETE FROM "Return"; DELETE FROM "Order";
DELETE FROM "QualityCheck"; DELETE FROM "ProductionRun";
DELETE FROM "CuringCycle"; DELETE FROM "PlastisolFormulation";
DELETE FROM "Component"; DELETE FROM "BOM"; DELETE FROM "Revision"; DELETE FROM "Product";
DELETE FROM "Customer"; DELETE FROM "ProductCard"; DELETE FROM "PriceListItem";
DELETE FROM "StockItem"; DELETE FROM "Warehouse";
DELETE FROM "MaintenanceRecord"; DELETE FROM "Mold"; DELETE FROM "CNCJob";
DELETE FROM "ChannelListing"; DELETE FROM "Metric";

INSERT INTO "Warehouse" (id, name, city, state) VALUES
('FUL-001','CD São Paulo','São Paulo','SP'),
('FUL-002','CD Recife','Recife','PE');

INSERT INTO "Product" (id, sku, name, category, status, revision, description) VALUES
('PROD-001','PP-BALDE-20L','Balde Plástico 20L PP','utilidades','active','2.1','Balde industrial PP 20 litros'),
('PROD-002','PEAD-TAMPA-110MM','Tampa PEAD 110mm','acessorios','active','1.3','Tampa rosca PEAD'),
('PROD-003','PVC-MANGUEIRA-1/2','Mangueira Cristal PVC','mangueiras','active','3.0','Mangueira PVC cristal reforçado'),
('PROD-004','PP-CAIXA-ORG','Caixa Organizadora PP 30L','utilidades','active','1.0','Caixa PP com tampa'),
('PROD-005','ABS-CARCACA-TOOL','Carcaça Ferramenta ABS','industriais','active','2.4','Carcaça ABS para ferramenta elétrica');

INSERT INTO "BOM" (id, "productId", components) VALUES
('BOM-001','PROD-001','[{"name":"Polipropileno PP","qty":0.85,"unit":"kg"}]'),
('BOM-005','PROD-005','[{"name":"ABS Terluran","qty":0.45,"unit":"kg"}]');

INSERT INTO "Revision" (id, "productId", "revisionNumber", changes, status, "approvedBy", "approvedAt") VALUES
('REV-001','PROD-001','2.0','Ajuste ECN-2026-042','approved','eng-001','2026-06-15');

INSERT INTO "StockItem" (id, sku, "warehouseId", quantity, "reorderPoint") VALUES
('S1','PP-BALDE-20L','FUL-001',5200,1000),
('S2','PP-BALDE-20L','FUL-002',1800,500),
('S3','PEAD-TAMPA-110MM','FUL-001',12000,2000),
('S4','ABS-CARCACA-TOOL','FUL-001',340,100),
('S5','PVC-MANGUEIRA-1/2','FUL-001',850,500);

INSERT INTO "Customer" (id, name, email, phone, document, tier) VALUES
('CUST-001','Distribuidora Plásticos Nordeste Ltda','compras@dpn.com.br','81 3456-7890','12.345.678/0001-90','ouro'),
('CUST-002','Casa das Embalagens SP','vendas@casadasembalagens.com','11 2345-6789','98.765.432/0001-10','prata'),
('CUST-003','Mega Construção Ltda','orcamentos@megaconstrucao.com','11 4567-8901','33.444.555/0001-66','ouro');

INSERT INTO "Order" (id, "customerId", channel, status, "totalAmount", "createdAt") VALUES
('ORD-001','CUST-001','b2b','delivered',8800.00,'2026-06-20'),
('ORD-002','CUST-002','shopee','shipped',1170.50,'2026-06-28'),
('ORD-003','CUST-003','b2b','confirmed',3380.00,'2026-07-01'),
('ORD-004','CUST-001','manual','placed',16120.00,'2026-07-02'),
('ORD-005','CUST-002','mercadolivre','delivered',89.90,'2026-06-25');

INSERT INTO "OrderLine" (id, "orderId", sku, name, quantity, "unitPrice") VALUES
(gen_random_uuid(),'ORD-001','PP-BALDE-20L','Balde Plastico 20L PP',500,16.90),
(gen_random_uuid(),'ORD-002','PEAD-TAMPA-110MM','Tampa PEAD 110mm',200,1.85),
(gen_random_uuid(),'ORD-003','ABS-CARCACA-TOOL','Carcaca Ferramenta ABS',800,4.00),
(gen_random_uuid(),'ORD-004','PP-BALDE-20L','Balde Plastico 20L PP',300,52.00),
(gen_random_uuid(),'ORD-005','PVC-MANGUEIRA-1/2','Mangueira Cristal PVC',10,8.99);

INSERT INTO "Fulfillment" (id, "orderId", "centerId", status, "estimatedDays", "trackingCode", "carrierId", "shippedAt") VALUES
('FUL1','ORD-001','FUL-001','delivered',3,'JDL-12345','JADLOG','2026-06-21'),
('FUL2','ORD-002','FUL-001','shipped',5,'BR-98765','Correios','2026-06-29'),
('FUL3','ORD-005','FUL-001','delivered',2,'ME-55512','Mercado Envios','2026-06-26');

INSERT INTO "Mold" (id, "moldCode", "productId", status, cavities, "steelType", "cycleLife") VALUES
('MOLD-001','M-BALDE-20L-A','PROD-001','active',4,'P20',500000),
('MOLD-002','M-TAMPA-110-A','PROD-002','active',8,'H13',300000);

INSERT INTO "MaintenanceRecord" (id, "moldId", type, description, cost, "performedAt") VALUES
(gen_random_uuid(),'MOLD-001','preventiva','Limpeza de canais e vedacoes',850.00,'2026-06-10');

INSERT INTO "CNCJob" (id, "partNumber", "estimatedHours", priority, status, "machineId", "programId") VALUES
('CNC-001','INSERT-MOLD-001',12.5,1,'completed','CNC-DMU50','NC-4421'),
('CNC-002','INSERT-MOLD-002',8.0,1,'running','CNC-DMU50','NC-4450');

INSERT INTO "ProductionRun" (id, "moldId", "machineId", "productSku", status, "targetQuantity", "producedQuantity", "scrapQuantity", "defectRate") VALUES
('RUN-001','MOLD-001','INJ-HAITIAN-300','PP-BALDE-20L','completed',5000,4950,50,1.0),
('RUN-002','MOLD-002','INJ-ARBURG-200','PEAD-TAMPA-110MM','running',10000,4500,30,0.67);

INSERT INTO "QualityCheck" (id, "runId", passed, defects, parameters, "checkedAt") VALUES
('QC-001','RUN-001',true,'{}','{"temp":210,"pressure":85}',NOW()),
('QC-002','RUN-001',false,'{rebarba}','{"temp":225,"pressure":90}',NOW()),
('QC-003','RUN-002',true,'{}','{"temp":195,"pressure":70}',NOW());

INSERT INTO "PlastisolFormulation" (id, "formulaCode", components, viscosity, "gelTemperature") VALUES
('FORM-001','PLAST-BRANCO-STD','{"PVC":"100phr","DOP":"60phr"}',3200,180);

INSERT INTO "CuringCycle" (id, "formulationId", "lineId", "targetTemperature", "targetDuration", "actualTemperature", "actualDuration", status) VALUES
('CURE-001','FORM-001','LINE-1',200,180,198,185,'completed');

INSERT INTO "ProductCard" (id, "productId", name, "categoryId", status, description, attributes, variants) VALUES
('CARD-001','PROD-001','Balde Plástico 20L PP Industrial','utilidades','published','Balde industrial PP','{"cor":"Branco","capacidade":"20L"}','[{"sku":"PP-BALDE-20L","price":16.90}]'),
('CARD-005','PROD-005','Carcaça Ferramenta ABS','industriais','published','Carcaça ABS','{"cor":"Preto"}','[{"sku":"ABS-CARCACA-TOOL","price":4.50}]');

INSERT INTO "PriceListItem" (id, "productId", price, cost, active) VALUES
('PR1','PROD-001',16.90,8.50,true),
('PR2','PROD-002',1.85,0.60,true),
('PR3','PROD-005',4.50,1.90,true);

INSERT INTO "ChannelListing" (id, "productId", channel, "mlItemId", "shopeeItemId", price, stock, status) VALUES
('CL1','PROD-001','shopee',NULL,'SH-BALDE20L',18.90,5200,'active'),
('CL2','PROD-001','mercadolivre','MLB123456',NULL,17.90,5200,'active');

INSERT INTO "Metric" (id, name, value, tags, "recordedAt") VALUES
('M1','oee',87.5,'["manufacturing","daily"]',NOW()),
('M2','defect_rate',1.2,'["quality","daily"]',NOW()),
('M3','shipping_on_time',94.3,'["logistics","daily"]',NOW());

COMMIT;
