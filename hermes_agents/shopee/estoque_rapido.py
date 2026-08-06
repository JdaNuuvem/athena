"""Shopee Estoque Rapido — grid SKU x loja para edicao em lote de estoque,
substituindo o fluxo Playwright do sistema ESTOQUE RAPIDO externo por
chamadas diretas a API oficial da Shopee.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import get_db, run_async
from core.lojas import listar_lojas_shopee, _loja_efetiva_async, obter
from core.estoque import ajustar_absoluto
from .stock import sincronizar_estoque_shopee

AGENT = "AG-03 | Shopee Estoque Rapido"


def listar_grid_estoque_rapido(busca: str = "", pagina: int = 1, por_pagina: int = 50,
                                skus: list = None) -> dict:
    """Monta o grid SKU x loja Shopee. Com `skus` informado, ignora busca/
    paginacao e retorna exatamente aquelas linhas (usado por
    atualizar_celula_estoque_rapido pra reler 1 linha apos salvar)."""
    async def _go():
        db = await get_db()
        lojas = listar_lojas_shopee()
        if not lojas:
            return {"lojas": [], "produtos": [], "total": 0}
        shop_ids = [l["shopee_shop_id"] for l in lojas]

        if skus:
            sku_rows = await db.fetch(
                "SELECT DISTINCT a.sku, c.descricao AS nome FROM anuncios a "
                "LEFT JOIN catalogo_produtos c ON c.sku = a.sku "
                "WHERE a.marketplace = 'shopee' AND a.shop_id = ANY($1) AND a.sku = ANY($2) "
                "ORDER BY a.sku", shop_ids, skus)
            total = len(sku_rows)
        else:
            where = ["a.marketplace = 'shopee'", "a.shop_id = ANY($1)"]
            params = [shop_ids]
            if busca:
                n = len(params) + 1
                where.append(f"(a.sku ILIKE ${n} OR c.descricao ILIKE ${n})")
                params.append(f"%{busca}%")
            sql_where = " AND ".join(where)
            total = await db.fetchval(
                f"SELECT COUNT(DISTINCT a.sku) FROM anuncios a "
                f"LEFT JOIN catalogo_produtos c ON c.sku = a.sku WHERE {sql_where}", *params)
            offset = (pagina - 1) * por_pagina
            n = len(params) + 1
            sku_rows = await db.fetch(
                f"SELECT DISTINCT a.sku, c.descricao AS nome FROM anuncios a "
                f"LEFT JOIN catalogo_produtos c ON c.sku = a.sku WHERE {sql_where} "
                f"ORDER BY a.sku LIMIT ${n} OFFSET ${n + 1}", *params, por_pagina, offset)

        lojas_out = [{"id": l["id"], "nome": l["nome"], "shopee_shop_name": l["shopee_shop_name"]} for l in lojas]
        skus_pagina = [r["sku"] for r in sku_rows]
        if not skus_pagina:
            return {"lojas": lojas_out, "produtos": [], "total": total}

        pares = await db.fetch(
            "SELECT sku, shop_id FROM anuncios WHERE marketplace = 'shopee' "
            "AND sku = ANY($1) AND shop_id = ANY($2)", skus_pagina, shop_ids)
        pares_set = {(p["sku"], p["shop_id"]) for p in pares}

        nomes_efetivos = {l["id"]: await _loja_efetiva_async(l["nome"]) for l in lojas}
        nomes_unicos = list(set(nomes_efetivos.values()))

        saldos = await db.fetch(
            "SELECT sku, loja, quantidade FROM estoque_lojas WHERE sku = ANY($1) AND loja = ANY($2)",
            skus_pagina, nomes_unicos)
        saldo_map = {(s["sku"], s["loja"]): float(s["quantidade"]) for s in saldos}

        produtos = []
        for r in sku_rows:
            estoque = {}
            for l in lojas:
                tem_anuncio = (r["sku"], l["shopee_shop_id"]) in pares_set
                if not tem_anuncio:
                    estoque[l["id"]] = None
                else:
                    nome_efetivo = nomes_efetivos[l["id"]]
                    estoque[l["id"]] = saldo_map.get((r["sku"], nome_efetivo), 0.0)
            produtos.append({"sku": r["sku"], "nome": r["nome"] or r["sku"], "estoque": estoque})

        return {"lojas": lojas_out, "produtos": produtos, "total": total}
    return run_async(_go())


def atualizar_celula_estoque_rapido(sku: str, loja_id: int, quantidade: float, usuario: dict,
                                     ip: str = None, dispositivo: str = None) -> dict:
    """Salva 1 celula do grid: grava saldo local e sincroniza com a Shopee de
    forma SINCRONA (nao dispara thread solta) — o usuario precisa ver na hora
    se a Shopee aceitou. Falha ao gravar local nunca chama a Shopee."""
    loja = obter(loja_id)
    if not loja:
        return {"ok": False, "erro_local": f"Loja {loja_id} nao encontrada"}

    resultado_local = ajustar_absoluto(sku, loja["nome"], quantidade, "estoque_rapido",
                                        usuario.get("user_id"), usuario.get("nome", ""), ip, dispositivo)
    if resultado_local.get("erro"):
        return {"ok": False, "erro_local": resultado_local["erro"]}

    resultado_shopee = sincronizar_estoque_shopee(sku, int(quantidade), loja_id=loja_id)
    grid = listar_grid_estoque_rapido(skus=[sku])
    linha = grid["produtos"][0] if grid["produtos"] else None

    return {
        "ok": "error" not in resultado_shopee,
        "salvo_local": True,
        "erro_shopee": resultado_shopee.get("error"),
        "linha": linha,
    }
