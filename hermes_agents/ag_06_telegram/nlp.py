"""
AG-06 NLP: Classificação de intenção e geração de respostas para Telegram.
"""
import re

def classificar_intencao(mensagem: str) -> str:
    """Classifica intenção do usuário."""
    mensagem = mensagem.lower()
    
    if any(p in mensagem for p in ['preço', 'quanto', 'valor', 'custa', '$', 'r$']):
        return 'preco'
    elif any(p in mensagem for p in ['quer', 'comprar', 'tem', 'gostaria', 'levar', 'pegar']):
        return 'compra'
    elif any(p in mensagem for p in ['atacado', 'revenda', 'venda', 'revendedor']):
        return 'atacado'
    elif any(p in mensagem for p in ['pedido', 'status', 'onde', 'chegou', 'entrega']):
        return 'status_pedido'
    elif any(p in mensagem for p in ['olá', 'oi', 'bom dia', 'boa tarde', 'boa noite', 'oi']):
        return 'saudacao'
    else:
        return 'geral'

def gerar_resposta_por_intencao(intencao: str, cliente: dict) -> str:
    """Gera resposta baseada na intenção."""
    if intencao == 'preco':
        return "Temos preços especiais de atacado a partir de R$200! Qual categoria você busca?"
    elif intencao == 'compra':
        tipo_msg = "Preços especiais de atacado" if cliente['tipo'] == 'atacado' else "Frete grátis a partir de R$99"
        return f"Ótimo! {tipo_msg}. Veja nossos produtos:"
    elif intencao == 'atacado':
        return "Para atacado, oferecemos descontos progressivos: 5% acima de R$200, 10% acima de R$500, 15% acima de R$1000"
    elif intencao == 'status_pedido':
        return "Por favor, forneça o número do seu pedido para verificar o status"
    elif intencao == 'saudacao':
        return f"Olá {cliente['nome']}! Como posso ajudar hoje?"
    else:
        return "Posso ajudar com produtos, preços, pedidos ou atacado. O que você precisa?"

def extrair_produtos_da_mensagem(mensagem: str) -> list:
    """Extrai possíveis produtos da mensagem."""
    palavras_chave = ['organizador', 'porta', 'pote', 'suporte', 'escorredor', 'capa', 'tempero', 'gaveta']
    encontrados = []
    
    mensagem_lower = mensagem.lower()
    for palavra in palavras_chave:
        if palavra in mensagem_lower:
            encontrados.append(palavra)
    
    return encontrados

def normalizar_texto(texto: str) -> str:
    """Normaliza texto para processamento."""
    texto = texto.lower().strip()
    texto = re.sub(r'[^\w\s]', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto