"""Contagem ciclica — contagem fisica parcial e recorrente (nao inventario
completo), priorizando os SKUs de maior valor em estoque por loja que nao
foram contados recentemente. Divergencia vira ajuste automatico (entrada
livre; saida acima do limite passa pela mesma alcada de aprovacao)."""
from core import get_db, run_async, log
from core.estoque import entrada as _entrada, saida as _saida, LIMITE_APROVACAO_UNIDADES

AGENT = "Estoque Contagem"

DIAS_SEM_RECONTAR = 30
SUGESTOES_POR_LOJA = 15

_ok = False

def _ensure():
    global _ok
    if _ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_contagens (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50) NOT NULL,
                loja VARCHAR(50) NOT NULL,
                quantidade_sistema DECIMAL(12,3) NOT NULL,
                quantidade_contada DECIMAL(12,3) NOT NULL,
                diferenca DECIMAL(12,3) NOT NULL,
                ajuste_status VARCHAR(20) NOT NULL,
                usuario_id INT, usuario_nome VARCHAR(100),
                criado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        # Fase 3: coluna aditiva loja_id (ver core/catalogo.py::estoque_lojas.loja_id).
        await db.execute("ALTER TABLE estoque_contagens ADD COLUMN IF NOT EXISTS loja_id INT REFERENCES lojas(id)")
    try:
        run_async(_go())
        _ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela: {e}")


def sugestoes(loja: str = "") -> list:
    """SKUs de maior valor (quantidade x custo) por loja, ainda nao contados
    nos ultimos DIAS_SEM_RECONTAR dias — foca o esforco onde uma discrepancia
    doeria mais no caixa, em vez de contar tudo ou contar aleatorio."""
    _ensure()
    async def _go():
        db = await get_db()
        where = ["e.quantidade > 0"]
        params = []
        if loja:
            where.append(f"e.loja = ${len(params) + 1}")
            params.append(loja)
        sql_where = " AND ".join(where)
        rows = await db.fetch(f"""
            SELECT e.sku, e.loja, e.quantidade, c.descricao AS nome,
                   COALESCE(c.preco_custo, 0) AS preco_custo,
                   (e.quantidade * COALESCE(c.preco_custo, 0)) AS valor_total,
                   (SELECT MAX(criado_em) FROM estoque_contagens ec WHERE ec.sku = e.sku AND ec.loja = e.loja) AS ultima_contagem
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE {sql_where}
            AND ((SELECT MAX(criado_em) FROM estoque_contagens ec WHERE ec.sku = e.sku AND ec.loja = e.loja) IS NULL
                 OR (SELECT MAX(criado_em) FROM estoque_contagens ec WHERE ec.sku = e.sku AND ec.loja = e.loja) < NOW() - INTERVAL '{DIAS_SEM_RECONTAR} days')
            ORDER BY e.loja, valor_total DESC
        """, *params)
        por_loja = {}
        for r in rows:
            por_loja.setdefault(r["loja"], []).append(dict(r))
        out = []
        for loja_nome, itens in por_loja.items():
            out.extend(itens[:SUGESTOES_POR_LOJA])
        return out
    try:
        return run_async(_go())
    except Exception as e:
        return []


def registrar(sku: str, loja: str, quantidade_contada: float,
              usuario_id: int = None, usuario_nome: str = "") -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        atual = await db.fetchval(
            "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, loja)
        return float(atual or 0)
    quantidade_sistema = run_async(_go())
    diferenca = round(quantidade_contada - quantidade_sistema, 3)

    if diferenca == 0:
        ajuste_status = "sem_diferenca"
        resultado_ajuste = {"ok": True}
    elif diferenca > 0:
        resultado_ajuste = _entrada(sku, loja, diferenca, "ajuste_inventario", usuario_id, usuario_nome)
        ajuste_status = "aplicado" if not resultado_ajuste.get("erro") else "erro"
    else:
        falta = abs(diferenca)
        if falta > LIMITE_APROVACAO_UNIDADES:
            from core.estoque_aprovacoes import solicitar as _solicitar_aprovacao
            resultado_ajuste = _solicitar_aprovacao(sku, loja, falta, "ajuste_inventario", usuario_id, usuario_nome)
            ajuste_status = "pendente_aprovacao" if not resultado_ajuste.get("erro") else "erro"
        else:
            resultado_ajuste = _saida(sku, loja, falta, "ajuste_inventario", usuario_id, usuario_nome)
            ajuste_status = "aplicado" if not resultado_ajuste.get("erro") else "erro"

    async def _salvar():
        db = await get_db()
        loja_id = await db.fetchval("SELECT id FROM lojas WHERE nome = $1", loja)
        await db.execute("""
            INSERT INTO estoque_contagens
                (sku, loja, loja_id, quantidade_sistema, quantidade_contada, diferenca, ajuste_status, usuario_id, usuario_nome)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, sku, loja, loja_id, quantidade_sistema, quantidade_contada, diferenca, ajuste_status, usuario_id, usuario_nome)
    try:
        run_async(_salvar())
    except Exception as e:
        log(AGENT, f"Erro ao salvar contagem: {e}")

    return {
        "sku": sku, "loja": loja, "quantidade_sistema": quantidade_sistema,
        "quantidade_contada": quantidade_contada, "diferenca": diferenca,
        "ajuste_status": ajuste_status, "ajuste": resultado_ajuste,
    }


def historico(loja: str = "", limite: int = 50, loja_ids: list = None) -> list:
    _ensure()
    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        if loja:
            where.append(f"loja = ${len(params) + 1}")
            params.append(loja)
        elif loja_ids is not None:
            params.append(loja_ids)
            where.append(f"loja_id = ANY(${len(params)})")
        sql_where = " AND ".join(where)
        rows = await db.fetch(f"""
            SELECT ec.*, c.descricao AS produto_nome
            FROM estoque_contagens ec
            LEFT JOIN catalogo_produtos c ON c.sku = ec.sku
            WHERE {sql_where}
            ORDER BY ec.criado_em DESC LIMIT {int(limite)}
        """, *params)
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        return []
