# Contatos — Paginação Real, Filtros e Dados de Remarketing

**Data:** 2026-08-07

## Contexto

`/crm/contatos` (`web/src/app/crm/contatos/page.tsx`) já usa paginação real de servidor (LIMIT/OFFSET + COUNT via `core/cadastros.py::list_paginado`) — não há bug de matemática na paginação atual. O que falta, e motivou o pedido:

- Navegação só tem "Anterior"/"Próxima" + texto "página X de Y" — sem botões de número de página.
- Único filtro é busca livre (nome/documento/email/telefone). Sem filtro por tag, WhatsApp, status ou tempo sem comprar.
- Nenhuma informação útil pra remarketing aparece na tela: sistema de tags já existe no banco (`cad_cliente_tags`) mas nunca foi exposto na UI; WhatsApp opt-in só existe numa tabela satélite de contatos adicionais (`cad_cliente_contatos.whatsapp`), não no cliente principal; última compra e valor total gasto não existem como campo, mas são deriváveis via join com `vendas_pedidos` (mesmo padrão já usado em `core/relatorios.py::rel_clientes`); data de nascimento não existe em lugar nenhum.

**Achado relevante (fora de escopo aqui, só registrando):** apesar do nome "Contatos" na tela, os dados vêm de `cad_clientes` (Cadastros), não de `crm_contatos` (CRM) — decisão deliberada de uma sessão anterior ("unifica entidades", commit `a320484`). Esta mudança mantém essa direção — não migra a tela de volta pra `crm_contatos`, que não tem nenhum vínculo com `vendas_pedidos` e perderia justamente os dados de remarketing que são o ponto desta mudança.

**Precedente direto neste mesmo repo:** existe um spec/plano irmão para `/crm/leads` (`docs/superpowers/specs/2026-08-07-leads-paginacao-filtros-design.md`), documentado mas **ainda não implementado** (confirmado: nenhum dos arquivos que ele descreve existe no disco). Esta mudança segue a mesma convenção onde faz sentido (formato de resposta paginada, nomenclatura de função `listar_X_filtrado`, não tocar em função genérica compartilhada por outras tabelas) para manter o padrão consistente entre as duas telas, mesmo sem depender de nada que o outro spec crie.

## Backend

### Novas colunas em `cad_clientes` (`hermes_agents/core/cadastros.py::_ensure_tables`)

```sql
ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS whatsapp BOOLEAN DEFAULT FALSE;
ALTER TABLE cad_clientes ADD COLUMN IF NOT EXISTS data_nascimento DATE;
```

`whatsapp` é do cliente principal (o telefone cadastrado tem WhatsApp ou não) — independente da flag já existente em `cad_cliente_contatos.whatsapp`, que continua servindo contatos adicionais de uma empresa, não é tocada. `data_nascimento` fica vazia pra toda a base atual (ninguém tem esse dado hoje) — é um campo novo pra passar a coletar daqui pra frente, não uma migração de dado existente.

### Novos índices

Nenhum dos dois joins que este endpoint precisa tem índice hoje:

```sql
CREATE INDEX IF NOT EXISTS idx_vendas_pedidos_cliente_id ON vendas_pedidos (cliente_id);
CREATE INDEX IF NOT EXISTS idx_cad_cliente_tags_cliente_id ON cad_cliente_tags (cliente_id);
```

### Endpoint reaproveitado, mesma convenção do spec de Leads

`GET /api/cadastros/clientes` (rota já existente, `hermes_agents/routes/cadastros.py::cad_list`) ganha um branch: quando `tabela == "clientes"` **e** `pagina` vier na querystring, passa a chamar uma função nova em vez de `list_paginado` genérico — que continua servindo as outras 5 tabelas de Cadastros exatamente como hoje, sem mudança de comportamento ou de contrato.

Parâmetros novos (todos opcionais, mantendo retrocompatibilidade com quem já chama `?pagina=&por_pagina=&busca=` sem eles):

