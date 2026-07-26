"""Relatorio de discrepancias por loja e por operador — agrega saidas grandes
aprovadas, transferencias com discrepancia e contagens ciclicas com falta,
para expor onde investigar (nao substitui investigacao humana, so' aponta)."""
from core import get_db, run_async

def por_loja(dias: int = 30) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT loja,
                SUM(CASE WHEN tipo = 'saida' THEN quantidade ELSE 0 END) AS saidas_aprovadas_qtd,
                COUNT(*) FILTER (WHERE tipo = 'saida') AS saidas_aprovadas_qtd_eventos
            FROM estoque_aprovacoes
            WHERE status = 'aprovada' AND criado_em >= NOW() - INTERVAL '{int(dias)} days'
            GROUP BY loja
        """)
        saidas = {r["loja"]: dict(r) for r in rows}

        rows = await db.fetch(f"""
            SELECT loja_destino AS loja, COUNT(*) AS transferencias_discrepancia
            FROM estoque_transferencias
            WHERE status = 'com_discrepancia' AND criado_em >= NOW() - INTERVAL '{int(dias)} days'
            GROUP BY loja_destino
        """)
        transf = {r["loja"]: r["transferencias_discrepancia"] for r in rows}

        rows = await db.fetch(f"""
            SELECT loja, COUNT(*) AS contagens_com_falta, SUM(ABS(diferenca)) AS unidades_falta
            FROM estoque_contagens
            WHERE diferenca < 0 AND criado_em >= NOW() - INTERVAL '{int(dias)} days'
            GROUP BY loja
        """)
        contagens = {r["loja"]: dict(r) for r in rows}

        lojas = set(saidas) | set(transf) | set(contagens)
        out = []
        for loja in lojas:
            out.append({
                "loja": loja,
                "saidas_aprovadas_qtd": float(saidas.get(loja, {}).get("saidas_aprovadas_qtd", 0) or 0),
                "saidas_aprovadas_eventos": int(saidas.get(loja, {}).get("saidas_aprovadas_qtd_eventos", 0) or 0),
                "transferencias_com_discrepancia": int(transf.get(loja, 0)),
                "contagens_com_falta": int(contagens.get(loja, {}).get("contagens_com_falta", 0) or 0),
                "unidades_falta_contagem": float(contagens.get(loja, {}).get("unidades_falta", 0) or 0),
            })
        out.sort(key=lambda x: x["saidas_aprovadas_qtd"] + x["unidades_falta_contagem"], reverse=True)
        return out
    try:
        return run_async(_go())
    except Exception:
        return []


def por_operador(dias: int = 30) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT usuario_solicitante_nome AS operador,
                COUNT(*) AS saidas_grandes_solicitadas,
                SUM(quantidade) FILTER (WHERE status = 'aprovada') AS saidas_grandes_aprovadas_qtd,
                COUNT(*) FILTER (WHERE status = 'rejeitada') AS saidas_grandes_rejeitadas
            FROM estoque_aprovacoes
            WHERE criado_em >= NOW() - INTERVAL '{int(dias)} days' AND usuario_solicitante_nome IS NOT NULL
            GROUP BY usuario_solicitante_nome
        """)
        por_op = {r["operador"]: dict(r) for r in rows}

        rows = await db.fetch(f"""
            SELECT usuario_nome AS operador, COUNT(*) AS contagens_com_falta, SUM(ABS(diferenca)) AS unidades_falta
            FROM estoque_contagens
            WHERE diferenca < 0 AND criado_em >= NOW() - INTERVAL '{int(dias)} days' AND usuario_nome IS NOT NULL
            GROUP BY usuario_nome
        """)
        for r in rows:
            op = por_op.setdefault(r["operador"], {"operador": r["operador"]})
            op["contagens_com_falta"] = r["contagens_com_falta"]
            op["unidades_falta"] = r["unidades_falta"]

        out = []
        for operador, dados in por_op.items():
            out.append({
                "operador": operador,
                "saidas_grandes_solicitadas": int(dados.get("saidas_grandes_solicitadas", 0) or 0),
                "saidas_grandes_aprovadas_qtd": float(dados.get("saidas_grandes_aprovadas_qtd", 0) or 0),
                "saidas_grandes_rejeitadas": int(dados.get("saidas_grandes_rejeitadas", 0) or 0),
                "contagens_com_falta": int(dados.get("contagens_com_falta", 0) or 0),
                "unidades_falta_contagem": float(dados.get("unidades_falta", 0) or 0),
            })
        out.sort(key=lambda x: x["saidas_grandes_aprovadas_qtd"] + x["unidades_falta_contagem"], reverse=True)
        return out
    try:
        return run_async(_go())
    except Exception:
        return []
