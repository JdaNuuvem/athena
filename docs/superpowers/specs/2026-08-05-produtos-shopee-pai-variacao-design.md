# Produtos Shopee — estruturar pai/variação no banco (+ verificação de imagem)

**Data:** 2026-08-05
**Status:** Aprovado para implementação

## Contexto

A aba `web/src/app/integracoes/shopee/produtos/page.tsx` lista produtos sincronizados da Shopee via
`GET /api/shopee/produtos-sincronizados` (`hermes_agents/routes/shopee.py:221-231` →
`listar_produtos_sincronizados()` em `hermes_agents/shopee_sync.py:451-472`).

O sync (`sync_produtos()`, `shopee_sync.py:123-200`) grava a tabela `anuncios` (multi-marketplace) de forma
**achatada**: cada variação (model) de um produto com `has_model=True` vira **1 linha própria**, com
`anuncio_id = f"{item_id}_{model_id}"`. Produto simples grava `anuncio_id = str(item_id)`. Não existe coluna
`item_id`/`model_id` dedicada — esse dado só existe embutido, como string, dentro de `anuncio_id`.

O agrupamento visual "produto pai com variações dentro" **já existe hoje**, mas inteiramente no frontend
(`agruparPorProdutoPai()`, `page.tsx:111-123`), via parsing frágil: `anuncio_id.split("_")[0]` para achar o
item_id, e `titulo.split(" - ")[0]` (`nomeBaseProduto`, `page.tsx:128-130`) para achar o nome do pai — depende
do sync ter composto o título como `"Produto - Variação"` (`shopee_sync.py:177`). Quando esse formato não bate
(título sem separador `" - "`, ou variação futura sem `"_"` no anuncio_id), o agrupamento quebra
silenciosamente e a variação aparece como produto solto — o sintoma relatado pelo usuário.

A Shopee já expõe um endpoint ao vivo com dados estruturados de verdade
(`GET /produtos/<item_id>/variacoes`, `shopee.py:398-409`, via `get_model_list`), com `tier_variation` real
(ex: atributo "Cor" = "Azul") — mas a tela de listagem não usa esse endpoint hoje.

**Imagem:** ao contrário do que foi presumido inicialmente, o import de imagem **já está implementado e
funcionando** — `sync_produtos` já lê `image.image_url_list[0]` do payload da Shopee (pedido via
`response_optional_fields=image`) e grava em `anuncios.imagem_url` (`shopee_sync.py:150-156`). Produtos com
variação herdam a mesma foto do item pai (a Shopee só guarda foto a nível de item, nunca por model). O
frontend já exibe com fallback gracioso (`ProdutoThumb`, `page.tsx:64-82` — placeholder com inicial se a URL
for nula ou falhar ao carregar). Existem testes cobrindo esse comportamento
(`test_shopee_sync.py:155,182,322`). Este trabalho não muda esse pipeline — só valida numa loja real que está
funcionando ponta a ponta, e corrige pontualmente se achar algo quebrado.

## Decisões (validadas com o usuário)

1. **Hierarquia persistida no banco** via colunas novas em `anuncios` — não busca ao vivo na API da Shopee a
   cada carregamento de tela (evita rate limit e latência), e não cria tabela nova dedicada (menor mudança,
   reaproveita a tabela `anuncios` já usada por todos os marketplaces).
2. **Granularidade da tabela não muda** — continua 1 linha por SKU (produto simples ou variação). O que muda é
   que `item_id`/`model_id` passam a ser colunas reais em vez de string embutida em `anuncio_id`.
3. **API `/produtos-sincronizados` continua flat** (1 linha por SKU) — não passa a devolver JSON aninhado. O
   agrupamento visual continua no frontend, só troca a fonte: em vez de parsear `anuncio_id`/`titulo`, usa os
   campos estruturados novos.
4. **Imagem:** sem mudança de pipeline. Escopo aqui é validação (smoke test numa loja real, produto simples e
   produto com variação) + correção pontual se achar bug — não é galeria/múltiplas fotos (fora de escopo,
   decisão do usuário).
5. **Dado legado (linhas já sincronizadas antes desta mudança):** recebe um backfill único que popula
   `item_id`/`model_id` fazendo parse do `anuncio_id` existente (mesma lógica que o frontend já fazia). O campo
   `tier_variacao` fica `NULL` nessas linhas até o próximo sync rodar — nesse meio-tempo, o frontend cai no
   fallback antigo (parse do título) só para o rótulo da variação, sem quebrar o agrupamento em si (que já usa
   `item_id` real do backfill).

## Modelo de dados

Três colunas novas em `anuncios` (sem criar tabela nova):

```sql
ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS item_id VARCHAR(50);
ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS model_id VARCHAR(50);
ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS tier_variacao JSONB;
CREATE INDEX IF NOT EXISTS idx_anuncios_item_id ON anuncios (item_id);
```

- `item_id`: ID do produto pai na Shopee. Preenchido para toda linha Shopee (produto simples ou variação).
- `model_id`: ID do model (variação) na Shopee. `NULL` quando a linha é um produto simples sem variação.
- `tier_variacao`: `{"atributo": "Cor", "valor": "Azul"}` para 1 tier, ou
  `[{"atributo": "Cor", "valor": "Azul"}, {"atributo": "Tamanho", "valor": "M"}]` para 2 tiers (Shopee permite
  até 2). `NULL` em produto simples e em linhas antigas ainda não resincronizadas.

