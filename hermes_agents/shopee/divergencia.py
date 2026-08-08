"""Divergencia de Saldo — Athena x Shopee. Mesmo principio do
core/i9logic.py: guarda so' o saldo externo bruto no snapshot (nunca o
saldo Athena, que muda a cada venda — comparacao e' sempre calculada ao
vivo na leitura, ver listar_divergencias em divergencia.py parte 2)."""
import sys, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from core import get_db, run_async, log
from core.lojas import obter as obter_loja
from core.estoque_divergencia import classificar_divergencia
from core.estoque import ajustar_absoluto
from .products import sync_all_items

AGENT = "Shopee Divergencia"

FRESCOR_MAXIMO_MINUTOS = 30  # mesmo valor do i9Logic — snapshot mais velho que isso dispara nova coleta

# Sem esse freio, uma coleta que falha RAPIDO (token Shopee expirado, por ex.)
# libera o lock em ~1s, o snapshot continua ausente, e o polling de 5s da tela
# dispara uma coleta nova a cada 5 segundos indefinidamente — martelando a API
# da Shopee ate' tomar rate-limit. O i9Logic nao precisa disso porque a coleta
# dele demora ~2min e se auto-limita pelo proprio tempo de execucao.
COOLDOWN_APOS_FALHA_SEGUNDOS = 60

