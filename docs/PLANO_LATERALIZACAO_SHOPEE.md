# Plano de Lateralização Shopee — Athena

**Objetivo:** Abrir N lojas na Shopee e gerenciar tudo centralizado pelo Athena: replicar produtos, manter estoque sincronizado, publicar em massa.

---

## Arquitetura

```
                    ┌─────────────────────┐
                    │    Catálogo Athena   │
                    │  (catalogo_produtos) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │  Loja Shopee │ │  Loja Shopee │ │  Loja Shopee │
     │   #1 (origem)│ │  #2 (nova)   │ │  #3 (nova)   │
     │  shop_id=A   │ │  shop_id=B   │ │  shop_id=C   │
     └──────────────┘ └──────────────┘ └──────────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Estoque Central    │
                    │  (estoque_lojas)    │
                    │  SKU → qtd por loja │
                    └─────────────────────┘
```

---

## Fluxo de Lateralização (passo a passo)

### Fase 0 — Pré-requisito
1 app Shopee Open Platform (1 partner_id + 1 partner_key) já configurado no Athena

### Fase 1 — Criar lojas na Shopee (fora do Athena)
```
Para cada nova loja:
  1. Criar conta de vendedor no shopee.com.br
  2. No Partner Center, autorizar o app Athena para essa nova loja
  3. No Athena: Integrações > Shopee > "Conectar Loja Shopee"
     → OAuth → loja aparece na lista com token
```

### Fase 2 — Replicar produtos (no Athena)
```
Após conectar a loja:
  Botão "Replicar produtos de [Loja Origem]"
  → Athena copia TODOS os produtos + imagens da origem
  → Publica na nova loja com os mesmos SKUs, preços, categorias
  → Estoque inicial = 0 (ajustar depois)
```

### Fase 3 — Sincronizar estoque (automático)
```
Sempre que estoque mudar no Athena:
  → Push automático para TODAS as lojas Shopee conectadas
  → Cada loja com seu próprio estoque (estoque_lojas)
```

---

## Funcionalidades que o Athena PRECISA TER

### 1. Replicar produtos entre lojas (🔴 Essencial)
Pega todos os produtos de uma loja Shopee origem e publica na loja destino.

**Como funciona:**
1. `get_item_list()` → lista todos item_ids da loja origem
2. Para cada item: `get_item_base_info()` → extrai nome, preço, SKU, categoria, atributos, peso, dimensões, descrição, imagens (URLs), logística
3. Download das imagens da origem
4. `upload_image()` → reenvia imagens para a loja destino (ganha novos image_ids)
5. `add_item()` → cria o produto na loja destino com os mesmos dados

**Payload mapeado:**
```
Campo add_item        ←  get_item_base_info
──────────────────────────────────────────
category_id           ←  category_id
item_name             ←  item_name
item_sku              ←  item_sku
original_price        ←  price_info[0].original_price
description           ←  description (rich_text se existir)
image                 ←  images URLs → upload → image_id[]
weight                ←  weight
dimension             ←  package_length/width/height
attribute_list        ←  attribute_list (mesmo schema)
logistic_info         ←  logistic_info[0].logistic_id
seller_stock          ←  stock_info_v2 → stock_list (zerado = 0)
brand                 ←  brand (se existir)
condition             ←  "new" (padrão)
```

**UI:** Botão "Replicar produtos para esta loja" com dropdown de loja origem + barra de progresso.

### 2. Publicar do catálogo local para Shopee (🟡 Importante)
Pega produtos do `catalogo_produtos` (Athena) e publica numa loja Shopee.

**Problema:** `add_item` exige `category_id` da Shopee + atributos obrigatórios. Produtos do catálogo local não têm isso.

**Solução:** Usar a `PublicarShopeeTab` existente (1 por vez) OU, para bulk, criar um "template de categoria" — o usuário mapeia uma categoria Shopee para um grupo de produtos do catálogo e o sistema completa os atributos automaticamente.

**UI:** Tela "Publicar em massa" com:
- Seletor de produtos (SKU, nome, filtros)
- Mapeamento de categoria Shopee (dropdown com busca)
- Preenchimento automático de atributos obrigatórios
- Botão "Publicar N produtos"

