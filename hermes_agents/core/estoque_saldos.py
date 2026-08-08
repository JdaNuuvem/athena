"""Saldos segregados de estoque (Fase 1 da revisao de arquitetura multilojas).
estoque_saldos e' a fonte de verdade; estoque_lojas.quantidade vira espelho do
saldo 'disponivel', mantido por trigger no banco (defesa em profundidade caso
algum caller ainda nao migrado escreva direto em estoque_lojas).

Duas portas de entrada para escrita:
  - mover_saldo(...)          -> sincrona, abre conexao+transacao propria.
  - _mover_saldo_async(conn,) -> async-native, reaproveita a conexao/transacao
                                 de quem chama. Use esta em qualquer caller que
                                 JA esteja dentro de um `async def` rodando sob
                                 run_async() — chamar a versao sincrona la
                                 dentro faz run_async abrir um novo event loop
                                 numa thread, e get_db() cria (e abandona) um
                                 pool asyncpg novo a cada chamada.
"""
from core import get_db, run_async, log
from core.lojas import _loja_efetiva_async, _log_erro

AGENT = "Estoque Saldos"

TIPOS_SALDO = (
    "disponivel", "reservado", "separacao", "transito", "bloqueado",
    "devolucao", "danificado", "perdido", "consignado", "inventario", "virtual",
)

TIPOS_MOVIMENTO = (
    "compra", "venda", "ajuste", "inventario", "transferencia_saida",
    "transferencia_transito", "transferencia_recebida", "reserva",
    "liberacao_reserva", "separacao", "expedicao", "recebimento", "devolucao",
    "troca", "perda", "roubo", "extravio", "bonificacao", "cancelamento", "estorno",
)

_ok = False


class SaldoError(Exception):
    """Erro de regra de saldo levantado de dentro de uma transacao aberta pelo
    caller — levantar (em vez de retornar dict) e' o que garante o ROLLBACK do
    que ja foi escrito na mesma transacao (ex.: perna 1 de uma transferencia)."""


