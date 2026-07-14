# Bling — Aba de Produtos completa (busca, filtros, dados completos)

**Data:** 2026-07-14
**Status:** Aprovado para implementação

## Contexto

A aba de Produtos da integração Bling (`web/src/app/integracoes/bling/_components/BlingProductsTab.tsx`) hoje só
lista produtos paginados (sem busca/filtros) e exibe apenas: imagem, SKU, nome, preço, estoque, status. O tipo
`BlingProduto` (`web/src/lib/api.ts`) só tipa `id, codigo, descricao, preco, situacao` — o resto é `[key: string]:
unknown`. O formulário de criação/edição (`ProductFormModal.tsx`) só tem SKU, nome, preço, situação.

O backend (`hermes_agents/bling_erp.py: listar_produtos`) é um passthrough direto para `GET /produtos` da API
Bling v3, só repassando `pagina`/`limite`. A listagem resumida do Bling não traz categoria, marca, NCM, GTIN,
peso/dimensões, estoque mínimo, fornecedor etc. — isso só vem no detalhe (`GET /produtos/{id}`), um endpoint por
produto.

**Bug encontrado (corrigir independente do resto):** `deletarBlingProduto` e `sincronizarBlingProdutos` em
`api.ts` usam `` `\api\bling\produtos\...` `` (barras invertidas literais) em vez de `/api/...`.

## Decisões (validadas com o usuário)

1. **Fonte de dados: cache local sincronizado.** A sincronização busca o detalhe completo de cada produto e
   persiste numa tabela local. Listagem e filtros rodam contra o banco local — rápido, sem rate limit do Bling,
   suporta qualquer combinação de filtros.
2. **Volume: 200–1000 produtos.** Sync completo (detalhe por produto) é aceitável rodando em background com
   throttle e barra de progresso; não precisa de sync incremental nesta fase.
3. **Layout: tabela enxuta + painel de detalhe.** A tabela mantém colunas essenciais; um drawer lateral abre ao
   clicar na linha com todos os campos completos, editável.
4. **Filtros:** busca textual (nome/SKU), período de datas (criação), faixa de estoque, faixa de preço, status
   (ativo/inativo), categoria, atalho "estoque baixo" (estoque atual < estoque mínimo).

## Modelo de dados

Nova tabela `bling_produtos` (Postgres, mesmo banco de `fichas_tecnicas`/`anuncios`):

```sql
CREATE TABLE bling_produtos (
  id_bling BIGINT PRIMARY KEY,
  codigo TEXT NOT NULL,
  nome TEXT NOT NULL,
  tipo TEXT, formato TEXT, situacao TEXT,
  preco NUMERIC, preco_custo NUMERIC,
  categoria_id BIGINT, categoria_nome TEXT,
  marca TEXT, unidade TEXT,
  gtin TEXT, ncm TEXT,
  peso_liquido NUMERIC, peso_bruto NUMERIC,
  largura NUMERIC, altura NUMERIC, profundidade NUMERIC,
  estoque_atual NUMERIC, estoque_minimo NUMERIC, estoque_maximo NUMERIC,
  imagem_url TEXT,
  descricao_curta TEXT, descricao_complementar TEXT,
  fornecedor_nome TEXT,
  data_criacao TIMESTAMPTZ, data_alteracao TIMESTAMPTZ,
  sincronizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_bling_produtos_nome ON bling_produtos (nome);
CREATE INDEX idx_bling_produtos_categoria ON bling_produtos (categoria_id);
CREATE INDEX idx_bling_produtos_situacao ON bling_produtos (situacao);
CREATE INDEX idx_bling_produtos_estoque ON bling_produtos (estoque_atual);
```

Campos ausentes na resposta do Bling para um produto específico ficam `NULL` e a UI exibe "—". Nenhum campo é
obrigatório além de `id_bling`, `codigo`, `nome`.

## Sincronização

`sincronizar_produtos()` passa a:
1. Listar produtos via `GET /produtos` (paginado, como hoje).
2. Para cada produto, buscar detalhe completo via `GET /produtos/{id}`, respeitando throttle (~3 req/s, dentro
   do rate limit do Bling v3).
3. Fazer upsert em `bling_produtos` (`INSERT ... ON CONFLICT (id_bling) DO UPDATE`).

Roda em background (thread), sem bloquear a resposta HTTP. Novo endpoint `GET /bling/produtos/sincronizar/status`
retorna `{ em_andamento, processados, total }` para a UI fazer polling e mostrar barra de progresso. Sync
incremental (via `dataAlteracaoInicial`) fica fora de escopo — a coluna `data_alteracao` já fica pronta para isso
no futuro.

## Backend — endpoints

- `GET /bling/produtos` — passa a ler a tabela local. Aceita query params:
  `busca` (nome ou SKU, `ILIKE`), `situacao`, `categoria_id`, `preco_min`, `preco_max`, `estoque_min`,
  `estoque_max`, `estoque_baixo` (bool — `estoque_atual < estoque_minimo`), `data_de`, `data_ate` (sobre
  `data_criacao`), `pagina`, `limite`, `ordenar_por` (`nome|preco|estoque|data_criacao`, default `nome`).
- `POST /bling/produtos`, `PUT /bling/produtos/{id}`, `DELETE /bling/produtos/{id}` — continuam batendo direto no
  Bling (como hoje); após sucesso, atualizam/removem a linha correspondente em `bling_produtos`.
- `GET /bling/produtos/categorias` — lista categorias distintas presentes em `bling_produtos`, para popular o
  select de filtro.
- `POST /bling/produtos/sincronizar` — dispara sync em background (retorna imediatamente).
- `GET /bling/produtos/sincronizar/status` — status do sync em andamento.

## Frontend

**`BlingProductsTab.tsx`:**
- Barra de filtros acima da tabela: busca textual (debounce 300ms), select de status, select de categoria, faixa
  de preço (min/max), faixa de estoque (min/max), toggle "só estoque baixo", período de datas de criação, botão
  "Limpar filtros". Filtros vão como query params na chamada de listagem.
- Tabela mantém: imagem, SKU, nome, categoria, preço, estoque (cores já existentes), status, data de criação —
  e os controles de estoque rápido (+/−) e seleção em lote já existentes.
- Clicar na linha (fora dos controles de ação) abre um drawer lateral com o detalhe completo do produto.
- Barra de progresso durante sincronização, via polling no novo endpoint de status.
- Corrige o bug das barras invertidas em `deletarBlingProduto`/`sincronizarBlingProdutos`.

**`ProductFormModal.tsx` → reaproveitado como painel de detalhe/edição:**
- Ganha os campos novos: categoria, marca, unidade, GTIN, NCM, peso líquido/bruto, largura/altura/profundidade,
  estoque mínimo/máximo, fornecedor, descrição complementar.
- Campos somente-leitura quando vêm do Bling e não fazem sentido editar localmente antes de mandar pro Bling
  (ex: `data_criacao`, `data_alteracao`, `sincronizado_em`).

**`web/src/lib/api.ts`:**
- `BlingProduto` ganha os campos tipados novos (mantendo `[key: string]: unknown` como fallback).
- `listarBlingProdutos` ganha parâmetro de filtros (objeto) serializado como query string.
- Novas funções: `listarBlingCategorias`, `statusSincronizacaoBlingProdutos`.

## Fora de escopo

- Sync incremental (por enquanto sync é sempre completo).
- Edição de imagens/mídia do produto (fica somente leitura no drawer).
- Filtro por fornecedor (não pedido; pode ser adicionado depois seguindo o mesmo padrão).
