"""
Integração Bling ERP - AG-?? (Financeiro)
API simples para sincronizar com ERP Bling brasileiro.
Ponytail: integração mínima, endpoints genéricos para pedido, estoque, financeiro.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from core import log, run_async, get_db
from core.config import get_config, set_config

AGENT = "AG-?? | Integração Bling ERP"

def get_api_key() -> str:
    """Obtém API key do Bling do sistema de configuração."""
    return get_config("bling", "api_key")

def get_api_url() -> str:
    """Obtém URL da API do Bling."""
    return get_config("bling", "api_url") or "https://bling.com.br/Api/v3"

def _bling_request(endpoint: str, params: dict = None, method: str = "GET") -> dict:
    """Request para API Bling."""
    api_key = get_api_key()
    if not api_key:
        return {"error": "API key não configurada"}
    
    url = f"{get_api_url()}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, params=params, timeout=30)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=params, timeout=30)
        else:
            r = requests.request(method, url, headers=headers, json=params, timeout=30)
        
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(AGENT, f"Erro Bling: {e}")
        return {"error": str(e)}

def enviar_pedido_bling(pedido: dict) -> dict:
    """Envia pedido para Bling."""
    # Converte pedido Hermes para formato Bling
    bling_pedido = {
        "numero": pedido.get("pedido_id"),
        "data": pedido.get("data"),
        "cliente": pedido.get("cliente", {}).get("nome", ""),
        "valor": pedido.get("desconto", {}).get("valor_final", 0),
        "situacao": "Aberto",
        "vendedor": "Telegram Bot",
        "observacoes": "Pedido via Telegram Bot AG-06"
    }
    
    # Adiciona itens
    bling_pedido["itens"] = []
    for item in pedido.get("itens", []):
        bling_pedido["itens"].append({
            "codigo": item.get("sku", ""),
            "descricao": item.get("produto", ""),
            "quantidade": item.get("qtd", 1),
            "valorun": item.get("preco", 0)
        })
    
    # Envia para Bling
    resultado = _bling_request("pedidos", bling_pedido, "POST")
    return resultado

def sincronizar_estoque_bling(sku: str, quantidade: int) -> dict:
    """Sincroniza estoque com Bling."""
    async def _go():
        db = await get_db()
        
        # Obter dados do produto
        produto = await db.fetchrow("SELECT * FROM produtos WHERE sku = $1", sku)
        if not produto:
            return {"error": "Produto não encontrado"}
        
        # Prepara dados para Bling
        bling_estoque = {
            "codigo": sku,
            "descricao": produto["descricao"],
            "quantidade": quantidade,
            "estoque_minimo": 10
        }
        
        # Envia para Bling
        return _bling_request("produtos", bling_estoque, "POST")
    return run_async(_go())

def obter_financeiro_bling(dias: int = 30) -> dict:
    """Obtém dados financeiros do Bling."""
    return _bling_request("financeiro", {"tipo": "receitas", "dias": dias}, "GET")

def webhook_bling_pedido(pedido_bling: dict) -> dict:
    """Processa webhook de pedido do Bling."""
    # Sincroniza pedido Bling → Hermes
    sku = pedido_bling.get("codigo", "")
    quantidade = pedido_bling.get("quantidade", 0)
    
    # Adiciona ao planejamento de produção
    from ag_04_planejador import adicionar_pedido_producao
    from datetime import date, timedelta
    
    if sku and quantidade:
        adicionar_pedido_producao(
            sku=sku,
            quantidade=quantidade,
            prazo=date.today() + timedelta(days=5),
            prioridade=7,  # Prioridade alta (pedido ERP)
            cliente_id=pedido_bling.get("cliente_id")
        )
        log(AGENT, f"Pedido ERP sincronizado: {sku} x{quantidade}")
        return {"success": True, "sku": sku, "quantidade": quantidade}
    
    return {"error": "Dados inválidos"}

# Mensagens pré-definidas para o Telegram bot falar sobre Bling
MENSAGENS_BLING = {
    "pedidos": f"📦 Pedidos sincronizados via Bling ERP. Veja mais em {get_api_url()}",
    "estoque": "📊 Estoque sincronizado com Bling em tempo real.",
    "financeiro": f"💰 Financeiro integrado com Bling. Acesse: {get_api_url()}"
}