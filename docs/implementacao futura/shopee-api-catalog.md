# Catálogo de APIs Shopee — Planejamento de Implementacao Futura

> Fonte: https://open.shopee.com/developer-guide (scraped 2026-07-16)
> Foco: Gestao de Estoque Multiloja
> Status atual: OAuth em andamento (partner_id=1237336, shop_id=227748635)

---

## 1. APIs por Categoria

### Product APIs (Module 87)

| API | Descricao | Prioridade |
|-----|-----------|-----------|
| `get_item_list` | Lista produtos da loja (paginado, com filtros) | ⭐⭐⭐ |
| `get_item_base_info` | Detalhes completos de um produto (descricao, peso, dimensoes, imagens, categoria) | ⭐⭐⭐ |
| `get_model_list` | Lista variacoes/modelos de um produto (SKU, preco, estoque por variacao) | ⭐⭐⭐ |
| `update_stock` | Atualiza estoque de um item/modelo | ⭐⭐⭐ |
| `update_price` | Atualiza preco de um item/modelo | ⭐⭐ |
| `search_item` | Busca produtos por nome/SKU | ⭐⭐ |
| `get_variations` | Lista todas as variacoes de um produto pai | ⭐⭐⭐ |
| `get_category` | Arvore de categorias da Shopee | ⭐ |
| `get_attribute_tree` | Atributos por categoria (cor, tamanho, etc) | ⭐ |
| `get_brand_list` | Lista de marcas cadastradas | ⭐ |
| `add_item` | Criar novo produto | ⭐ |
| `update_item` | Atualizar produto existente | ⭐ |
| `delete_item` | Remover produto | ⭐ |
| `init_tier_variation` | Inicializar variacoes (cor/tamanho) | ⭐⭐ |
| `update_tier_variation` | Atualizar variacoes | ⭐⭐ |
| `unlist_item` | Tirar produto do ar | ⭐ |
| `boost_item` | Impulsionar produto nos resultados de busca | ⭐ |

### Global Product APIs (Cross-Market)

| API | Descricao | Prioridade |
|-----|-----------|-----------|
| `get_global_item_list` | Lista produtos globais (disponiveis em todos os mercados) | ⭐⭐⭐ |
| `get_global_item_info` | Detalhes do produto global | ⭐⭐ |
| `add_global_item` | Criar produto global | ⭐ |
| `update_global_item` | Atualizar produto global | ⭐ |
| `update_price` | Atualizar preco global | ⭐⭐ |
| `update_stock` | Atualizar estoque global | ⭐⭐⭐ |
| `create_publish_task` | Publicar produto global em uma loja especifica | ⭐⭐⭐ |
| `get_publishable_shop` | Lista lojas onde o produto pode ser publicado | ⭐⭐⭐ |
| `get_published_list` | Lista produtos publicados em cada loja | ⭐⭐⭐ |

### Merchant APIs (Module 123)

| API | Descricao | Prioridade |
|-----|-----------|-----------|
| `get_merchant_info` | Informacoes do merchant (vendedor master) | ⭐⭐ |
| `get_shop_list_by_merchant` | **Lista TODAS as lojas vinculadas ao merchant** (Shopee, TikTok Shop, Kwai Shop, etc se conectadas) | ⭐⭐⭐ |

### Shop APIs (Module 94)

| API | Descricao | Prioridade |
|-----|-----------|-----------|
| `get_shop_info` | Info de uma loja (nome, status, regiao, warehouse) | ⭐⭐ |
| `get_profile` | Perfil da loja (descricao, logo) | ⭐ |
| `update_profile` | Atualizar perfil | ⭐ |
| `get_warehouse_detail` | Detalhes do armazem/estoque fisico | ⭐⭐ |

### Order APIs (Module 93)

| API | Descricao | Prioridade |
|-----|-----------|-----------|
| `get_order_list` | Lista pedidos (com filtro por status, data) | ⭐⭐ |
| `get_order_detail` | Detalhes completos do pedido (itens, comprador, frete, pagamento) | ⭐⭐ |
| `cancel_order` | Cancelar pedido | ⭐ |
| `handle_buyer_cancellation` | Processar cancelamento do comprador | ⭐ |

### Logistics APIs (Module 89)

| API | Descricao | Prioridade |
|-----|-----------|-----------|
| `get_shipping_parameter` | Parametros de frete (dimensoes, peso, origem/destino) | ⭐⭐ |
| `get_tracking_info` | Rastreio de pedido | ⭐⭐ |
| `get_address_list` | Enderecos de retirada/devolucao | ⭐ |

---

## 2. Pipeline para Estoque Multiloja

```
┌─────────────────────────────────────────────┐
│ AUTENTICACAO                                │
│ /api/v2/auth/token/get                      │
│ └─ code + shop_id → access_token            │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│ DESCOBERTA DE LOJAS                         │
│ v2.merchant.get_shop_list_by_merchant       │
│ └─ Retorna TODAS as lojas vinculadas        │
│ └─ Popula dropdown "Loja" na sidebar        │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│ SINCRONIZACAO DE PRODUTOS                   │
│ Para cada loja:                             │
│   v2.product.get_item_list                  │
│   └─ Lista produtos + modelos/variacoes     │
│   └─ Popula catalogo_produtos (SSOT)        │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│ GESTAO DE ESTOQUE                           │
│ Para cada loja:                             │
│   GET v2.product.get_model_list             │
│   └─ Visualizar estoque por variacao        │
│   POST v2.product.update_stock              │
│   └─ Atualizar estoque no Shopee            │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│ PEDIDOS                                     │
│ Para cada loja:                             │
│   v2.order.get_order_list                   │
│   └─ Puxar pedidos para dashboard de vendas │
└─────────────────────────────────────────────┘
```

---

## 3. O que ja temos vs o que falta

| Componente | Status |
|-----------|--------|
| HMAC-SHA256 signing | ✅ `shopee.py:_sign()` |
| OAuth get_auth_url | ✅ Corrigido (faltava api_key no sign) |
| OAuth exchange_shopee_code | ✅ Implementado |
| OAuth refresh_shopee_token | ✅ Implementado |
| Token storage (env var) | ✅ `SHOPEE_ACCESS_TOKEN` |
| Rotas Flask (callback, auth-url) | ✅ Adicionadas |
| **get_shop_list_by_merchant** | 🔴 Nao implementado |
| **get_item_list** (por loja) | 🔴 Nao implementado |
| **get_model_list** (variacoes) | 🔴 Nao implementado |
| **update_stock** (push Shopee) | 🔴 Nao implementado |
| **get_order_list** (pedidos) | 🔴 Nao implementado |
| Sincronizacao Shopee → catalogo SSOT | 🔴 Nao implementado |
| Seletor de loja Shopee na sidebar | 🔴 Nao implementado |

---

## 4. Ordem de Implementacao Sugerida

1. **Finalizar OAuth** → obter access_token funcional
2. **get_shop_list_by_merchant** → descobrir todas as lojas
3. **Sync lojas** → popular dropdown da sidebar com lojas Shopee
4. **get_item_list + get_model_list** → sincronizar produtos/variacoes
5. **Estoque visual** → mostrar estoque por loja/variacao
6. **update_stock** → push de alteracoes para Shopee
7. **get_order_list** → integrar pedidos no modulo Vendas
