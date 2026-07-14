"""
AG-06: Vendedor do Telegram
Identifica se o cliente é atacado ou varejo, recomenda produtos,
faz upsell, calcula descontos, gera pedido, acompanha pagamento.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje
from .nlp import classificar_intencao, gerar_resposta_por_intencao, extrair_produtos_da_mensagem

AGENT = "AG-06 | Vendedor do Telegram"

def classificar_cliente(user_id: str, nome: str = "") -> dict:
    """Classifica cliente como atacado/varejo e novo/recorrente."""
    async def _go():
        db = await get_db()
        r = await db.fetchrow("""
            SELECT total_pedidos, total_gasto, ticket_medio, ultimo_pedido
            FROM clientes_telegram WHERE user_id = $1
        """, user_id)
        if not r:
            return {"tipo": "varejo", "historico": "novo", "nome": nome or "Cliente"}
        return {
            "tipo": "atacado" if float(r["ticket_medio"]) > 300 else "varejo",
            "historico": "recorrente",
            "total_pedidos": r["total_pedidos"],
            "ticket_medio": float(r["ticket_medio"]),
            "ultimo_pedido": str(r["ultimo_pedido"]),
            "nome": nome,
        }
    return run_async(_go())

def recomendar_produtos(cliente: dict, categoria: str = "") -> list:
    """Recomenda produtos baseado no perfil do cliente."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT p.*, m.margem_pct FROM produtos p
            LEFT JOIN margens_diarias m ON m.sku = p.sku AND m.data = CURRENT_DATE
            WHERE p.ativo = true
            ORDER BY m.margem_pct DESC NULLS LAST LIMIT 10
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

def calcular_desconto(tipo_cliente: str, valor_total: float, qtd_itens: int) -> dict:
    """Calcula desconto progressivo."""
    desconto = 0
    if tipo_cliente == "atacado":
        if valor_total > 1000: desconto = 15
        elif valor_total > 500: desconto = 10
        elif valor_total > 200: desconto = 5
    else:
        if qtd_itens >= 5: desconto = 5
        elif qtd_itens >= 3: desconto = 3

    valor_desconto = round(valor_total * desconto / 100, 2)
    return {
        "tipo_cliente": tipo_cliente,
        "valor_original": round(valor_total, 2),
        "desconto_pct": desconto,
        "valor_desconto": valor_desconto,
        "valor_final": round(valor_total - valor_desconto, 2),
    }

def sugerir_upsell(sku_atual: str) -> list:
    """Sugere produtos complementares (cross-sell/upsell)."""
    return [
        {"sku": "EMB001", "nome": "Embalagem Premium", "preco": 5.90, "motivo": "Apresentação profissional"},
        {"sku": "KIT002", "nome": "Kit de Reposição", "preco": 19.90, "motivo": "Compra recorrente"},
        {"sku": "BRINDE01", "nome": "Amostra Grátis Novo Produto", "preco": 0.00, "motivo": "Fidelização"},
    ]

def gerar_pedido(user_id: str, itens: list, pagamento: str = "pix") -> dict:
    """Gera pedido no sistema."""
    total = sum(i.get("preco", 0) * i.get("qtd", 1) for i in itens)
    cliente = classificar_cliente(user_id)
    desconto = calcular_desconto(cliente["tipo"], total, len(itens))

    return {
        "pedido_id": f"TG-{hoje()}-{user_id[-6:]}",
        "cliente": cliente,
        "itens": itens,
        "desconto": desconto,
        "pagamento": pagamento,
        "status": "aguardando_pagamento",
        "data": hoje(),
    }

def acompanhar_pagamento(pedido_id: str) -> dict:
    """Simula acompanhamento de pagamento."""
    return {"pedido_id": pedido_id, "status": "confirmado", "data_confirmacao": hoje()}

def pos_venda(pedido_id: str) -> str:
    """Mensagem de pós-venda."""
    return (
        f"Obrigado pela compra #{pedido_id}! 🎉\n"
        "Seu pedido está sendo separado.\n"
        "Prazo de entrega: 3-5 dias úteis.\n"
        "⭐ Avalie sua experiência: /avaliar"
    )

