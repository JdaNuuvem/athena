"""Import de catalogo — app proprio de bipagem/atualizacao de estoque
(core/estoque_app_client.py) -> Athena (importacao unica, disparo manual).
NAO fala com a API i9Logic — a unica fonte de dados aqui e' o app da
empresa em http://ipu9fzz363muaape6dklfnpb.177.7.45.242.sslip.io (endpoints
/api/cache/* publicos, sem autenticacao).

Faz upsert direto em catalogo_produtos por sku=codproduto, sem fila de
revisao. So' campos com significado direto entram (sku, descricao, ean,
ncm, unidade, peso) — categoria/marca/fabricante ficam de fora porque no
catalogo de origem sao so' codigos numericos sem tabela de resolucao
disponivel. Grava o de-para (tabela de_para_i9logic, tipo='produto')
automaticamente no mesmo upsert — essa tabela e' compartilhada com a
reconciliacao de saldo fisico x contabil (core/i9logic.py, que essa sim
fala com a API i9Logic de verdade para outra finalidade: comparar saldo
declarado vs contado). Reaproveitar o de-para aqui deixa aquela
reconciliacao pronta pra usar os produtos importados por este modulo sem
matching manual - os ids sao do mesmo catalogo de origem em ambos os casos."""
from core import get_db, run_async, log
from core.estoque_app_client import fetch_produtos, fetch_estoques, EstoqueAppError
from core.i9logic import listar_mapeamentos

AGENT = "Produtos Bipador"

TAMANHO_LOTE = 200  # produtos por transacao/conexao no upsert em lote


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


def sincronizar_catalogo_bipador() -> dict:
    """Importacao unica do catalogo inteiro — disparo manual (nao entra no
    scheduler). Idempotente: rodar de novo do zero so' reprocessa (upsert por
    sku), nao duplica."""
    log(AGENT, "Iniciando import de catalogo (app de bipagem/estoque)")
    try:
        produtos = fetch_produtos()
    except EstoqueAppError as e:
        log(AGENT, f"Import de catalogo falhou ao buscar produtos: {e}")
        return {"erro": str(e)}
    importados = 0
    erros_registro = []
    for inicio in range(0, len(produtos), TAMANHO_LOTE):
        lote = produtos[inicio:inicio + TAMANHO_LOTE]
        count, erros = _upsert_pagina(lote)
        importados += count
        erros_registro.extend(erros)
    log(AGENT, f"Import de catalogo concluido: {importados} importados, {len(erros_registro)} erros")
    return {"ok": True, "importados": importados, "total_recebidos": len(produtos), "erros_registro": erros_registro}


# ── Estoque por loja fisica (a partir do mesmo cache) ──

def _mapa_produto_bipador_para_sku(produtos: list) -> dict:
    """{idproduto_i9logic: sku} a partir do proprio payload de produtos —
    mais barato que reconsultar de_para_i9logic produto a produto."""
    return {p["id"]: str(p.get("codproduto", "")).strip()
            for p in produtos if p.get("id") is not None and str(p.get("codproduto", "")).strip()}


async def _upsert_estoque_loja_async(conn, sku: str, loja: str, quantidade: float) -> None:
    await conn.execute("""
        INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (sku, loja) DO UPDATE SET quantidade=$3, data_atualizacao=NOW()
    """, sku, loja, quantidade)


def sincronizar_estoque_lojas_fisicas() -> dict:
    """Popula estoque_lojas (usado pela listagem /api/produtos) para toda
    loja fisica que ja tem de-para de filial cadastrado (tipo='filial' em
    de_para_i9logic) — sem esse de-para nao ha' como saber qual filial do
    cache corresponde a qual loja Athena, entao essa loja fica de fora
    (reportada em `sem_mapeamento`). Usa tipoestoque=1 (fisico), o mesmo
    criterio que a reconciliacao (core/i9logic.py) trata como saldo de
    prateleira; tipoestoque=2 (contabil) nunca vira saldo aqui."""
    try:
        produtos = fetch_produtos()
        estoques = fetch_estoques()
    except EstoqueAppError as e:
        return {"erro": str(e)}
    sku_por_idproduto = _mapa_produto_bipador_para_sku(produtos)
    filiais_mapeadas = listar_mapeamentos("filial")
    if not filiais_mapeadas:
        return {"erro": "nenhuma filial i9Logic mapeada em de_para_i9logic ainda "
                         "(cadastre em /api/integrations/i9logic/depara antes)"}

    async def _go():
        db = await get_db()
        atualizados, sem_sku = 0, 0
        resultado_por_loja = {}
        async with db.acquire() as conn:
            for m in filiais_mapeadas:
                filial_id = int(m["id_i9logic"])
                loja = m["codigo_athena"]
                itens_filial = [e for e in estoques
                                 if e.get("filial") == filial_id and e.get("tipoestoque") == 1]
                gravados_loja = 0
                async with conn.transaction():
                    for item in itens_filial:
                        sku = sku_por_idproduto.get(item.get("idproduto"))
                        if not sku:
                            sem_sku += 1
                            continue
                        await _upsert_estoque_loja_async(conn, sku, loja, float(item.get("qtd") or 0))
                        gravados_loja += 1
                atualizados += gravados_loja
                resultado_por_loja[loja] = gravados_loja
        return atualizados, sem_sku, resultado_por_loja
    try:
        atualizados, sem_sku, resultado_por_loja = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    log(AGENT, f"Estoque fisico sincronizado: {atualizados} linhas, {sem_sku} sem sku mapeado")
    return {"ok": True, "atualizados": atualizados, "sem_sku_mapeado": sem_sku,
            "por_loja": resultado_por_loja}
