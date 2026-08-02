#!/usr/bin/env python3
"""Aplica schema CRM ao banco PostgreSQL."""
import asyncio
import os
import asyncpg
from pathlib import Path

DB_URL = os.environ.get("DATABASE_URL", "")
if not DB_URL:
    raise RuntimeError("DATABASE_URL nao configurado — defina a connection string do Postgres antes de rodar esta migration")
SQL_FILE = Path(__file__).parent / "sql" / "create_tables_crm.sql"

async def apply_crm():
    print("🚀 Aplicando schema CRM...")

    sql = SQL_FILE.read_text(encoding="utf-8")

    conn = await asyncpg.connect(DB_URL)

    try:
        await conn.execute(sql)
        print("✅ Schema CRM aplicado com sucesso!")

        tabelas = [
            "crm_empresas", "crm_leads", "crm_contatos", "crm_negociacoes",
            "crm_atividades", "crm_propostas", "crm_contratos",
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

    except Exception as e:
        print(f"❌ Erro: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_crm())
