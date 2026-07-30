# Catálogo e Vendas PDV das lojas físicas — Ponte i9Logic → Athena

**Relacionado:** [2026-07-28-reconciliacao-fisico-contabil-i9logic-design.md](2026-07-28-reconciliacao-fisico-contabil-i9logic-design.md) (Fase 1 — reconciliação de saldo). Esta spec reusa o client HTTP paginado, o rate limit e o mecanismo de de-para (`de_para_i9logic`) já construídos naquela fase. Não mexe em saldo/estoque — isso continua manual pelo usuário, como já decidido.

## Contexto

> "as lojas físicas tem o sistema do i9logic já implementadas [...] e a partir da api do i9logic nós vamos puxar os produtos para o painel de produtos do athena, as vendas feitas fisicamente no pdv das lojas fisicas, e o estoque irei fazer manualmente após puxarmos os produtos da api i9logic [...] as lojas virtuais serão alimentadas a partir da api da shopee"

Duas frentes, ambas só para lojas físicas (lojas virtuais são 100% Shopee, fora de escopo aqui):

1. **Catálogo de produtos** — importar o catálogo completo do i9Logic pro `catalogo_produtos` do Athena.
2. **Vendas do PDV** — sincronizar os pedidos feitos no caixa físico pro `vendas_pedidos`/`vendas_itens`/`vendas_pagamentos`.

## Descobertas confirmadas testando a API real

Credenciais reais testadas contra `https://api.i9logic.net` (auth: `X-Client-Id` + `Authorization: Bearer`, já corrigido em `core/i9logic.py` num fix separado, mergeado antes desta spec):

- `GET /v1/produtos`: **22.105 produtos** no total, sem filtro de filial (catálogo é global). Campos confirmados: `codproduto`, `descricao`, `ean`, `ncm`, `unidademedida`, `peso`, `ativo` ("1"/"0"), `emlinha` ("1"/"0"), `categoria`/`marca`/`fabricante`/`fornecedor` (só códigos numéricos internos — `GET /v1/categorias` e `GET /v1/marcas` retornam `404 ENTITY_NOT_FOUND`, não há como resolver pra nome).
- `GET /v1/filiais`: só **8 filiais** cadastradas. Campos: `id`, `codigo`, `razaosocial`, `fantasia`, `cnpj`, `endereco`, `ativa`.
- `GET /v1/pedidos`: exige pelo menos um filtro (`id`, `data`, `cliente`, `status_id` ou `origem`) — `data_de`+`data_ate` funciona e **não precisa filtrar por filial** (uma chamada só traz pedidos de todas as filiais). Campos confirmados: `id`, `data`, `hora`, `filial_venda`, `filial_estoque`, `valor_total`, `cancelado` ("0"/"1"), `devolvido`, `trocado`, `cliente` (numérico), `obs` (contém "PEDIDO REALIZADO VIA PDV..." — confirma que são vendas de PDV físico). Volume real medido: **~830 pedidos/dia** somando as 8 filiais.
- `GET /v1/pedidos_produtos?idpedido=X`: endpoint **separado** de `/pedidos` (não vem aninhado), retorna os itens daquele pedido. Não aceita lista de ids separada por vírgula (testado, retorna vazio) — uma chamada por pedido. Campos: `codproduto`, `idproduto`, `qtd`, `valorvenda`, `valorcusto`, `valortabela`.
- `GET /v1/pedidos_pagamentos?pedido=X`: mesmo formato, uma chamada por pedido. Campos: `formadepagamento` (código numérico, sem lookup testado/disponível), `valor`, `codautorizacao`, `nsu`, `cv`.

## Decisões

