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


async def _upsert_produto_async(conn, produto: dict) -> dict:
    """conn: uma conexao asyncpg ja adquirida (nao a pool) - quem adquire e
    controla o ciclo de vida da conexao e' o chamador (uma por pagina, ver
    _upsert_pagina)."""
    sku = str(produto.get("codproduto", "")).strip()
    if not sku:
        return {"erro": "codproduto vazio"}
    async with conn.transaction():
        row = await conn.fetchrow("""
            INSERT INTO catalogo_produtos (sku, descricao, ean, ncm, unidade_padrao, peso_bruto, id_i9logic)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (sku) DO UPDATE SET
                descricao=COALESCE(NULLIF($2,''), catalogo_produtos.descricao),
                ean=COALESCE($3, catalogo_produtos.ean),
                ncm=COALESCE($4, catalogo_produtos.ncm),
                unidade_padrao=COALESCE(NULLIF($5,''), catalogo_produtos.unidade_padrao),
                peso_bruto=COALESCE(NULLIF($6,0), catalogo_produtos.peso_bruto),
                id_i9logic=$7,
                updated_at=NOW()
            RETURNING *
        """, sku, produto.get("descricao") or "", produto.get("ean") or None,
            produto.get("ncm") or None, produto.get("unidademedida") or "UN",
            produto.get("peso") or 0, produto.get("id"))
        await conn.execute("""
            INSERT INTO de_para_i9logic (tipo, id_i9logic, codigo_athena) VALUES ('produto',$1,$2)
            ON CONFLICT (tipo, id_i9logic) DO UPDATE SET codigo_athena=$2
        """, str(produto.get("id")), sku)
    return dict(row)


def _upsert_produto(produto: dict) -> dict:
    """Mantido para uso isolado/pontual - abre a pool e adquire UMA conexao
    real antes de chamar _upsert_produto_async."""
    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            return await _upsert_produto_async(conn, produto)
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def _upsert_pagina(pagina_registros: list) -> tuple:
    """Upserta uma pagina inteira numa unica conexao/transacao por produto -
    reduz de 1 conexao/produto pra 1 conexao/pagina (~111 no total pro
    catalogo inteiro em vez de ~22.105). Retorna (importados, erros_registro)."""
    elegiveis = [p for p in pagina_registros
                 if str(p.get("ativo", "")) == "1" and str(p.get("emlinha", "")) == "1"]
    async def _go():
        db = await get_db()
        importados_pagina = 0
        erros_pagina = []
        async with db.acquire() as conn:
            for produto in elegiveis:
                try:
                    r = await _upsert_produto_async(conn, produto)
                    if isinstance(r, dict) and r.get("erro"):
                        erros_pagina.append({"codproduto": produto.get("codproduto"), "erro": r["erro"]})
                    else:
                        importados_pagina += 1
                except Exception as e:
                    erros_pagina.append({"codproduto": produto.get("codproduto"), "erro": str(e)})
        return importados_pagina, erros_pagina
    try:
        return run_async(_go())
    except Exception as e:
        return 0, [{"codproduto": None, "erro": f"falha na pagina inteira: {e}"}]


def sincronizar_catalogo_i9logic() -> dict:
    """Importacao unica do catalogo inteiro — disparo manual (nao entra no
    scheduler). Idempotente: rodar de novo do zero so' reprocessa (upsert por
    sku), nao duplica."""
    if not BASE_URL:
        return {"erro": "I9LOGIC_BASE_URL nao configurado - configure antes de importar"}
    log(AGENT, "Iniciando import de catalogo i9Logic")
    importados = {"count": 0}
    erros_registro = []

    def _on_pagina(pagina_registros):
        count, erros = _upsert_pagina(pagina_registros)
        importados["count"] += count
        erros_registro.extend(erros)

    try:
        _paginar("produtos", {}, on_pagina=_on_pagina)
    except I9LogicPaginaError as e:
        log(AGENT, f"Import de catalogo falhou na pagina {e.pagina}: {importados['count']} importados ate a falha, {len(erros_registro)} erros")
        return {"erro": str(e), "pagina_falhou": e.pagina,
                "importados_ate_agora": importados["count"], "erros_registro": erros_registro}
    log(AGENT, f"Import de catalogo concluido: {importados['count']} importados, {len(erros_registro)} erros")
    return {"ok": True, "importados": importados["count"], "erros_registro": erros_registro}
