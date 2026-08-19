"""Store management CRUD — substitui lojas hardcoded do core/config."""
import traceback
import asyncpg
from core import get_db, run_async, log

AGENT = "Lojas"
_table_ok = False

# Cadastro empresarial da loja (identificacao/endereco/contatos) — ALTER TABLE
# defensivo, mesmo padrao ja usado pra "tipo"/"ativa". Cada tupla e' (coluna, DDL).
_CAMPOS_GERAIS_DDL = [
    ("status", "VARCHAR(20) DEFAULT 'ativa'"),
    ("nome_fantasia", "VARCHAR(150)"),
    ("razao_social", "VARCHAR(200)"),
    ("cnpj_cpf", "VARCHAR(18)"),
    ("inscricao_estadual", "VARCHAR(20)"),
    ("inscricao_municipal", "VARCHAR(20)"),
    ("cor_principal", "VARCHAR(7)"),
    ("cor_secundaria", "VARCHAR(7)"),
    ("cep", "VARCHAR(9)"),
    ("rua", "VARCHAR(200)"),
    ("numero", "VARCHAR(20)"),
    ("complemento", "VARCHAR(100)"),
    ("bairro", "VARCHAR(100)"),
    ("cidade", "VARCHAR(100)"),
    ("estado", "VARCHAR(2)"),
    ("pais", "VARCHAR(60) DEFAULT 'Brasil'"),
    ("latitude", "NUMERIC(10,7)"),
    ("longitude", "NUMERIC(10,7)"),
    ("telefone", "VARCHAR(20)"),
    ("whatsapp", "VARCHAR(20)"),
    ("email", "VARCHAR(150)"),
    ("site", "VARCHAR(200)"),
    ("instagram", "VARCHAR(100)"),
    ("facebook", "VARCHAR(100)"),
    ("tiktok", "VARCHAR(100)"),
    ("youtube", "VARCHAR(100)"),
]
STATUS_VALIDOS = ("ativa", "inativa", "em_implantacao", "bloqueada")
TIPOS_VALIDOS = ("fisica", "virtual", "hibrida", "marketplace")
CAMPOS_GERAIS = {nome for nome, _ in _CAMPOS_GERAIS_DDL}

def _log_erro(onde: str, e: Exception):
    """Log local (console) + persistido no banco (system_logs), visivel em
    /seguranca/logs sem precisar acessar o log do container no Coolify."""
    tb = traceback.format_exc()
    log(AGENT, f"Erro {onde}: {e}\n{tb}")
    try:
        from core.seguranca import syslog
        syslog("ERROR", "lojas", f"{onde}: {e}", stacktrace=tb)
    except Exception:
        pass

# Cache simples nome->id, usado pelo dual-write da Fase 3 (migracao aditiva
# de estoque_lojas/etc de loja-por-texto pra loja_id). Invalidado sempre que
# uma loja e' criada/renomeada — ver invalidar_cache_loja_id().
_cache_loja_id: dict = {}

def invalidar_cache_loja_id():
    _cache_loja_id.clear()

def resolver_loja_id(nome: str):
    """Resolve o nome de uma loja pro id real — usado pelos write-paths que
    hoje so' tem o nome em maos (core/estoque.py e afins), pra popular a
    nova coluna loja_id em paralelo a coluna loja (texto) ja existente."""
    if not nome:
        return None
    if nome in _cache_loja_id:
        return _cache_loja_id[nome]
    async def _go():
        db = await get_db()
        return await db.fetchval("SELECT id FROM lojas WHERE nome = $1", nome)
    try:
        loja_id = run_async(_go())
    except Exception as e:
        _log_erro("resolver_loja_id", e)
        return None
    _cache_loja_id[nome] = loja_id
    return loja_id

# Cache simples chave->nome_efetivo (chave = nome OU id como string), usado
# pelo vinculo de estoque fisica x virtual (Fase Vinculo). Uma loja virtual
# com loja_vinculada_id ativo compartilha o saldo da fisica vinculada —
# qualquer operacao de estoque na virtual deve gravar/ler na fisica.
# Invalidado sempre que um vinculo e' criado/desfeito — ver invalidar_cache_loja_efetiva().
_cache_loja_efetiva: dict = {}

def invalidar_cache_loja_efetiva():
    _cache_loja_efetiva.clear()