- **Catálogo é importação única** (não recorrente). 22.105 produtos não mudam a ponto de justificar um resync diário — roda uma vez, disparo manual. Se precisar reimportar no futuro, o mesmo endpoint pode ser chamado de novo (upsert idempotente).
- **Upsert direto, sem fila de revisão.** Produto novo (sku/codproduto que não existe em `catalogo_produtos`) é criado automaticamente; produto existente é atualizado. Sem aprovação manual — combina com "puxar produtos pro painel", hands-off.
- **categoria/marca/fabricante ficam de fora.** São só códigos numéricos do i9Logic sem endpoint de resolução (confirmado 404). Gravar o número cru seria inconsistente com os produtos vindos do Bling (que têm texto) e de baixo valor. Só os campos com significado direto entram: sku, descricao, ean, ncm, unidade, peso.
- **Só produtos `ativo="1"` e `emlinha="1"`** entram no catálogo Athena — evita poluir o painel com item descontinuado/fora de linha.
- **Vendas do PDV sincronizam continuamente**, via `core/scheduler.py`, a cada ~10 minutos — precisa aparecer fresco no Athena, diferente do catálogo.
- **Janela rolante fixa (últimas 3h) em vez de checkpoint persistido.** Cada ciclo busca `data_de = agora - 3h` até `agora`. Pedido que falhou no meio do processamento reaparece sozinho no próximo ciclo (10min depois) — autocura sem tabela de estado extra. Antes de gastar rate limit com itens/pagamentos, uma query em lote descobre quais pedidos da janela já estão sincronizados (`id_i9logic` já existe em `vendas_pedidos`) e pula esses.
- **De-para de filial (`tipo='filial'`) é reused da Fase 1**, não recriado. Pedido cuja `filial_venda` não tem de-para mapeado é ignorado (log, não erro fatal) — protege contra filial não cadastrada ainda. É uma pendência operacional do usuário (mapear as 8 filiais via os endpoints de matching/de-para já existentes), não código novo.
- **Backfill inicial via os mesmos módulos**, aceitando `data_de`/`data_ate` explícitos — importa histórico de vendas antes de ligar o job recorrente de 10min, papel equivalente ao `seed_inicial` da Fase 1.

## Modelo de dados

```sql
-- catalogo_produtos: rastreabilidade + campo que não existia
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS ean VARCHAR(20);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS id_i9logic BIGINT;

-- vendas_pedidos: mesmo padrão já usado pra bling_id/shopee_order_sn
ALTER TABLE vendas_pedidos ADD COLUMN IF NOT EXISTS id_i9logic BIGINT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_vendas_pedidos_id_i9logic
    ON vendas_pedidos (id_i9logic) WHERE id_i9logic IS NOT NULL;
```

Nenhuma tabela nova — reusa `catalogo_produtos`, `vendas_pedidos`, `vendas_itens`, `vendas_pagamentos`, `de_para_i9logic` (já existentes).

## Arquitetura

Dois módulos novos, irmãos de `core/i9logic.py`:

- `core/i9logic_catalogo.py` — import de produtos (uma função principal, disparo manual).
- `core/i9logic_vendas.py` — sync de pedidos PDV (job recorrente + backfill).

Refatoração em `core/i9logic.py`: `_paginar_estoques` vira um paginador genérico `_paginar(endpoint, params)` reusado pelos três módulos (saldo, catálogo, vendas) — hoje só o saldo usa a versão hardcoded pra `/produtos_estoques`.

Rotas novas em `routes/i9logic.py` (mesmo blueprint da Fase 1, não cria arquivo novo):

- `POST /api/integrations/i9logic/produtos/importar` — dispara a importação única do catálogo.
- `POST /api/integrations/i9logic/vendas/sincronizar` — dispara um ciclo de sync de vendas (aceita `data_de`/`data_ate` opcionais pra backfill; sem eles, usa a janela rolante de 3h).

## Fluxo — Catálogo

1. Pagina `GET /v1/produtos` inteiro (~111 páginas de 200, ~4,6min com o rate limit de 2,5s entre chamadas).
2. Filtra client-side: só `ativo="1"` e `emlinha="1"`.
3. Upsert em `catalogo_produtos` por `sku=codproduto`: descricao, ean, ncm, unidademedida→unidade_padrao, peso→peso_bruto, id_i9logic=produto["id"].
4. Grava o de-para (`tipo='produto'`, `id_i9logic`, `codigo_athena=codproduto`) no mesmo passo — automático, sem trabalho manual, e já deixa a Fase 1 (saldo) pronta pra usar esses produtos sem matching manual.
5. Falha de página (timeout/500/429): retry até 3x com backoff (2,5s/5s/10s) sem avançar página; esgotou, aborta e retorna `{"erro":..., "pagina_falhou": N, "importados_ate_agora": count}`. Idempotente — rodar de novo do zero não duplica.
6. Produto malformado (codproduto vazio): pula o registro, conta em `erros`, não aborta o lote inteiro.

