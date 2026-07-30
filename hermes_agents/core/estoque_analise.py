"""Analise de estoque — giro, ruptura e cobertura calculados sobre dado
real (estoque_lojas, vendas_itens, produtos_loja/catalogo_produtos).
Substitui os indicadores que a tela `/estoque/analise` gerava com
Math.random() no cliente (ver spec 2026-07-29-estoque-analise-*)."""
from datetime import date
from core import get_db, run_async

AGENT = "Estoque Analise"

# Tipos de estoque_movimentacoes que representam reabastecimento sem
# ambiguidade de sinal. "ajuste" e "devolucao" sao usados tanto pra
# entrada quanto pra saida no ledger hoje (ver core/estoque.py
# _MAPA_MOVIMENTO_ENTRADA/_MAPA_MOVIMENTO_SAIDA) — contar um "ajuste"
# como abastecimento estaria errado metade das vezes, entao ficam de fora.
TIPOS_ABASTECIMENTO = ("compra", "recebimento")


def _filtro_loja(coluna: str, loja: str, where: list, params: list):
    if loja:
        params.append(loja)
        where.append(f"{coluna} = ${len(params)}")


def giro(loja: str = "", dias: int = 30) -> list:
    """Giro = saidas do periodo / saldo atual. "Estoque medio" e' aproximado
    pelo saldo atual — nao ha snapshot diario de estoque no banco pra
    calcular media de verdade (limitacao declarada na spec)."""
    async def _go():
        db = await get_db()
        where_saldo = ["1=1"]
        params_saldo = []
        _filtro_loja("e.loja", loja, where_saldo, params_saldo)
        saldos = await db.fetch(f"""
            SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS saldo_atual
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE {" AND ".join(where_saldo)}
            GROUP BY e.sku, c.descricao
        """, *params_saldo)

        where_vendas = ["vp.status != 'cancelado'", f"vp.data >= CURRENT_DATE - {int(dias) * 2}"]
        params_vendas = []
        if loja:
            params_vendas.append(loja)
            where_vendas.append(f"vp.loja_id = (SELECT id FROM lojas WHERE nome = ${len(params_vendas)})")
        vendas = await db.fetch(f"""
            SELECT vi.sku,
                   SUM(CASE WHEN vp.data >= CURRENT_DATE - {int(dias)} THEN vi.quantidade ELSE 0 END) AS saidas_periodo,
                   SUM(CASE WHEN vp.data < CURRENT_DATE - {int(dias)} THEN vi.quantidade ELSE 0 END) AS saidas_periodo_anterior
            FROM vendas_itens vi
            JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE {" AND ".join(where_vendas)}
            GROUP BY vi.sku
        """, *params_vendas)
        vendas_por_sku = {v["sku"]: v for v in vendas}

        out = []
        for s in saldos:
            v = vendas_por_sku.get(s["sku"], {})
            saidas = float(v.get("saidas_periodo") or 0)
            saidas_ant = float(v.get("saidas_periodo_anterior") or 0)
            saldo_atual = float(s["saldo_atual"] or 0)
            divisor = saldo_atual if saldo_atual > 0 else 1
            giro_val = round(saidas / divisor, 1)
            tendencia = "up" if saidas > saidas_ant else "down" if saidas < saidas_ant else "stable"
            out.append({
                "sku": s["sku"], "produto": s["produto"],
                "saidas_30d": int(saidas), "estoque_medio": int(saldo_atual),
                "giro": giro_val, "tendencia": tendencia,
            })
        return out
    try:
        return run_async(_go())
    except Exception:
        return []