def _sync_run(coro):
    """Helper de teste — roda uma coroutine isolada sem passar por run_async
    (que abriria um pool asyncpg de verdade). Producao usa loja_efetiva()."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

async def _loja_efetiva_async(loja) -> str:
    """Aceita nome OU id (string de digitos) de loja; devolve sempre o NOME
    efetivo — se for virtual com vinculo ativo, o nome da fisica vinculada;
    senao, o proprio nome (resolvendo id->nome primeiro, se for o caso)."""
    if not loja:
        return loja
    chave = str(loja)
    if chave in _cache_loja_efetiva:
        return _cache_loja_efetiva[chave]
    db = await get_db()
    if chave.isdigit():
        row = await db.fetchrow(
            "SELECT l1.nome, l1.tipo, l2.nome AS nome_fisica FROM lojas l1 "
            "LEFT JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.id = $1", int(chave))
        # so' usa nome_fisica se a PROPRIA loja for tipo='virtual' — defesa
        # contra loja_vinculada_id setado numa loja fisica/hibrida/marketplace
        # (nao deveria acontecer se quem grava validar, mas o resolver nao
        # pode confiar so' na escrita; mesmo criterio do branch por nome abaixo).
        if not row:
            efetiva = loja
        elif row.get("tipo") == "virtual" and row.get("nome_fisica"):
            efetiva = row["nome_fisica"]
        else:
            efetiva = row["nome"]
    else:
        row = await db.fetchrow(
            "SELECT l2.nome FROM lojas l1 JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.nome = $1 AND l1.tipo = 'virtual' AND l1.loja_vinculada_id IS NOT NULL", chave)
        efetiva = row["nome"] if row else chave
    _cache_loja_efetiva[chave] = efetiva
    return efetiva

def loja_efetiva(loja: str) -> str:
    """Versao sincrona (wrapper sobre run_async) — use em qualquer caller
    que ja tenha so' o nome/id em maos fora de um `async def`."""
    if not loja:
        return loja
    try:
        return run_async(_loja_efetiva_async(loja))
    except Exception as e:
        _log_erro("loja_efetiva", e)
        return loja

def loja_efetiva_sync(cur, loja: str) -> str:
    """Para callers com conexao psycopg2 direta (routes/estoque.py,
    athena_bridge.py) — usa cursor sincrono, mesmo cache compartilhado."""
    if not loja:
        return loja
    chave = str(loja)
    if chave in _cache_loja_efetiva:
        return _cache_loja_efetiva[chave]
    if chave.isdigit():
        cur.execute(
            "SELECT l1.nome, l1.tipo, l2.nome AS nome_fisica FROM lojas l1 "
            "LEFT JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.id = %s", (int(chave),))
        row = cur.fetchone()
        # mesma defesa do branch async acima: so' usa nome_fisica (row[2]) se
        # a propria loja (row[1]) for tipo='virtual'.
        if not row:
            efetiva = loja
        elif row[1] == "virtual" and row[2]:
            efetiva = row[2]
        else:
            efetiva = row[0]
    else:
        cur.execute(
            "SELECT l2.nome FROM lojas l1 JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
            "WHERE l1.nome = %s AND l1.tipo = 'virtual' AND l1.loja_vinculada_id IS NOT NULL", (chave,))
        row = cur.fetchone()
        efetiva = row[0] if row else chave
    _cache_loja_efetiva[chave] = efetiva
    return efetiva

def vincular_estoque(loja_virtual_id: int, loja_fisica_id: int) -> dict:
    """Ativa o vinculo: saldo da fisica vira o compartilhado. Linhas que a
    virtual tinha em estoque_saldos/estoque_lojas sob o proprio nome ficam
    orfas (nao apagadas — historico preservado), porque leitura/escrita
    passam a resolver pro nome da fisica a partir de agora."""
    async def _go():
        db = await get_db()
        virtual = await db.fetchrow("SELECT id, tipo, nome FROM lojas WHERE id = $1", loja_virtual_id)
        if not virtual:
            return {"erro": "Loja virtual nao encontrada"}
        if virtual["tipo"] != "virtual":
            return {"erro": f"Loja {virtual['nome']} nao e' do tipo virtual"}
        fisica = await db.fetchrow("SELECT id, tipo, nome FROM lojas WHERE id = $1", loja_fisica_id)
        if not fisica:
            return {"erro": "Loja fisica nao encontrada"}
        if fisica["tipo"] != "fisica":
            return {"erro": f"Loja {fisica['nome']} nao e' do tipo fisica"}
        await db.execute("UPDATE lojas SET loja_vinculada_id = $1 WHERE id = $2", loja_fisica_id, loja_virtual_id)
        return {"ok": True, "loja_virtual": virtual["nome"], "loja_fisica": fisica["nome"]}
    try:
        resultado = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    if not resultado.get("erro"):
        invalidar_cache_loja_efetiva()
    return resultado


