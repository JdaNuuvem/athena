"""Fulfillment Shopee -> Bling — ponte entre um pedido Shopee sincronizado
(shopee_pedidos_sincronizados) e o pedido/nota fiscal correspondente no
Bling. A etiqueta de envio e o despacho em si (create_shipping_document/
mass_ship_order) sao 100% Shopee e ja existem prontos em shopee/logistics.py
+ rotas dedicadas — este modulo cobre so' o que faltava: vincular ao pedido
Bling (a integracao nativa Shopee<->Bling ja cria o pedido la', so' falta
achar/gravar o id), emitir a NF-e, baixar o PDF, e persistir que o despacho
aconteceu (a chamada real de despacho continua vindo das rotas de logistica
Shopee ja existentes; marcar_despachado so' registra o resultado aqui)."""
from core import log
from shopee import get_shopee_config
from shopee_sync import obter_pedido_sincronizado, atualizar_vinculo_pedido
from bling_erp import emitir_nfe, get_nfe_pdf_bytes, buscar_pedido_por_numero_loja
from core.fiscal import sincronizar_uma_nota_fiscal

AGENT = "Shopee Fulfillment"


def _shop_id(loja_id: int):
    return get_shopee_config(loja_id).get("shop_id") or ""


def status_fulfillment(order_sn: str, loja_id: int) -> dict:
    """Estado atual do fulfillment de um pedido — usado pela UI pra saber
    quais botoes mostrar (vincular, emitir nota, despachar)."""
    shop_id = _shop_id(loja_id)
    if not shop_id:
        return {"erro": "loja sem shop_id Shopee configurado"}
    pedido = obter_pedido_sincronizado(order_sn, shop_id)
    if not pedido:
        return {"erro": "pedido nao encontrado — sincronize antes de consultar o fulfillment"}
    return {
        "order_sn": order_sn,
        "vinculado_bling": bool(pedido.get("bling_pedido_id")),
        "bling_pedido_id": pedido.get("bling_pedido_id"),
        "nota_emitida": bool(pedido.get("bling_nota_fiscal_id")),
        "bling_nota_fiscal_id": pedido.get("bling_nota_fiscal_id"),
        "despachado": bool(pedido.get("despachado_em")),
        "despachado_em": pedido.get("despachado_em"),
        "package_number": pedido.get("package_number"),
    }


def vincular_pedido_bling(order_sn: str, loja_id: int, id_pedido_bling: int = None) -> dict:
    """Vincula o pedido Shopee ao pedido Bling correspondente. Sem
    id_pedido_bling explicito, tenta achar automaticamente pelo numero do
    pedido no canal (numeroLoja) — se nao achar, pede vinculo manual (a
    busca automatica depende de um nome de campo nao confirmado ao vivo,
    ver bling_erp.buscar_pedido_por_numero_loja)."""
    shop_id = _shop_id(loja_id)
    if not shop_id:
        return {"erro": "loja sem shop_id Shopee configurado"}
    if id_pedido_bling is None:
        pedido_bling = buscar_pedido_por_numero_loja(order_sn)
        if not pedido_bling:
            return {"erro": "pedido nao encontrado automaticamente no Bling — "
                             "informe id_pedido_bling manualmente (busque pelo numero/cliente no Bling)"}
        id_pedido_bling = pedido_bling.get("id")
    return atualizar_vinculo_pedido(order_sn, shop_id, bling_pedido_id=int(id_pedido_bling))


def emitir_nota_fiscal(order_sn: str, loja_id: int) -> dict:
    """Emite a NF-e no Bling para o pedido ja vinculado. Idempotente: recusa
    se ja houver nota emitida (evita duplicar nota fiscal por duplo clique)."""
    shop_id = _shop_id(loja_id)
    if not shop_id:
        return {"erro": "loja sem shop_id Shopee configurado"}
    pedido = obter_pedido_sincronizado(order_sn, shop_id)
    if not pedido:
        return {"erro": "pedido nao encontrado"}
    if not pedido.get("bling_pedido_id"):
        return {"erro": "pedido ainda nao vinculado a um pedido Bling — vincule antes de emitir a nota"}
    if pedido.get("bling_nota_fiscal_id"):
        return {"erro": "nota fiscal ja emitida para este pedido",
                "bling_nota_fiscal_id": pedido["bling_nota_fiscal_id"]}
    resultado = emitir_nfe(int(pedido["bling_pedido_id"]))
    if resultado.get("error"):
        return {"erro": resultado["error"]}
    data = resultado.get("data") or {}
    nota_id = data.get("id") or (data.get("notaFiscal") or {}).get("id")
    if not nota_id:
        log(AGENT, f"emitir_nota_fiscal: resposta sem id reconhecivel para pedido {pedido['bling_pedido_id']}: {data}")
        return {"erro": "nota emitida no Bling, mas nao foi possivel identificar o id retornado — "
                        "confira manualmente no painel do Bling e vincule com o id correto",
                "resposta_bruta": data}
    atualizar_vinculo_pedido(order_sn, shop_id, bling_nota_fiscal_id=int(nota_id))
    try:
        sincronizar_uma_nota_fiscal(int(nota_id))
    except Exception as e:
        log(AGENT, f"emitir_nota_fiscal: nota {nota_id} emitida mas falhou sync local: {e}")
    return {"ok": True, "bling_nota_fiscal_id": int(nota_id)}


def baixar_nota_pdf(order_sn: str, loja_id: int):
    """(conteudo_pdf, content_type) do DANFE da nota vinculada, ou (None, None)
    se ainda nao houver nota emitida."""
    shop_id = _shop_id(loja_id)
    if not shop_id:
        return None, None
    pedido = obter_pedido_sincronizado(order_sn, shop_id)
    if not pedido or not pedido.get("bling_nota_fiscal_id"):
        return None, None
    return get_nfe_pdf_bytes(int(pedido["bling_nota_fiscal_id"]))


def marcar_despachado(order_sn: str, loja_id: int, package_number: str = None) -> dict:
    """Registra que o despacho aconteceu — chamar SO' depois que
    /api/shopee/logistica/despachar (mass_ship_order) confirmar sucesso.
    Este modulo nao dispara o despacho real, so' persiste o resultado."""
    from datetime import datetime
    shop_id = _shop_id(loja_id)
    if not shop_id:
        return {"erro": "loja sem shop_id Shopee configurado"}
    campos = {"despachado_em": datetime.now()}
    if package_number:
        campos["package_number"] = package_number
    return atualizar_vinculo_pedido(order_sn, shop_id, **campos)
