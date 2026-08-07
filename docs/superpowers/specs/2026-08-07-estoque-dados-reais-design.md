# Estoque — Frente 1: Elimina Dados Fabricados (Depósitos, Inventário, Custos)

**Data:** 2026-08-07
**Status:** Aprovado para planejamento

## Contexto

Critique do módulo de Estoque (`.impeccable/critique/2026-08-07T20-47-22Z__web-src-app-estoque-page-tsx.md`) identificou como achado P0: `web/src/app/estoque/depositos/page.tsx` e `web/src/app/estoque/inventario/page.tsx` renderizam números fabricados via `Math.random()` — SKUs, valor de estoque, itens críticos — em cards que parecem dados reais de produção, porque usam o design system compartilhado (`KpiCard`, `DataTable`). Ambas as páginas são inacessíveis pelo menu de navegação hoje, mas continuam navegáveis por URL direta.

Este é o primeiro de 5 sub-projetos da reforma do módulo de Estoque, na ordem: **dados fabricados** (este documento) → navegação/IA → componente unificado de ajuste de estoque → confirmação de ações irreversíveis → acessibilidade. Feito primeiro para que a Frente 2 (navegação) não precise adicionar ao menu páginas que serão removidas ou reescritas aqui.

## Decisões (fechadas com o usuário durante o brainstorming)

- **Depósitos**: conectar a dados reais, não travar atrás de flag. Existe base real suficiente (ver Backend abaixo).
- **Inventário**: remover — é conceitualmente duplicado de Contagem Cíclica (`/estoque/contagem`), que já é real, funcional e está no menu. Não tem nenhum endpoint de backend (100% mock), então não há nada para migrar.
- **Custos**: sem mudança de código nesta rodada. Stub de 8 linhas ("Em construção"), já fora do menu. Demanda documentada em `docs/DEMANDAS.md` (Agosto 2026) — decisão do usuário foi registrar como pendência futura em vez de remover ou implementar agora.
- **"Depósito" é o mesmo conceito que existe no Bling** (ERP), não um conceito novo do Athena. O sistema já mapeia `loja_id → deposito_id` (Bling) via `GET /api/lojas/deposito-map` (`hermes_agents/routes/lojas_manage.py:161`). Cada loja/CD tem estoque contado separado na operação real (confirmado com o usuário) — mas essa separação já existe hoje via o conceito de loja + o mapeamento pro depósito Bling correspondente. **Não é necessário criar tabela nova nem migrar schema.**

## Backend — endpoint agregado de KPIs por depósito

### Fontes de dado já existentes (nenhuma é nova)

- `estoque_lojas` (tabela) — quantidade por SKU por loja, usada hoje por `GET /api/estoque/lojas` (`hermes_agents/routes/estoque.py:31-84`).
- `catalogo_produtos` (tabela) — via JOIN, fornece descrição, `estoque_minimo` e `preco_custo` (`core/catalogo.py:81`, `DECIMAL(12,2)`, nullable).
- `core/estoque_analise.py::ruptura()` (linhas 91-133) — já define o critério de "baixo estoque": `SUM(quantidade) < COALESCE(estoque_minimo por loja, estoque_minimo do catálogo, 0)`. A Frente 1 reaproveita esse critério em vez de inventar um novo (o código atual do front usa um `< 10` hardcoded — isso desaparece).
- `GET /api/lojas/deposito-map` — mapeia `loja_id → deposito_id` (id do depósito no Bling).
- `listarBlingDepositos()` (já importado em `depositos/page.tsx:15`) — lista os depósitos reais do Bling (nome, código/id, status ativo).

### Nova função `core/estoque.py` (ou `core/estoque_analise.py`, ao lado de `ruptura()`)

`kpis_por_deposito() -> list[dict]` — para cada loja com depósito Bling mapeado (via `deposito-map`):
1. Agrega `estoque_lojas` por `loja_id`: `COUNT(DISTINCT sku)` como `skus`, `SUM(quantidade * COALESCE(preco_custo, 0))` como `valor`.
2. Calcula `baixo_estoque` com o mesmo `HAVING SUM(quantidade) < estoque_minimo` de `ruptura()`, contado por loja.
3. Atribui o resultado ao `deposito_id` correspondente via o mapa.

Depósitos do Bling **sem nenhuma loja mapeada** (ex.: depósitos "virtuais" tipo E-commerce/Marketplace, se existirem no Bling sem vínculo de loja) entram no resultado com `skus: null, valor: null, baixo_estoque: null` — sinal explícito de "sem dado disponível", nunca `0` (que seria indistinguível de "depósito vazio de verdade").

### Rota

`GET /api/estoque/depositos/kpis` (rota nova, dentro de `estoque_bp`) — chama `kpis_por_deposito()`, retorna `{"data": [...]}`. Sem parâmetro de filtro nesta rodada (a página não tem filtro hoje).

## Frontend

### `depositos/page.tsx`

- Remove a geração `Math.random()` das linhas 62-64 e 71-74.
- Remove o import e uso de `DEPOSITOS_MOCK` (`../data/depositos`) — a lista de depósitos passa a vir inteiramente de `listarBlingDepositos()` (já usado) combinada com os KPIs do novo endpoint (`GET /api/estoque/depositos/kpis`), casados por `deposito_id`/`id`.
- Colunas de SKUs/Valor/Baixo Estoque: quando o valor for `null` (depósito sem loja mapeada), renderizar `—` com `title="Sem estoque rastreado neste depósito"` em vez de tratar como zero.
- KPIs do topo (`Depósitos Ativos`, `Total SKUs`, `Valor Total`, `Itens Baixo Estoque`) somam só os depósitos com dado disponível (ignoram os `null`).

### Remoções

- `web/src/app/estoque/inventario/page.tsx`
- `web/src/app/estoque/data/inventario.ts`
- `web/src/app/estoque/data/depositos.ts` (o mock `DEPOSITOS_MOCK` some; se `totaisPorDeposito()` no mesmo arquivo não for usado em nenhum outro lugar, o arquivo inteiro sai — confirmar com grep antes de apagar)

`web/src/app/estoque/custos/page.tsx` não é tocado.

## Fora de escopo

- Endereço detalhado de depósito (corredor, estante) — não existe fonte de dado real para isso hoje; fica fora desta frente.
- Depósitos "virtuais" sem loja mapeada ganharem estoque rastreado de verdade — precisaria de decisão de produto sobre como estoque de canais puramente online se relaciona com depósito, não decidido nesta rodada.
- Qualquer mudança em `/estoque/lojas`, `/estoque/rapido`, ou nas demais 13 páginas do módulo — cobertas pelas Frentes 2-5.
- `custos/page.tsx` — demanda futura documentada, não implementada aqui.

## Testes

- Backend: `kpis_por_deposito()` — teste com loja mapeada e sem dados de estoque (retorna 0, não null — depósito existe e está vazio de verdade), loja mapeada com estoque abaixo do mínimo (conta em `baixo_estoque`), depósito Bling sem loja mapeada (retorna `null` nos 3 campos), valor calculado corretamente com `preco_custo` presente e ausente (`COALESCE` para 0). Teste de RBAC/permissão na rota nova seguindo o mesmo padrão de `/api/estoque/lojas`.
- Frontend: verificação manual (sem backend/DB local disponível nesta sessão — mesma limitação já registrada para a reforma de Leads) cobrindo: depósito com dado real mostra números corretos, depósito sem loja mapeada mostra `—` em vez de `0`, KPIs do topo não contam os `—`, `/estoque/inventario` retorna 404, `/estoque/custos` continua acessível por URL direta e inalterado.
