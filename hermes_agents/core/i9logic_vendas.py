"""Sync de vendas do PDV — i9Logic -> Athena (lojas fisicas).

_buscar_dados_pedido busca e monta um pedido completo (cabecalho + itens +
pagamentos) SEM gravar nada no banco — a gravacao so' acontece se as 3
chamadas de API tiverem sucesso (ver sincronizar_pedidos_i9logic, Task 5),
pra nunca deixar um pedido meio gravado (cabecalho sem itens) que a janela
rolante nao conseguiria mais detectar como pendente. Verifica o de-para de
filial ANTES de buscar itens/pagamentos - pedido de filial nao mapeada nao
gasta chamada nenhuma com isso, economiza rate limit."""
from core.i9logic import _paginar, buscar_codigo_athena


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
