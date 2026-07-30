"""Sync de vendas do PDV — i9Logic -> Athena (lojas fisicas).

_buscar_dados_pedido busca e monta um pedido completo (cabecalho + itens +
pagamentos) SEM gravar nada no banco — a gravacao so' acontece se as 3
chamadas de API tiverem sucesso (ver sincronizar_pedidos_i9logic, Task 5),
pra nunca deixar um pedido meio gravado (cabecalho sem itens) que a janela
rolante nao conseguiria mais detectar como pendente. Verifica o de-para de
filial ANTES de buscar itens/pagamentos - pedido de filial nao mapeada nao
gasta chamada nenhuma com isso, economiza rate limit."""
from datetime import datetime, timedelta
from core import get_db, run_async, log
from core.i9logic import _paginar, buscar_codigo_athena, BASE_URL

AGENT = "I9Logic Vendas"

JANELA_ROLANTE_DIAS = 1
MAX_PEDIDOS_NOVOS_POR_CICLO = 100


def _buscar_dados_pedido(pedido_id_i9logic: int) -> dict:
    """Busca e monta um pedido i9Logic (cabecalho + itens + pagamentos).

    Retorna um dict com:
    - pedido: dict com dados do cabecalho do pedido
    - loja_athena: codigo da loja no Athena (de-para de filial)
    - itens: lista de produtos do pedido
    - pagamentos: lista de pagamentos do pedido

    Retorna None se a filial do pedido nao tiver de-para mapeado (economiza
    rate limit ao nao chamar endpoints de itens/pagamentos).

    Levanta RuntimeError se o pedido nao for encontrado na API i9Logic.
    """
    pedidos = _paginar("pedidos", {"id": pedido_id_i9logic})
    if not pedidos:
        raise RuntimeError(f"pedido {pedido_id_i9logic} nao encontrado na API i9Logic")
    pedido = pedidos[0]
    loja_athena = buscar_codigo_athena("filial", pedido.get("filial_venda"))
    if not loja_athena:
        return None
    itens = _paginar("pedidos_produtos", {"idpedido": pedido_id_i9logic})
    pagamentos = _paginar("pedidos_pagamentos", {"pedido": pedido_id_i9logic})
    return {"pedido": pedido, "loja_athena": loja_athena, "itens": itens, "pagamentos": pagamentos}


def _janela_padrao() -> tuple:
    agora = datetime.now()
    inicio = agora - timedelta(days=JANELA_ROLANTE_DIAS)
    return inicio.strftime("%Y-%m-%d"), agora.strftime("%Y-%m-%d")


def _ja_sincronizados(ids_i9logic: list) -> set:
    async def _go():
        db = await get_db()
        rows = await db.fetch(
            "SELECT id_i9logic FROM vendas_pedidos WHERE id_i9logic = ANY($1::bigint[])", ids_i9logic)
        return {r["id_i9logic"] for r in rows}
    try:
        return run_async(_go())
    except Exception:
        return set()


def _gravar_pedido(dados: dict) -> dict:
    """Grava pedido+itens+pagamentos numa UNICA conexao/transacao (nunca
    db.execute/db.fetchval direto na pool - asyncpg.Pool nao tem .transaction(),
    so' asyncpg.Connection tem, obtida via db.acquire()). Tudo-ou-nada: se
    qualquer INSERT falhar no meio, nada deste pedido fica gravado, e ele
    continua elegivel pra retry no proximo ciclo (a janela rolante so' pula
    pedido cujo id_i9logic ja existe em vendas_pedidos - uma gravacao parcial
    quebraria essa premissa)."""
    pedido = dados["pedido"]
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
                    """, str(pedido["id"]), status, pedido.get("valor_total", 0), pedido.get("data"),
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
    ja_sincronizados = _ja_sincronizados(ids_i9logic)
    novos = [pid for pid in ids_i9logic if pid not in ja_sincronizados]
    truncado = len(novos) > MAX_PEDIDOS_NOVOS_POR_CICLO
    if truncado:
        log(AGENT, f"MAX_PEDIDOS_NOVOS_POR_CICLO ({MAX_PEDIDOS_NOVOS_POR_CICLO}) atingido - resto entra no proximo ciclo")
        novos = novos[:MAX_PEDIDOS_NOVOS_POR_CICLO]
    sincronizados, pulados, erros = 0, 0, []
    for pid in novos:
        try:
            dados = _buscar_dados_pedido(pid)
        except Exception as e:
            erros.append({"pedido": pid, "erro": str(e)})
            continue
        if dados is None:
            pulados += 1
            continue
        r = _gravar_pedido(dados)
        if r.get("erro"):
            erros.append({"pedido": pid, "erro": r["erro"]})
        else:
            sincronizados += 1
    return {"ok": True, "pedidos_na_janela": len(pedidos), "sincronizados": sincronizados,
            "pulados_filial_nao_mapeada": pulados, "erros": erros, "truncado": truncado}
