# O que dá pra fazer com Shopee + Athena

> Baseado no código real hoje (`hermes_agents/shopee.py`, `shopee_sync.py`, `athena_bridge.py`, tela `/integracoes/shopee`) e no catálogo de APIs já levantado em `docs/implementacao futura/shopee-api-catalog.md`. Organizado do mais simples/pronto para o mais avançado.

---

## 1. Já funciona hoje (testável agora, sem escrever código novo)

| Funcionalidade | Onde | Observação |
|---|---|---|
| Conectar 1 ou mais lojas Shopee (OAuth) | `/integracoes/shopee` → "Conectar Loja Shopee" | Cada loja gera seu próprio `shop_id` + token |
| Ver lojas Shopee conectadas | `/integracoes/shopee` | Lista com nome e `shop_id` |
| Sincronizar produtos Shopee → catálogo local | Botão "Sincronizar" por loja | Grava em `anuncios` (preço, status, título) e `fichas_tecnicas` |
| Consultar estoque disponível de um item | `shopee.check_stock(item_id)` | Retorna disponível + reservado |
| **Atualizar estoque de um SKU numa loja específica** | Aba **Controle** do produto → botão "Enviar" na linha da loja | Empurra a quantidade local para a Shopee |
| Atualizar preço de um item | `shopee.update_price()` | Função pronta, ainda sem botão na tela |
| Sincronizar pedidos Shopee → vendas | `shopee_sync.sync_pedidos()` | Alimenta relatórios de vendas/lucratividade |
| Listar modelos/variações de um produto | `shopee.get_model_list()` | Função pronta, sem tela ainda |

---

## 2. Organizar estoque (multiloja) — o que já dá e o que falta

**Já dá:**
- Ver estoque físico por loja/depósito no produto (aba Visão Geral / Controle)
- Ver estoque mínimo/máximo vindo do Bling
- Enviar a quantidade local para uma loja Shopee específica, produto a produto

**Fácil de adicionar (próximo passo natural):**
- Botão "Enviar estoque para TODAS as lojas Shopee de uma vez" (hoje é loja por loja)
- Alerta automático "estoque baixo → sincronizar com Shopee" (a lógica de mínimo já existe, só falta disparar a ação)
- Tela de "estoque em lote": escolher vários SKUs e mandar todos para a Shopee de uma vez (a API da Shopee aceita atualizar vários modelos numa chamada só)

---

## 3. Adicionar produtos — cuidado, não é tão simples quanto parece

No Bling, criar produto é simples (SKU + nome + preço já basta — tem até formulário pronto em `/integracoes/bling`).

**Na Shopee é mais burocrático**, porque a API (`add_item`) exige, além do básico:
- `category_id` — escolher uma categoria **folha** dentro da árvore de categorias da Shopee (centenas de opções)
- Atributos obrigatórios da categoria escolhida (ex: "Material", "Voltagem" — variam por categoria)
- Pelo menos 1 imagem já hospedada
- Peso, dimensões, marca (`brand_id`)

Ou seja: dá pra fazer, mas exige primeiro buscar `get_category`/`get_attribute_tree`/`get_brand_list` e montar um formulário que se adapta à categoria escolhida. **Não é um formulário fixo de 4 campos como o do Bling.**

**Caminho mais simples pra começar:** cadastrar o produto no Bling (que já tem o formulário pronto) e usar a Shopee só para publicar produtos que já existem lá — isso evita lidar com a árvore de categorias na mão.

---

## 4. Fácil de adicionar (pouco código, função já existe ou é direta)

| O que | Esforço | Nota |
|---|---|---|
| Botão "Atualizar preço" na tela do produto | Baixo | `update_price()` já existe, só falta o botão |
| Editar produto existente (nome, descrição) | Baixo-médio | `update_item` da Shopee, sem categoria envolvida se não mudar categoria |
| Tirar produto do ar / reativar (`unlist_item`) | Baixo | Útil pra pausar um anúncio sem apagar |
| Ver detalhe completo de um pedido Shopee | Baixo | `get_order_detail()` já existe, falta tela |
| Listar categorias da Shopee | Baixo | `get_category` — pré-requisito pra criar produto depois |

---

## 5. Médio prazo

| O que | Esforço | Nota |
|---|---|---|
| Criar produto novo direto na Shopee | Médio | Precisa do fluxo de categoria/atributos (seção 3) |
| Gestão de variações (cor/tamanho) | Médio | `init_tier_variation`/`update_tier_variation` |
| Processar pedido (aceitar, imprimir etiqueta, despachar) | Médio | Módulo de Logistics da Shopee |
| Cancelar pedido / tratar cancelamento do comprador | Médio | `cancel_order`, `handle_buyer_cancellation` |
| Descobrir todas as lojas de uma vez (conta agregadora) | Médio | `get_shop_list_by_merchant` — só relevante se você tiver conta "Merchant" da Shopee, não o modelo padrão de vendedor |

---

## 6. Avançado / nicho (baixa prioridade)

- Produto global multi-mercado (`global_item`, `create_publish_task`) — só relevante se vender em vários países
- Shopee Ads real — hoje a tela `/integracoes/shopee-ads` é **só simulação local** (não fala de verdade com a API de Ads da Shopee ainda; os números são fixos/zerados)
- Chat com comprador via API
- Webhooks em tempo real (hoje a sincronização é manual, sob demanda — não fica escutando eventos da Shopee)

---

## Resumo prático — por onde eu começaria

1. Botão de atualizar preço (rápido, função já pronta)
2. Enviar estoque para todas as lojas de uma vez (não só uma por uma)
3. Listar categorias (pré-requisito de tudo que envolve criar/editar produto)
4. Só depois: criar produto direto na Shopee — ou manter o fluxo "cadastra no Bling, publica na Shopee"