Adicionar esses `ALTER TABLE ... IF NOT EXISTS` em `core/catalogo.py::_ensure_tables()` (mesmo padrão já usado
ali para as colunas `shop_id`/`estoque`/`imagem_url` de `anuncios`).

Essas colunas são específicas de marketplaces com hierarquia por model (Shopee hoje; Mercado Livre/Shein no
futuro, se vierem a ter sync próprio) — ficam `NULL` para linhas de outros marketplaces sem variação
estruturada, sem impacto neles.

## Sincronização (`sync_produtos()`, `shopee_sync.py`)

Nenhuma chamada nova à API — os dados já chegam no payload atual de `get_item_base_info` (`item_id`) e
`get_model_list` (`model_id`, `tier_index`). Só passa a persistir o que já é lido:

- Produto simples (loop de `item`, linha ~150): grava `item_id = str(item["item_id"])`, `model_id = NULL`,
  `tier_variacao = NULL`.
- Produto com variação (loop de `model` dentro de `has_model`, linha ~178): grava
  `item_id = str(item["item_id"])`, `model_id = str(model["model_id"])`, e monta `tier_variacao` combinando
  `tier_variation` (lista de `{name, option_list}` do item) com o `tier_index` do model específico (cada
  posição do `tier_index` aponta pro índice de `option_list` do tier correspondente).

`_upsert_anuncio()` (linhas 102-120) ganha 3 parâmetros novos (`item_id`, `model_id`, `tier_variacao`),
incluídos no `INSERT ... ON CONFLICT (sku, marketplace, shop_id) DO UPDATE`.

## Backfill (dado já sincronizado antes desta mudança)

Script único (roda manualmente uma vez, não fica agendado):

```sql
UPDATE anuncios
SET item_id = split_part(anuncio_id, '_', 1),
    model_id = NULLIF(split_part(anuncio_id, '_', 2), '')
WHERE marketplace = 'shopee' AND item_id IS NULL;
```

`tier_variacao` não é retroativamente calculável a partir do que já está salvo (a informação de qual atributo/
valor cada `tier_index` representa não fica persistida hoje) — fica `NULL` até o próximo `sync_produtos` rodar
para aquela loja, o que já acontece periodicamente.

## Backend — endpoint

`GET /api/shopee/produtos-sincronizados` (`listar_produtos_sincronizados()`, `shopee_sync.py:451-472`): SELECT
passa a incluir `a.item_id, a.model_id, a.tier_variacao`. Continua devolvendo lista flat, ordenada por
`a.titulo` como hoje — só ganha os 3 campos novos no JSON de cada linha.

## Frontend

**`web/src/lib/api.ts`** — `ShopeeProdutoSincronizado` ganha:
```ts
item_id: string;
model_id: string | null;
tier_variacao: { atributo: string; valor: string }[] | null;
```

**`web/src/app/integracoes/shopee/produtos/page.tsx`:**
- `agruparPorProdutoPai()` (linha 111): troca `p.anuncio_id.split("_")[0]` por `p.item_id` direto.
- `nomeBaseProduto()` (linha 128): mantém o parse de `titulo.split(" - ")[0]` como está — não há campo de
  "nome do produto pai" separado vindo da Shopee; título continua sendo a única fonte para isso.
- `sufixoVariacao()` (linha 135): passa a montar o rótulo a partir de `tier_variacao` estruturado (ex:
  `"Cor: Azul"`, ou `"Cor: Azul, Tamanho: M"` se 2 tiers) quando presente; cai no parse antigo do título
  (sufixo após `" - "`) só quando `tier_variacao` for `NULL` (linha ainda não resincronizada após o backfill).
- `temVariacao` (linha 120): simplifica para `variacoes.some(v => v.model_id !== null)` — direto, sem mais
  depender de heurística sobre `anuncio_id.includes("_")`.

**`_components/ProdutoVariacoesModal.tsx`:** usa a mesma `sufixoVariacao()` (hoje duplicada — nesta mudança,
extrair para um helper compartilhado em vez de manter as duas cópias divergindo, já que a lógica muda de forma
idêntica nos dois lugares).

## Verificação de imagem

Sem mudança de código no pipeline de sync/exibição. Ação: smoke test manual numa loja real com produtos —
conferir que `imagem_url` chega preenchida tanto em produto simples quanto em cada variação de um produto com
`has_model=True`, e que a miniatura aparece na listagem (modo card e modo lista) e no cabeçalho do
`ProdutoVariacoesModal`. Se algo estiver quebrado, corrigir como fix pontual dentro desta mesma entrega.

## Fora de escopo (fica para specs futuros)

- **Galeria de múltiplas fotos por produto** (hoje só a 1ª de `image_url_list` é salva) — decisão do usuário:
  não é o problema agora.
- **Foto por variação** — limitação da própria API da Shopee (só guarda foto a nível de item pai), não é
  algo que dá para resolver do nosso lado.
- **Migrar a fonte de variação para o endpoint ao vivo `/produtos/<item_id>/variacoes`** — hoje avaliado e
  descartado em favor de dado persistido no sync (decisão do usuário, ver Decisões #1); pode ser revisitado se
  o dado persistido se mostrar insuficiente (ex: Shopee mudar tier depois do sync sem re-sincronizar).
- **Redesenho visual mais amplo da tela de produtos** ("lapidar a interface") além do que está descrito aqui —
  o usuário sinalizou intenção de continuar iterando na interface depois desta entrega; próximos itens ficam
  para specs futuros, um de cada vez.
