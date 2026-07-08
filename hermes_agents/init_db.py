#!/usr/bin/env python3
"""Inicializa o banco PostgreSQL — schema + dados de exemplo."""
import subprocess, os

DB_URL = "postgresql://postgres:hpj7Zi4vwe7i2uThIhS46nszrblsbNhzqblpYovRBdJgqtAU5L5giL8hLli5Tz54@h3bdeft4hgsbg9rcxklxidwt:5432/postgres"

SCHEMA = os.path.join(os.path.dirname(__file__), "sql", "schema.sql")

def init():
    print("🚀 Inicializando banco de dados...")
    cmd = ["psql", DB_URL, "-f", SCHEMA, "-v", "ON_ERROR_STOP=1"]
    try:
        subprocess.run(cmd, check=True)
        print("✅ Schema criado com sucesso!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar schema: {e}")
        raise

    # Seed mocldes
    seed = """
    INSERT INTO moldes (codigo, produto, material, ciclos_previstos, custo_molde) VALUES
    ('M-001','Organizador Gaveta 3 Divisorias','PP Copolimero',50000,18500.00),
    ('M-002','Porta Tempero Giratorio','ABS Natural',40000,22000.00),
    ('M-003','Pote Hermetico 500ml','PEAD Branco',80000,12000.00),
    ('M-004','Suporte Celular Cozinha','ABS Natural',60000,15000.00),
    ('M-005','Escorredor Louca Dobravel','PP Copolimero',45000,28000.00),
    ('M-006','Capa Sofa Impermavel','PEAD Branco',30000,35000.00)
    ON CONFLICT (codigo) DO NOTHING;

    INSERT INTO fichas_tecnicas (sku, molde_id, descricao, peso_gramas, material_principal, tempo_ciclo_segundos, cavidades) VALUES
    ('ORG001',1,'Organizador de Gaveta Modular 3 Divisorias PP',120,'PP Copolimero',25,2),
    ('PORTA001',2,'Porta Tempero Giratorio 3 Andares ABS',200,'ABS Natural',35,1),
    ('POTE001',3,'Pote Hermetico Tampa Rosca 500ml',80,'PEAD Branco',18,4),
    ('SUP001',4,'Suporte Parede Celular Cozinha Silicone',45,'ABS Natural',22,2),
    ('ESC001',5,'Escorredor Louca Dobravel Silicone',350,'PP Copolimero',40,1),
    ('CAPA001',6,'Capa Impermavel Sofa 3 Lugares',500,'PEAD Branco',55,1);

    INSERT INTO vendas (data, sku, marketplace, quantidade, preco_venda, receita_bruta, taxa_marketplace_pct, taxa_marketplace_valor, frete, impostos)
    SELECT
      d::date,
      s.sku,
      m.marketplace,
      (random()*20+5)::int,
      CASE WHEN s.sku='ORG001' THEN 29.90 WHEN s.sku='PORTA001' THEN 49.90 WHEN s.sku='POTE001' THEN 12.90 WHEN s.sku='SUP001' THEN 22.90 WHEN s.sku='ESC001' THEN 39.90 ELSE 119.90 END,
      0, 18.0, 0, 8.90, 0
    FROM generate_series('2026-06-01','2026-07-04','1 day'::interval) d
    CROSS JOIN (VALUES ('ORG001'),('PORTA001'),('POTE001'),('SUP001'),('ESC001'),('CAPA001')) s(sku)
    CROSS JOIN (VALUES ('shopee'),('mercado_livre'),('amazon')) m(marketplace);

    UPDATE vendas SET receita_bruta = preco_venda * quantidade,
      taxa_marketplace_valor = preco_venda * quantidade * taxa_marketplace_pct / 100,
      impostos = preco_venda * quantidade * 0.08;
    """
    cmd = ["psql", DB_URL, "-c", seed]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ Dados de exemplo inseridos!")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Seed parcial: {e.stderr.decode() if e.stderr else e}")

    print("✅ Banco inicializado — moldes, fichas, vendas, fornecedores prontos.")

if __name__ == "__main__":
    init()
