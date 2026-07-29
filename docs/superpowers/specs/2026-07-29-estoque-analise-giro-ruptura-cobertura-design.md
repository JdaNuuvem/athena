# Estoque — Análise (Giro, Ruptura, Cobertura) com dado real

**Relacionado:** [2026-07-28-produtos-catalogo-mestre-loja-reconciliacao-design.md](2026-07-28-produtos-catalogo-mestre-loja-reconciliacao-design.md) (decide onde vive `estoque_minimo`/`estoque_maximo` e o critério de migração pra `produtos_loja`).

**Parte de:** lapidação do módulo Estoque (4 frentes: Análise → Depósitos → Custos → Inventário, nessa ordem). Este documento cobre só a primeira.

## Por que este documento existe

Auditoria de 29/07/2026 nos 35 módulos do sistema achou que `web/src/app/estoque/analise/page.tsx` (Giro de Estoque, Ruptura, Cobertura) é 100% `Math.random()` gerado no cliente (`estoque/data/custos.ts:70-73`), sem rota de backend equivalente. A tela finge ser dado do banco e não é — é a lacuna mais enganosa do módulo Estoque, porque é a tela usada pra decidir compra/reposição.

O núcleo operacional de Estoque (entrada/saída/transferência/aprovação/contagem cíclica) já é real e testado (~50 testes). Esta spec estende esse núcleo real com 3 indicadores analíticos, sem inventar tabela nova — usa dado que já existe.

## Escopo decidido

- Agregado de todas as lojas por padrão, com filtro de loja opcional (mesmo padrão de seletor que `estoque/contagem` já usa) — decisão do usuário, cobre os dois casos de uso sem duplicar tela.
- "Vendas perdidas" / "Impacto receita" da Ruptura calculadas por **velocidade média de venda do próprio SKU nos 30 dias antes da ruptura começar** × dias em ruptura × preço médio de venda no período — decisão do usuário, reflete o padrão real daquele SKU em vez de uma média genérica.

## Fontes de dado reais

- **Saídas / demanda**: `vendas_itens` (tem `sku`, `quantidade`, `valor_unitario`) join `vendas_pedidos` (`data`, `loja_id`, `status`) — não a movimentação genérica de estoque, que inclui transferência/perda/ajuste e poluiria "demanda real". Filtro `status != 'cancelado'`.
- **Saldo atual**: `estoque_lojas.quantidade`, somado por SKU quando agregado, filtrado por `loja_id` quando o filtro de loja é usado.
- **Mínimo/máximo**: `produtos_loja.estoque_minimo`/`estoque_maximo` (override por loja) com fallback pra `catalogo_produtos.estoque_minimo`/`estoque_maximo` (padrão global, colunas congeladas desde a reconciliação Mestre+Loja). Este módulo recebe `loja` como parâmetro explícito — pelo critério já documentado na reconciliação, isso o qualifica como primeiro consumidor real migrado pra ler `produtos_loja`.
- **Último abastecimento / início da ruptura**: ledger de movimentações já existente (`core.estoque`, usado por `/api/estoque/movimentacoes`) — última `entrada` por SKU/loja, e a `saida`/ajuste que derrubou o saldo abaixo do mínimo.

## Fórmulas

**Giro** = saídas no período (padrão 30d) / estoque médio. Estoque médio é **aproximado pelo saldo atual** — não existe snapshot diário de estoque no banco pra calcular média de verdade. Isso fica documentado no código (docstring) e como nota de rodapé discreta na própria tela ("aproximado pelo saldo atual"), não escondido. Tendência (▲/▼) compara giro do período atual contra o período anterior de mesmo tamanho.

**Ruptura** = SKU com saldo < mínimo (efetivo, após fallback). Dias em ruptura = hoje − data da movimentação que derrubou o saldo abaixo do mínimo. Vendas perdidas = velocidade média pré-ruptura × dias em ruptura. Impacto receita = vendas perdidas × preço médio de venda (`AVG(vendas_itens.valor_unitario)` do próprio SKU no período pré-ruptura). SKU sem nenhuma venda histórica não entra no cálculo de vendas perdidas (fica 0, não divide por zero nem inventa número).

**Cobertura** = saldo atual / demanda diária média (saídas 30d / 30). Demanda zero → cobertura "sem venda recente" (não `Infinity`, não crash). Status: `critico` (saldo ≤ 0 ou abaixo do mínimo), `baixo` (cobertura < 7 dias), `normal` (7–30 dias ou dentro da faixa mín/máx), `excesso` (saldo > máximo) — mesmos cortes de cor que a tela já usa hoje.

## API

Novo módulo `hermes_agents/core/estoque_analise.py` (arquivo próprio — `estoque_relatorios.py` é auditoria/discrepância, responsabilidade diferente):

```
giro(loja: str = "", dias: int = 30) -> list[dict]
ruptura(loja: str = "") -> list[dict]
cobertura(loja: str = "") -> list[dict]
```

Rotas em `routes/estoque.py`:
```
GET /api/estoque/analise/giro?loja=&dias=30
GET /api/estoque/analise/ruptura?loja=
GET /api/estoque/analise/cobertura?loja=
```

## Frontend

`web/src/app/estoque/analise/page.tsx`: troca as 3 chamadas `gerarIndicadores*()` (mock) por `fetch` real via `lib/api.ts` (novas funções `estoqueAnaliseGiro`, `estoqueAnaliseRuptura`, `estoqueAnaliseCobertura`), com `LoadingState`/`ErrorAlert` (padrão já usado no resto do módulo, ausente nesta tela hoje). Adiciona seletor de loja no topo, mesmo componente/padrão de `estoque/contagem`. Remove import de `estoque/data/custos.ts` (as 3 funções geradoras ficam mortas — apagar o arquivo se nada mais importar depois de migrar).

## Testes

`hermes_agents/tests/test_estoque_analise.py`:
- Giro: saída zero no período (sem venda) não quebra, giro = 0; saldo zero não causa divisão por zero.
- Ruptura: nenhum SKU abaixo do mínimo → lista vazia; SKU sem venda histórica → vendas perdidas = 0, não erro.
- Cobertura: sem mínimo/máximo definido em nenhuma das duas tabelas → status cai em `normal` por padrão, não crash; demanda diária zero → "sem venda recente".
- Filtro de loja: agregado bate com soma de todas as lojas individualmente.

## Fora de escopo (registrado, não decidido aqui)

- Depósitos, Custos, Inventário — próximas specs desta mesma lapidação, um documento cada.
- `/api/estoque/sync/processar` e `/sync/status/<sku>` (fila de sync offline, hoje 501 explícito e documentado) — não faz parte desta spec; é gap honesto, não dado fake, prioridade diferente.
- Cálculo de estoque médio "de verdade" via snapshot diário — exigiria tabela de histórico de saldo que não existe; fica registrado como melhoria futura se a aproximação por saldo atual se mostrar insuficiente na prática.

## Próximo passo

`superpowers:writing-plans` — plano de implementação TDD (schema/queries → core → rotas → frontend → testes) pra esta spec.
