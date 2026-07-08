"""
Deploy script — copia os agentes para dentro do container Hermes.
Rode este script localmente ou via Hermes execute_code.
"""
import os, sys, shutil
from pathlib import Path

SRC = Path(__file__).resolve().parent  # hermes_agents/
DST = Path("/workspace/hermes_agents")

def deploy():
    """Copia todo o pacote hermes_agents para /workspace."""
    print(f"Deploy: {SRC} → {DST}")

    # Remove destino anterior se existir
    if DST.exists():
        print(f"  Removendo {DST}...")
        shutil.rmtree(DST)

    # Copia diretórios
    shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))

    # Verifica
    for sub in ["core", "ag_09_memoria", "ag_01_cacador", "ag_02_lucratividade", "ag_03_marketplaces", "profiles"]:
        assert (DST / sub).exists(), f"Faltando {sub}!"

    print(f"Deploy concluído: {DST}")
    print("\nPara testar, no execute_code do Hermes:")
    print("  import sys; sys.path.insert(0, '/workspace')")
    print("  from hermes_agents.ag_01_cacador import executar_cacada")
    print("  executar_cacada()")

def init_db():
    """Inicializa o schema do banco de dados."""
    schema_path = SRC / "sql" / "schema.sql"
    if not schema_path.exists():
        print(f"Schema não encontrado: {schema_path}")
        return

    sql = schema_path.read_text(encoding="utf-8")
    print(f"Schema: {len(sql)} bytes")
    print("Cole este SQL no terminal do PostgreSQL ou execute via Python:")
    print(f"  cat {schema_path} | psql -h <host> -U <user> -d hermes_factory")

if __name__ == "__main__":
    if "--init-db" in sys.argv:
        init_db()
    else:
        deploy()