async def _ensure_async():
    """Cria/ajusta schema. Idempotente. Versao async pra callers que ja estao
    dentro de um loop; `_ensure()` e' o wrapper sincrono."""
    global _ok
    if _ok:
        return
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS estoque_saldos (
            id SERIAL PRIMARY KEY,
            sku VARCHAR(50) NOT NULL,
            loja VARCHAR(50) NOT NULL,
            tipo VARCHAR(20) NOT NULL,
            quantidade DECIMAL(12,3) NOT NULL DEFAULT 0,
            data_atualizacao TIMESTAMP DEFAULT NOW(),
            UNIQUE(sku, loja, tipo)
        )
    """)
    # Defensivo: garante que estoque_lojas existe mesmo se core/catalogo.py
    # (dono original) ainda nao rodou nesta conexao.
    await db.execute("""
        CREATE TABLE IF NOT EXISTS estoque_lojas (
            id SERIAL PRIMARY KEY, sku VARCHAR(50) NOT NULL, loja VARCHAR(50) NOT NULL,
            quantidade DECIMAL(12,3) DEFAULT 0, data_atualizacao TIMESTAMP DEFAULT NOW(),
            UNIQUE (sku, loja)
        )
    """)
    # ── BACKFILL (fix review final #1) ──
    # Sem isto, estoque_saldos nasce vazio no deploy: saldo() retorna 0 pra
    # todo SKU existente e a PRIMEIRA entrada() grava um delta pequeno que o
    # trigger de espelho copia por cima de estoque_lojas.quantidade,
    # destruindo o estoque real. Roda ANTES do trigger ser criado (no primeiro
    # deploy) e e' idempotente via ON CONFLICT DO NOTHING — nas execucoes
    # seguintes nao insere nada, entao nao dispara o espelho de volta.
    await db.execute("""
        INSERT INTO estoque_saldos (sku, loja, tipo, quantidade, data_atualizacao)
        SELECT sku, loja, 'disponivel', COALESCE(quantidade, 0), NOW() FROM estoque_lojas
        ON CONFLICT (sku, loja, tipo) DO NOTHING
    """)
    # Defensivo: garante estoque_movimentacoes com as colunas novas de
    # auditoria mesmo se core/estoque.py ainda nao rodou nesta conexao.
    await db.execute("""
        CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
            id SERIAL PRIMARY KEY,
            sku VARCHAR(50) NOT NULL,
            loja VARCHAR(50) NOT NULL,
            tipo VARCHAR(30) NOT NULL,
            quantidade DECIMAL(12,3) NOT NULL,
            loja_relacionada VARCHAR(50),
            motivo VARCHAR(200),
            data TIMESTAMP DEFAULT NOW()
        )
    """)
    # ── LARGURA DE COLUNA (fix review final #2) ──
    # A tabela em producao foi criada com tipo VARCHAR(20); CREATE TABLE IF NOT
    # EXISTS e ADD COLUMN IF NOT EXISTS nao alargam coluna existente. Dois
    # valores novos estouram 20 chars ('transferencia_recebida' = 22,
    # 'transferencia_transito' = 22), o que quebraria toda transferencia
    # concluida. Guardado por information_schema pra nao pegar ACCESS
    # EXCLUSIVE lock em todo boot quando ja esta larga.
    await db.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'estoque_movimentacoes'
                  AND column_name = 'tipo'
                  AND character_maximum_length IS NOT NULL
                  AND character_maximum_length < 30
            ) THEN
                ALTER TABLE estoque_movimentacoes ALTER COLUMN tipo TYPE VARCHAR(30);
            END IF;
        END $$
    """)
    await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS usuario_id INT")
    await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS usuario_nome VARCHAR(100)")
    await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS tipo_saldo VARCHAR(20)")
    await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS saldo_anterior DECIMAL(12,3)")
    await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS saldo_posterior DECIMAL(12,3)")
    await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS ip VARCHAR(45)")
    await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS dispositivo VARCHAR(300)")
    # ── Fase 3 (loja_id FK): colunas aditivas, defensivas ──
    # Os donos originais dessas colunas sao core/catalogo.py (estoque_lojas) e
    # core/estoque.py (estoque_movimentacoes, cujo _ensure() saiu na Fase 1).
    # Repetidas aqui porque _mover_saldo_async e o trigger de espelho abaixo
    # dependem delas e podem rodar antes daqueles modulos nesta conexao.
    # ADD COLUMN IF NOT EXISTS e' no-op quando a coluna ja existe (entao nao
    # "perde" a FK criada pelo dono original); o BEGIN/EXCEPTION cobre o caso
    # de a tabela `lojas` ainda nao existir, sem abortar o resto do _ensure.
    await db.execute("""
        DO $$
        BEGIN
            BEGIN
                ALTER TABLE estoque_lojas ADD COLUMN IF NOT EXISTS loja_id INT REFERENCES lojas(id);
            EXCEPTION WHEN others THEN NULL;
            END;
            BEGIN
                ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS loja_id INT REFERENCES lojas(id);
            EXCEPTION WHEN others THEN NULL;
            END;
        END $$
    """)
    # Espelho: estoque_lojas.quantidade sempre reflete estoque_saldos
    # (tipo='disponivel') — defesa em profundidade pra callers nao migrados.
    #
    # Fase 3 x Fase 1: o espelho tambem resolve estoque_lojas.loja_id a partir
    # do nome da loja. Sem isso, o dual-write de loja_id morria aqui: como
    # estoque_saldos nao tem loja_id (e nao precisa ter — a chave e' (sku,
    # loja, tipo)), toda linha de estoque_lojas criada pelo espelho nasceria
    # com loja_id NULL, e o filtro de RBAC por loja (`e.loja_id = ANY(...)`)
    # simplesmente nao veria esse estoque. COALESCE pra que um nome de loja
    # sem correspondencia em `lojas` nunca APAGUE um loja_id ja preenchido
    # (pelo dual-write ou pela reconciliacao periodica).
    await db.execute("""
        CREATE OR REPLACE FUNCTION fn_espelhar_saldo_disponivel() RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.tipo = 'disponivel' THEN
                INSERT INTO estoque_lojas (sku, loja, loja_id, quantidade, data_atualizacao)
                VALUES (NEW.sku, NEW.loja,
                        (SELECT id FROM lojas WHERE nome = NEW.loja),
                        NEW.quantidade, NOW())
                ON CONFLICT (sku, loja) DO UPDATE
                    SET loja_id = COALESCE(EXCLUDED.loja_id, estoque_lojas.loja_id),
                        quantidade = NEW.quantidade, data_atualizacao = NOW();
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    await db.execute("DROP TRIGGER IF EXISTS trg_espelhar_saldo_disponivel ON estoque_saldos")
    await db.execute("""
        CREATE TRIGGER trg_espelhar_saldo_disponivel
        AFTER INSERT OR UPDATE ON estoque_saldos
        FOR EACH ROW EXECUTE FUNCTION fn_espelhar_saldo_disponivel()
    """)
    _ok = True


def _ensure():
    global _ok
    if _ok:
        return
    try:
        run_async(_ensure_async())
    except Exception as e:
        log(AGENT, f"Erro tabela/trigger: {e}")


def _validar(tipo_origem, tipo_destino, tipo_movimento, quantidade):
    """Retorna string de erro ou None. Compartilhado pelas duas portas."""
    if tipo_origem is None and tipo_destino is None:
        return "tipo_origem e tipo_destino nao podem ser ambos None"
    if tipo_origem is not None and tipo_origem not in TIPOS_SALDO:
        return f"tipo_origem invalido: {tipo_origem}"
    if tipo_destino is not None and tipo_destino not in TIPOS_SALDO:
        return f"tipo_destino invalido: {tipo_destino}"
    if tipo_movimento not in TIPOS_MOVIMENTO:
        return f"tipo_movimento invalido: {tipo_movimento}"
    if quantidade <= 0:
        return "quantidade deve ser maior que zero"
    return None


async def _saldo_async(conn, sku: str, loja: str, tipo: str = "disponivel") -> float:
    """Le um bucket usando a conexao/transacao ja aberta pelo caller."""
    # Vinculo fisica x virtual (Fase Vinculo): resolve ANTES de qualquer
    # leitura — mesmo espirito do choke point de escrita (_mover_saldo_async,
    # acima): se `loja` for uma virtual com vinculo ativo, devolve o nome da
    # fisica vinculada; senao, devolve o proprio nome. Este e' o UNICO choke
    # point de LEITURA de estoque_saldos usado por callers async-native (ex.:
    # core/estoque.py::ajustar_absoluto_async), entao fica vinculo-aware sem
    # precisar tocar em cada caller individualmente.
    #
    # Mesmo fail-open de _mover_saldo_async (ver comentario detalhado la'):
    # _loja_efetiva_async abre sua PROPRIA conexao via get_db(), independente
    # do `conn` ja aberto aqui, entao um DB indisponivel — ou, em teste, um
    # fake que nao cobre essa query — nao pode derrubar toda LEITURA de
    # estoque do sistema. Melhor prosseguir com o nome original (mesmo
    # comportamento de antes do vinculo existir) do que propagar a excecao ou,
    # pior, ler sob um valor corrompido devolvido por um mock/fake alheio.
    # _log_erro persiste em system_logs (visivel em /seguranca/logs) pra
    # cobrir os DOIS jeitos de falhar: excecao (DB indisponivel) e retorno
    # invalido sem excecao (mock/fake alheio que devolve algo que nao e' str).
    try:
        loja_resolvida = await _loja_efetiva_async(loja)
        if isinstance(loja_resolvida, str) and loja_resolvida:
            loja = loja_resolvida
        else:
            _log_erro(
                "estoque_saldos._saldo_async: resolver_loja_efetiva",
                ValueError(f"loja '{loja}' -> valor invalido {loja_resolvida!r} (esperado str nao-vazia)"))
    except Exception as e:
        _log_erro("estoque_saldos._saldo_async: resolver_loja_efetiva", e)

    v = await conn.fetchval(
        "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3",
        sku, loja, tipo)
    return float(v or 0)


def saldo(sku: str, loja: str, tipo: str = "disponivel") -> float:
    """Wrapper SINCRONO. NAO delega pra _saldo_async(conn, ...) — abre sua
    propria conexao via get_db() em vez de reaproveitar uma `conn` de
    transacao (nao ha' nenhuma pra reaproveitar aqui) — por isso precisa do
    seu PROPRIO guard de resolucao de loja abaixo, e nao so' o de
    _saldo_async."""
    _ensure()
    async def _go():
        db = await get_db()
        # Vinculo fisica x virtual (Fase Vinculo): mesmo fail-open de
        # _saldo_async (ver comentario detalhado la'). Usa uma variavel local
        # separada (loja_efetiva) em vez de reatribuir o parametro `loja` do
        # escopo externo — evita mutar via closure/nonlocal a variavel usada
        # na mensagem de erro do except abaixo caso o fetchval falhe depois.
        loja_efetiva = loja
        try:
            loja_resolvida = await _loja_efetiva_async(loja)
            if isinstance(loja_resolvida, str) and loja_resolvida:
                loja_efetiva = loja_resolvida
            else:
                _log_erro(
                    "estoque_saldos.saldo: resolver_loja_efetiva",
                    ValueError(f"loja '{loja}' -> valor invalido {loja_resolvida!r} (esperado str nao-vazia)"))
        except Exception as e:
            _log_erro("estoque_saldos.saldo: resolver_loja_efetiva", e)

        v = await db.fetchval(
            "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3",
            sku, loja_efetiva, tipo)
        return float(v or 0)
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao consultar saldo({sku}, {loja}, {tipo}): {e}")
        return 0.0


def saldos_em_lote(skus, loja: str, tipo: str = "disponivel") -> dict:
    """Versao EM LOTE de saldo(): resolve loja_efetiva UMA vez e le todos os
    skus num unico SELECT, em vez de N chamadas sequenciais de saldo() (cada
    uma custa um run_async — hop entre threads — mais um round-trip proprio).
    Telas que comparam um catalogo inteiro contra um sistema externo (a
    Divergencia de Saldo i9Logic/Shopee) faziam ~9k queries sequenciais por
    request com o loop de saldo(), segurando uma thread do Flask por dezenas
    de segundos.

    DIFERENCA DELIBERADA em relacao a saldo(): esta versao NAO e' fail-open.
    saldo() devolve 0.0 em qualquer excecao, o que num loop de milhares de
    chamadas transforma um erro transiente de banco num zero indistinguivel
    de um zero legitimo — e numa tela de divergencia isso vira uma linha
    "alerta" FABRICADA, com botao de "Ajustar" do lado. Aqui a excecao sobe e
    quem chama decide (as duas telas de divergencia devolvem erro claro).

    Sku ausente na tabela sai como 0.0: ai a ausencia de linha e' mesmo
    ausencia de saldo, nao uma falha mascarada.
    """
    skus_unicos = sorted({str(s) for s in skus if s})
    if not skus_unicos:
        return {}
    _ensure()
    async def _go():
        db = await get_db()
        # Mesmo fail-open de saldo() SO' pra resolucao de loja vinculada (ver
        # comentario detalhado em _saldo_async): um vinculo irresolvivel nao
        # pode derrubar a leitura inteira, o nome original serve de fallback.
        loja_efetiva = loja
        try:
            loja_resolvida = await _loja_efetiva_async(loja)
            if isinstance(loja_resolvida, str) and loja_resolvida:
                loja_efetiva = loja_resolvida
            else:
                _log_erro(
                    "estoque_saldos.saldos_em_lote: resolver_loja_efetiva",
                    ValueError(f"loja '{loja}' -> valor invalido {loja_resolvida!r} (esperado str nao-vazia)"))
        except Exception as e:
            _log_erro("estoque_saldos.saldos_em_lote: resolver_loja_efetiva", e)

        rows = await db.fetch(
            "SELECT sku, quantidade FROM estoque_saldos "
            "WHERE loja = $1 AND tipo = $2 AND sku = ANY($3::text[])",
            loja_efetiva, tipo, skus_unicos)
        encontrados = {r["sku"]: float(r["quantidade"] or 0) for r in rows}
        return {sku: encontrados.get(sku, 0.0) for sku in skus_unicos}
    return run_async(_go())


async def _mover_saldo_async(conn, sku: str, loja: str, tipo_origem, tipo_destino,
                             quantidade: float, tipo_movimento: str, motivo: str = "",
                             usuario_id: int = None, usuario_nome: str = "",
                             ip: str = None, dispositivo: str = None) -> dict:
    """Nucleo da escrita. Assume que `conn` ja esta dentro de uma transacao
    aberta pelo caller (SELECT ... FOR UPDATE so' segura de verdade assim).

    Erros de validacao/saldo sao RETORNADOS como {"erro": ...} — esta funcao
    nunca escreve nada antes de detectar um erro proprio. Quando o caller
    encadeia duas chamadas na mesma transacao (transferencia), ele deve
    levantar SaldoError no erro da segunda pra forcar o ROLLBACK da primeira."""
    # Vinculo fisica x virtual (Fase Vinculo): resolve ANTES de qualquer
    # leitura/escrita — se `loja` for uma virtual com vinculo ativo, devolve o
    # nome da fisica vinculada; senao, devolve o proprio nome (so' resolvendo
    # id->nome, se for o caso). Este e' o UNICO choke point de escrita de
    # estoque_saldos (mover_saldo() delega pra ca'), entao todo write-path
    # (PDV, entrada/saida manual, transferencia, aprovacao, rateio) fica
    # vinculo-aware sem precisar tocar em cada caller individualmente.
    #
    # Try/except + isinstance defensivos, mesmo espirito de
    # core.lojas.loja_efetiva() (o wrapper sincrono, que ja' faz
    # try/except-e-fallback ao redor desta mesma _loja_efetiva_async):
    # _loja_efetiva_async abre sua PROPRIA conexao via get_db() (independente
    # do `conn' ja aberto aqui), entao um DB indisponivel — ou, em teste, um
    # fake que nao cobre essa query — nao pode derrubar TODA movimentacao de
    # estoque do sistema. Melhor prosseguir com o nome original (mesmo
    # comportamento de antes do vinculo existir) do que propagar a excecao ou,
    # pior, gravar sob um valor corrompido devolvido por um mock/fake alheio.
    #
    # Fail-open exige trilha duravel: se a resolucao falha e a escrita segue
    # sob o nome original silenciosamente, uma loja vinculada gravando no
    # balanco errado so' e' descoberta se o erro ficar registrado em algum
    # lugar consultavel. _log_erro (core.lojas — mesmo helper que
    # rbac_lojas.py/lojas_operacional.py/lojas_virtual.py/etc ja' importam
    # cross-module) persiste em system_logs (visivel em /seguranca/logs),
    # nao so' no console do container — cobre os DOIS jeitos de falhar:
    # excecao (DB indisponivel) e retorno invalido sem excecao (mock/fake
    # alheio que devolve algo que nao e' string).
    try:
        loja_resolvida = await _loja_efetiva_async(loja)
        if isinstance(loja_resolvida, str) and loja_resolvida:
            loja = loja_resolvida
        else:
            _log_erro(
                "estoque_saldos._mover_saldo_async: resolver_loja_efetiva",
                ValueError(f"loja '{loja}' -> valor invalido {loja_resolvida!r} (esperado str nao-vazia)"))
    except Exception as e:
        _log_erro("estoque_saldos._mover_saldo_async: resolver_loja_efetiva", e)

    erro = _validar(tipo_origem, tipo_destino, tipo_movimento, quantidade)
    if erro:
        return {"erro": erro}

    # Fase 3 (dual-write loja_id): resolvido UMA vez aqui, na conexao/transacao
    # que ja esta aberta, e usado nos INSERTs de estoque_movimentacoes abaixo.
    # Fica nesta funcao — e nao em cada caller — porque desde a Fase 1 este e'
    # o unico lugar que escreve estoque_movimentacoes; um dual-write feito
    # pelo caller depois do fato seria uma segunda declaracao podendo divergir.
    # None quando o nome da loja nao existe em `lojas` (nome digitado errado,
    # loja legada): nao quebra o fluxo, fica para reconciliar_loja_id().
    loja_id = await conn.fetchval("SELECT id FROM lojas WHERE nome = $1", loja)

    resultado = {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade}

    if tipo_origem is not None:
        atual = await conn.fetchval(
            "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3 FOR UPDATE",
            sku, loja, tipo_origem)
        atual = float(atual or 0)
        if atual < quantidade:
            return {"erro": f"Saldo insuficiente em '{tipo_origem}' ({atual} disponivel, {quantidade} solicitado)"}
        nova_origem = atual - quantidade
        await conn.execute("""
            INSERT INTO estoque_saldos (sku, loja, tipo, quantidade, data_atualizacao)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (sku, loja, tipo) DO UPDATE SET quantidade = $4, data_atualizacao = NOW()
        """, sku, loja, tipo_origem, nova_origem)
        await conn.execute("""
            INSERT INTO estoque_movimentacoes
                (sku, loja, loja_id, tipo, quantidade, motivo, usuario_id, usuario_nome,
                 tipo_saldo, saldo_anterior, saldo_posterior, ip, dispositivo)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """, sku, loja, loja_id, tipo_movimento, quantidade, motivo, usuario_id, usuario_nome,
            tipo_origem, atual, nova_origem, ip, dispositivo)
        resultado["saldo_origem"] = {"tipo": tipo_origem, "anterior": atual, "atual": nova_origem}

    if tipo_destino is not None:
        # Fix review final #5: SKU que so' existe no ledger e' invisivel nas
        # listagens (estoque_lojas JOIN catalogo_produtos e' INNER). Garante a
        # linha minima de catalogo aqui, na mesma transacao, pra valer pra
        # qualquer caller (entrada/ajustar_absoluto/rateio/...).
        if tipo_destino == "disponivel":
            await conn.execute("""
                INSERT INTO catalogo_produtos (sku, descricao) VALUES ($1, $1)
                ON CONFLICT (sku) DO NOTHING
            """, sku)
        atual_d = await conn.fetchval(
            "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3",
            sku, loja, tipo_destino)
        atual_d = float(atual_d or 0)
        nova_destino = atual_d + quantidade
        await conn.execute("""
            INSERT INTO estoque_saldos (sku, loja, tipo, quantidade, data_atualizacao)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (sku, loja, tipo) DO UPDATE SET quantidade = $4, data_atualizacao = NOW()
        """, sku, loja, tipo_destino, nova_destino)
        await conn.execute("""
            INSERT INTO estoque_movimentacoes
                (sku, loja, loja_id, tipo, quantidade, motivo, usuario_id, usuario_nome,
                 tipo_saldo, saldo_anterior, saldo_posterior, ip, dispositivo)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """, sku, loja, loja_id, tipo_movimento, quantidade, motivo, usuario_id, usuario_nome,
            tipo_destino, atual_d, nova_destino, ip, dispositivo)
        resultado["saldo_destino"] = {"tipo": tipo_destino, "anterior": atual_d, "atual": nova_destino}

    return resultado


def mover_saldo(sku: str, loja: str, tipo_origem, tipo_destino, quantidade: float,
                tipo_movimento: str, motivo: str = "", usuario_id: int = None, usuario_nome: str = "",
                ip: str = None, dispositivo: str = None) -> dict:
    """Unica funcao SINCRONA que escreve em estoque_saldos + estoque_movimentacoes,
    na mesma transacao. tipo_origem=None => credito puro (entrada).
    tipo_destino=None => debito puro (saida). Pelo menos um dos dois precisa
    estar presente. Nunca chamar UPDATE/INSERT em estoque_saldos fora daqui
    (ou de _mover_saldo_async, o mesmo nucleo).

    NAO chame esta versao de dentro de um `async def` — use
    `_mover_saldo_async(conn, ...)`, senao run_async abre um event loop novo e
    get_db() vaza um pool asyncpg por chamada."""
    _ensure()
    erro = _validar(tipo_origem, tipo_destino, tipo_movimento, quantidade)
    if erro:
        return {"erro": erro}

    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                return await _mover_saldo_async(
                    conn, sku, loja, tipo_origem, tipo_destino, quantidade,
                    tipo_movimento, motivo, usuario_id, usuario_nome, ip, dispositivo)
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
