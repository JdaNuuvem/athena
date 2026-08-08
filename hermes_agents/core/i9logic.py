"""Reconciliacao Fisico x Contabil — Ponte i9Logic -> Athena.

De-para de identidade, client HTTP paginado (respeitando rate limit), staging
table de snapshot, classificacao de divergencia, job de coleta e seed inicial.
Fisico (tipoestoque=1) semeia estoque_saldos (Fase 1); contabil (tipoestoque=2)
nunca vira bucket, so' serve como sinal de auditoria. Nenhum ajuste automatico
de saldo — toda decisao sobre divergencia e' manual."""
import os, time, requests, threading
from datetime import datetime
from core import get_db, run_async, log
from core.config import get_config

AGENT = "I9Logic Reconciliacao"

BASE_URL = os.environ.get("I9LOGIC_BASE_URL") or get_config("i9logic", "base_url") or ""
# I9LOGIC_BASE_URL deve incluir "/v1" (ex.: "https://api.i9logic.net/v1") — o
# client HTTP nao concatena "/v1" por conta propria, pra nao arriscar
# duplicar o path se a env var ja vier com ele.
RATE_LIMIT_SLEEP_SEGUNDOS = 2.5  # ~24 req/min, margem sob o limite de 30/min da API
PER_PAGE_PADRAO = 200

FRESCOR_MAXIMO_MINUTOS = 30  # snapshot mais velho que isso dispara nova coleta em background

_coleta_em_andamento = set()  # filial_id -> coleta rodando agora, evita disparo duplicado
_coleta_erro_recente = {}  # filial_id -> mensagem de erro da ultima tentativa
_coleta_lock = threading.Lock()

from core.estoque_divergencia import (
    LIMIAR_ALERTA_ABSOLUTO, LIMIAR_ALERTA_PERCENTUAL, TOLERANCIA_ZERO,
    classificar_divergencia,
)

MAX_TENTATIVAS_PAGINA = 3
BACKOFF_SEGUNDOS = [2.5, 5, 10]


class I9LogicPaginaError(Exception):
    def __init__(self, pagina: int, causa):
        self.pagina = pagina
        self.causa = causa
        super().__init__(f"falha ao buscar pagina {pagina} apos {MAX_TENTATIVAS_PAGINA} tentativas: {causa}")


def _api_key() -> str:
    return os.environ.get("I9LOGIC_API_KEY") or get_config("i9logic", "api_key") or ""


