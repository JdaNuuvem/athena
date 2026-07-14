# Integração Bling ERP - API v3 Oficial

## Documentação
- Referência: https://developer.bling.com.br/referencia
- API Base: https://api.bling.com.br/Api/v3

## Autenticação
- Método: Bearer Token
- Header: `Authorization: Bearer <API_KEY>`

## Endpoints Implementados

### Contatos (Clientes/Fornecedores)
- `GET /contatos` - Lista contatos (paginado)
- `GET /contatos/{id}` - Obtem contato específico
- `POST /contatos` - Cria novo contato

### Produtos
- `GET /produtos` - Lista produtos
- `GET /produtos/{id}` - Obtém produto específico
- `POST /produtos` - Cria novo produto
- `PUT /produtos/{id}/estoques` - Atualiza estoque

### Pedidos
- `POST /pedidos/vendas` - Cria pedido de venda

### Financeiro
- `GET /contas/pagar` - Lista contas a pagar
- `GET /contas/receber` - Lista contas a receber
- `POST /contas/receber` - Cria conta a receber

## Fluxo de Integração

### 1. Configuração
```python
from core.config import set_config
set_config("bling", "api_key", "seu-token-aqui")
```

### 2. Enviar Pedido do Telegram para Bling
```python
from bling_erp import enviar_pedido_bling

pedido = {
    "data": "2026-07-07",
    "cliente": {
        "nome": "João Silva",
        "telefone": "11999999999",
        "email": "joao@email.com"
    },
    "itens": [
        {"sku": "PROD01", "qtd": 2, "preco": 50.00}
    ]
}

resultado = enviar_pedido_bling(pedido)
```

### 3. Sincronizar Estoque
```python
from bling_erp import atualizar_estoque
resultado = atualizar_estoque("PROD01", 100)
```

### 4. Webhook - Pedido do Bling → Hermes
```python
from bling_erp import webhook_bling_pedido
resultado = webhook_bling_pedido(pedido_bling)
```

## Webhooks Coolify
- `POST /webhook/bling/pedido` - Recebe pedidos do Bling
- Configurar no painel do Bling: https://app.bling.com.br/webhooks

## Configuração via Frontend
- Acessar: https://177.7.45.242:5173
- Preencher API Key do Bling
- Salvar configurações

## Erros Comuns

### 401 Unauthorized
- API Key inválida ou expirada
- Verifique a chave no painel do Bling

### 404 Not Found
- Produto não encontrado no Bling
- Contato não encontrado
- Verifique se os códigos (SKU) existem

### 422 Unprocessable Entity
- Dados inválidos no payload
- Campos obrigatórios faltando
- Verifique a estrutura JSON

## Exemplo de Payload Completo

### Pedido de Venda
```json
{
  "cliente": {
    "id": 123456
  },
  "itens": [
    {
      "produto": {
        "codigo": "PROD01"
      },
      "quantidade": 2,
      "valor": 50.00
    }
  ],
  "situacao": "Aberto",
  "data": "2026-07-07",
  "vendedor": "Telegram Bot"
}
```

### Atualização de Estoque
```json
{
  "estoque": {
    "depositos": [
      {
        "id": "default",
        "quantidade": 100
      }
    ]
  }
}
```

## Limitações

- API Bling v3 tem rate limiting (aprox. 1000 req/hora)
- Paginação em todos os endpoints de listagem
- Validar campos obrigatórios antes de enviar

## Próximas Melhorias

- [ ] Tratamento de erros mais granular
- [ ] Cache de produtos para reduzir chamadas
- [ ] Retentativas automáticas em caso de falha
- [ ] Suporte a múltiplos depósitos de estoque