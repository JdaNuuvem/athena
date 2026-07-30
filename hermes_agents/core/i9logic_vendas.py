"""Sync de vendas do PDV — i9Logic -> Athena (lojas fisicas).

_buscar_dados_pedido monta um pedido completo (cabecalho + itens +
pagamentos) SEM gravar nada no banco — a gravacao so' acontece se as
chamadas de API tiverem sucesso (ver sincronizar_pedidos_i9logic, Task 5),
pra nunca deixar um pedido meio gravado (cabecalho sem itens) que a janela
rolante nao conseguiria mais detectar como pendente. O cabecalho e' passado
pelo chamador (ja obtido na busca em lote por data, Achado 5) - a funcao NAO
rebusca /pedidos?id=X, so' verifica o de-para de filial ANTES de buscar
itens/pagamentos - pedido de filial nao mapeada nao gasta chamada nenhuma
com isso, economiza rate limit."""
import time
from datetime import datetime, timedelta
from core import get_db, run_async, log
from core.i9logic import _paginar, buscar_codigo_athena, BASE_URL, RATE_LIMIT_SLEEP_SEGUNDOS

AGENT = "I9Logic Vendas"

JANELA_ROLANTE_DIAS = 1
# Dimensionado originalmente pro spec (janela rolante de 3h, ~104 pedidos
# medidos nessa janela - docs/superpowers/specs/2026-07-30-i9logic-catalogo-
# vendas-fisica-design.md). A janela implementada acabou sendo de 1 dia
# inteiro (JANELA_ROLANTE_DIAS acima), bem maior que as 3h do spec original -
# reavaliado pra esse cenario real: numa partida a fria, um backlog de
# ~1.660 pedidos (medido em 2 dias corridos) e' esvaziado a 100 novos/ciclo
# (ciclo de 10min, ver core/scheduler.py) em ~17 ciclos (~2h50min), o que e'
# aceitavel. So' deixa de ser um livelock permanente (backlog nunca esvazia)
# porque o Achado 2 corrigiu o silenciamento de excecao em
# _status_sincronizados - antes disso, uma falha na query fazia TODO pedido
# da janela parecer novo pra sempre, a cada ciclo. Valor mantido em 100.
MAX_PEDIDOS_NOVOS_POR_CICLO = 100


def _buscar_dados_pedido(pedido: dict) -> dict:
    """Monta um pedido i9Logic completo (cabecalho + itens + pagamentos).

    pedido: dict do cabecalho do pedido, ja obtido pelo chamador (busca em
    lote por data em sincronizar_pedidos_i9logic) - NAO rebusca /pedidos?id=X
    (evita uma chamada de API extra por pedido; numa partida a fria/backfill
    isso seria centenas de chamadas que a API ja tinha respondido no lote).

    Retorna um dict com:
    - pedido: o mesmo dict recebido
    - loja_athena: codigo da loja no Athena (de-para de filial)
    - itens: lista de produtos do pedido
    - pagamentos: lista de pagamentos do pedido

    Retorna None se a filial do pedido nao tiver de-para mapeado (economiza
    rate limit ao nao chamar endpoints de itens/pagamentos).
    """
    loja_athena = buscar_codigo_athena("filial", pedido.get("filial_venda"))
    if not loja_athena:
        return None
    itens = _paginar("pedidos_produtos", {"idpedido": pedido["id"]})
    pagamentos = _paginar("pedidos_pagamentos", {"pedido": pedido["id"]})
    return {"pedido": pedido, "loja_athena": loja_athena, "itens": itens, "pagamentos": pagamentos}


def _janela_padrao() -> tuple:
    agora = datetime.now()
    inicio = agora - timedelta(days=JANELA_ROLANTE_DIAS)
    return inicio.strftime("%Y-%m-%d"), agora.strftime("%Y-%m-%d")