## Fluxo — Vendas PDV

1. Job no `core/scheduler.py`, intervalo de 600s (10min).
2. Busca `GET /v1/pedidos?data_de=<agora-3h>&data_ate=<agora>` (paginado; ~104 pedidos numa janela de 3h no volume medido, cabe numa página).
3. Query em lote: quais desses `id`s já existem como `id_i9logic` em `vendas_pedidos`? Só os que faltam seguem pro próximo passo.
4. Pra cada pedido novo: resolve `filial_venda` → loja Athena via `de_para_i9logic` (tipo='filial'). Sem mapeamento, pula (log).
5. Busca itens (`GET /pedidos_produtos?idpedido=X`) e pagamentos (`GET /pedidos_pagamentos?pedido=X`) — 2 chamadas por pedido novo.
6. Upsert em `vendas_pedidos` (status=cancelado se `cancelado="1"` senão concluído, total=valor_total, origem='i9logic_pdv', loja_id resolvido), `vendas_itens` (sku=codproduto, quantidade=qtd, valor_unitario=valorvenda), `vendas_pagamentos` (forma=str(formadepagamento) cru — mesmo caso do categoria/marca, sem lookup disponível; valor, autorizacao=codautorizacao). Campo `cliente` de `vendas_pedidos` fica vazio pra pedidos i9Logic — o `pedido["cliente"]` da API é só um id numérico (0 na amostra testada) sem endpoint de cliente explorado; fora de escopo desta spec.
7. Falha isolada num pedido (item/pagamento não veio): loga, pula só aquele pedido — a janela rolante do próximo ciclo tenta de novo automaticamente.
8. `MAX_PEDIDOS_NOVOS_POR_CICLO = 100` (válvula de segurança, mesmo espírito do `MAX_PAGINAS` do Bling — bem acima da média medida de ~6 pedidos novos por janela de 10min): estourou, processa só o teto e loga aviso — resto entra no próximo ciclo (ainda dentro da janela de 3h, ou via backfill manual se o gap for maior).
9. Backfill: mesma função aceita `data_de`/`data_ate` explícitos via chamada manual — usado pra importar histórico antes do job recorrente começar a rodar de verdade.

## Testes

Mesmo padrão de `hermes_agents/tests/test_i9logic.py` (unittest, mock de `asyncpg`/`requests`):

- **Catálogo**: filtro ativo/emlinha aplicado, upsert por sku com todos os campos mapeados, de-para gravado junto no mesmo upsert, retry em falha de página (conta as tentativas), abort após esgotar retries preserva contagem parcial, registro malformado não aborta o lote, rodar 2x não duplica (idempotência).
- **Vendas**: janela de data construída corretamente (agora-3h até agora), filial sem de-para é pulada sem erro fatal, pedido já sincronizado não gasta chamada de itens/pagamentos (verifica que `requests.get` não foi chamado pra ele), falha isolada num pedido não impede os demais do mesmo ciclo, teto do `MAX_PEDIDOS_NOVOS_POR_CICLO` é respeitado, backfill com `data_de`/`data_ate` explícitos chama a API com esses valores em vez da janela rolante.

## Fora de escopo

- Resolver categoria/marca/fabricante/forma de pagamento pra texto legível — a API não oferece lookup; fica como código cru ou vazio, decisão registrada acima.
- Sync de saldo/estoque físico — isso é manual pelo usuário, e o mecanismo de reconciliação (Fase 1) já existe separado.
- Vínculo física↔virtual e correções no lado Shopee (produtos/pedidos não carregando) — outra frente de trabalho em andamento em paralelo (`vinculo-estoque-fisica-virtual`), sem overlap de arquivo com esta spec.
- Mapear as 8 filiais reais no de-para — pendência operacional do usuário, mecanismo já existe.

## Próximo passo

`superpowers:writing-plans` — plano de implementação TDD, dividido em tasks por módulo (paginador genérico, catálogo, vendas + rotas).