def desvincular_estoque(loja_virtual_id: int) -> dict:
    """Desativa o vinculo: a virtual recebe uma copia do saldo compartilhado
    no momento da desvinculacao (entrada por sku com saldo > 0 na fisica),
    como novo ponto de partida independente. A fisica fica intocada.

    Tudo roda numa unica conexao/transacao (fix pos-review: a versao
    original chamava a entrada() SINCRONA por sku dentro de um loop Python —
    cada chamada passa por run_async(), que abre um asyncio.run() novo, e
    get_db() cria [e abandona] um pool asyncpg sempre que o loop muda (ver
    aviso em core/__init__.py::get_db() e em
    core/estoque_saldos.py::mover_saldo()). Pra uma fisica com centenas de
    skus isso vazava centenas de pools nunca fechados numa unica chamada.
    Tambem nao era atomico: uma falha no meio deixava o vinculo ja limpo
    com so' parte dos saldos copiados, e uma nova tentativa esbarrava em
    "sem vinculo ativo" — sem jeito de retomar. Agora, como em
    core/estoque.py::transferir()/ratear(), tudo (leitura do saldo da
    fisica, limpeza do vinculo e a copia por sku via entrada_async) roda
    numa so' conexao/transacao: se qualquer sku falhar, a transacao inteira
    e' revertida — vinculo continua ativo, nada foi copiado, e o operador
    pode tentar de novo."""
    from core.estoque import entrada_async as estoque_entrada_async
    from core.estoque_saldos import SaldoError
    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                virtual = await conn.fetchrow(
                    "SELECT id, tipo, nome, loja_vinculada_id FROM lojas WHERE id = $1", loja_virtual_id)
                if not virtual:
                    return {"erro": "Loja virtual nao encontrada"}
                if not virtual["loja_vinculada_id"]:
                    return {"erro": f"Loja {virtual['nome']} nao tem vinculo ativo"}
                fisica = await conn.fetchrow("SELECT nome FROM lojas WHERE id = $1", virtual["loja_vinculada_id"])
                saldos = await conn.fetch(
                    "SELECT sku, quantidade FROM estoque_saldos WHERE loja = $1 AND tipo = 'disponivel' AND quantidade > 0",
                    fisica["nome"])
                await conn.execute("UPDATE lojas SET loja_vinculada_id = NULL WHERE id = $1", loja_virtual_id)
                copiados = 0
                for s in saldos:
                    r = await estoque_entrada_async(
                        conn, s["sku"], virtual["nome"], float(s["quantidade"]), "ajuste_inventario")
                    if r.get("erro"):
                        raise SaldoError(f"{s['sku']}: {r['erro']}")
                    copiados += 1
                return {"ok": True, "loja_virtual": virtual["nome"], "loja_fisica": fisica["nome"],
                        "skus_copiados": copiados}
    try:
        resultado = run_async(_go())
    except SaldoError as e:
        return {"erro": str(e)}
    except Exception as e:
        return {"erro": str(e)}
    if not resultado.get("erro"):
        invalidar_cache_loja_efetiva()
    return resultado