### 3. Estoque multicanal sincronizado (🔴 Essencial)
Sempre que o estoque for ajustado no Athena (manual ou via Bling), empurrar para TODAS as lojas Shopee.

**Já existe:**
- `shopee.py:sincronizar_estoque_todas_lojas(sku, qtd)` — push para todas lojas
- `estoque_lojas` — tabela com estoque por SKU por loja

**O que falta:**
- Disparo automático (atualmente precisa chamar manualmente)
- Batch (hoje é 1 SKU por vez)
- Fila de retry para falhas de rede

**Solução proposta:**
```
Ao salvar estoque no Athena:
  → Disparar job assíncrono (filas do módulo automacoes)
  → Para cada loja Shopee: update_stock(item_id, stock_list)
  → Se falhar: retry 3x com backoff
  → Log de resultado
```

### 4. Dashboard unificado de preços (🟡 Importante)
Ver e ajustar preços de todas as lojas numa única tela.

**Já existe:**
- `update_price(item_id, price, loja_id)`

**UI proposta:**
```
Tabela: SKU | Nome | Preço Base | Loja A | Loja B | Loja C | Ação
        ABC | Sabonete | R$ 10 | R$ 12 | R$ 11,50 | R$ 13 | [Editar]
```
Com opção de "Aplicar markup % para todas as lojas" e "Sincronizar preços agora".

### 5. Agendamento de publicação (🟢 Desejável)
Programar a publicação em massa para um horário (ex: fora do horário comercial).

**Backend:** Usar o módulo `automacoes` (agendamentos) — dispara a replicação num horário agendado.

### 6. Log e auditoria de operações (🟢 Desejável)
Registrar cada operação: produto X publicado na loja Y com sucesso/erro, estoque sincronizado, preço alterado.

---

## Matriz de funcionalidades

| # | Funcionalidade | Já existe | O que falta | Esforço |
|---|---------------|-----------|-------------|---------|
| 1 | **Replicar produtos entre lojas** | `get_items`, `get_item_base_info`, `add_item`, `upload_image` | Função `transferir_produtos()` + endpoint + frontend | 6-8h |
| 2 | **Publicar catálogo local → Shopee** | `PublicarShopeeTab` (1 produto) | Bulk + mapeamento de categoria | 10-15h |
| 3 | **Estoque automático multicanal** | `sincronizar_estoque_todas_lojas()` | Disparo automático + fila de retry | 4-6h |
| 4 | **Dashboard de preços unificado** | `update_price()` | Tela de grid + markup % | 6-8h |
| 5 | **Agendamento** | `automacoes` (agendamentos) | Conectar webhook de replicação ao scheduler | 2-3h |
| 6 | **Log/auditoria** | `seguranca.py` | Conectar operações Shopee ao log | 2-3h |
| | **Total** | | | **30-43h** |

---

## Fluxo resumido para abrir uma nova loja

```
1. Criar conta de vendedor na Shopee (fora do Athena)
2. Autorizar o app Athena no Partner Center (Shopee)
3. No Athena:
   a. Integrações > Shopee > Conectar Loja Shopee (OAuth)
   b. Botão "Replicar produtos da [Loja Principal]"
   c. Aguardar publicação (N produtos em X minutos)
   d. Ajustar estoque inicial manualmente
4. Pronto — estoque futuro é sincronizado automagicamente
```

---

## Observações técnicas

**Shopee API não tem batch create:** Cada produto precisa ser criado individualmente (`add_item`). Para 500 produtos, espere ~20-40 minutos de replicação (com upload de imagens).

**Imagens precisam ser reenviadas:** O `image_id` é vinculado ao `shop_id`. Não é possível reutilizar image_id entre lojas. O Athena precisa baixar a imagem da loja origem e fazer upload na loja destino.

**SKU duplicado entre lojas:** Shopee permite o mesmo SKU em lojas diferentes (cada loja é independente). O Athena usa `produto_codigo`/`codigo` como referência cruzada entre lojas.

**Estoque independente por loja:** Cada loja tem seu próprio estoque. `estoque_lojas(sku, loja_id)` — o dashboard de estoque já filtra por loja.
