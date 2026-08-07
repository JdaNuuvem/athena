# Leads — Paginação, Filtros, Ordenação e Exportador

**Data:** 2026-08-07
**Status:** Aprovado para planejamento

## Contexto

`/crm/leads` usa o componente genérico `CrudPanel` (`web/src/app/_components/CrudPanel.tsx`), compartilhado por 12 telas (cadastros, CRM inteiro, atendimento). Hoje o painel de Leads:

- Busca até 500 registros de uma vez (`hermes_agents/core/crm.py::_list`, `LIMIT 500` fixo, sem paginação real).
- Só tem busca por texto livre client-side (filtra as colunas visíveis).
- Sem ordenação por coluna.
- Sem exportação.

**Decisão de escopo:** as mudanças ficam isoladas em Leads. `CrudPanel` não muda de comportamento nem de API pública — as outras 11 telas que o usam continuam idênticas.

## Backend

### Endpoint reaproveitado

`GET /api/crm/leads` (mesma rota já existente em `hermes_agents/routes/crm.py`) passa a aceitar querystring opcional. Se nenhum parâmetro novo vier, comportamento atual se mantém (retrocompatibilidade — nenhuma outra tela é afetada, já que só a tabela `leads` ganha esse branch).

Parâmetros:

| Param | Tipo | Descrição |
|---|---|---|
| `page` | int | Página, 1-based. Default 1. |
| `page_size` | int | 25, 50 ou 100. Default 25. |
| `sort` | string | Whitelist fixa: `id`, `valor_potencial`, `status`, `funil_etapa`. Default `id`. |
| `order` | string | `asc` ou `desc`. Default `desc`. |
| `status` | string | Filtro exato (`novo`, `contatado`, `qualificado`, `convertido`, `perdido`). |
| `funil_etapa` | string | Filtro exato (uma das 6 etapas). |
| `origem` | string | Filtro `ILIKE %valor%`. |
| `empresa_id` | int | Filtro exato. |
| `com_telefone` | `true`\|`false` | `true` → `telefone IS NOT NULL AND telefone <> ''`; `false` → o inverso. |
| `q` | string | Busca livre em `nome`, `email`, `telefone`, `origem` (ILIKE, OR). |
| `export` | `true` | Ignora paginação, aplica filtros/ordenação, cap de 5000 linhas. |

Todos os valores de filtro e `sort`/`order` são validados contra whitelist/regex antes de entrar na query (mesma prática de `CRM_COLUNAS` já usada no arquivo, sem interpolação de valor do usuário direto no SQL — só os identificadores de coluna vêm de whitelist fixa, valores continuam parametrizados `$1, $2...`).

### Nova função `core/crm.py`

`listar_leads_filtrado(page, page_size, sort, order, filtros, export=False) -> dict` — monta `WHERE` dinâmico a partir dos filtros presentes, roda `COUNT(*)` (para `meta.total`) e o `SELECT ... LIMIT/OFFSET` (ou sem limite, capado em 5000, quando `export=True`). Fica ao lado de `_list`/`list`, sem alterá-las — as outras 7 tabelas do CRM continuam chamando o `list(tabela)` genérico como hoje.

### Resposta

```json
{
  "data": [...],
  "meta": { "total": 137, "page": 1, "page_size": 25, "pages": 6 }
}
```

Segue o envelope `{ success, data, error, meta: { total, page, limit } }` já convencionado no projeto.

### Rota (`routes/crm.py`)

`crm_list` ganha um branch: se `tabela == "leads"` e a querystring tiver qualquer um dos parâmetros acima, chama `listar_leads_filtrado`; senão, cai no `crm_list_fn(tabela)` atual. Nenhuma rota nova é criada.

## Frontend

### Componente novo: `web/src/app/crm/leads/_components/LeadsPanel.tsx`

Substitui o uso de `CrudPanel` na página de Leads. Não é genérico — é específico dessa tela.

### Extração de baixo risco em `CrudPanel.tsx`

O modal de criar/editar (JSX das linhas ~238-272 do `CrudPanel.tsx` atual) vira um subcomponente `CrudFormModal` (mesmo arquivo ou `_components/CrudFormModal.tsx`), recebendo `formFields`, `formData`, `onChange`, `onSave`, `onClose`, `mode`. `CrudPanel` passa a renderizar `<CrudFormModal .../>` internamente — API pública e comportamento de `CrudPanel` não mudam; é refatoração interna, coberta pelo fato de as 12 telas continuarem chamando `CrudPanel` do mesmo jeito. `LeadsPanel` reusa esse mesmo `CrudFormModal` para não duplicar o formulário de criar/editar lead.

### Estado e dados

`LeadsPanel` mantém seu próprio `fetchData` chamando o novo endpoint com os params atuais (`page`, `page_size`, `sort`, `order`, filtros, `q`). Debounce de 300ms em `q` e no filtro de `origem` antes de refazer o fetch. Os demais filtros (selects, toggle) disparam fetch imediato ao mudar.

### UI

- **Barra de filtros** acima da tabela: dropdown Status, dropdown Etapa do funil, dropdown Empresa (reaproveita o `useEffect` que já busca `api.crmList("empresas")` na página atual), input Origem (contém), toggle 3 estados Telefone (qualquer / com / sem), input Busca (nome/email/telefone/origem — substitui a busca client-side atual). Botão "Limpar filtros".
- **Tabela**: cabeçalhos de Valor potencial, Status e Data (ID) clicáveis, com ícone de seta indicando direção ativa. Demais colunas (Nome, Empresa, E-mail, Telefone, Origem, Etapa) sem sort, mesmo visual atual.
- **Paginação**: rodapé com "Mostrando X–Y de Z", seletor de itens por página (25/50/100), botões Anterior/Próxima (desabilitados nos extremos).
- **Exportar CSV**: botão no cabeçalho da barra de ações (ao lado de "Novo"). Chama o endpoint com `export=true` + filtros/ordenação atuais, monta CSV client-side (sem lib nova — join manual com escape de vírgula/aspas) e dispara download via `Blob` + `<a download>`. Nome do arquivo: `leads_AAAA-MM-DD.csv`.

### Estados de erro/loading

Mesmo padrão visual já usado no `CrudPanel` (skeleton de linhas, banner de erro vermelho). Erro do export (ex.: falha de rede) mostra alerta simples, sem travar a tela.

## Fora de escopo

- Paginação/filtro/export nas outras 7 tabelas do CRM ou nas 4 telas de Cadastros — não fazem parte desta mudança.
- Exportação em Excel (.xlsx) — decidido CSV.
- Filtros salvos/persistência de estado entre sessões.

## Testes

- Backend: teste de `listar_leads_filtrado` cobrindo cada filtro isolado, combinação de filtros, ordenação em cada coluna da whitelist, paginação (página fora do intervalo retorna lista vazia com `meta.total` correto), `export=true` respeitando filtros e cap de 5000, e `sort`/`order` fora da whitelist (caem no default `id`/`desc` silenciosamente, nunca interpolam o valor bruto no SQL).
- Frontend: verificação manual via Playwright (browser real) cobrindo: aplicar cada filtro, ordenar por cada coluna, navegar páginas, trocar itens por página, exportar CSV com filtro ativo e conferir conteúdo baixado bate com o filtrado na tela.
