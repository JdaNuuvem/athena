# Fase 0 + Fase 1 — Fundação de Acesso e Núcleo Multiloja

**Data:** 2026-07-13
**Status:** Aprovado para implementação

## Contexto

O PRD antigo (`docs/PRD_DASHBOARD_MULTILOJA.md`) está obsoleto e foi descartado. O pedido atual é
por uma reconstrução completa do dashboard para operação multiloja (físicas + digitais): cotação,
estoque, lucro, perdas, vendas, e abas dedicadas por agente (tributário, compra/venda, relatórios
administrativos).

Levantamento do estado atual mostrou:
- `GET /api/lojas` já existe (`hermes_agents/routes/catalog.py`) e devolve comparativo por loja/canal,
  mas **não existe página `/lojas` no frontend nem item de menu** — por isso a aba "não aparece".
- Tabela `vendas` (Postgres) já tem `data`, `loja_id`, `marketplace`, `sku`, `quantidade`,
  `receita_bruta`, `preco_venda` — base real para vendas e para o detalhe de loja.
- `hermes_agents/routes/auth.py` já modela `role` por usuário (via env `ATHENA_USERS`) e uma lista de
  `permissoes` em `/api/me`, mas o endpoint está **hardcoded para sempre devolver "Admin"**,
  independente de quem logou — bug de autorização, não feature nova.
- `PyJWT` já está instalado no ambiente.
- Perdas (quebras/avarias/roubo/devolução), Tributário real e Compras formal **não existem** em
  lugar nenhum do backend hoje — ficam para Fases 2, 3 e 4 (fora do escopo deste documento).

O projeto completo foi decomposto em 5 fases; este documento cobre apenas as duas primeiras:

| Fase | Escopo | Status |
|---|---|---|
| **0 — Fundação de Acesso** | Auth JWT por usuário, papéis, menu filtrado por papel | **Neste documento** |
| **1 — Núcleo Multiloja** | Aba Lojas (comparativo + detalhe) e aba Vendas | **Neste documento** |
| 2 — Financeiro & Perdas | DRE real, margem por SKU/canal, registro de perdas | Fase futura |
| 3 — Tributário | NF-e via Bling, imposto retido por canal | Fase futura |
| 4 — Compras & Relatórios Admin | Sugestão de reposição (AG-01/AG-04), painel consolidado admin | Fase futura |

## Papéis e permissões

Três papéis, confirmados com o usuário:

- **admin** — acesso total a todas as abas atuais e futuras.
- **financeiro** — foco em financeiro/tributário/perdas (abas dessas fases futuras); na Fase 1 também
  vê a aba Vendas.
- **operador_loja** — foco em lojas/estoque/perdas (lançamento); na Fase 1 vê Lojas e Vendas.

Fora de escopo desta fase: endurecer autenticação nas rotas de API já existentes (hoje quase nenhuma
valida `Authorization`, exceto `/api/me`). Essa é uma pré-existência do sistema, não introduzida aqui.
Apenas as novas rotas criadas nas Fases 1+ (`/api/lojas/<id>`, `/api/vendas`) serão protegidas por papel.

## Fase 0 — Fundação de Acesso

### Backend (`hermes_agents/routes/auth.py`)

- Remove o `API_TOKEN` global compartilhado como fonte de identidade. Login (`POST /api/auth/login`)
  passa a assinar um **JWT por usuário** com PyJWT: claims `{sub: username, role, name, exp: now+24h}`,
  segredo de `ATHENA_JWT_SECRET` (gera um valor aleatório em memória no boot se a env não estiver
  setada — mesmo padrão de fallback que já existe hoje para `API_TOKEN`).
- `GET /api/me` decodifica o JWT do header `Authorization: Bearer <token>` (em vez de sempre devolver
  `"Admin"`/`"admin"` hardcoded) e monta a resposta a partir do `role` real do token.
- Mapa `ROLE_PERMISSIONS` novo (dict `role -> list[str]`):
  - `admin`: `["ver_produtos", "ver_estoque", "ver_lojas", "ver_vendas", "ver_financeiro",
    "ver_tributario", "ver_perdas", "ver_marketplaces", "ver_integracoes", "exportar",
    "gerenciar_usuarios"]`
  - `financeiro`: `["ver_financeiro", "ver_tributario", "ver_perdas", "ver_vendas", "exportar"]`
  - `operador_loja`: `["ver_lojas", "ver_estoque", "ver_vendas", "ver_perdas", "ver_produtos"]`