def ruptura(loja: str = "") -> list:
    """SKU com saldo < minimo efetivo. Com loja filtrada, minimo efetivo e'
    o override de produtos_loja pra aquela loja (fallback catalogo mestre).
    Agregado (sem filtro), compara o total contra o minimo global do
    catalogo — somar minimos diferentes por loja nao teria um limiar unico
    que faca sentido."""
    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        _filtro_loja("e.loja", loja, where, params)
        if loja:
            rows = await db.fetch(f"""
                SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS saldo_atual,
                       COALESCE(MAX(pl.estoque_minimo), MAX(c.estoque_minimo), 0) AS estoque_minimo
                FROM estoque_lojas e
                JOIN catalogo_produtos c ON c.sku = e.sku
                LEFT JOIN produtos_loja pl ON pl.sku = e.sku AND pl.loja = e.loja
                WHERE {" AND ".join(where)}
                GROUP BY e.sku, c.descricao
                HAVING SUM(e.quantidade) < COALESCE(MAX(pl.estoque_minimo), MAX(c.estoque_minimo), 0)
            """, *params)
        else:
            rows = await db.fetch(f"""
                SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS saldo_atual,
                       COALESCE(c.estoque_minimo, 0) AS estoque_minimo
                FROM estoque_lojas e
                JOIN catalogo_produtos c ON c.sku = e.sku
                WHERE {" AND ".join(where)}
                GROUP BY e.sku, c.descricao, c.estoque_minimo
                HAVING SUM(e.quantidade) < COALESCE(c.estoque_minimo, 0)
            """, *params)
        if not rows:
            return []

        skus = [r["sku"] for r in rows]
        abastecimento = await db.fetch("""
            SELECT DISTINCT ON (sku) sku, data
            FROM estoque_movimentacoes
            WHERE sku = ANY($1) AND tipo = ANY($2)
            ORDER BY sku, data DESC
        """, skus, list(TIPOS_ABASTECIMENTO))
        abastecimento_por_sku = {a["sku"]: a["data"] for a in abastecimento}

        out = []
        for r in rows:
            ultimo = abastecimento_por_sku.get(r["sku"])
            if ultimo is None:
                out.append({
                    "sku": r["sku"], "produto": r["produto"],
                    "dias_ruptura": 0, "vendas_perdidas_estimadas": 0,
                    "impacto_receita": 0.0, "ultimo_abastecimento": None,
                })
                continue
            dias_ruptura = (date.today() - ultimo.date()).days
            # Velocidade media de venda do SKU nos 30d ANTES do ultimo
            # abastecimento (decisao da spec) — nao a media generica.
            where_vendas = ["vi.sku = $1", "vp.status != 'cancelado'",
                           "vp.data >= $2::timestamp - INTERVAL '30 days' AND vp.data < $2"]
            params_vendas = [r["sku"], ultimo]
            if loja:
                params_vendas.append(loja)
                where_vendas.append(f"vp.loja_id = (SELECT id FROM lojas WHERE nome = ${len(params_vendas)})")
            vendas = await db.fetchrow(f"""
                SELECT COALESCE(SUM(vi.quantidade), 0) AS qtd, COALESCE(AVG(vi.valor_unitario), 0) AS preco_medio
                FROM vendas_itens vi
                JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
                WHERE {" AND ".join(where_vendas)}
            """, *params_vendas)
            velocidade_diaria = float(vendas["qtd"] or 0) / 30
            vendas_perdidas = round(velocidade_diaria * dias_ruptura, 1)
            impacto = round(vendas_perdidas * float(vendas["preco_medio"] or 0), 2)
            out.append({
                "sku": r["sku"], "produto": r["produto"],
                "dias_ruptura": dias_ruptura,
                "vendas_perdidas_estimadas": vendas_perdidas,
                "impacto_receita": impacto,
                "ultimo_abastecimento": ultimo.date().isoformat(),
            })
        return out
    try:
        return run_async(_go())
    except Exception:
        return []


def cobertura(loja: str = "") -> list:
    """Cobertura = saldo atual / demanda diaria media (saidas 30d / 30).
    Sem demanda no periodo, cobertura fica None internamente ("sem venda
    recente", nao Infinity nem crash) e sai como 0 no payload."""
    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        _filtro_loja("e.loja", loja, where, params)
        if loja:
            saldos = await db.fetch(f"""
                SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS estoque_atual,
                       COALESCE(MAX(pl.estoque_minimo), MAX(c.estoque_minimo), 0) AS estoque_minimo,
                       COALESCE(MAX(pl.estoque_maximo), MAX(c.estoque_maximo), 0) AS estoque_maximo
                FROM estoque_lojas e
                JOIN catalogo_produtos c ON c.sku = e.sku
                LEFT JOIN produtos_loja pl ON pl.sku = e.sku AND pl.loja = e.loja
                WHERE {" AND ".join(where)}
                GROUP BY e.sku, c.descricao
            """, *params)
        else:
            saldos = await db.fetch(f"""
                SELECT e.sku, c.descricao AS produto, SUM(e.quantidade) AS estoque_atual,
                       COALESCE(c.estoque_minimo, 0) AS estoque_minimo,
                       COALESCE(c.estoque_maximo, 0) AS estoque_maximo
                FROM estoque_lojas e
                JOIN catalogo_produtos c ON c.sku = e.sku
                WHERE {" AND ".join(where)}
                GROUP BY e.sku, c.descricao, c.estoque_minimo, c.estoque_maximo
            """, *params)

        where_v = ["vp.status != 'cancelado'", "vp.data >= CURRENT_DATE - 30"]
        params_v = []
        if loja:
            params_v.append(loja)
            where_v.append(f"vp.loja_id = (SELECT id FROM lojas WHERE nome = ${len(params_v)})")
        vendas = await db.fetch(f"""
            SELECT vi.sku, SUM(vi.quantidade) AS saidas_30d
            FROM vendas_itens vi
            JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE {" AND ".join(where_v)}
            GROUP BY vi.sku
        """, *params_v)
        vendas_por_sku = {v["sku"]: float(v["saidas_30d"] or 0) for v in vendas}

        out = []
        for s in saldos:
            estoque_atual = float(s["estoque_atual"] or 0)
            minimo = float(s["estoque_minimo"] or 0)
            maximo = float(s["estoque_maximo"] or 0)
            demanda_diaria = vendas_por_sku.get(s["sku"], 0.0) / 30
            cobertura_dias = round(estoque_atual / demanda_diaria) if demanda_diaria > 0 else None

            if estoque_atual <= 0:
                status = "critico"
            elif minimo > 0 and estoque_atual < minimo:
                status = "baixo"
            elif maximo > 0 and estoque_atual > maximo:
                status = "excesso"
            elif cobertura_dias is not None and cobertura_dias < 7:
                status = "baixo"
            else:
                status = "normal"

            out.append({
                "sku": s["sku"], "produto": s["produto"],
                "estoque_atual": int(estoque_atual),
                "demanda_diaria_media": round(demanda_diaria, 1),
                "cobertura_dias": cobertura_dias if cobertura_dias is not None else 0,
                "estoque_minimo": int(minimo), "estoque_maximo": int(maximo),
                "status": status,
            })
        return out
    try:
        return run_async(_go())
    except Exception:
        return []