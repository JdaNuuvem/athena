"""Reconciliacao Fisico x Contabil — Ponte i9Logic -> Athena.

De-para de identidade, client HTTP paginado (respeitando rate limit), staging
table de snapshot, classificacao de divergencia, job de coleta e seed inicial.
Fisico (tipoestoque=1) semeia estoque_saldos (Fase 1); contabil (tipoestoque=2)
nunca vira bucket, so' serve como sinal de auditoria. Nenhum ajuste automatico
de saldo — toda decisao sobre divergencia e' manual."""
import os, time, requests
from datetime import datetime
from core import get_db, run_async, log
from core.config import get_config

AGENT = "I9Logic Reconciliacao"

BASE_URL = os.environ.get("I9LOGIC_BASE_URL") or get_config("i9logic", "base_url") or ""
RATE_LIMIT_SLEEP_SEGUNDOS = 2.5  # ~24 req/min, margem sob o limite de 30/min da API
PER_PAGE_PADRAO = 200

LIMIAR_ALERTA_ABSOLUTO = 5
LIMIAR_ALERTA_PERCENTUAL = 0.10
TOLERANCIA_ZERO = 0.5


def _api_key() -> str:
    return os.environ.get("I9LOGIC_API_KEY") or get_config("i9logic", "api_key") or ""


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

def _paginar_estoques(filial_id_i9logic: int, tipoestoque: int) -> list:
    """Pagina o catalogo inteiro da filial pro tipo de estoque pedido
    (1=fisico, 2=contabil), respeitando o rate limit de 30 req/min via sleep
    de RATE_LIMIT_SLEEP_SEGUNDOS entre chamadas (nao dorme apos a ultima
    pagina). Retorna todos os registros de todas as paginas, sem duplicar."""
    registros = []
    pagina = 1
    while True:
        resp = requests.get(
            f"{BASE_URL}/v1/produtos_estoques",
            params={"filial": filial_id_i9logic, "tipoestoque": tipoestoque,
                     "page": pagina, "per_page": PER_PAGE_PADRAO},
            headers={"Authorization": f"Bearer {_api_key()}"},
            timeout=30,
        )
        resp.raise_for_status()
        dados = resp.json()
        pagina_registros = dados.get("data", [])
        registros.extend(pagina_registros)
        total = dados.get("total", len(registros))
        if pagina * PER_PAGE_PADRAO >= total or not pagina_registros:
            break
        pagina += 1
        time.sleep(RATE_LIMIT_SLEEP_SEGUNDOS)
    return registros


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

def classificar_divergencia(qtd_fisico: float, qtd_comparacao: float) -> str:
    """qtd_comparacao e' o contabil (i9Logic isolado, modo seed/auditoria) ou o
    disponivel do Athena (modo monitoramento continuo) — a mesma regra de
    classificacao serve pros dois casos, so' muda o que se compara contra o
    fisico. Nunca ajusta nada sozinho, so' classifica pra fila de revisao."""
    divergencia = abs(float(qtd_comparacao) - float(qtd_fisico))
    if divergencia <= TOLERANCIA_ZERO:
        return "sem_acao"
    base = max(float(qtd_fisico), 1)
    if divergencia >= LIMIAR_ALERTA_ABSOLUTO or (divergencia / base) >= LIMIAR_ALERTA_PERCENTUAL:
        return "alerta"
    return "registrado"


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


def aplicar_ajuste_divergencia(snapshot_id: int, usuario_id: int = None, usuario_nome: str = "") -> dict:
    """Resolve o item como 'ajustar manualmente' (spec): aplica o fisico
    coletado como quantidade absoluta via core.estoque.ajustar_absoluto() —
    passa pelo ledger formal do Athena (Fase 1), motivo fixo 'ajuste_inventario'
    (nao da' pra colar o id do snapshot dentro do motivo — e' um enum validado
    contra MOTIVOS_ENTRADA/MOTIVOS_SAIDA, nao texto livre). Rastreabilidade fica
    por correlacao de tempo entre estoque_movimentacoes e este snapshot, mais o
    proprio snapshot_id que o chamador ja tinha na mao pra disparar isto.
    So' marca revisado=TRUE se o ajuste realmente aplicar sem erro."""
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
    from core.estoque import ajustar_absoluto
    resultado = ajustar_absoluto(
        snap["sku_athena"], snap["loja_athena"], float(snap["qtd_fisico"] or 0),
        motivo="ajuste_inventario", usuario_id=usuario_id, usuario_nome=usuario_nome)
    if resultado.get("erro"):
        return resultado
    marcado = marcar_revisado(snapshot_id)
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