| Param | Tipo | Descrição |
|---|---|---|
| `sort` | string | Whitelist fixa: `id`, `nome`, `ultima_compra`, `total_gasto`. Default `id`. |
| `order` | string | `asc` ou `desc`. Default `desc`. |
| `status` | string | Filtro exato (`ativo`/`inativo`). |
| `tag` | string | Cliente precisa ter essa tag associada (`EXISTS` em `cad_cliente_tags`). |
| `whatsapp` | `true`\|`false` | Filtra por `cad_clientes.whatsapp`. |
| `sem_comprar_dias` | int | Cliente nunca comprou OU a última compra foi há mais de N dias — o par mais valioso pra reativação. |

Sort/order/status validados contra whitelist antes de entrar na query (mesma prática de `_CAMPOS_BUSCA`/whitelist já usada no arquivo — identificadores de coluna nunca vêm direto do request, só os valores, sempre parametrizados).

### Nova função `core/cadastros.py::listar_clientes_filtrado`

```
listar_clientes_filtrado(pagina, por_pagina, busca=None, sort="id", order="desc",
                          status=None, tag=None, whatsapp=None, sem_comprar_dias=None) -> dict
```

Fica ao lado de `list_paginado`/`_list_pagina`/`_count`, sem alterá-las. Monta:
- Uma `LEFT JOIN LATERAL` em `vendas_pedidos` (filtrado por `cliente_id` e `status != 'cancelado'`) computando `ultima_compra` (MAX), `total_gasto` (SUM) e `qtd_pedidos` (COUNT) por cliente — usada tanto no `SELECT` quanto disponível pro filtro `sem_comprar_dias` e pro `ORDER BY`.
- Uma segunda `LEFT JOIN LATERAL` em `cad_cliente_tags` com `array_agg(tag)`, só no `SELECT` (não no `COUNT`, que não precisa dela).
- `WHERE` dinâmico combinando busca livre + os 4 filtros acima, exatamente como `_list_filtered` já faz em `core/vendas.py` (mesmo padrão de `where = []; params = []` incrementando `$N`).

Resposta segue o mesmo formato que `list_paginado` já usa hoje (sem quebrar o frontend que já lê esse formato):
```json
{ "data": [...], "total": 137, "pagina": 1, "por_pagina": 20, "total_paginas": 7 }
```
Cada item de `data` ganha os campos novos: `whatsapp`, `data_nascimento`, `ultima_compra`, `total_gasto`, `qtd_pedidos`, `tags` (array de string).

### Endpoint novo pra popular o filtro de tag

`GET /api/cadastros/clientes/tags-disponiveis` → `core/cadastros.py::tags_disponiveis()` → `SELECT DISTINCT tag FROM cad_cliente_tags ORDER BY tag`. Rota dedicada (path de 2 segmentos não colide com `/<tabela>` nem `/<tabela>/<int:id>`) porque tags são texto livre, não um enum fixo no código — sem isso o filtro seria um campo de texto sem sugestão, pior UX do que o pedido.

## Frontend

### `web/src/lib/api.ts`

`cadListPaginado` ganha um 5º parâmetro opcional `filtros?: Record<string, string>` (sort/order/status/tag/whatsapp/sem_comprar_dias), anexado à querystring já montada — chamadas existentes (que não passam esse parâmetro) continuam idênticas. Novo método `cadClientesTagsDisponiveis(): Promise<{ data: string[] }>`.

### `web/src/app/crm/contatos/page.tsx`

