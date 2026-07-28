"""Produto da Loja — dados operacionais (preco, custo, fornecedor, promocao,
comissao, deposito, localizacao) independentes por loja. Nao guarda
quantidade de estoque (isso e' sempre estoque_lojas, lido via join).
Complementa catalogo_produtos (mestre, dados cadastrais globais) — ver
docs/superpowers/specs/2026-07-28-produtos-catalogo-mestre-loja-reconciliacao-design.md"""
from core import get_db, run_async, log
from core.seguranca import auditar_alteracao, auditar_exclusao

AGENT = "Produtos Loja"

CAMPOS_EDITAVEIS = (
    "produto_mestre_sku", "codigo_interno", "codigo_barras_override", "nome_override",
    "status", "preco_custo", "preco_venda", "promocao_ativa", "promocao_preco",
    "promocao_inicio", "promocao_fim", "comissao_pct", "fornecedor_id", "deposito",
    "localizacao_fisica", "estoque_minimo", "estoque_maximo", "observacoes_internas",
)

CAMPOS_SINCRONIZAVEIS_DO_MESTRE = ("nome_override", "codigo_barras_override")

_ok = False


def _ensure():
    global _ok
    if _ok:
        return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS produtos_loja (
                id SERIAL PRIMARY KEY,
                empresa_id INT,
                loja VARCHAR(50) NOT NULL,
                produto_mestre_sku VARCHAR(50),
                sku VARCHAR(50) NOT NULL,
                codigo_interno VARCHAR(50),
                codigo_barras_override VARCHAR(50),
                nome_override VARCHAR(300),
                status VARCHAR(1) DEFAULT 'A',
                preco_custo DECIMAL(12,2),
                preco_venda DECIMAL(12,2),
                promocao_ativa BOOLEAN DEFAULT FALSE,
                promocao_preco DECIMAL(12,2),
                promocao_inicio DATE,
                promocao_fim DATE,
                comissao_pct DECIMAL(5,2),
                fornecedor_id INT,
                deposito VARCHAR(100),
                localizacao_fisica VARCHAR(100),
                estoque_minimo DECIMAL(12,3),
                estoque_maximo DECIMAL(12,3),
                observacoes_internas TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(loja, sku)
            )
        """)
    try:
        run_async(_go())
        _ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela: {e}")


def criar(loja: str, sku: str, produto_mestre_sku: str = None, **campos) -> dict:
    _ensure()
    if not loja or not sku:
        return {"erro": "loja e sku sao obrigatorios"}
    extras = {k: v for k, v in campos.items() if k in CAMPOS_EDITAVEIS}

    async def _go():
        try:
            db = await get_db()
            existente = await db.fetchval(
                "SELECT id FROM produtos_loja WHERE loja = $1 AND sku = $2", loja, sku)
            if existente:
                return {"erro": f"ja existe produto_loja para sku={sku} na loja={loja}"}
            colunas = ["loja", "sku", "produto_mestre_sku"] + list(extras.keys())
            valores = [loja, sku, produto_mestre_sku] + list(extras.values())
            placeholders = ", ".join(f"${i+1}" for i in range(len(valores)))
            row = await db.fetchrow(
                f"INSERT INTO produtos_loja ({', '.join(colunas)}) VALUES ({placeholders}) "
                f"RETURNING id, loja, sku, produto_mestre_sku",
                *valores)
            return dict(row)
        except Exception as e:
            if "unique" in str(e).lower():
                return {"erro": f"ja existe produto_loja para sku={sku} na loja={loja}"}
            return {"erro": str(e)}

    resultado = run_async(_go())
    if resultado.get("erro"):
        return resultado
    auditar_alteracao("criar", "produtos_loja", "produtos_loja", resultado["id"], dados_depois=resultado)
    return {"ok": True, **resultado}


def obter(loja: str, sku: str) -> dict | None:
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "SELECT * FROM produtos_loja WHERE loja = $1 AND sku = $2", loja, sku)
        return dict(row) if row else None
    return run_async(_go())


def listar_por_loja(loja: str, busca: str = "", pagina: int = 1, por_pagina: int = 30) -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        where = ["pl.loja = $1"]
        params = [loja]
        if busca:
            where.append(f"(pl.sku ILIKE ${len(params)+1} OR c.descricao ILIKE ${len(params)+1})")
            params.append(f"%{busca}%")
        sql_where = " AND ".join(where)
        total = await db.fetchval(
            f"SELECT COUNT(*) FROM produtos_loja pl "
            f"LEFT JOIN catalogo_produtos c ON c.sku = pl.produto_mestre_sku "
            f"WHERE {sql_where}", *params)
        offset = (pagina - 1) * por_pagina
        params_pag = params + [por_pagina, offset]
        rows = await db.fetch(
            f"""SELECT pl.*, c.descricao AS nome_mestre, c.imagens,
                       COALESCE(el.quantidade, 0) AS estoque_atual
                FROM produtos_loja pl
                LEFT JOIN catalogo_produtos c ON c.sku = pl.produto_mestre_sku
                LEFT JOIN estoque_lojas el ON el.sku = pl.sku AND el.loja = pl.loja
                WHERE {sql_where}
                ORDER BY pl.updated_at DESC, pl.id DESC
                LIMIT ${len(params)+1} OFFSET ${len(params)+2}""",
            *params_pag)
        return {"produtos": [dict(r) for r in rows], "total": total, "pagina": pagina}
    return run_async(_go())


def atualizar(loja: str, sku: str, **campos) -> dict:
    _ensure()
    extras = {k: v for k, v in campos.items() if k in CAMPOS_EDITAVEIS}
    if not extras:
        return {"erro": "nenhum campo editavel informado"}

    async def _go():
        db = await get_db()
        antes = await db.fetchrow(
            "SELECT * FROM produtos_loja WHERE loja = $1 AND sku = $2", loja, sku)
        if not antes:
            return {"erro": "produto_loja nao encontrado"}, None
        sets = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(extras.keys()))
        row = await db.fetchrow(
            f"UPDATE produtos_loja SET {sets}, updated_at = NOW() "
            f"WHERE loja = $1 AND sku = $2 RETURNING *",
            loja, sku, *extras.values())
        return None, (dict(antes), dict(row))

    erro, par = run_async(_go())
    if erro:
        return erro
    dados_antes, dados_depois = par
    auditar_alteracao("editar", "produtos_loja", "produtos_loja", dados_depois["id"],
                       dados_antes=dados_antes, dados_depois=dados_depois)
    return {"ok": True, **dados_depois}


def sincronizar_do_mestre(loja: str, sku: str, campos: list[str],
                           usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Limpa os overrides escolhidos, fazendo a linha voltar a herdar o valor
    do mestre via join (nome_mestre/codigo de catalogo_produtos). So cobre
    os campos que sao override — o resto do cadastro (categoria, marca,
    imagens, atributos, tributacao) ja vem do join, nao precisa de acao."""
    invalidos = [c for c in campos if c not in CAMPOS_SINCRONIZAVEIS_DO_MESTRE]
    if invalidos:
        return {"erro": f"campos nao sincronizaveis: {invalidos}"}
    if not campos:
        return {"erro": "informe ao menos um campo"}
    valores_none = {c: None for c in campos}
    return atualizar(loja, sku, usuario_id=usuario_id, usuario_nome=usuario_nome, **valores_none)


