#!/usr/bin/env python3
"""Aplica schema Fase 3 ao banco PostgreSQL."""
import asyncio
import os
import asyncpg
from pathlib import Path

DB_URL = os.environ.get("DATABASE_URL", "")
if not DB_URL:
    raise RuntimeError("DATABASE_URL nao configurado — defina a connection string do Postgres antes de rodar esta migration")
SQL_FILE = Path(__file__).parent / "sql" / "create_tables_fase3.sql"

async def apply_fase3():
    print("🚀 Aplicando schema Fase 3...")
    
    # Ler SQL
    sql = SQL_FILE.read_text(encoding="utf-8")
    
    # Conectar
    conn = await asyncpg.connect(DB_URL)
    
    try:
        # Executar SQL
        await conn.execute(sql)
        print("✅ Schema Fase 3 aplicado com sucesso!")
        
        # Verificar tabelas criadas
        tabelas = [
            "moldes_eventos", "cnc_jobs", "producao_lotes",
            "inspecao_qualidade", "inspecao_defeitos", "defeitos",
            "capa_registros", "manutencoes", "manutencoes_historico",
            "estoque_produtos", "transferencias_estoque"
        ]
        
        print("\n📊 Verificando tabelas:")
        for tabela in tabelas:
            result = await conn.fetchval(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{tabela}'
                )
            """)
            status = "✅" if result else "❌"
            print(f"{status} {tabela}")
        
        # Verificar colunas adicionadas em moldes
        colunas_moldes = [
            "status_atual", "data_design", "data_fabricacao_inicio",
            "data_fabricacao_fim", "data_instalacao", "maquina_id",
            "ciclos_acumulados", "ultima_manutencao", "proxima_manutencao"
        ]
        
        print("\n📊 Verificando colunas em moldes:")
        for coluna in colunas_moldes:
            result = await conn.fetchval(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'moldes' AND column_name = '{coluna}'
                )
            """)
            status = "✅" if result else "❌"
            print(f"{status} moldes.{coluna}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_fase3())