def _status_sincronizados(ids_i9logic: list) -> dict:
    """Retorna {id_i9logic: status_atual} dos pedidos da janela que ja estao
    em vendas_pedidos - usado tanto pra saber quais sao novos quanto pra
    detectar mudanca de status (ex: cancelamento) sem gastar chamada de API
    extra, ja que o cabecalho da listagem em lote ja traz o campo cancelado."""
    async def _go():
        db = await get_db()
        rows = await db.fetch(
            "SELECT id_i9logic, status FROM vendas_pedidos WHERE id_i9logic = ANY($1::bigint[])", ids_i9logic)
        return {r["id_i9logic"]: r["status"] for r in rows}
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao checar pedidos ja sincronizados: {e}")
        return {}


def _atualizar_status_se_mudou(pedido: dict, status_atual: str) -> bool:
    """Compara o status esperado (derivado de pedido['cancelado']) contra o
    ja gravado; se mudou (ex: pedido cancelado depois do sync inicial),
    atualiza status+total sem tocar itens/pagamentos. Retorna True se
    atualizou algo."""
    status_esperado = "cancelado" if str(pedido.get("cancelado")) == "1" else "concluido"
    if status_esperado == status_atual:
        return False
    async def _go():
        db = await get_db()
        await db.execute(
            "UPDATE vendas_pedidos SET status=$1, total=$2, updated_at=NOW() WHERE id_i9logic=$3",
            status_esperado, pedido.get("valor_total", 0), pedido["id"])
    try:
        run_async(_go())
        return True
    except Exception as e:
        log(AGENT, f"Erro ao atualizar status do pedido {pedido['id']}: {e}")
        return False