_coleta_em_andamento = set()  # loja_id -> coleta rodando agora, evita disparo duplicado
_coleta_erro_recente = {}  # loja_id -> mensagem de erro da ultima tentativa (exposta em listar_divergencias)
_ultima_falha = {}  # loja_id -> datetime da ultima falha, base do cooldown acima
_coleta_lock = threading.Lock()


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS shopee_estoque_snapshot (
            id SERIAL PRIMARY KEY,
            sku VARCHAR(50) NOT NULL,
            loja_id INT NOT NULL REFERENCES lojas(id),
            item_id_shopee VARCHAR(100),
            qtd_shopee DECIMAL(12,3),
            data_coleta TIMESTAMP DEFAULT NOW(),
            revisado BOOLEAN DEFAULT FALSE,
            UNIQUE(sku, loja_id, data_coleta)
        )""")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao criar tabela shopee_estoque_snapshot: {e}")

_ensure_tables()


async def _revisados_da_corrida_anterior(db, loja_id: int) -> dict:
    """{sku: qtd_shopee} das linhas ja' marcadas revisado=TRUE na corrida mais
    recente da loja. Base pra herdar o estado de revisao na proxima coleta
    (ver executar_coleta_loja)."""
    rows = await db.fetch(
        "SELECT sku, qtd_shopee FROM shopee_estoque_snapshot "
        "WHERE loja_id=$1 AND revisado=TRUE AND data_coleta=("
        "  SELECT MAX(data_coleta) FROM shopee_estoque_snapshot WHERE loja_id=$1)",
        loja_id)
    return {r["sku"]: float(r["qtd_shopee"] or 0) for r in rows}


def executar_coleta_loja(loja_id: int) -> dict:
    """Chama sync_all_items(loja_id) e grava um snapshot por sku com o
    saldo Shopee bruto. Item com sku == str(item_id) (fallback da propria
    Shopee quando nao ha' item_sku real) ainda e' gravado — o pareamento
    com o saldo Athena na leitura (listar_divergencias) e' quem trata a
    ausencia de produto correspondente, nao a coleta.

    HERDA revisado=TRUE da corrida anterior quando o sku ja' estava revisado
    E a qtd_shopee nao mudou: cada corrida insere linhas novas (data_coleta
    faz parte da UNIQUE), entao sem isso o flag caia no DEFAULT FALSE e toda
    divergencia marcada como revisada reaparecia como nova a cada <=30min,
    esvaziando o unico diferencial do lado Shopee. Se a quantidade mudou, a
    divergencia e' OUTRA e volta a ser nao-revisada — isso e' intencional."""
    inicio_corrida = datetime.now()
    try:
        itens = sync_all_items(loja_id)
    except Exception as e:
        log(AGENT, f"Erro ao sincronizar itens da loja {loja_id}: {e}")
        return {"erro": str(e)}
    async def _go():
        db = await get_db()
        try:
            revisados = await _revisados_da_corrida_anterior(db, loja_id)
        except Exception as e:
            # Degradacao aceitavel: sem o estado anterior a coleta continua e
            # tudo entra como nao-revisado. Perder o flag e' bem menos grave do
            # que perder a coleta inteira do saldo.
            log(AGENT, f"Nao foi possivel herdar 'revisado' da coleta anterior da loja {loja_id}: {e}")
            revisados = {}
        gravados, erros = 0, 0
        for item in itens:
            try:
                qtd = float(item.get("stock", 0) or 0)
                herda_revisado = revisados.get(item["sku"]) == qtd
                await db.fetchrow("""
                    INSERT INTO shopee_estoque_snapshot (sku, loja_id, item_id_shopee, qtd_shopee, data_coleta, revisado)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (sku, loja_id, data_coleta) DO UPDATE SET qtd_shopee = $4, revisado = $6
                    RETURNING id
                """, item["sku"], loja_id, str(item["item_id"]), qtd, inicio_corrida, herda_revisado)
                gravados += 1
            except Exception:
                erros += 1
        return gravados, erros
    try:
        gravados, erros = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao gravar snapshot da loja {loja_id}: {e}")
        return {"erro": str(e)}
    resultado = {"ok": True, "loja_id": loja_id, "itens": len(itens), "gravados": gravados,
                 "erros": erros, "data_coleta": inicio_corrida}
    if erros:
        # Sem isso o contador de falhas por item morria aqui: _coleta_em_background
        # descarta o retorno, e ninguem jamais via que N itens nao entraram.
        resultado["erro"] = f"{erros} de {len(itens)} itens falharam ao gravar no snapshot"
    return resultado


def snapshot_mais_recente(loja_id: int):
    """(data_coleta, itens) da corrida mais recente da loja. (None, []) se
    essa loja nunca foi coletada. Identico em forma a
    core.i9logic.snapshot_mais_recente."""
    async def _go():
        db = await get_db()
        data_coleta = await db.fetchval(
            "SELECT MAX(data_coleta) FROM shopee_estoque_snapshot WHERE loja_id=$1", loja_id)
        if data_coleta is None:
            return None, []
        rows = await db.fetch(
            "SELECT id, sku, item_id_shopee, qtd_shopee, revisado FROM shopee_estoque_snapshot "
            "WHERE loja_id=$1 AND data_coleta=$2", loja_id, data_coleta)
        return data_coleta, [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception:
        return None, []


def _registrar_falha(loja_id: int, mensagem: str):
    """Guarda a mensagem (pra tela ver) e o instante (pra o cooldown). Sob o
    lock, junto do resto do estado de coleta."""
    with _coleta_lock:
        _coleta_erro_recente[loja_id] = mensagem
        _ultima_falha[loja_id] = datetime.now()
    log(AGENT, f"Falha na coleta da loja {loja_id}: {mensagem}")


def _coleta_em_background(loja_id: int):
    """Roda a coleta completa fora do request. Sempre libera o lock ao
    final, mesmo em erro — senao a loja fica presa em 'processando'.

    executar_coleta_loja CAPTURA suas proprias excecoes e devolve {"erro":...}
    em vez de propagar, entao checar so' o `except` daqui nunca detectava nada:
    o dicionario de erros ficava eternamente vazio e a tela nunca sabia que a
    coleta vinha falhando. Por isso o retorno e' inspecionado explicitamente."""
    try:
        resultado = executar_coleta_loja(loja_id) or {}
        if resultado.get("erro"):
            _registrar_falha(loja_id, str(resultado["erro"]))
        else:
            with _coleta_lock:
                _coleta_erro_recente.pop(loja_id, None)
                _ultima_falha.pop(loja_id, None)
    except Exception as e:
        _registrar_falha(loja_id, str(e))
    finally:
        with _coleta_lock:
            _coleta_em_andamento.discard(loja_id)


def disparar_coleta_se_necessario(loja_id: int, data_coleta) -> bool:
    """Dispara coleta em background se nao houver uma rodando e o snapshot
    estiver ausente ou mais velho que FRESCOR_MAXIMO_MINUTOS. Retorna True
    se a loja ficou (ou ja estava) em processamento. Mesma forma de
    core.i9logic._disparar_coleta_se_necessario, mais o cooldown pos-falha.

    Em cooldown devolve False de proposito (nao "processando"): a tela para
    de fazer polling e mostra o erro_ultima_coleta em vez de ficar girando pra
    sempre num banner de 'coletando...' que nunca termina."""
    precisa_coletar = data_coleta is None or (
        (datetime.now() - data_coleta).total_seconds() / 60 > FRESCOR_MAXIMO_MINUTOS)
    with _coleta_lock:
        ja_rodando = loja_id in _coleta_em_andamento
        ultima_falha = _ultima_falha.get(loja_id)
        em_cooldown = ultima_falha is not None and (
            (datetime.now() - ultima_falha).total_seconds() < COOLDOWN_APOS_FALHA_SEGUNDOS)
        deve_iniciar = precisa_coletar and not ja_rodando and not em_cooldown
        if deve_iniciar:
            _coleta_em_andamento.add(loja_id)
    if deve_iniciar:
        threading.Thread(target=_coleta_em_background, args=(loja_id,), daemon=True).start()
    return ja_rodando or deve_iniciar


def listar_divergencias(loja_id: int) -> dict:
    """Le o snapshot mais recente da loja (disparando coleta se
    necessario), resolve o nome da loja, e pra cada sku compara qtd_shopee
    contra core.estoque_saldos.saldos_em_lote() — mesmo formato de retorno de
    core.i9logic.listar_divergencias_athena, pra o frontend tratar os dois
    lados de forma simetrica."""
    from core.estoque_saldos import saldos_em_lote  # import local (nao no topo do modulo):
    # precisa resolver core.estoque_saldos em tempo de chamada, nao em tempo de
    # import do modulo, senao o patch("core.estoque_saldos.saldos_em_lote", ...)
    # usado nos testes (e no i9logic.py, mesmo padrao la') nao teria efeito aqui.
    loja = obter_loja(loja_id)
    nome_loja = loja["nome"] if loja else ""
    data_coleta, itens = snapshot_mais_recente(loja_id)
    processando = disparar_coleta_se_necessario(loja_id, data_coleta)
    # Uma query pros saldos de todos os skus, em vez de um saldo() por item
    # (ver core/estoque_saldos.py::saldos_em_lote pro porque de nao ser fail-open).
    try:
        saldos = saldos_em_lote([item["sku"] for item in itens], nome_loja, "disponivel")
    except Exception as e:
        return {"erro": f"falha ao ler os saldos do Athena para a loja '{nome_loja}': {e}"}
    divergencias = []
    for item in itens:
        qtd_shopee = float(item["qtd_shopee"] or 0)
        disponivel_athena = saldos.get(item["sku"], 0.0)
        divergencias.append({
            "id": item["id"],
            "sku": item["sku"],
            "qtd_shopee": qtd_shopee,
            "disponivel_athena": disponivel_athena,
            "divergencia": round(disponivel_athena - qtd_shopee, 3),
            "classificacao": classificar_divergencia(qtd_shopee, disponivel_athena),
            "revisado": item.get("revisado", False),
        })
    resultado = {
        "ok": True,
        "status": "processando" if processando else "pronto",
        "data_coleta": data_coleta.isoformat() if data_coleta else None,
        "data": divergencias,
    }
    # Mesmo campo que estoque_fisico_por_loja expoe (e que EstoqueFisicoI9Logic.tsx
    # ja' mostra): sem isso uma loja com token Shopee expirado ficava em silencio
    # total — lista vazia, nenhum aviso, e o usuario sem saber que a coleta falhou.
    erro_recente = _coleta_erro_recente.get(loja_id)
    if erro_recente:
        resultado["erro_ultima_coleta"] = erro_recente
    return resultado


def marcar_revisado(snapshot_id: int) -> dict:
    """Aceita a divergencia como conhecida — so' marca revisado, nunca
    ajusta saldo. Identico em forma a core.i9logic.marcar_revisado."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "UPDATE shopee_estoque_snapshot SET revisado=TRUE WHERE id=$1 RETURNING *", snapshot_id)
        return dict(row) if row else None
    try:
        r = run_async(_go())
        return {"ok": True, "snapshot": r} if r else {"erro": "snapshot nao encontrado"}
    except Exception as e:
        return {"erro": str(e)}


def _buscar_snapshot_raw(snapshot_id: int):
    """Nao engole excecao (ao contrario de _buscar_snapshot) — usada por
    loja_do_snapshot, que precisa distinguir 'snapshot nao existe' (None
    valido) de 'falha ao consultar' (excecao), pra a checagem de escopo por
    loja em routes/shopee.py::_negar_se_loja_fora_do_escopo nao virar
    fail-open so' porque o banco deu erro nessa query."""
    async def _go():
        db = await get_db()
        return await db.fetchrow(
            "SELECT sku, loja_id, qtd_shopee FROM shopee_estoque_snapshot WHERE id=$1", snapshot_id)
    row = run_async(_go())
    return dict(row) if row else None


def _buscar_snapshot(snapshot_id: int):
    try:
        return _buscar_snapshot_raw(snapshot_id)
    except Exception:
        return None


def loja_do_snapshot(snapshot_id: int):
    """loja_id dono de um snapshot. Propaga excecao de banco (fail-closed) —
    quem chama (routes/shopee.py::_negar_se_loja_fora_do_escopo) precisa
    negar por seguranca quando a consulta falha, nunca tratar erro de banco
    como 'snapshot inexistente, deixa passar'."""
    snap = _buscar_snapshot_raw(snapshot_id)
    return snap["loja_id"] if snap else None


def _snapshot_mais_recente_id(sku: str, loja_id: int):
    """Nao engole excecao (ao contrario de _buscar_snapshot): quem chama
    (aplicar_ajuste_divergencia) precisa distinguir 'nao ha snapshot mais
    recente' (None valido, ja que ORDER BY ... LIMIT 1 sem match retorna
    None do fetchval) de 'falha ao consultar' (excecao) — so' a segunda
    deve bloquear o ajuste por seguranca (fail-closed), a guarda de frescor
    nao pode virar fail-open so' porque o banco deu erro nessa query."""
    async def _go():
        db = await get_db()
        return await db.fetchval(
            "SELECT id FROM shopee_estoque_snapshot WHERE sku=$1 AND loja_id=$2 "
            "ORDER BY data_coleta DESC LIMIT 1", sku, loja_id)
    return run_async(_go())


def aplicar_ajuste_divergencia(snapshot_id: int, usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Le o snapshot (sku, qtd_shopee), resolve o nome da loja a partir de
    loja_id, chama core.estoque.ajustar_absoluto(sku, nome_loja, qtd_shopee,
    ...). Mesma guarda de frescor do i9Logic: so' aplica se for o snapshot
    mais recente pra aquele sku/loja."""
    snap = _buscar_snapshot(snapshot_id)
    if not snap:
        return {"erro": "snapshot nao encontrado"}
    try:
        id_mais_recente = _snapshot_mais_recente_id(snap["sku"], snap["loja_id"])
    except Exception as e:
        # Fail-closed (ver core/i9logic.py): erro na guarda de frescor bloqueia
        # o ajuste, nunca deixa passar — o contrario abriria brecha pra ajustar
        # com base num snapshot desatualizado sempre que o banco falhar.
        return {"erro": f"falha ao verificar frescor do snapshot: {e}"}
    if id_mais_recente is not None and id_mais_recente != snapshot_id:
        return {"erro": f"este snapshot (id={snapshot_id}) nao e' o mais recente pra este sku/loja "
                         f"(o mais recente e' id={id_mais_recente}) - ajuste a partir do mais recente"}
    loja = obter_loja(snap["loja_id"])
    nome_loja = loja["nome"] if loja else ""
    resultado = ajustar_absoluto(
        snap["sku"], nome_loja, float(snap["qtd_shopee"] or 0),
        motivo="ajuste_inventario", usuario_id=usuario_id, usuario_nome=usuario_nome)
    if resultado.get("erro"):
        return resultado
    marcado = marcar_revisado(snapshot_id)
    if marcado.get("erro"):
        return {"erro": f"ajuste aplicado mas falha ao marcar revisado: {marcado['erro']}", "ajuste": resultado}
    return {"ok": True, "ajuste": resultado, "snapshot": marcado.get("snapshot")}
