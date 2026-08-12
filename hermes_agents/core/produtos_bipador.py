"""Import de catalogo + estoque fisico — app proprio de bipagem/atualizacao
de estoque (core/estoque_app_client.py) -> Athena (importacao unica,
disparo manual). NAO fala com a API i9Logic — a unica fonte de dados aqui
e' GET /api/external/produtos-existentes do app da empresa (autenticado via
X-API-Key), que ja devolve catalogo + contagem fisica da bipagem mescladas
por produto/filial (todas as sessoes da loja, nao so' hoje).

Catalogo: upsert direto em catalogo_produtos por sku=codproduto, sem fila
de revisao. So' campos com significado direto entram (sku, descricao, ean,
ncm, unidade) — categoria/marca/fornecedor ficam de fora porque no
catalogo de origem sao so' codigos numericos sem tabela de resolucao
disponivel. Grava o de-para (tabela de_para_i9logic, tipo='produto')
automaticamente no mesmo upsert — essa tabela e' compartilhada com a
reconciliacao de saldo fisico x contabil (core/i9logic.py, que essa sim
fala com a API i9Logic de verdade para outra finalidade). Reaproveitar o
de-para aqui deixa aquela reconciliacao pronta pra usar os produtos
importados por este modulo sem matching manual - os ids sao do mesmo
catalogo de origem em ambos os casos.

Estoque por loja: usa qtdContada diretamente do mesmo payload (contagem
fisica real da bipagem, nao o saldo teorico do ERP) — qtdContada None
significa "escaneado mas ainda sem quantidade digitada" e NUNCA vira
zero aqui, so' e' pulado (contabilizado em sem_qtd_contada)."""
from core import get_db, run_async, log
from core.estoque_app_client import fetch_produtos_existentes, EstoqueAppError
from core.i9logic import listar_mapeamentos

AGENT = "Produtos Bipador"

TAMANHO_LOTE = 200  # produtos por transacao/conexao no upsert em lote


async def _upsert_produto_async(conn, produto: dict) -> dict:
    """conn: uma conexao asyncpg ja adquirida (nao a pool) - quem adquire e
    controla o ciclo de vida da conexao e' o chamador (uma por lote, ver
    _upsert_lote)."""
    sku = str(produto.get("codproduto", "")).strip()
    if not sku:
        return {"erro": "codproduto vazio"}
    async with conn.transaction():
        row = await conn.fetchrow("""
            INSERT INTO catalogo_produtos (sku, descricao, ean, ncm, unidade_padrao, id_i9logic)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (sku) DO UPDATE SET
                descricao=COALESCE(NULLIF($2,''), catalogo_produtos.descricao),
                ean=COALESCE($3, catalogo_produtos.ean),
                ncm=COALESCE($4, catalogo_produtos.ncm),
                unidade_padrao=COALESCE(NULLIF($5,''), catalogo_produtos.unidade_padrao),
                id_i9logic=$6,
                updated_at=NOW()
            RETURNING *
        """, sku, produto.get("descricao") or "", produto.get("ean") or None,
            produto.get("ncm") or None, produto.get("unidademedida") or "UN",
            produto.get("produtoId"))
        await conn.execute("""
            INSERT INTO de_para_i9logic (tipo, id_i9logic, codigo_athena) VALUES ('produto',$1,$2)
            ON CONFLICT (tipo, id_i9logic) DO UPDATE SET codigo_athena=$2
        """, str(produto.get("produtoId")), sku)
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


def _deduplicar_por_sku(produtos: list) -> list:
    """O payload traz uma linha por [produto, filial] onde o item foi
    bipado — pro catalogo (dados cadastrais, iguais em toda filial) so'
    interessa uma linha por sku. Primeira ocorrencia vence."""
    vistos = {}
    for p in produtos:
        sku = str(p.get("codproduto", "")).strip()
        if sku and sku not in vistos:
            vistos[sku] = p
    return list(vistos.values())