def _gravar_pedido(dados: dict) -> dict:
    """Grava pedido+itens+pagamentos numa UNICA conexao/transacao (nunca
    db.execute/db.fetchval direto na pool - asyncpg.Pool nao tem .transaction(),
    so' asyncpg.Connection tem, obtida via db.acquire()). Tudo-ou-nada: se
    qualquer INSERT falhar no meio, nada deste pedido fica gravado, e ele
    continua elegivel pra retry no proximo ciclo (a janela rolante so' pula
    pedido cujo id_i9logic ja existe em vendas_pedidos - uma gravacao parcial
    quebraria essa premissa).

    pedido["data"] vem da API i9Logic como string "YYYY-MM-DD", mas a coluna
    vendas_pedidos.data e' DATE - asyncpg exige um datetime.date/datetime
    nativo pro bind, nao aceita str (nem com ::date no SQL: o cast e' um
    no-op quando a coluna ja e' DATE, o tipo do parametro e' resolvido pela
    coluna e o bind falha antes disso com DataError). Mesmo precedente ja
    usado em sincronizar_pedidos_shopee() (core/vendas.py), que converte
    create_time pra .date() antes de bindar."""
    pedido = dados["pedido"]
    data_pedido = None
    if pedido.get("data"):
        try:
            data_pedido = datetime.strptime(pedido["data"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            data_pedido = None
    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                loja_id = await conn.fetchval("SELECT id FROM lojas WHERE nome=$1", dados["loja_athena"])
                status = "cancelado" if str(pedido.get("cancelado")) == "1" else "concluido"
                existente = await conn.fetchval("SELECT id FROM vendas_pedidos WHERE id_i9logic=$1", pedido["id"])
                if existente:
                    await conn.execute(
                        "UPDATE vendas_pedidos SET status=$1, total=$2, updated_at=NOW() WHERE id_i9logic=$3",
                        status, pedido.get("valor_total", 0), pedido["id"])
                    pedido_id = existente
                    await conn.execute("DELETE FROM vendas_itens WHERE pedido_id=$1", pedido_id)
                    await conn.execute("DELETE FROM vendas_pagamentos WHERE pedido_id=$1", pedido_id)
                else:
                    pedido_id = await conn.fetchval("""
                        INSERT INTO vendas_pedidos (numero, status, total, data, origem, loja_id, id_i9logic)
                        VALUES ($1,$2,$3,$4,'i9logic_pdv',$5,$6) RETURNING id
                    """, str(pedido["id"]), status, pedido.get("valor_total", 0), data_pedido,
                        loja_id, pedido["id"])
                for item in dados["itens"]:
                    qtd = float(item.get("qtd", 0) or 0)
                    valor_unitario = float(item.get("valorvenda", 0) or 0)
                    await conn.execute("""
                        INSERT INTO vendas_itens (pedido_id, sku, descricao, quantidade, valor_unitario, valor_total)
                        VALUES ($1,$2,$3,$4,$5,$6)
                    """, pedido_id, item.get("codproduto", ""), item.get("descricao", ""),
                        qtd, valor_unitario, qtd * valor_unitario)
                for pagamento in dados["pagamentos"]:
                    await conn.execute("""
                        INSERT INTO vendas_pagamentos (pedido_id, forma, valor, autorizacao)
                        VALUES ($1,$2,$3,$4)
                    """, pedido_id, str(pagamento.get("formadepagamento", "")),
                        pagamento.get("valor", 0), pagamento.get("codautorizacao") or None)
        return {"ok": True, "pedido_id": pedido_id}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def sincronizar_pedidos_i9logic(data_de: str = None, data_ate: str = None) -> dict:
    """Ciclo de sync de vendas PDV. Sem data_de/data_ate, usa a janela rolante
    padrao (JANELA_ROLANTE_DIAS) - autocura sozinha: pedido que falhou num
    ciclo reaparece na janela do ciclo seguinte, sem checkpoint persistido.
    Com data_de/data_ate explicitos, serve de backfill manual (historico)."""
    if not BASE_URL:
        return {"erro": "I9LOGIC_BASE_URL nao configurado - configure antes de sincronizar"}
    if not data_de or not data_ate:
        data_de, data_ate = _janela_padrao()
    try:
        pedidos = _paginar("pedidos", {"data_de": data_de, "data_ate": data_ate})
    except Exception as e:
        return {"erro": f"falha ao listar pedidos: {e}"}
    ids_i9logic = [p["id"] for p in pedidos]
    status_sincronizados = _status_sincronizados(ids_i9logic)
    pedido_por_id = {p["id"]: p for p in pedidos}
    novos = [pid for pid in ids_i9logic if pid not in status_sincronizados]
    truncado = len(novos) > MAX_PEDIDOS_NOVOS_POR_CICLO
    if truncado:
        log(AGENT, f"MAX_PEDIDOS_NOVOS_POR_CICLO ({MAX_PEDIDOS_NOVOS_POR_CICLO}) atingido - resto entra no proximo ciclo")
        novos = novos[:MAX_PEDIDOS_NOVOS_POR_CICLO]
    total_novos = len(novos)
    sincronizados, pulados, atualizados, erros = 0, 0, 0, []
    for i, pid in enumerate(novos):
        erro_busca = None
        try:
            dados = _buscar_dados_pedido(pedido_por_id[pid])
        except Exception as e:
            dados = None
            erro_busca = str(e)
        if erro_busca:
            erros.append({"pedido": pid, "erro": erro_busca})
        elif dados is None:
            pulados += 1
        else:
            r = _gravar_pedido(dados)
            if r.get("erro"):
                erros.append({"pedido": pid, "erro": r["erro"]})
            else:
                sincronizados += 1
        # Rate limit: mesmo espirito do paginador (core/i9logic.py) - nunca
        # dorme depois do ultimo pedido do lote.
        if i < total_novos - 1:
            time.sleep(RATE_LIMIT_SLEEP_SEGUNDOS)
    for p in pedidos:
        if p["id"] in status_sincronizados:
            if _atualizar_status_se_mudou(p, status_sincronizados[p["id"]]):
                atualizados += 1
    return {"ok": True, "pedidos_na_janela": len(pedidos), "sincronizados": sincronizados,
            "pulados_filial_nao_mapeada": pulados, "atualizados": atualizados,
            "erros": erros, "truncado": truncado}