def _ensure_table():
    global _table_ok
    if _table_ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lojas (
                id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL,
                ativa BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # CREATE TABLE IF NOT EXISTS nao altera tabela ja existente — em prod a
        # tabela "lojas" foi criada antes da coluna "ativa" existir na definicao
        # acima, entao ela precisa do mesmo ALTER defensivo que "tipo" ja tem.
        try: await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS ativa BOOLEAN DEFAULT TRUE")
        except Exception as e: _log_erro("ALTER lojas.ativa", e)
        # fisica (PDV/estoque/caixa fisico) ou virtual (marketplace/Shopee) —
        # usado pelo frontend para mostrar so' os utilitarios relevantes no
        # menu quando essa loja especifica esta selecionada.
        try: await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS tipo VARCHAR(10) DEFAULT 'fisica'")
        except Exception as e: _log_erro("ALTER lojas.tipo", e)
        # tipo agora tambem aceita "hibrida"/"marketplace" (11 chars) —
        # VARCHAR(10) original nao cabe. ALTER COLUMN TYPE so' alarga,
        # nunca trunca dado existente.
        try: await db.execute("ALTER TABLE lojas ALTER COLUMN tipo TYPE VARCHAR(20)")
        except Exception as e: _log_erro("ALTER lojas.tipo (widen)", e)
        # vinculo de estoque fisica x virtual — quando preenchido numa loja
        # "virtual", aponta pra loja "fisica" que efetivamente detem o saldo
        # compartilhado (ver _loja_efetiva_async/loja_efetiva/loja_efetiva_sync acima).
        try: await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS loja_vinculada_id INT REFERENCES lojas(id)")
        except Exception as e: _log_erro("ALTER lojas.loja_vinculada_id", e)
        for col, ddl in _CAMPOS_GERAIS_DDL:
            try: await db.execute(f"ALTER TABLE lojas ADD COLUMN IF NOT EXISTS {col} {ddl}")
            except Exception as e: _log_erro(f"ALTER lojas.{col}", e)
        count = await db.fetchval("SELECT COUNT(*) FROM lojas")
        if count == 0:
            try:
                from bling_erp import listar_depositos, get_access_token
                token = get_access_token()
                if token:
                    pagina = 1
                    while True:
                        r = listar_depositos(pagina=pagina, limite=100)
                        dados = r.get("data", [])
                        if not dados or r.get("error"):
                            break
                        for dep in dados:
                            nome = dep.get("descricao", f"Deposito {dep.get('id')}")
                            ativa = dep.get("situacao", "A") == "A"
                            await db.execute(
                                "INSERT INTO lojas (nome, ativa, bling_id, bling_descricao) VALUES ($1, $2, $3, $4)",
                                nome, ativa, dep.get("id"), nome)
                        if len(dados) < 100:
                            break
                        pagina += 1
                else:
                    await db.execute("INSERT INTO lojas (nome) VALUES ($1)", "Loja Padrão")
            except Exception:
                await db.execute("INSERT INTO lojas (nome) VALUES ($1)", "Loja Padrão")
    try:
        run_async(_go())
        _table_ok = True
    except Exception as e:
        _log_erro("_ensure_table", e)

def listar() -> list:
    _ensure_table()
    async def _go():
        db = await get_db()
        # ponytail: shopee_markup_pct/grupos_publicacao precisam vir aqui —
        # e' o unico SELECT que alimenta o hub /lojas, cujo modal "Editar
        # rapido" pre-carrega esses 2 campos. Sem eles aqui, o modal sempre
        # mostrava markup=100 (default do form) e o Salvar sobrescrevia
        # silenciosamente qualquer markup real configurado.
        rows = await db.fetch(
            "SELECT id, nome, ativa, status, created_at, bling_id, tipo, "
            "shopee_markup_pct, grupos_publicacao, (shopee_shop_id IS NOT NULL) AS shopee_conectado "
            "FROM lojas ORDER BY id")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: _log_erro("listar", e); return []

def criar(nome: str, tipo: str = "fisica"):
    _ensure_table()
    if tipo not in TIPOS_VALIDOS:
        tipo = "fisica"
    async def _go():
        db = await get_db()
        row = await db.fetchrow("INSERT INTO lojas (nome, tipo) VALUES ($1, $2) RETURNING id, nome, ativa, tipo", nome, tipo)
        return dict(row) if row else None
    try:
        return run_async(_go())
    except Exception as e:
        _log_erro("criar", e); return {"error": str(e)}
    finally:
        invalidar_cache_loja_id()

def atualizar(id_loja: int, nome: str = None, shopee_markup_pct: float = None, grupos_publicacao: str = None, tipo: str = None) -> bool:
    """nome e' opcional — antes era sempre obrigatorio nesta funcao, entao
    um PUT parcial (ex.: so' trocar o status ativa/inativa via
    atualizar_geral) precisava reenviar o nome atual so' pra nao quebrar
    aqui, e a rota /manage/<id> exigia nome em TODO PUT por causa disso
    (o botao Ativar/Desativar do hub so' manda {status}, entao sempre
    devolvia 400 'Nome e obrigatorio' — nunca funcionou)."""
    _ensure_table()
    async def _go():
        db = await get_db()
        tocou = False
        if nome is not None:
            r = await db.execute("UPDATE lojas SET nome = $1 WHERE id = $2", nome, id_loja)
            if r == "UPDATE 0":
                return False
            tocou = True
        if shopee_markup_pct is not None:
            await db.execute("UPDATE lojas SET shopee_markup_pct = $1 WHERE id = $2", float(shopee_markup_pct), id_loja)
            tocou = True
        if grupos_publicacao is not None:
            await db.execute("UPDATE lojas SET grupos_publicacao = $1 WHERE id = $2", grupos_publicacao.strip(), id_loja)
            tocou = True
        if tipo in TIPOS_VALIDOS:
            await db.execute("UPDATE lojas SET tipo = $1 WHERE id = $2", tipo, id_loja)
            tocou = True
        if not tocou:
            existe = await db.fetchval("SELECT 1 FROM lojas WHERE id = $1", id_loja)
            return bool(existe)
        return True
    try:
        return run_async(_go())
    except Exception as e:
        _log_erro("atualizar", e); return False
    finally:
        invalidar_cache_loja_id()

def _update_campos(id_loja: int, campos: dict, whitelist: set) -> bool:
    """Helper generico p/ atualizar um subconjunto de colunas de "lojas" a
    partir de um dict ja filtrado pela camada de rota. Reaproveitado por
    core/lojas_operacional.py, lojas_fiscal_financeiro.py e lojas_virtual.py
    pra nao duplicar a construcao de UPDATE dinamico em cada arquivo.
    O whitelist restringe os NOMES de coluna aceitos antes de qualquer
    interpolacao — os VALORES sempre vao parametrizados ($n)."""
    _ensure_table()
    campos = {k: v for k, v in campos.items() if k in whitelist and v is not None}
    if not campos:
        return True
    async def _go():
        db = await get_db()
        colunas = list(campos.keys())
        sets = ", ".join(f"{col} = ${i + 1}" for i, col in enumerate(colunas))
        valores = [campos[c] for c in colunas] + [id_loja]
        r = await db.execute(f"UPDATE lojas SET {sets} WHERE id = ${len(colunas) + 1}", *valores)
        return r != "UPDATE 0"
    try: return run_async(_go())
    except Exception as e: _log_erro("_update_campos", e); return False

def obter(id_loja: int) -> dict:
    """Retorna a loja completa (todas as colunas) — usado nas telas de
    detalhe/edicao, ao contrario de listar() que traz so' o resumo."""
    _ensure_table()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM lojas WHERE id = $1", id_loja)
        return dict(row) if row else None
    try: return run_async(_go())
    except Exception as e: _log_erro("obter", e); return None

def atualizar_geral(id_loja: int, campos: dict) -> bool:
    """Atualiza identificacao/endereco/contatos da loja. 'status' sincroniza
    a coluna legada 'ativa' (usada em dezenas de "WHERE ativa = TRUE" em
    estoque/pdv/vendas/relatorios) sem exigir migrar essas queries agora."""
    campos = dict(campos)
    if "status" in campos:
        if campos["status"] not in STATUS_VALIDOS:
            campos["status"] = "ativa"
        campos["ativa"] = campos["status"] == "ativa"
    return _update_campos(id_loja, campos, CAMPOS_GERAIS | {"ativa"})

def deletar(id_loja: int) -> dict:
    """Retorna {"ok": True} se excluiu, ou {"erro": "..."} — distingue loja
    inexistente de exclusao bloqueada por FK (estoque/vendas/caixas/etc
    vinculados), que antes virava silenciosamente "Loja nao encontrada"
    (achado real durante limpeza de dados de teste em producao)."""
    _ensure_table()
    async def _go():
        db = await get_db()
        r = await db.execute("DELETE FROM lojas WHERE id = $1", id_loja)
        if r == "DELETE 0":
            return {"erro": "Loja nao encontrada"}
        return {"ok": True}
    try:
        return run_async(_go())
    except asyncpg.ForeignKeyViolationError:
        return {"erro": "Nao e possivel excluir: existem dados vinculados a esta loja "
                         "(estoque, vendas, caixas, etc). Desative-a em vez de excluir."}
    except Exception as e:
        _log_erro("deletar", e)
        return {"erro": str(e)}

# ── Exclusao forcada (irreversivel) ──
# Cascata completa de tabelas com dado vinculado a uma loja, na ordem
# correta de dependencia (filhas antes de maes) — reaproveitada por
# impacto_exclusao() (so' leitura) e excluir_forcado() (apaga de verdade).
# compras_pedidos/fin_contas_pagar ficam FORA de proposito: seu loja_id e'
# so' um default de "loja principal" (core/compras.py), nao escopo real por
# loja — apagar por loja_id nessas tabelas destruiria dado da empresa
# inteira sempre que a loja-alvo for a principal.
_CASCATA_EXCLUSAO_FORCADA = [
    ("pdv_devolucoes", "venda_id IN (SELECT id FROM pdv_vendas WHERE caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1))"),
    ("pdv_pagamentos", "venda_id IN (SELECT id FROM pdv_vendas WHERE caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1))"),
    ("pdv_itens", "venda_id IN (SELECT id FROM pdv_vendas WHERE caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1))"),
    ("pdv_turnos", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_caixa_conferencia", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_caixa_contagem", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_suprimentos", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_sangrias", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_vendas", "caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)"),
    ("pdv_caixas", "loja_id = $1"),
    ("vendas_pagamentos", "pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)"),
    ("vendas_historico_status", "pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)"),
    ("vendas_itens", "pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)"),
    ("vendas_pedidos", "loja_id = $1"),
    ("fin_cofre_movimentos", "cofre_id IN (SELECT id FROM fin_cofre WHERE loja_id = $1)"),
    ("fin_cofre", "loja_id = $1"),
    ("estoque_lojas", "loja_id = $1"),
    ("estoque_movimentacoes", "loja_id = $1"),
    ("estoque_transferencias", "(loja_origem_id = $1 OR loja_destino_id = $1)"),
    ("estoque_contagens", "loja_id = $1"),
    ("producao_bom", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_apontamentos", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_consumo", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_perdas", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_custos", "op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)"),
    ("producao_ops", "loja_id = $1"),
    ("chat_conversas", "loja_id = $1"),
    ("shopee_estoque_snapshot", "loja_id = $1"),
    ("fiscal_nfe_itens", "nota_id IN (SELECT id FROM fiscal_notas_fiscais WHERE loja_id = $1)"),
    ("fiscal_impostos_nota", "nota_id IN (SELECT id FROM fiscal_notas_fiscais WHERE loja_id = $1)"),
    ("fiscal_notas_fiscais", "loja_id = $1"),
    ("fin_contas_receber", "loja_id = $1"),
    ("autom_regras_preco", "loja_id = $1"),
    # 4 tabelas abaixo adicionadas apos achado do review final da branch:
    # loja_integracoes/loja_responsaveis/usuario_lojas ja tem ON DELETE CASCADE
    # (ficavam invisiveis na previa/auditoria mesmo ja sendo apagadas de fato
    # no DELETE FROM lojas final — inclusao aqui e' so' honestidade do
    # dry-run/auditoria, nao muda o que e' apagado). "vendas" e' tabela legada
    # sem FK (loja_id INTEGER simples) — inclusao no escopo real, decisao
    # explicita do usuario apos pergunta do controller.
    ("loja_integracoes", "loja_id = $1"),
    ("loja_responsaveis", "loja_id = $1"),
    ("usuario_lojas", "loja_id = $1"),
    ("vendas", "loja_id = $1"),
]

# crm_negociacoes.pedido_id e' nullable (FK -> vendas_pedidos.id) — a
# negociacao nunca e' apagada, so' perde a referencia ao pedido.
_WHERE_CRM_NEGOCIACOES_VINCULADAS = "pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)"

async def _garantir_coluna_crm_negociacoes_pedido_id(conn) -> None:
    """core/crm.py cria a coluna no boot, mas modulos sao importados sob
    demanda (nenhum import top-level de core.crm/core.vendas na app) — se
    exclusao-forcada for a primeira rota do processo a tocar crm_negociacoes,
    a coluna pode ainda nao existir. Defensivo aqui = nao depende de ordem de
    import (achado real: "column pedido_id does not exist" ao tentar excluir
    uma loja Shopee, mesma causa de ao_converter_negociacao() precisar do
    mesmo ALTER antes de usar a coluna)."""
    try:
        await conn.execute("ALTER TABLE crm_negociacoes ADD COLUMN IF NOT EXISTS pedido_id INT REFERENCES vendas_pedidos(id)")
    except Exception as e:
        _log_erro("_garantir_coluna_crm_negociacoes_pedido_id", e)


def impacto_exclusao(id_loja: int) -> dict:
    """Dry-run de excluir_forcado(): conta quantas linhas seriam apagadas em
    cada tabela do escopo, sem apagar nada. So' aceita loja ja inativa —
    mesma trava que excluir_forcado() usa."""
    _ensure_table()
    async def _go():
        db = await get_db()
        loja_row = await db.fetchrow("SELECT * FROM lojas WHERE id = $1", id_loja)
        if not loja_row:
            return {"erro": "Loja nao encontrada"}
        loja = dict(loja_row)
        if loja.get("status") != "inativa":
            return {"erro": "Loja precisa estar inativa antes de avaliar exclusao forcada"}
        impacto = {}
        total = 0
        for tabela, where_clause in _CASCATA_EXCLUSAO_FORCADA:
            n = await db.fetchval(f"SELECT COUNT(*) FROM {tabela} WHERE {where_clause}", id_loja)
            impacto[tabela] = n
            total += n
        await _garantir_coluna_crm_negociacoes_pedido_id(db)
        negociacoes = await db.fetchval(
            f"SELECT COUNT(*) FROM crm_negociacoes WHERE {_WHERE_CRM_NEGOCIACOES_VINCULADAS}", id_loja)
        # loja_row completa (acima) so' e' usada internamente pra checar o
        # status — o dict devolvido pro cliente (jsonify'd direto pela rota
        # lojas_impacto_exclusao) precisa ser minimo: a linha completa de
        # "lojas" tem pix_chave/shopee_access_token/shopee_refresh_token, que
        # nunca podem chegar no browser (achado do review final da branch).
        loja_minima = {"id": loja["id"], "nome": loja["nome"], "status": loja["status"]}
        return {"loja": loja_minima, "impacto": impacto,
                "negociacoes_crm_desvinculadas": negociacoes, "total_linhas": total}
    try:
        return run_async(_go())
    except Exception as e:
        _log_erro("impacto_exclusao", e)
        return {"erro": str(e)}


def excluir_forcado(id_loja: int, confirmar_nome: str) -> dict:
    """Apaga permanentemente uma loja inativa e todo o dado vinculado a ela
    (ver _CASCATA_EXCLUSAO_FORCADA), numa unica transacao. Existe pra quando
    o operador confirma que o historico vinculado e' dado errado/lixo (loja
    de teste), nao venda real que precise ser preservada — a exclusao comum
    (deletar()) continua bloqueando por FK de proposito pra todo o resto."""
    _ensure_table()
    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                loja_row = await conn.fetchrow("SELECT * FROM lojas WHERE id = $1", id_loja)
                if not loja_row:
                    return {"erro": "Loja nao encontrada"}
                loja = dict(loja_row)
                if loja.get("status") != "inativa":
                    return {"erro": "Loja precisa estar inativa antes de forcar exclusao"}
                if confirmar_nome != loja["nome"]:
                    return {"erro": "Nome de confirmacao nao confere"}
                await _garantir_coluna_crm_negociacoes_pedido_id(conn)
                r = await conn.execute(
                    f"UPDATE crm_negociacoes SET pedido_id = NULL WHERE {_WHERE_CRM_NEGOCIACOES_VINCULADAS}", id_loja)
                negociacoes_desvinculadas = int(r.split()[-1])
                apagado = {}
                for tabela, where_clause in _CASCATA_EXCLUSAO_FORCADA:
                    r = await conn.execute(f"DELETE FROM {tabela} WHERE {where_clause}", id_loja)
                    apagado[tabela] = int(r.split()[-1])
                await conn.execute("UPDATE lojas SET loja_vinculada_id = NULL WHERE loja_vinculada_id = $1", id_loja)
                await conn.execute("UPDATE lojas SET loja_matriz_id = NULL WHERE loja_matriz_id = $1", id_loja)
                await conn.execute("DELETE FROM lojas WHERE id = $1", id_loja)
                return {"ok": True, "apagado": apagado,
                        "negociacoes_crm_desvinculadas": negociacoes_desvinculadas}
    try:
        resultado = run_async(_go())
    except Exception as e:
        _log_erro("excluir_forcado", e)
        return {"erro": str(e)}
    if not resultado.get("erro"):
        invalidar_cache_loja_efetiva()
        invalidar_cache_loja_id()
    return resultado

# ── Sync Bling ──

def _ensure_bling_id():
    async def _go():
        db = await get_db()
        try:
            exists = await db.fetchval("SELECT column_name FROM information_schema.columns WHERE table_name='lojas' AND column_name='bling_id'")
            if not exists:
                await db.execute("ALTER TABLE lojas ADD COLUMN bling_id BIGINT")
                await db.execute("ALTER TABLE lojas ADD COLUMN bling_descricao VARCHAR(200)")
        except Exception as e: _log_erro("_ensure_bling_id", e)
    try: run_async(_go())
    except Exception as e: _log_erro("_ensure_bling_id (run_async)", e)

_ensure_bling_id()

# ── Shopee: multiloja (cada loja Shopee tem seu proprio shop_id + tokens) ──

def _ensure_shopee_cols():
    async def _go():
        db = await get_db()
        try:
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_shop_id VARCHAR(50)")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_shop_name VARCHAR(200)")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_access_token TEXT")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_refresh_token TEXT")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_token_expira_em TIMESTAMP")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS shopee_markup_pct NUMERIC(5,2) DEFAULT 100")
            await db.execute("ALTER TABLE lojas ADD COLUMN IF NOT EXISTS grupos_publicacao VARCHAR(300)")
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lojas_shopee_shop_id ON lojas (shopee_shop_id) WHERE shopee_shop_id IS NOT NULL")
        except Exception as e:
            _log_erro("_ensure_shopee_cols", e)
    try: run_async(_go())
    except Exception as e: _log_erro("_ensure_shopee_cols (run_async)", e)

