#!/usr/bin/env python3
"""Aplica schema Fase 2 ao banco PostgreSQL."""
import asyncio
import asyncpg
from pathlib import Path

DB_URL = "postgresql://postgres:hpj7Zi4vwe7i2uThIhS46nszrblsbNhzqblpYovRBdJgqtAU5L5giL8hLli5Tz54@h3bdeft4hgsbg9rcxklxidwt:5432/hermes_factory"
SQL_FILE = Path(__file__).parent / "sql" / "create_tables_fase2.sql"

async def apply_fase2():
    print("🚀 Aplicando schema Fase 2...")
    
    # Ler SQL
    sql = SQL_FILE.read_text(encoding="utf-8")
    
    # Conectar
    conn = await asyncpg.connect(DB_URL)
    
    try:
        # Executar SQL
        await conn.execute(sql)
        print("✅ Schema Fase 2 aplicado com sucesso!")
        
        # Verificar tabelas criadas
        tabelas = [
            "pedidos_producao", "materias_primas", "plano_producao_diario",
            "status_maquinas", "ferramentas_cnc",
            "clientes_telegram", "sessoes_telegram", "pedidos_telegram",
            "pipeline_lancamentos", "componentes_bom", "historico_custos_simulados"
        ]
        
        for tabela in tabelas:
            result = await conn.fetchval(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{tabela}'
                )
            """)
            status = "✅" if result else "❌"
            print(f"{status} {tabela}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_fase2())