- Usuários continuam vindo de `ATHENA_USERS` (`username:hash:role:nome`), como hoje — só o `role` passa
  a ser usado de verdade.
- Erros de token inválido/expirado devolvem 401 com JSON `{"error": "..."}"`, mesmo padrão já usado.

### Frontend (`web/src/app/layout.tsx`)

- `NAV_ITEMS` ganha campo `roles: string[]` por item.
- Sidebar filtra `NAV_ITEMS` pelo `user.role` retornado por `api.me()` antes de renderizar.
- Acesso direto a uma rota fora do papel do usuário redireciona para `/dashboard` (guard client-side
  simples no `useEffect` de carregamento de layout, mesmo padrão do redirect de "sem token" que já
  existe).

## Fase 1 — Núcleo Multiloja

### Backend — detalhe de loja

Novo `GET /api/lojas/<loja_id>` em `catalog.py`, ao lado do `listar_lojas` existente:
- Vendas por dia dos últimos 30 dias da loja/canal (query em `vendas` filtrando por `loja_id` para
  física ou `marketplace` para digital, mesma distinção que `listar_lojas` já faz).
- Top produtos vendidos na loja/canal (join `vendas` + `fichas_tecnicas`).
- Estoque local: loja física usa dado agregado de `vendas`; canal digital reaproveita `anuncios`
  (mesma fonte que já alimenta `estoque_lojas` em `/api/produtos`).
- Protegido por papel (`admin`, `operador_loja`) via o JWT da Fase 0.
- Segue o padrão de erro do arquivo: try/except retornando JSON com chave `erro`, nunca 500 cru.

### Backend — vendas agregadas

Novo `GET /api/vendas?loja=&periodo=&agrupado_por=dia|loja|canal` — generaliza a lógica de agregação
que `kpi_overview` já usa, com filtros por loja/canal/período. Protegido por papel (`admin`,
`operador_loja`, `financeiro`).

### Frontend — `/lojas`

- Tabela comparativa (uma linha por loja física + canal digital + linha "Consolidado"), consumindo
  `api.lojas(periodo)` que **já existe** no client (`web/src/lib/api.ts`).
- Clique numa linha abre `/lojas/[id]`: vendas por dia (gráfico), top produtos, estoque local —
  consumindo o endpoint novo de detalhe.
- Item de menu **"Lojas"** em `NAV_ITEMS`, `roles: ["admin", "operador_loja"]`.

### Frontend — `/vendas`

- Filtros por loja/canal/período; tabela + gráfico de vendas agregadas.
- Item de menu **"Vendas"** em `NAV_ITEMS`, `roles: ["admin", "operador_loja", "financeiro"]`.

### Tratamento de erros e testes

- Backend: mesmo padrão try/except → JSON com `erro` já usado em todo `catalog.py`.
- Frontend: `error` state exibido em banner vermelho, mesmo padrão do `dashboard/page.tsx` atual.
- Não há suite de testes automatizada no projeto hoje. Verificação é manual:
  1. Login como cada um dos 3 papéis → conferir que o menu lateral mostra só os itens do papel.
  2. Abrir `/lojas` → comparativo carrega com dado real do Postgres (não mock).
  3. Abrir detalhe de uma loja → vendas por dia, top produtos e estoque local aparecem.
  4. Abrir `/vendas` → filtros por loja/canal/período funcionam e batem com os números de `/lojas`.
  5. Acessar uma rota fora do papel do usuário logado → redireciona para `/dashboard`.

## Fora de escopo (fases futuras)

- Perdas (registro manual em loja física + devolução/cancelamento automático em canal digital) — Fase 2.
- Financeiro real (DRE, margem por SKU/canal, ROI) — Fase 2.
- Tributário via NF-e do Bling — Fase 3.
- Sugestão de reposição/compra (AG-01 + AG-04) e painel consolidado do Admin — Fase 4.
- Endurecimento de autenticação nas rotas de API pré-existentes.