_ensure_shopee_cols()

def listar_lojas_shopee() -> list:
    """Lojas que ja tem uma conta Shopee vinculada (shop_id + tokens).
    tem_token indica se o access_token foi realmente salvo (confirmacao visual na tela)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT id, nome, shopee_shop_id, shopee_shop_name, shopee_token_expira_em,
                   (shopee_access_token IS NOT NULL AND shopee_access_token != '') AS tem_token
            FROM lojas WHERE shopee_shop_id IS NOT NULL ORDER BY id
        """)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: _log_erro("listar_lojas_shopee", e); return []

def listar_ids_por_tipo(tipo: str) -> list:
    """IDs de lojas ativas de um `tipo` (ex: 'virtual', 'fisica' — ver
    ALTER TABLE lojas ADD COLUMN tipo acima). Usado pelo dashboard pra
    agregar todas as lojas virtuais (Shopee) de uma vez, ignorando o
    seletor de loja unica (ver routes/relatorios.py::_resolver_loja_ids)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id FROM lojas WHERE tipo = $1 AND ativa = TRUE", tipo)
        return [r["id"] for r in rows]
    try: return run_async(_go())
    except Exception as e: _log_erro("listar_ids_por_tipo", e); return []


def obter_credenciais_shopee(loja_id: int) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""SELECT shopee_shop_id, shopee_access_token, shopee_refresh_token
                                   FROM lojas WHERE id = $1""", loja_id)
        return dict(row) if row else {}
    try: return run_async(_go())
    except Exception as e: _log_erro("obter_credenciais_shopee", e); return {}

