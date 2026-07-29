"""Reconciliacao Fisico x Contabil — Ponte i9Logic -> Athena.

De-para de identidade, client HTTP paginado (respeitando rate limit), staging
table de snapshot, classificacao de divergencia, job de coleta e seed inicial.
Fisico (tipoestoque=1) semeia estoque_saldos (Fase 1); contabil (tipoestoque=2)
nunca vira bucket, so' serve como sinal de auditoria. Nenhum ajuste automatico
de saldo — toda decisao sobre divergencia e' manual."""
import os, time, requests
from datetime import datetime
from core import get_db, run_async, log
from core.config import get_config

AGENT = "I9Logic Reconciliacao"

BASE_URL = os.environ.get("I9LOGIC_BASE_URL") or get_config("i9logic", "base_url") or ""
RATE_LIMIT_SLEEP_SEGUNDOS = 2.5  # ~24 req/min, margem sob o limite de 30/min da API
PER_PAGE_PADRAO = 200

LIMIAR_ALERTA_ABSOLUTO = 5
LIMIAR_ALERTA_PERCENTUAL = 0.10
TOLERANCIA_ZERO = 0.5


def _api_key() -> str:
    return os.environ.get("I9LOGIC_API_KEY") or get_config("i9logic", "api_key") or ""


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS de_para_i9logic (
            id SERIAL PRIMARY KEY,
            tipo VARCHAR(10) NOT NULL,
            id_i9logic VARCHAR(50) NOT NULL,
            codigo_athena VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (tipo, id_i9logic)
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS i9logic_estoque_snapshot (
            id SERIAL PRIMARY KEY,
            idproduto_i9logic INT NOT NULL,
            codproduto_i9logic VARCHAR(50),
            sku_athena VARCHAR(50),
            filial_i9logic INT NOT NULL,
            loja_athena VARCHAR(50),
            qtd_fisico DECIMAL(12,3),
            qtd_contabil DECIMAL(12,3),
            divergencia DECIMAL(12,3) GENERATED ALWAYS AS (qtd_contabil - qtd_fisico) STORED,
            data_coleta TIMESTAMP DEFAULT NOW(),
            revisado BOOLEAN DEFAULT FALSE,
            UNIQUE(idproduto_i9logic, filial_i9logic, data_coleta)
        )""")
    try:
        run_async(_go())
        log(AGENT, "Tabelas i9logic seeded")
    except Exception as e:
        log(AGENT, f"Erro tabelas i9logic: {e}")

_ensure_tables()

# ── De-para de identidade ──

def criar_mapeamento(tipo: str, id_i9logic, codigo_athena: str) -> dict:
    """Cria ou atualiza (upsert) o de-para entre um id interno do i9Logic e o
    codigo correspondente no Athena. tipo: 'produto' (id_i9logic=idproduto,
    codigo_athena=sku) ou 'filial' (id_i9logic=id da filial, codigo_athena=
    nome da loja)."""
    if tipo not in ("produto", "filial"):
        return {"erro": f"tipo invalido: {tipo}. Use 'produto' ou 'filial'"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO de_para_i9logic (tipo, id_i9logic, codigo_athena) VALUES ($1,$2,$3) "
            "ON CONFLICT (tipo, id_i9logic) DO UPDATE SET codigo_athena=$3 RETURNING *",
            tipo, str(id_i9logic), codigo_athena)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"erro": str(e)}


def buscar_codigo_athena(tipo: str, id_i9logic):
    async def _go():
        db = await get_db()
        return await db.fetchval(
            "SELECT codigo_athena FROM de_para_i9logic WHERE tipo=$1 AND id_i9logic=$2",
            tipo, str(id_i9logic))
    try: return run_async(_go())
    except Exception: return None


def listar_mapeamentos(tipo: str = None) -> list:
    async def _go():
        db = await get_db()
        if tipo:
            rows = await db.fetch("SELECT * FROM de_para_i9logic WHERE tipo=$1 ORDER BY id", tipo)
        else:
            rows = await db.fetch("SELECT * FROM de_para_i9logic ORDER BY tipo, id")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception: return []