def _client_id() -> str:
    return os.environ.get("I9LOGIC_CLIENT_ID") or get_config("i9logic", "client_id") or ""


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS de_para_i9logic (
            id SERIAL PRIMARY KEY,
            tipo VARCHAR(10) NOT NULL,
            id_i9logic VARCHAR(50) NOT NULL,
            codigo_athena VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (tipo, id_i9logic)
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS i9logic_estoque_snapshot (
            id SERIAL PRIMARY KEY,
            idproduto_i9logic INT NOT NULL,
            codproduto_i9logic VARCHAR(50),
            sku_athena VARCHAR(50),
            filial_i9logic INT NOT NULL,
            loja_athena VARCHAR(50),
            qtd_fisico DECIMAL(12,3),
            qtd_contabil DECIMAL(12,3),
            divergencia DECIMAL(12,3) GENERATED ALWAYS AS (qtd_contabil - qtd_fisico) STORED,
            data_coleta TIMESTAMP DEFAULT NOW(),
            revisado BOOLEAN DEFAULT FALSE,
            UNIQUE(idproduto_i9logic, filial_i9logic, data_coleta)
        )""")
    try:
        run_async(_go())
        log(AGENT, "Tabelas i9logic seeded")
    except Exception as e:
        log(AGENT, f"Erro tabelas i9logic: {e}")

_ensure_tables()

# ── De-para de identidade ──

def criar_mapeamento(tipo: str, id_i9logic, codigo_athena: str) -> dict:
    """Cria ou atualiza (upsert) o de-para entre um id interno do i9Logic e o
    codigo correspondente no Athena. tipo: 'produto' (id_i9logic=idproduto,
    codigo_athena=sku) ou 'filial' (id_i9logic=id da filial, codigo_athena=
    nome da loja)."""
    if tipo not in ("produto", "filial"):
        return {"erro": f"tipo invalido: {tipo}. Use 'produto' ou 'filial'"}
    if not str(id_i9logic).strip():
        return {"erro": "id_i9logic obrigatorio"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO de_para_i9logic (tipo, id_i9logic, codigo_athena) VALUES ($1,$2,$3) "
            "ON CONFLICT (tipo, id_i9logic) DO UPDATE SET codigo_athena=$3 RETURNING *",
            tipo, str(id_i9logic), codigo_athena)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"erro": str(e)}


def buscar_codigo_athena(tipo: str, id_i9logic):
    async def _go():
        db = await get_db()
        return await db.fetchval(
            "SELECT codigo_athena FROM de_para_i9logic WHERE tipo=$1 AND id_i9logic=$2",
            tipo, str(id_i9logic))
    try: return run_async(_go())
    except Exception: return None


def buscar_id_i9logic(tipo: str, codigo_athena: str):
    """Inverso de buscar_codigo_athena — resolve o id_i9logic a partir do
    codigo Athena (usado pra achar a filial i9Logic de uma loja pelo nome)."""
    async def _go():
        db = await get_db()
        return await db.fetchval(
            "SELECT id_i9logic FROM de_para_i9logic WHERE tipo=$1 AND codigo_athena=$2",
            tipo, codigo_athena)
    try: return run_async(_go())
    except Exception: return None


def listar_mapeamentos(tipo: str = None) -> list:
    async def _go():
        db = await get_db()
        if tipo:
            rows = await db.fetch("SELECT * FROM de_para_i9logic WHERE tipo=$1 ORDER BY id", tipo)
        else:
            rows = await db.fetch("SELECT * FROM de_para_i9logic ORDER BY tipo, id")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception: return []


def executar_matching_automatico(tipo: str, pares_i9logic: list) -> dict:
    """pares_i9logic: [{"id_i9logic": ..., "codigo_i9logic": ...}, ...] vindos da
    API i9Logic (codproduto pra tipo='produto', nome da filial pra tipo='filial').
    Casa por igualdade textual exata contra catalogo_produtos.sku ou lojas.nome —
    NUNCA matching fuzzy. O que nao casar vai pro relatorio de nao_casados pra
    revisao humana, sem tentativa de match aproximado."""
    if tipo not in ("produto", "filial"):
        return {"erro": f"tipo invalido: {tipo}. Use 'produto' ou 'filial'"}
    async def _go():
        db = await get_db()
        casados, nao_casados = [], []
        for par in pares_i9logic:
            codigo = par.get("codigo_i9logic", "")
            if tipo == "produto":
                existe = await db.fetchval("SELECT sku FROM catalogo_produtos WHERE sku=$1", codigo)
            else:
                existe = await db.fetchval("SELECT nome FROM lojas WHERE nome=$1", codigo)
            if existe:
                await db.execute(
                    "INSERT INTO de_para_i9logic (tipo, id_i9logic, codigo_athena) VALUES ($1,$2,$3) "
                    "ON CONFLICT (tipo, id_i9logic) DO UPDATE SET codigo_athena=$3",
                    tipo, str(par["id_i9logic"]), codigo)
                casados.append({"id_i9logic": par["id_i9logic"], "codigo_athena": codigo})
            else:
                nao_casados.append(par)
        return casados, nao_casados
    try:
        casados, nao_casados = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    return {"ok": True, "casados": len(casados), "nao_casados": nao_casados}


# ── Client HTTP (paginacao + rate limit) ──

def _paginar(endpoint: str, params: dict, on_pagina=None) -> list:
    """Pagina qualquer endpoint do i9Logic respeitando o rate limit (sleep de
    RATE_LIMIT_SLEEP_SEGUNDOS entre paginas, nunca apos a ultima). Falha de
    rede/API numa pagina tenta de novo ate MAX_TENTATIVAS_PAGINA vezes com
    backoff (BACKOFF_SEGUNDOS); esgotou, levanta I9LogicPaginaError (carrega
    o numero da pagina que falhou, pro chamador reportar progresso parcial).
    on_pagina, se passado, e' chamado com a lista de registros de cada
    pagina assim que ela chega — permite processamento/gravacao incremental
    em cargas grandes (import de catalogo) sem perder o progresso se uma
    pagina posterior falhar."""
    registros = []
    pagina = 1
    while True:
        dados = None
        ultimo_erro = None
        for tentativa in range(MAX_TENTATIVAS_PAGINA):
            try:
                resp = requests.get(
                    f"{BASE_URL}/{endpoint}",
                    params={**params, "page": pagina, "per_page": PER_PAGE_PADRAO},
                    headers={"X-Client-Id": _client_id(), "Authorization": f"Bearer {_api_key()}"},
                    timeout=30,
                )
                resp.raise_for_status()
                dados = resp.json()
                break
            except Exception as e:
                ultimo_erro = e
                if tentativa < MAX_TENTATIVAS_PAGINA - 1:
                    time.sleep(BACKOFF_SEGUNDOS[tentativa])
        if dados is None:
            raise I9LogicPaginaError(pagina, ultimo_erro)
        pagina_registros = dados.get("data", [])
        registros.extend(pagina_registros)
        if on_pagina:
            on_pagina(pagina_registros)
        total = dados.get("total", len(registros))
        if pagina * PER_PAGE_PADRAO >= total or not pagina_registros:
            break
        pagina += 1
        time.sleep(RATE_LIMIT_SLEEP_SEGUNDOS)
    return registros


def _paginar_estoques(filial_id_i9logic: int, tipoestoque: int) -> list:
    return _paginar("produtos_estoques", {"filial": filial_id_i9logic, "tipoestoque": tipoestoque})


# ── Leitura ao vivo (snapshot + coleta em background) ──
# Filiais grandes (~9k produtos, ~47 paginas com rate limit de 2.5s entre
# elas) levam ~2min pra paginar — puxar isso direto dentro do request da
# tela /estoque estourava o timeout do proxy (Cloudflare, ~100s). Em vez
# disso: le o snapshot mais recente (rapido, so' leitura de banco) e dispara
# a coleta completa numa thread em background quando ele nao existe ou esta'
# velho; o chamador poll'a de novo ate' o status virar "pronto".

def snapshot_mais_recente(filial_id_i9logic: int):
    """(data_coleta, itens) da corrida mais recente da filial no snapshot,
    enriquecido com descricao via catalogo_produtos.id_i9logic. (None, [])
    se essa filial nunca foi coletada."""
    async def _go():
        db = await get_db()
        data_coleta = await db.fetchval(
            "SELECT MAX(data_coleta) FROM i9logic_estoque_snapshot WHERE filial_i9logic=$1",
            filial_id_i9logic)
        if data_coleta is None:
            return None, []
        rows = await db.fetch("""
            SELECT s.idproduto_i9logic AS idproduto, s.codproduto_i9logic AS codproduto,
                   s.sku_athena, s.qtd_fisico AS qtd, c.descricao
            FROM i9logic_estoque_snapshot s
            LEFT JOIN catalogo_produtos c ON c.id_i9logic = s.idproduto_i9logic::text
            WHERE s.filial_i9logic=$1 AND s.data_coleta=$2
        """, filial_id_i9logic, data_coleta)
        return data_coleta, [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception:
        return None, []


def _coleta_em_background(filial_id_i9logic: int):
    """Roda a coleta completa fora do request. Sempre libera o lock ao
    final, mesmo em erro — senao a filial fica presa em 'processando' pra
    sempre e nunca mais tenta de novo."""
    try:
        executar_coleta_filial(filial_id_i9logic)
        _coleta_erro_recente.pop(filial_id_i9logic, None)
    except Exception as e:
        _coleta_erro_recente[filial_id_i9logic] = str(e)
        log(AGENT, f"Erro na coleta em background da filial {filial_id_i9logic}: {e}")
    finally:
        with _coleta_lock:
            _coleta_em_andamento.discard(filial_id_i9logic)


def _disparar_coleta_se_necessario(filial_id_i9logic: int, data_coleta) -> bool:
    """Dispara coleta em background se nao houver uma rodando e o snapshot
    estiver ausente ou mais velho que FRESCOR_MAXIMO_MINUTOS. Retorna True
    se a filial ficou (ou ja estava) em processamento."""
    precisa_coletar = data_coleta is None or (
        (datetime.now() - data_coleta).total_seconds() / 60 > FRESCOR_MAXIMO_MINUTOS)
    with _coleta_lock:
        ja_rodando = filial_id_i9logic in _coleta_em_andamento
        deve_iniciar = precisa_coletar and not ja_rodando
        if deve_iniciar:
            _coleta_em_andamento.add(filial_id_i9logic)
    # thread disparada fora do lock: _coleta_em_background tenta readquiri-lo
    # no finally, e o Thread.start() pode rodar o alvo na mesma thread
    # (sincrono, como em testes) — segurando o lock aqui seria autodeadlock.
    if deve_iniciar:
        threading.Thread(target=_coleta_em_background, args=(filial_id_i9logic,), daemon=True).start()
    return ja_rodando or deve_iniciar


def estoque_fisico_por_loja(loja_athena: str) -> dict:
    """Resolve a loja (pelo nome Athena) pra filial i9Logic via de-para e
    devolve o fisico do snapshot mais recente, disparando coleta em
    background quando ausente/desatualizado (nunca bloqueia esperando a
    paginacao). Erro claro se a loja ainda nao tem mapeamento de filial —
    sem isso, o chamador nao tem como diferenciar 'loja sem integracao
    i9Logic' de uma falha de rede generica."""
    id_i9logic = buscar_id_i9logic("filial", loja_athena)
    if id_i9logic is None:
        return {"erro": f"mapeamento de filial i9Logic nao encontrado para a loja '{loja_athena}' "
                         f"(cadastre em /api/integrations/i9logic/depara antes)"}
    filial_id = int(id_i9logic)
    data_coleta, itens = snapshot_mais_recente(filial_id)
    processando = _disparar_coleta_se_necessario(filial_id, data_coleta)
    resultado = {
        "ok": True,
        "status": "processando" if processando else "pronto",
        "filial_i9logic": filial_id,
        "data": itens,
    }
    if data_coleta is not None:
        resultado["coletado_em"] = data_coleta.isoformat()
        resultado["idade_minutos"] = round((datetime.now() - data_coleta).total_seconds() / 60, 1)
    erro_recente = _coleta_erro_recente.get(filial_id)
    if erro_recente:
        resultado["erro_ultima_coleta"] = erro_recente
    return resultado


# ── Snapshot (staging) ──

def gravar_snapshot(idproduto_i9logic: int, codproduto_i9logic: str, filial_i9logic: int,
                     qtd_fisico: float, qtd_contabil: float, data_coleta: datetime = None) -> dict:
    """Resolve sku_athena/loja_athena via de-para no momento da gravacao; grava
    nulo se nao encontrar mapeamento — nao perde o dado bruto coletado esperando
    resolucao manual do de-para. data_coleta explicito (nao so' o DEFAULT NOW()
    da coluna) permite que o job de coleta (Task 6) marque todas as linhas de
    uma mesma corrida com o MESMO instante, mesmo gravando fora de uma unica
    transacao — necessario pra 'uma linha por corrida completa' do spec."""
    async def _go():
        db = await get_db()
        sku_athena = await db.fetchval(
            "SELECT codigo_athena FROM de_para_i9logic WHERE tipo='produto' AND id_i9logic=$1",
            str(idproduto_i9logic))
        loja_athena = await db.fetchval(
            "SELECT codigo_athena FROM de_para_i9logic WHERE tipo='filial' AND id_i9logic=$1",
            str(filial_i9logic))
        row = await db.fetchrow("""
            INSERT INTO i9logic_estoque_snapshot
                (idproduto_i9logic, codproduto_i9logic, sku_athena, filial_i9logic, loja_athena,
                 qtd_fisico, qtd_contabil, data_coleta)
            VALUES ($1,$2,$3,$4,$5,$6,$7,COALESCE($8, NOW()))
            ON CONFLICT (idproduto_i9logic, filial_i9logic, data_coleta) DO UPDATE
                SET qtd_fisico=$6, qtd_contabil=$7
            RETURNING *
        """, idproduto_i9logic, codproduto_i9logic, sku_athena, filial_i9logic, loja_athena,
            qtd_fisico, qtd_contabil, data_coleta)
        return dict(row)
    try: return run_async(_go())
    except Exception as e: return {"erro": str(e)}


# ── Divergencia: classificacao, listagem, comparacao com Athena ──

def listar_itens_para_revisao(revisado: bool = False) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch(
            "SELECT * FROM i9logic_estoque_snapshot WHERE revisado=$1 AND ABS(divergencia) > $2 "
            "ORDER BY ABS(divergencia) DESC", revisado, TOLERANCIA_ZERO)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception: return []


def marcar_revisado(snapshot_id: int) -> dict:
    """Resolve o item como 'aceitar a divergencia como conhecida' — so' marca
    revisado, nunca toca saldo. Pro caminho que ajusta saldo de verdade, ver
    aplicar_ajuste_divergencia()."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "UPDATE i9logic_estoque_snapshot SET revisado=TRUE WHERE id=$1 RETURNING *", snapshot_id)
        return dict(row) if row else None
    try:
        r = run_async(_go())
        return {"ok": True, "snapshot": r} if r else {"erro": "snapshot nao encontrado"}
    except Exception as e: return {"erro": str(e)}


def aplicar_ajuste_divergencia(snapshot_id: int, usuario_id: int = None, usuario_nome: str = "",
                                confirmar_zerar: bool = False) -> dict:
    """Resolve o item como 'ajustar manualmente' (spec): aplica o fisico
    coletado como quantidade absoluta via core.estoque.ajustar_absoluto() —
    passa pelo ledger formal do Athena (Fase 1), motivo fixo 'ajuste_inventario'
    (nao da' pra colar o id do snapshot dentro do motivo — e' um enum validado
    contra MOTIVOS_ENTRADA/MOTIVOS_SAIDA, nao texto livre). Rastreabilidade fica
    por correlacao de tempo entre estoque_movimentacoes e este snapshot, mais o
    proprio snapshot_id que o chamador ja tinha na mao pra disparar isto.
    So' marca revisado=TRUE se o ajuste realmente aplicar sem erro.

    Duas guardas antes de aplicar:
    1. qtd_fisico zero/nula: um produto que so' apareceu no feed contabil
       (ausente do fisico) grava qtd_fisico=0 no snapshot como sinal de
       auditoria (Task 6) — nao necessariamente estoque zero de verdade.
       Aplicar isso como absoluto zeraria o saldo do Athena sem querer. So'
       aceita se o chamador confirmar explicitamente via confirmar_zerar=True.
    2. frescor: so' aplica se este snapshot_id for o MAIS RECENTE pra aquele
       sku_athena/loja_athena — evita aplicar um snapshot antigo por cima do
       saldo atual."""
    async def _buscar():
        db = await get_db()
        return await db.fetchrow(
            "SELECT sku_athena, loja_athena, qtd_fisico FROM i9logic_estoque_snapshot WHERE id=$1",
            snapshot_id)
    try:
        snap = run_async(_buscar())
    except Exception as e:
        return {"erro": str(e)}
    if not snap:
        return {"erro": "snapshot nao encontrado"}
    if not snap["sku_athena"] or not snap["loja_athena"]:
        return {"erro": "snapshot sem de-para resolvido (sku_athena/loja_athena nulos) - resolva o de-para antes de ajustar"}
    qtd = snap["qtd_fisico"]
    if (qtd is None or float(qtd) <= 0) and not confirmar_zerar:
        return {"erro": "quantidade fisica deste snapshot e' zero ou nula - aplicar isso zeraria o saldo do "
                         "Athena. Pode ser produto ausente do feed fisico da coleta (nao necessariamente "
                         "estoque zero de verdade). Confirme explicitamente com confirmar_zerar=True se for "
                         "intencional, ou investigue a coleta antes."}
    async def _mais_recente():
        db = await get_db()
        return await db.fetchval(
            "SELECT id FROM i9logic_estoque_snapshot WHERE sku_athena=$1 AND loja_athena=$2 "
            "ORDER BY data_coleta DESC LIMIT 1",
            snap["sku_athena"], snap["loja_athena"])
    try:
        id_mais_recente = run_async(_mais_recente())
    except Exception as e:
        return {"erro": str(e)}
    if id_mais_recente is not None and id_mais_recente != snapshot_id:
        return {"erro": f"este snapshot (id={snapshot_id}) nao e' o mais recente pra este sku/loja "
                         f"(o mais recente e' id={id_mais_recente}) - ajuste a partir do mais recente, "
                         f"nao de um snapshot antigo"}
    from core.estoque import ajustar_absoluto
    resultado = ajustar_absoluto(
        snap["sku_athena"], snap["loja_athena"], float(qtd or 0),
        motivo="ajuste_inventario", usuario_id=usuario_id, usuario_nome=usuario_nome)
    if resultado.get("erro"):
        return resultado
    marcado = marcar_revisado(snapshot_id)
    if marcado.get("erro"):
        return {"erro": f"ajuste aplicado mas falha ao marcar revisado: {marcado['erro']}", "ajuste": resultado}
    return {"ok": True, "ajuste": resultado, "snapshot": marcado.get("snapshot")}


def comparar_com_athena(sku: str, loja: str) -> dict:
    """Modo monitoramento continuo (spec): compara o disponivel atual do Athena
    contra o fisico mais recente coletado do i9Logic pro mesmo sku/loja."""
    from core.estoque_saldos import saldo
    async def _go():
        db = await get_db()
        return await db.fetchrow("""
            SELECT qtd_fisico, data_coleta FROM i9logic_estoque_snapshot
            WHERE sku_athena=$1 AND loja_athena=$2 ORDER BY data_coleta DESC LIMIT 1
        """, sku, loja)
    try:
        ultimo = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    if not ultimo:
        return {"erro": "sem snapshot para este sku/loja"}
    disponivel_athena = saldo(sku, loja, "disponivel")
    qtd_fisico = float(ultimo["qtd_fisico"] or 0)
    return {
        "sku": sku, "loja": loja,
        "disponivel_athena": disponivel_athena,
        "qtd_fisico_i9logic": qtd_fisico,
        "divergencia": round(disponivel_athena - qtd_fisico, 3),
        "classificacao": classificar_divergencia(qtd_fisico, disponivel_athena),
        "data_coleta": ultimo["data_coleta"],
    }


# ── Job de coleta ──

def executar_coleta_filial(filial_id_i9logic: int) -> dict:
    """Coleta fisico e contabil da filial inteira, pareia por idproduto, e grava
    cada par no snapshot com o MESMO data_coleta (uma corrida = um instante),
    resolvendo sku_athena/loja_athena via de-para em cada gravacao."""
    inicio_corrida = datetime.now()
    fisicos = _paginar_estoques(filial_id_i9logic, 1)
    contabeis = _paginar_estoques(filial_id_i9logic, 2)
    fisico_por_produto = {r["idproduto"]: r for r in fisicos}
    contabil_por_produto = {r["idproduto"]: r for r in contabeis}
    todos_ids = set(fisico_por_produto) | set(contabil_por_produto)
    gravados, erros = 0, 0
    for idproduto in todos_ids:
        f = fisico_por_produto.get(idproduto, {})
        c = contabil_por_produto.get(idproduto, {})
        codproduto = f.get("codproduto") or c.get("codproduto")
        r = gravar_snapshot(
            idproduto, codproduto, filial_id_i9logic,
            f.get("qtd", 0), c.get("qtd", 0), data_coleta=inicio_corrida)
        if r.get("erro"): erros += 1
        else: gravados += 1
    return {"ok": True, "filial": filial_id_i9logic, "fisicos": len(fisicos),
            "contabeis": len(contabeis), "gravados": gravados, "erros": erros,
            "data_coleta": inicio_corrida}


def executar_coleta_todas_filiais() -> dict:
    """Roda executar_coleta_filial pra cada filial ja mapeada em de_para_i9logic
    (tipo='filial'). Filial sem de-para nao entra — nao ha id_i9logic resolvido
    sem o mapeamento. Cada filial roda isolada num try/except: erro de
    rede/API malformada numa filial vira {"erro": ...} no lugar do resultado
    daquela filial, sem abortar o processamento das demais."""
    if not BASE_URL:
        return {"erro": "I9LOGIC_BASE_URL nao configurado - configure antes de rodar a coleta"}
    filiais = listar_mapeamentos("filial")
    resultados = []
    for m in filiais:
        try:
            resultados.append(executar_coleta_filial(int(m["id_i9logic"])))
        except Exception as e:
            resultados.append({"erro": str(e), "filial_i9logic_bruto": m.get("id_i9logic")})
    return {"ok": True, "filiais_processadas": len(resultados), "resultados": resultados}


# ── Seed inicial ──

def seed_inicial(sku_athena: str, loja_athena: str, usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Usa o fisico mais recente coletado como entrada UNICA no Athena — so'
    faz sentido na primeira migracao do sku/loja pra Athena (spec: 'modo 1'). O
    contabil nao participa do seed, fica so' no snapshot como referencia."""
    from core.estoque import entrada
    async def _go():
        db = await get_db()
        return await db.fetchrow("""
            SELECT qtd_fisico FROM i9logic_estoque_snapshot
            WHERE sku_athena=$1 AND loja_athena=$2 ORDER BY data_coleta DESC LIMIT 1
        """, sku_athena, loja_athena)
    try:
        ultimo = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    if not ultimo:
        return {"erro": "sem snapshot para este sku/loja"}
    qtd = float(ultimo["qtd_fisico"] or 0)
    if qtd <= 0:
        return {"erro": "quantidade fisica coletada e' zero ou negativa, seed nao aplicado"}
    return entrada(sku_athena, loja_athena, qtd, motivo="import_i9logic",
                    usuario_id=usuario_id, usuario_nome=usuario_nome)