def vincular_shopee(loja_id: int, shop_id: str, access_token: str, refresh_token: str = "",
                     shop_name: str = "", expira_em=None) -> dict:
    """Salva as credenciais de uma conta Shopee numa loja existente."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            UPDATE lojas SET shopee_shop_id = $1, shopee_shop_name = COALESCE(NULLIF($2,''), shopee_shop_name),
                shopee_access_token = $3, shopee_refresh_token = $4, shopee_token_expira_em = $5
            WHERE id = $6 RETURNING id, nome, shopee_shop_id
        """, shop_id, shop_name, access_token, refresh_token, expira_em, loja_id)
        return dict(row) if row else {"error": "loja nao encontrada"}
    try: return run_async(_go())
    except Exception as e: _log_erro("vincular_shopee", e); return {"error": str(e)}

def criar_loja_shopee(shop_id: str, access_token: str, refresh_token: str = "", shop_name: str = "", expira_em=None) -> dict:
    """Cria uma nova loja ja vinculada a uma conta Shopee (usado quando nenhuma loja_id foi indicada no auth)."""
    async def _go():
        db = await get_db()
        nome = shop_name or f"Shopee {shop_id}"
        row = await db.fetchrow("""
            INSERT INTO lojas (nome, shopee_shop_id, shopee_shop_name, shopee_access_token, shopee_refresh_token, shopee_token_expira_em)
            VALUES ($1, $2, $3, $4, $5, $6) RETURNING id, nome, shopee_shop_id
        """, nome, shop_id, shop_name, access_token, refresh_token, expira_em)
        return dict(row) if row else {"error": "falha ao criar loja"}
    try: return run_async(_go())
    except Exception as e: _log_erro("criar_loja_shopee", e); return {"error": str(e)}