def processar_mensagem(user_id: str, mensagem: str, nome: str = "") -> dict:
    """Pipeline completo: recebe msg do Telegram, retorna resposta."""
    log(AGENT, f"Processando msg de {user_id}...")
    
    # Classificar ou criar cliente
    cliente = classificar_cliente(user_id, nome)
    
    # Classificar intenção
    intencao = classificar_intencao(mensagem)
    
    # Gerar resposta
    resposta = gerar_resposta_por_intencao(intencao, cliente)
    
    # Extrair produtos mencionados
    produtos_mencionados = extrair_produtos_da_mensagem(mensagem)
    
    # Recomendar produtos
    produtos_sugeridos = recomendar_produtos(cliente)
    
    # Atualizar sessão
    async def _update_session():
        db = await get_db()
        await db.execute("""
            INSERT INTO sessoes_telegram (user_id, estado, contexto)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE
            SET estado = $2, contexto = $3, ultima_mensagem = NOW()
        """, user_id, intencao, json.dumps({
            "ultima_mensagem": mensagem,
            "produtos_mencionados": produtos_mencionados
        }))
    try:
        run_async(_update_session())
    except Exception as e:
        log(AGENT, f"⚠️ Erro ao atualizar sessão: {e}")
    
    return {
        "user_id": user_id,
        "cliente": cliente,
        "intencao": intencao,
        "resposta": resposta,
        "produtos_sugeridos": produtos_sugeridos[:3],
        "produtos_mencionados": produtos_mencionados,
        "acao": "aguardando_resposta" if intencao == "geral" else f"processando_{intencao}",
    }

def salvar_pedido_telegram(user_id: str, itens: list, pagamento: str = "pix") -> dict:
    """Salva pedido no banco de dados."""
    total = sum(i.get("preco", 0) * i.get("qtd", 1) for i in itens)
    cliente = classificar_cliente(user_id)
    desconto = calcular_desconto(cliente["tipo"], total, len(itens))
    
    pedido_id = f"TG-{hoje()}-{user_id[-6:]}"
    
    async def _save():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO pedidos_telegram (pedido_id, user_id, itens, desconto_pct, valor_total, pagamento)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """, pedido_id, user_id, json.dumps(itens), desconto["desconto_pct"], desconto["valor_final"], pagamento)
        
        # Atualizar cliente
        await db.execute("""
            INSERT INTO clientes_telegram (user_id, nome, tipo, total_pedidos, total_gasto, ticket_medio)
            VALUES ($1, $2, $3, 1, $4, $4)
            ON CONFLICT (user_id) DO UPDATE
            SET total_pedidos = clientes_telegram.total_pedidos + 1,
                total_gasto = clientes_telegram.total_gasto + $4,
                ticket_medio = (clientes_telegram.total_gasto + $4) / (clientes_telegram.total_pedidos + 1),
                ultimo_pedido = NOW()
        """, user_id, cliente.get('nome', 'Cliente'), cliente['tipo'], desconto["valor_final"])
        
        return dict(row)
    
    return run_async(_save())

def obter_estatisticas_telegram() -> dict:
    """Obtém estatísticas do bot Telegram."""
    async def _go():
        db = await get_db()
        
        total_clientes = await db.fetchval("SELECT COUNT(*) FROM clientes_telegram")
        total_pedidos = await db.fetchval("SELECT COUNT(*) FROM pedidos_telegram")
        faturamento_total = await db.fetchval("SELECT COALESCE(SUM(valor_total), 0) FROM pedidos_telegram")
        ticket_medio_geral = await db.fetchval("""
            SELECT COALESCE(AVG(ticket_medio), 0) FROM clientes_telegram WHERE total_pedidos > 0
        """)
        
        pedidos_por_status = await db.fetch("""
            SELECT status, COUNT(*) as quantidade
            FROM pedidos_telegram
            GROUP BY status
        """)
        
        return {
            "total_clientes": total_clientes,
            "total_pedidos": total_pedidos,
            "faturamento_total": float(faturamento_total) if faturamento_total else 0,
            "ticket_medio_geral": float(ticket_medio_geral) if ticket_medio_geral else 0,
            "pedidos_por_status": {r['status']: r['quantidade'] for r in pedidos_por_status},
            "data": hoje(),
        }
    return run_async(_go())

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    print("Cliente:", classificar_cliente("usr_123"))
    print("Desconto:", calcular_desconto("atacado", 1200, 10))
    print("Pedido:", gerar_pedido("usr_123", [{"sku": "ORG001", "preco": 29.90, "qtd": 5}]))
    print("Pós-venda:", pos_venda("TG-123"))
