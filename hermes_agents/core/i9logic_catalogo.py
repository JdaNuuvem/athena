"""Import de catalogo — i9Logic -> Athena (importacao unica, disparo manual).

Puxa o catalogo inteiro (/produtos, global, sem filial — 22.105 produtos
confirmados na API real) e faz upsert direto em catalogo_produtos por
sku=codproduto, sem fila de revisao. So' campos com significado direto
entram (sku, descricao, ean, ncm, unidade, peso) — categoria/marca/
fabricante ficam de fora porque sao so' codigos numericos internos do
i9Logic sem endpoint de resolucao (GET /categorias e /marcas retornam 404,
confirmado). Grava o de-para (tipo='produto') automaticamente no mesmo
upsert, deixando a Fase 1 (reconciliacao de saldo) pronta pra usar esses
produtos sem matching manual."""
from core import get_db, run_async, log
from core.i9logic import _paginar, I9LogicPaginaError, BASE_URL

AGENT = "I9Logic Catalogo"


def _upsert_produto(produto: dict) -> dict:
    sku = str(produto.get("codproduto", "")).strip()
    if not sku:
        return {"erro": "codproduto vazio"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO catalogo_produtos (sku, descricao, ean, ncm, unidade_padrao, peso_bruto, id_i9logic)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (sku) DO UPDATE SET
                descricao=$2, ean=$3, ncm=$4, unidade_padrao=$5, peso_bruto=$6, id_i9logic=$7,
                updated_at=NOW()
            RETURNING *
        """, sku, produto.get("descricao") or "", produto.get("ean") or None,
            produto.get("ncm") or None, produto.get("unidademedida") or "UN",
            produto.get("peso") or 0, produto.get("id"))
        await db.execute("""
            INSERT INTO de_para_i9logic (tipo, id_i9logic, codigo_athena) VALUES ('produto',$1,$2)
            ON CONFLICT (tipo, id_i9logic) DO UPDATE SET codigo_athena=$2
        """, str(produto.get("id")), sku)
        return dict(row)
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def sincronizar_catalogo_i9logic() -> dict:
    """Importacao unica do catalogo inteiro — disparo manual (nao entra no
    scheduler). Idempotente: rodar de novo do zero so' reprocessa (upsert por
    sku), nao duplica."""
    if not BASE_URL:
        return {"erro": "I9LOGIC_BASE_URL nao configurado - configure antes de importar"}
    importados = {"count": 0}
    erros_registro = []

    def _on_pagina(pagina_registros):
        for produto in pagina_registros:
            if str(produto.get("ativo", "")) != "1" or str(produto.get("emlinha", "")) != "1":
                continue
            r = _upsert_produto(produto)
            if r.get("erro"):
                erros_registro.append({"codproduto": produto.get("codproduto"), "erro": r["erro"]})
            else:
                importados["count"] += 1

    try:
        _paginar("produtos", {}, on_pagina=_on_pagina)
    except I9LogicPaginaError as e:
        return {"erro": str(e), "pagina_falhou": e.pagina,
                "importados_ate_agora": importados["count"], "erros_registro": erros_registro}
    return {"ok": True, "importados": importados["count"], "erros_registro": erros_registro}