def desconectar_shopee(loja_id: int) -> dict:
    """Remove a vinculacao de uma conta Shopee de uma loja (limpa shop_id e tokens).
    A loja em si nao e' apagada, apenas fica disponivel para conectar outra conta Shopee."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            UPDATE lojas SET shopee_shop_id = NULL, shopee_shop_name = NULL,
                shopee_access_token = NULL, shopee_refresh_token = NULL, shopee_token_expira_em = NULL
            WHERE id = $1 RETURNING id, nome
        """, loja_id)
        return dict(row) if row else {"error": "loja nao encontrada"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def sincronizar_bling() -> dict:
    """Puxa depositos/lojas do Bling e cria cada um como loja no Athena."""
    from bling_erp import listar_depositos, get_access_token, get_auth_url
    token = get_access_token()
    if not token:
        return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    _ensure_table()
    async def _go():
        db = await get_db()
        resultados = []
        pagina = 1
        while True:
            r = listar_depositos(pagina=pagina, limite=100)
            dados = r.get("data", [])
            if not dados or r.get("error"):
                break
            for dep in dados:
                bling_id = dep.get("id")
                nome = dep.get("descricao", f"Deposito {bling_id}")
                situacao = dep.get("situacao", "A")
                ativa = situacao == "A"
                existing = await db.fetchrow("SELECT id FROM lojas WHERE bling_id = $1", bling_id)
                if existing:
                    await db.execute("UPDATE lojas SET nome = $1, ativa = $2, bling_descricao = $3 WHERE bling_id = $4",
                        nome, ativa, nome, bling_id)
                    resultados.append({"acao": "atualizado", "id": existing["id"], "nome": nome})
                else:
                    row = await db.fetchrow(
                        "INSERT INTO lojas (nome, ativa, bling_id, bling_descricao) VALUES ($1, $2, $3, $4) RETURNING id",
                        nome, ativa, bling_id, nome)
                    resultados.append({"acao": "criado", "id": row["id"] if row else 0, "nome": nome})
            if len(dados) < 100:
                break
            pagina += 1
        return {"sync": len(resultados), "lojas": resultados}
    try: return run_async(_go())
    except Exception as e: _log_erro("sincronizar_bling", e); return {"error": str(e)}

# ── Helpers para entidades ──

def _primeira_loja() -> str:
    """Nome da primeira loja ativa — usado como loja padrao em operacoes internas."""
    _ensure_table()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT nome FROM lojas WHERE ativa = TRUE ORDER BY id LIMIT 1")
        return row["nome"] if row else "Loja Centro"
    try: return run_async(_go())
    except Exception as e: _log_erro("_primeira_loja", e); return "Loja Centro"

def _primeira_loja_id() -> int:
    """Id da primeira loja ativa — companion de _primeira_loja(), usado onde
    o registro precisa de loja_id (FK) em vez do nome (compras, contas a
    pagar: hoje centralizadas numa unica loja, sem selecao de loja na UI)."""
    _ensure_table()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT id FROM lojas WHERE ativa = TRUE ORDER BY id LIMIT 1")
        return row["id"] if row else 0
    try: return run_async(_go())
    except Exception as e: _log_erro("_primeira_loja_id", e); return 0

LOJA_PRINCIPAL: str = ""
LOJA_PRINCIPAL_ID: int = 0
LOJA_PRODUCAO: str = ""

def _init_loja_names():
    global LOJA_PRINCIPAL, LOJA_PRINCIPAL_ID, LOJA_PRODUCAO
    if LOJA_PRINCIPAL:
        return
    LOJA_PRINCIPAL = _primeira_loja()
    LOJA_PRINCIPAL_ID = _primeira_loja_id()
    LOJA_PRODUCAO = "Produção"

_init_loja_names()
