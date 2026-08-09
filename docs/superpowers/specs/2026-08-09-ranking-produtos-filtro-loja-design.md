# Ranking de Produtos — Filtro por Loja (Shopee/i9Logic conforme o tipo)

**Data:** 2026-08-09

## Contexto

O card "Top produtos" do `/dashboard` foi corrigido hoje (commit `410e6bb`, sessão paralela) pra parar de ler de uma tabela órfã (`vendas`) e passar a usar `core.relatorios.ranking_produtos()` — a mesma fonte real que alimenta o modal "Ranking de produtos" já lapidado nesta sessão (spec `2026-08-09-ranking-produtos-metricas-design.md`). Mas esse fix deixou uma lacuna documentada no próprio código (`athena_bridge.py::kpi_overview`, comentário linha ~2035-2037): `ranking_produtos()` não filtra por loja — o card sempre mistura todas as lojas juntas, mesmo quando o usuário já selecionou uma loja específica no seletor global.

Pedido do usuário: quando uma loja virtual está selecionada, os produtos mostrados devem refletir a Shopee (fonte de verdade daquela loja); quando uma loja física está selecionada, devem refletir o i9Logic (fonte de verdade física).

**Isso já é a realidade dos dados, só falta o filtro.** Confirmado nesta investigação:
- `core.vendas.sincronizar_pedidos_shopee()` grava `loja_id` resolvido via `shop_id→loja` em todo pedido Shopee inserido em `vendas_pedidos`.
- `core.i9logic_vendas.sincronizar_pedidos_i9logic()` grava `loja_id` resolvido via `filial→loja` em todo pedido físico inserido em `vendas_pedidos`.
- `estoque_lojas` já tem coluna `loja_id` (migração aditiva "Fase 3", `core/catalogo.py`/`core/estoque_saldos.py`, já rodada).

Ou seja: cada linha em `vendas_pedidos`/`estoque_lojas` já nasce marcada com a loja certa pelo sync de origem. Filtrar por `loja_id` automaticamente separa Shopee de i9Logic — nenhuma lógica de "se é virtual, chama API X" é necessária, porque essa separação já aconteceu no momento da sincronização, não precisa acontecer de novo na leitura.

## O que muda

4 funções em `core/relatorios.py`/`core/bi.py` ganham parâmetro opcional `loja_id: int = None`, mesmo padrão já usado em `core.vendas.dashboard()` (`($N::int IS NULL OR loja_id = $N)`): `ranking_produtos`, `produtos_tendencia`, `risco_ruptura`, `curvas` (filtram por `vp.loja_id`, a tabela `vendas_pedidos` já unida na query) e `estoque_parado` (filtra por `e.loja_id`, a tabela `estoque_lojas`).

5 rotas em `routes/relatorios.py` ganham `?loja_id=` opcional (`/ranking-produtos`, `/produtos-tendencia`, `/risco-ruptura`, `/curvas`, `/estoque-parado`).

`athena_bridge.py::kpi_overview()` — já extrai `loja_id` de `request.args` (linha 1991) mas não repassa pra `ranking_produtos()` (linha 2039); passa a repassar.

`web/src/lib/api.ts` — 5 client functions ganham parâmetro `lojaId?: number` opcional, anexado à querystring quando presente.

`web/src/app/_components/RankingProdutosModal.tsx` — ganha prop `lojaId?: number`, repassa em todas as 5 chamadas de API, entra nas dependências do `useEffect` de busca (trocar de loja recarrega a categoria ativa).

`web/src/app/dashboard/page.tsx` — passa `lojaId` (já disponível via `useStore()`, já usado nas outras chamadas da página) pro `<RankingProdutosModal>`.

## Sem loja selecionada ("todas as lojas")

`loja_id=None`/parâmetro ausente → nenhum filtro aplicado, comportamento idêntico ao atual (todas as lojas somadas). Mesma convenção já usada em `lojaId === "todas"` no frontend (`api.kpiOverview`, linha 698: só envia `loja_id` quando não é `"todas"`).

## Testes

- Backend: cada uma das 5 funções ganha um teste confirmando que passar `loja_id` filtra corretamente (mock de 2 lojas diferentes, confirma que só a linha da loja pedida aparece) e que `loja_id=None` continua retornando tudo (comportamento atual preservado, sem regressão).
- Rotas: smoke test confirmando que `?loja_id=N` é aceito e repassado (reaproveita padrão `_assert_200_json` já usado nas rotas de relatórios).
- Frontend: `tsc --noEmit` limpo; smoke visual confirmando que trocar de loja no seletor global do dashboard recarrega tanto o card "Top produtos" quanto a categoria ativa do modal "Ranking de produtos".

## Fora de escopo

- Nenhuma mudança na estrutura do union Bling+PDV legado dentro de `ranking_produtos()`/`curvas()` — só acrescenta uma cláusula `WHERE`, não toca nas tabelas unidas (mesma restrição já estabelecida na spec anterior).
- Nenhuma chamada direta a API da Shopee ou do i9Logic nesta fase — a separação por fonte já é resultado do sync existente, não desta feature.
- Nenhuma mudança em `pdv_vendas`/`pdv_itens` (tabela morta, confirmado na spec anterior).