- `interface Cliente` ganha `whatsapp: boolean`, `data_nascimento: string | null`, `ultima_compra: string | null`, `total_gasto: number`, `qtd_pedidos: number`, `tags: string[]`.
- **Barra de filtros** (nova linha abaixo da busca): dropdown Status (Todos/Ativo/Inativo), dropdown Tag (populado via `cadClientesTagsDisponiveis`, "Todas" + lista), toggle 3 estados WhatsApp (qualquer/com/sem), select "Sem comprar há" (30/60/90/180 dias + "Qualquer"). Botão "Limpar filtros" quando algum estiver ativo.
- **Tabela reorganizada** pra caber os dados novos sem virar 12 colunas: `Nome | Contato | Tags | Última compra | Total gasto | Status | Ações`. "Contato" combina email (linha 1) + telefone (linha 2) com um ícone de WhatsApp ao lado do telefone quando `whatsapp=true`. Tipo e Documento saem da tabela principal mas continuam no formulário de criar/editar (não são removidos do sistema, só não ocupam coluna na listagem — informação secundária pro caso de uso de remarketing desta tela). Cabeçalhos de Nome (via `sort=nome`), Última compra e Total gasto ficam clicáveis pra ordenar, com seta indicando direção ativa — mesmo padrão visual que o spec de Leads propôs (mesmo não estando implementado ainda, o padrão visual é reaproveitável).
- **Paginação**: troca o rodapé atual (Anterior/Próxima + texto) por "Mostrando X–Y de Z" + botões de número de página (janela de até 5 números ao redor da página atual + Primeira/Última quando há mais páginas que cabem) + seletor de itens por página (20/50/100, era fixo em 20).
- **Modal de criar/editar**: ganha campos WhatsApp (checkbox ao lado de Telefone) e Data de nascimento (input `type="date"`), no mesmo grid 2 colunas já usado.
- **Badge de tags** por linha: pills pequenas (reaproveita o estilo de badge já usado pro Status nesta mesma tabela), até 3 visíveis + "+N" se houver mais (sem popover/expansão — é só leitura aqui, gestão de tags fica pra uma fase futura, não faz parte deste escopo).

### Estados de erro/loading

Mesmo padrão já usado na tela (skeleton de linhas, banner de erro vermelho) — sem mudança de mecanismo, só de conteúdo das colunas.

## Fora de escopo

- Migrar a tela de volta pra `crm_contatos` — decisão já tomada em sessão anterior, mantida.
- Gestão de tags (criar/remover tag de um cliente pela tela) — só leitura/filtro nesta fase.
- Exportação CSV — o spec de Leads propõe isso pra outra tela; aqui não foi pedido e fica de fora até ser pedido (evita escopo não solicitado).
- Envio de campanha de remarketing em si (WhatsApp/email) — esta mudança só qualifica/filtra a lista, não dispara nada.
- Qualquer mudança em `list_paginado`/`_list_pagina`/`_count` genéricos ou nas outras 5 tabelas de Cadastros (empresas, usuários, fornecedores, transportadoras, vendedores) — continuam idênticas.
- `CrudPanel.tsx` genérico (usado por 11 outras telas) — não é tocado, esta tela já tem implementação própria desde antes.

## Testes

- Backend: `listar_clientes_filtrado` — cada filtro isolado (`status`, `tag`, `whatsapp`, `sem_comprar_dias` incluindo o caso "nunca comprou"), combinação de filtros, ordenação em cada coluna da whitelist (incluindo pelas colunas derivadas do join, `ultima_compra`/`total_gasto`), paginação (página fora do intervalo devolve lista vazia com `total`/`total_paginas` corretos), `sort`/`order`/`status` fora da whitelist caem no default sem interpolar valor bruto no SQL. `tags_disponiveis()` isolado.
- Backend: confirmar que a rota `/api/cadastros/<outra-tabela>?pagina=...` (ex. `fornecedores`) continua chamando `list_paginado` genérico, não a função nova — regressão explícita, mesmo padrão do teste que já existe pra filtro de loja em vendas.
- Frontend: `npx tsc --noEmit` limpo, smoke visual (Playwright ou navegador) confirmando a tabela renderiza com as colunas novas, filtros e paginação por número funcionam sem quebrar o fluxo de criar/editar/desativar já existente.
