"""Cofre Core — Fase 2 da spec de Caixa/Cofre (docs/superpowers/specs/2026-08-02-financeiro-caixa-cofre-design.md).

Nao duplica o conceito de "caixa" (pdv_caixas) — PDV continua dono da verdade
transacional. Cofre e' a camada de categorizacao/rastreio por loja: sangria
do PDV entra automaticamente (ver core/entidades.py::ao_fechar_caixa_pdv),
saidas de despesa/troco e ajustes entram manualmente por aqui.
"""
from core import get_db, run_async, log

AGENT = "Cofre Core"

TIPOS_VALIDOS = ("entrada_sangria", "saida_troco", "saida_despesa", "ajuste")
CATEGORIAS_DESPESA = ("mat_limpeza", "padaria", "papelaria", "passagem", "outros")


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_cofre (
            id SERIAL PRIMARY KEY,
            loja_id INT NOT NULL UNIQUE REFERENCES lojas(id),
            saldo_atual DECIMAL(12,2) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS fin_cofre_movimentos (
            id SERIAL PRIMARY KEY,
            cofre_id INT NOT NULL REFERENCES fin_cofre(id),
            tipo VARCHAR(20) NOT NULL,
            categoria VARCHAR(30),
            valor DECIMAL(12,2) NOT NULL,
            descricao VARCHAR(200),
            caixa_id INT REFERENCES pdv_caixas(id),
            data DATE NOT NULL DEFAULT CURRENT_DATE,
            criado_por VARCHAR(100),
            criado_por_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_fin_cofre_movimentos_cofre_id ON fin_cofre_movimentos (cofre_id)")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro tabelas cofre: {e}")


_ensure_tables()


def get_ou_criar_cofre(loja_id: int) -> dict:
    """Cofre e' criado sob demanda na primeira movimentacao de uma loja —
    nao precisa de seed manual por loja."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM fin_cofre WHERE loja_id = $1", loja_id)
        if row:
            return dict(row)
        row = await db.fetchrow(
            "INSERT INTO fin_cofre (loja_id, saldo_atual) VALUES ($1, 0) ON CONFLICT (loja_id) DO UPDATE SET loja_id = EXCLUDED.loja_id RETURNING *",
            loja_id)
        return dict(row)
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro get_ou_criar_cofre loja {loja_id}: {e}")
        return {"error": str(e)}


def saldo(loja_id: int) -> float:
    async def _go():
        db = await get_db()
        return await db.fetchval("SELECT saldo_atual FROM fin_cofre WHERE loja_id = $1", loja_id)
    try:
        v = run_async(_go())
        return float(v or 0)
    except Exception as e:
        log(AGENT, f"Erro saldo loja {loja_id}: {e}")
        return 0.0


def listar_movimentos(loja_id: int, dias: int = 90) -> dict:
    async def _go():
        db = await get_db()
        cofre = await db.fetchrow("SELECT * FROM fin_cofre WHERE loja_id = $1", loja_id)
        if not cofre:
            return {"saldo_atual": 0.0, "movimentos": []}
        rows = await db.fetch(
            "SELECT * FROM fin_cofre_movimentos WHERE cofre_id = $1 AND data >= CURRENT_DATE - $2::int ORDER BY data DESC, id DESC",
            cofre["id"], dias)
        return {"saldo_atual": float(cofre["saldo_atual"] or 0), "movimentos": [dict(r) for r in rows]}
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro listar_movimentos loja {loja_id}: {e}")
        return {"saldo_atual": 0.0, "movimentos": []}


def criar_movimento(loja_id: int, tipo: str, valor: float, categoria: str = None,
                     descricao: str = None, caixa_id: int = None,
                     criado_por: str = None, criado_por_id: int = None) -> dict:
    if tipo not in TIPOS_VALIDOS:
        return {"error": f"Tipo invalido. Use um de: {', '.join(TIPOS_VALIDOS)}"}
    if tipo == "saida_despesa" and categoria not in CATEGORIAS_DESPESA:
        return {"error": f"Categoria invalida pra saida_despesa. Use uma de: {', '.join(CATEGORIAS_DESPESA)}"}
    valor = float(valor or 0)
    if valor == 0:
        return {"error": "Valor nao pode ser zero"}
    # entrada soma no saldo; toda saida (troco/despesa) subtrai; ajuste pode
    # ser positivo ou negativo — o sinal informado ja' e' o delta aplicado.
    if tipo == "entrada_sangria":
        delta = abs(valor)
    elif tipo in ("saida_troco", "saida_despesa"):
        delta = -abs(valor)
    else:  # ajuste
        delta = valor

    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                cofre = await conn.fetchrow("SELECT * FROM fin_cofre WHERE loja_id = $1 FOR UPDATE", loja_id)
                if not cofre:
                    cofre = await conn.fetchrow(
                        "INSERT INTO fin_cofre (loja_id, saldo_atual) VALUES ($1, 0) RETURNING *", loja_id)
                mov = await conn.fetchrow("""
                    INSERT INTO fin_cofre_movimentos
                        (cofre_id, tipo, categoria, valor, descricao, caixa_id, criado_por, criado_por_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *
                """, cofre["id"], tipo, categoria, valor, descricao, caixa_id, criado_por, criado_por_id)
                novo_saldo = await conn.fetchval(
                    "UPDATE fin_cofre SET saldo_atual = saldo_atual + $1 WHERE id = $2 RETURNING saldo_atual",
                    delta, cofre["id"])
                return {"movimento": dict(mov), "saldo_atual": float(novo_saldo or 0)}
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro criar_movimento loja {loja_id}: {e}")
        return {"error": str(e)}


def saldo_total(loja_ids: list = None) -> float:
    """Soma saldo_atual de todos os cofres — usado no dashboard de Visao
    Geral. loja_ids restringe a lojas especificas (RBAC de lojas_permitidas
    aplicado na rota)."""
    async def _go():
        db = await get_db()
        if loja_ids is not None:
            if not loja_ids:
                return 0
            return await db.fetchval("SELECT COALESCE(SUM(saldo_atual),0) FROM fin_cofre WHERE loja_id = ANY($1::int[])", loja_ids)
        return await db.fetchval("SELECT COALESCE(SUM(saldo_atual),0) FROM fin_cofre")
    try:
        v = run_async(_go())
        return float(v or 0)
    except Exception as e:
        log(AGENT, f"Erro saldo_total: {e}")
        return 0.0


def get_loja_do_movimento(movimento_id: int) -> int:
    """Resolve o loja_id dono de um movimento — usado na rota DELETE pra
    checar requer_acesso_loja ANTES de excluir (a URL so' tem movimento_id,
    sem loja_id, entao o decorator normal nao teria o que checar)."""
    async def _go():
        db = await get_db()
        return await db.fetchval(
            "SELECT cf.loja_id FROM fin_cofre_movimentos m JOIN fin_cofre cf ON cf.id = m.cofre_id WHERE m.id = $1",
            movimento_id)
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro get_loja_do_movimento {movimento_id}: {e}")
        return None


def excluir_movimento(movimento_id: int) -> dict:
    """Exclusao reverte o delta aplicado no saldo — nao deixa o saldo
    dessincronizado do extrato."""
    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                mov = await conn.fetchrow("SELECT * FROM fin_cofre_movimentos WHERE id = $1 FOR UPDATE", movimento_id)
                if not mov:
                    return {"error": "Movimento nao encontrado"}
                valor = float(mov["valor"] or 0)
                if mov["tipo"] == "entrada_sangria":
                    delta = -abs(valor)
                elif mov["tipo"] in ("saida_troco", "saida_despesa"):
                    delta = abs(valor)
                else:
                    delta = -valor
                await conn.execute("UPDATE fin_cofre SET saldo_atual = saldo_atual + $1 WHERE id = $2", delta, mov["cofre_id"])
                await conn.execute("DELETE FROM fin_cofre_movimentos WHERE id = $1", movimento_id)
                return {"success": True}
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro excluir_movimento {movimento_id}: {e}")
        return {"error": str(e)}