def _upsert_lote(lote: list) -> tuple:
    """Upserta um lote inteiro numa unica conexao/transacao por produto -
    reduz de 1 conexao/produto pra 1 conexao/lote. Retorna (importados, erros_registro)."""
    elegiveis = [p for p in lote if str(p.get("ativo", "")) == "1"]
    async def _go():
        db = await get_db()
        importados_lote = 0
        erros_lote = []
        async with db.acquire() as conn:
            for produto in elegiveis:
                try:
                    r = await _upsert_produto_async(conn, produto)
                    if isinstance(r, dict) and r.get("erro"):
                        erros_lote.append({"codproduto": produto.get("codproduto"), "erro": r["erro"]})
                    else:
                        importados_lote += 1
                except Exception as e:
                    erros_lote.append({"codproduto": produto.get("codproduto"), "erro": str(e)})
        return importados_lote, erros_lote
    try:
        return run_async(_go())
    except Exception as e:
        return 0, [{"codproduto": None, "erro": f"falha no lote inteiro: {e}"}]


def sincronizar_catalogo_bipador() -> dict:
    """Importacao unica do catalogo inteiro — disparo manual (nao entra no
    scheduler). Idempotente: rodar de novo do zero so' reprocessa (upsert por
    sku), nao duplica."""
    log(AGENT, "Iniciando import de catalogo (app de bipagem/estoque)")
    try:
        produtos = fetch_produtos_existentes()
    except EstoqueAppError as e:
        log(AGENT, f"Import de catalogo falhou ao buscar produtos: {e}")
        return {"erro": str(e)}
    unicos = _deduplicar_por_sku(produtos)
    importados = 0
    erros_registro = []
    for inicio in range(0, len(unicos), TAMANHO_LOTE):
        lote = unicos[inicio:inicio + TAMANHO_LOTE]
        count, erros = _upsert_lote(lote)
        importados += count
        erros_registro.extend(erros)
    log(AGENT, f"Import de catalogo concluido: {importados} importados, {len(erros_registro)} erros")
    return {"ok": True, "importados": importados, "total_recebidos": len(produtos),
            "skus_unicos": len(unicos), "erros_registro": erros_registro}


# ── Estoque por loja fisica (a partir do mesmo endpoint) ──

async def _upsert_estoque_loja_async(conn, sku: str, loja: str, quantidade: float) -> None:
    await conn.execute("""
        INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (sku, loja) DO UPDATE SET quantidade=$3, data_atualizacao=NOW()
    """, sku, loja, quantidade)


def sincronizar_estoque_lojas_fisicas() -> dict:
    """Popula estoque_lojas (usado pela listagem /api/produtos) com a
    contagem fisica real da bipagem (qtdContada), para toda loja fisica ja
    mapeada em de_para_i9logic (tipo='filial') — sem esse de-para nao ha'
    como saber qual filialId do payload corresponde a qual loja Athena,
    entao essa filial fica de fora. qtdContada None (escaneado mas sem
    quantidade digitada ainda) e' pulado, nunca vira zero."""
    try:
        produtos = fetch_produtos_existentes()
    except EstoqueAppError as e:
        return {"erro": str(e)}
    filiais_mapeadas = listar_mapeamentos("filial")
    if not filiais_mapeadas:
        return {"erro": "nenhuma filial mapeada em de_para_i9logic ainda "
                         "(cadastre em /api/integrations/i9logic/depara antes)"}
    loja_por_filial_id = {int(m["id_i9logic"]): m["codigo_athena"] for m in filiais_mapeadas}

    async def _go():
        db = await get_db()
        atualizados, sem_qtd_contada, sem_filial_mapeada = 0, 0, 0
        resultado_por_loja = {}
        async with db.acquire() as conn:
            async with conn.transaction():
                for item in produtos:
                    loja = loja_por_filial_id.get(item.get("filialId"))
                    if loja is None:
                        sem_filial_mapeada += 1
                        continue
                    if item.get("qtdContada") is None:
                        sem_qtd_contada += 1
                        continue
                    sku = str(item.get("codproduto", "")).strip()
                    if not sku:
                        continue
                    await _upsert_estoque_loja_async(conn, sku, loja, float(item["qtdContada"]))
                    atualizados += 1
                    resultado_por_loja[loja] = resultado_por_loja.get(loja, 0) + 1
        return atualizados, sem_qtd_contada, sem_filial_mapeada, resultado_por_loja
    try:
        atualizados, sem_qtd_contada, sem_filial_mapeada, resultado_por_loja = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    log(AGENT, f"Estoque fisico sincronizado: {atualizados} linhas, "
               f"{sem_qtd_contada} sem qtd contada, {sem_filial_mapeada} sem filial mapeada")
    return {"ok": True, "atualizados": atualizados, "sem_qtd_contada": sem_qtd_contada,
            "sem_filial_mapeada": sem_filial_mapeada, "por_loja": resultado_por_loja}
