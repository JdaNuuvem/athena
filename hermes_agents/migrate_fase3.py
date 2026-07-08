#!/usr/bin/env python3
"""Aplica schema Fase 3 ao banco PostgreSQL."""
import asyncio
import asyncpg
from pathlib import Path

DB_URL = "postgresql://postgres:hpj7Zi4vwe7i2uThIhS46nszrblsbNhzqblpYovRBdJgqtAU5L5giL8hLli5Tz54@h3bdeft4hgsbg9rcxklxidwt:5432/hermes_factory"
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