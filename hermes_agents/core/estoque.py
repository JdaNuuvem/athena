"""Estoque por loja — CRUD local + movimentacoes + Bling sync."""
from core import get_db, run_async, log

AGENT = "Estoque"

_ok = False

def _ensure():
    global _ok
    if _ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50) NOT NULL,
                loja VARCHAR(50) NOT NULL,
                tipo VARCHAR(20) NOT NULL,
                quantidade DECIMAL(12,3) NOT NULL,
                loja_relacionada VARCHAR(50),
                motivo VARCHAR(200),
                data TIMESTAMP DEFAULT NOW()
            )
        """)
    try:
        run_async(_go())
        _ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela: {e}")


def _where_loja(loja: str) -> str:
    if loja.isdigit():
        return f"e.loja = (SELECT nome FROM lojas WHERE id = {int(loja)})"
    return f"e.loja = '{loja.replace(chr(39), chr(39) + chr(39))}'"


def listar(loja: str = "", busca: str = "", pagina: int = 1, por_pagina: int = 30) -> dict:
    async def _go():
        db = await get_db()
        where = ["1=1"]
        if loja and loja != "todas":
            where.append(_where_loja(loja))
        if busca:
            where.append(f"(c.sku ILIKE '%{busca}%' OR c.descricao ILIKE '%{busca}%')")
        sql_where = " AND ".join(where)
        total = await db.fetchval(
            f"SELECT COUNT(*) FROM estoque_lojas e JOIN catalogo_produtos c ON c.sku = e.sku WHERE {sql_where}")
        offset = (pagina - 1) * por_pagina
        rows = await db.fetch(f"""
            SELECT e.id, e.sku, c.descricao AS nome, e.loja, e.quantidade, e.data_atualizacao,
                   COALESCE(c.imagem_url, '') AS imagem_url, c.situacao
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE {sql_where}
            ORDER BY e.data_atualizacao DESC
            LIMIT {por_pagina} OFFSET {offset}
        """)
        return {"estoque": [dict(r) for r in rows], "total": total, "pagina": pagina}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e), "estoque": [], "total": 0}


def atualizar(sku: str, loja_nome: str, quantidade: float, sync_bling: bool = True) -> dict:
    if quantidade < 0:
        return {"erro": "quantidade nao pode ser negativa"}
    async def _go():
        db = await get_db()
        await db.execute("""
            INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (sku, loja) DO UPDATE SET quantidade = $3, data_atualizacao = NOW()
        """, sku, loja_nome, quantidade)
        await db.execute("""
            INSERT INTO catalogo_produtos (sku, descricao) VALUES ($1, $1)
            ON CONFLICT (sku) DO NOTHING
        """, sku)
    try:
        run_async(_go())
        result = {"ok": True, "sku": sku, "loja": loja_nome, "quantidade": quantidade}
        if sync_bling:
            from bling_erp import sincronizar_estoque_para_bling
            result["bling_sync"] = sincronizar_estoque_para_bling(sku, loja_nome, quantidade)
        return result
    except Exception as e:
        return {"erro": str(e)}


def entrada(sku: str, loja: str, quantidade: float, motivo: str = "") -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        atual = await db.fetchval(
            "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, loja)
        atual = float(atual or 0)
        nova = atual + quantidade
        await db.execute("""
            INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (sku, loja) DO UPDATE SET quantidade = $3, data_atualizacao = NOW()
        """, sku, loja, nova)
        await db.execute("""
            INSERT INTO estoque_movimentacoes (sku, loja, tipo, quantidade, motivo)
            VALUES ($1, $2, 'entrada', $3, $4)
        """, sku, loja, quantidade, motivo)
        return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade,
                "anterior": atual, "atual": nova}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def saida(sku: str, loja: str, quantidade: float, motivo: str = "") -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        atual = await db.fetchval(
            "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, loja)
        atual = float(atual or 0)
        if atual < quantidade:
            return {"erro": f"Saldo insuficiente ({atual} disponivel, {quantidade} solicitado)"}
        nova = atual - quantidade
        await db.execute(
            "UPDATE estoque_lojas SET quantidade = $1, data_atualizacao = NOW() WHERE sku = $2 AND loja = $3",
            nova, sku, loja)
        await db.execute("""
            INSERT INTO estoque_movimentacoes (sku, loja, tipo, quantidade, motivo)
            VALUES ($1, $2, 'saida', $3, $4)
        """, sku, loja, quantidade, motivo)
        return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade,
                "anterior": atual, "atual": nova}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def transferir(sku: str, origem: str, destino: str, quantidade: float, motivo: str = "") -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        saldo_origem = await db.fetchval(
            "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, origem)
        saldo_origem = float(saldo_origem or 0)
        if saldo_origem < quantidade:
            return {"erro": f"Saldo insuficiente na origem ({saldo_origem} em {origem})"}
        saldo_destino = await db.fetchval(
            "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, destino)
        saldo_destino = float(saldo_destino or 0)

        await db.execute(
            "UPDATE estoque_lojas SET quantidade = $1, data_atualizacao = NOW() WHERE sku = $2 AND loja = $3",
            saldo_origem - quantidade, sku, origem)
        await db.execute("""
            INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (sku, loja) DO UPDATE SET quantidade = estoque_lojas.quantidade + $3, data_atualizacao = NOW()
        """, sku, destino, quantidade)

        await db.execute("""
            INSERT INTO estoque_movimentacoes (sku, loja, tipo, quantidade, loja_relacionada, motivo)
            VALUES ($1, $2, 'transferencia_origem', $3, $4, $5)
        """, sku, origem, quantidade, destino, motivo)
        await db.execute("""
            INSERT INTO estoque_movimentacoes (sku, loja, tipo, quantidade, loja_relacionada, motivo)
            VALUES ($1, $2, 'transferencia_destino', $3, $4, $5)
        """, sku, destino, quantidade, origem, motivo)

        return {"ok": True, "sku": sku, "origem": origem, "destino": destino,
                "quantidade": quantidade, "saldo_origem": saldo_origem - quantidade,
                "saldo_destino": saldo_destino + quantidade}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def movimentacoes(sku: str = "", loja: str = "", limite: int = 50) -> list:
    _ensure()
    async def _go():
        db = await get_db()
        where = ["1=1"]
        if sku:
            where.append(f"m.sku = '{sku}'")
        if loja:
            where.append(f"m.loja = '{loja}'")
        sql_where = " AND ".join(where)
        rows = await db.fetch(f"""
            SELECT m.*, c.descricao AS produto_nome
            FROM estoque_movimentacoes m
            LEFT JOIN catalogo_produtos c ON c.sku = m.sku
            WHERE {sql_where}
            ORDER BY m.data DESC LIMIT {limite}
        """)
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except:
        return []


def ratear(sku: str, total: float, modo: str = "igual", lojas: list = None,
           periodo_dias: int = 30, percentuais: dict = None) -> dict:
    _ensure()
    percentuais = percentuais or {}
    async def _go():
        db = await get_db()
        if lojas:
            lojas_validas = [l for l in lojas if l.strip()]
        else:
            rows = await db.fetch("SELECT nome FROM lojas ORDER BY nome")
            lojas_validas = [r["nome"] for r in rows]
        if not lojas_validas:
            return {"erro": "Nenhuma loja ativa encontrada"}
        n = len(lojas_validas)
        if modo == "igual":
            pcts = {l: round(100.0 / n, 4) for l in lojas_validas}
        elif modo == "proporcional":
            if percentuais:
                pcts = {l: float(p) for l, p in percentuais.items() if l in lojas_validas}
            else:
                rows = await db.fetch(
                    f"SELECT COALESCE(l.nome, 'Venda direta') AS loja, SUM(v.quantidade) AS qtd "
                    f"FROM vendas v LEFT JOIN lojas l ON l.id = v.loja_id "
                    f"WHERE v.sku = $1 AND v.data >= CURRENT_DATE - {periodo_dias} "
                    f"GROUP BY COALESCE(l.nome, 'Venda direta') ORDER BY qtd DESC", sku)
                vendas_map = {r["loja"]: float(r["qtd"]) for r in rows}
                total_vendido = sum(vendas_map.values())
                if total_vendido > 0:
                    pcts = {}
                    for l in lojas_validas:
                        v = vendas_map.get(l, 0)
                        pcts[l] = round(v / total_vendido * 100, 4) if total_vendido else 0
                    resto = 100 - sum(pcts.values())
                    if lojas_validas and abs(resto) > 0.001:
                        pcts[lojas_validas[0]] = round(pcts.get(lojas_validas[0], 0) + resto, 4)
                else:
                    pcts = {l: round(100.0 / n, 4) for l in lojas_validas}
        else:
            return {"erro": f"Modo desconhecido: {modo}"}
        soma = sum(pcts.values())
        if abs(soma - 100) > 0.01:
            pcts[lojas_validas[0]] = round(pcts.get(lojas_validas[0], 0) + (100 - soma), 4)
        resultados = []
        distribuido = 0
        for i, loja in enumerate(lojas_validas):
            qtd = round(total * pcts[loja] / 100, 3)
            if i == n - 1:
                qtd = round(total - distribuido, 3)
            distribuido += qtd
            await db.execute("""
                INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (sku, loja) DO UPDATE SET quantidade = $3, data_atualizacao = NOW()
            """, sku, loja, qtd)
            await db.execute("""
                INSERT INTO estoque_movimentacoes (sku, loja, tipo, quantidade, motivo)
                VALUES ($1, $2, 'rateio', $3, $4)
            """, sku, loja, qtd, f"rateio {modo}: {pcts[loja]}%")
            resultados.append({"loja": loja, "quantidade": qtd, "percentual": pcts[loja]})
        return {"ok": True, "sku": sku, "total": total, "modo": modo,
                "lojas": resultados, "percentuais": pcts}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}

def sync_bling(sku: str, loja: str) -> dict:
    try:
        async def _go():
            db = await get_db()
            return await db.fetchval(
                "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, loja)
        qtd = float(run_async(_go()) or 0)
        from bling_erp import sincronizar_estoque_para_bling
        return sincronizar_estoque_para_bling(sku, loja, qtd)
    except Exception as e:
        return {"erro": str(e)}