def excluir(loja: str, sku: str) -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "DELETE FROM produtos_loja WHERE loja = $1 AND sku = $2 RETURNING id", loja, sku)
        return dict(row) if row else None
    resultado = run_async(_go())
    if not resultado:
        return {"erro": "produto_loja nao encontrado"}
    auditar_exclusao("produtos_loja", "produtos_loja", resultado["id"])
    return {"ok": True}


def replicar_para_lojas(loja_origem: str, sku: str, lojas_destino: list[str],
                         usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Cria produtos_loja em cada loja destino vinculados ao mesmo mestre da
    origem. NUNCA copia estoque, preco, fornecedor, promocao, localizacao,
    historico — cada linha nasce vazia nesses campos (cadastro manual
    depois). Dados cadastrais (nome/descricao/categoria/marca/imagens/
    atributos/tributacao) nao sao copiados porque vem do join com
    catalogo_produtos via produto_mestre_sku, nao de uma copia fisica."""
    origem = obter(loja_origem, sku)
    if not origem:
        return {"erro": f"produto_loja de origem nao encontrado: {loja_origem}/{sku}"}
    mestre_sku = origem.get("produto_mestre_sku")

    criados, ja_existentes, erros = [], [], []
    for loja_destino in lojas_destino:
        if obter(loja_destino, sku):
            ja_existentes.append(loja_destino)
            continue
        r = criar(loja_destino, sku, produto_mestre_sku=mestre_sku,
                   usuario_id=usuario_id, usuario_nome=usuario_nome)
        if r.get("ok"):
            criados.append(loja_destino)
        else:
            erros.append({"loja": loja_destino, "erro": r.get("erro", "erro desconhecido")})
    return {"ok": True, "criados": criados, "ja_existentes": ja_existentes, "erros": erros}
