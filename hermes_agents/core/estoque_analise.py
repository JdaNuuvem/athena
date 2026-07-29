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