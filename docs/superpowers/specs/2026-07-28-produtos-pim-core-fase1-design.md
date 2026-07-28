# Produtos — PIM Core Fase 1 (normalização de identificação)

**Data:** 2026-07-28
**Status:** Aprovado para implementação
**Relacionado:** [2026-07-15-produtos-hierarquia-pai-filho-design.md](2026-07-15-produtos-hierarquia-pai-filho-design.md) (hierarquia pai/filho de variação já implementada em `catalogo_produtos`)

## Contexto

Pedido original do usuário: transformar o módulo de Produtos num PIM/ERP completo — multiempresa, multiloja,
variações, kits, produção, fiscal completo, marketplace, mídia, importação em massa, auditoria, RBAC granular,
APIs versionadas, performance, testes. Escopo grande demais para um spec só (~14 subsistemas independentes).

Decompomos em fases sequenciais, cada uma com seu próprio ciclo spec → plano → implementação:

1. **PIM Core** (este documento) — identificação, organização, normalização
2. Estoque nativo multi-loja/depósito
3. Preços (múltiplas tabelas, custo, margem)
4. Fiscal (NCM/CFOP/CST/CSOSN/alíquotas) + emissão NF-e via Bling
5. Variações (extensão da hierarquia pai/filho já existente)
6. Fornecedores por produto
7. Mídia (galeria de imagens/vídeos/docs)
8. Kits/Combos/BOM produção
9. Duplicação inteligente
10. Importação em massa (CSV/Excel/XML/API)
11. Marketplace por canal + SEO
12. API pública versionada + OpenAPI
13. Performance (cache, busca full-text, filas)

Auditoria e RBAC não são fases separadas — são infraestrutura que já existe (`core/seguranca.py`,
`core/rbac.py`) e cada fase apenas se conecta a ela.

**Descoberta que mudou o plano inicial:** o módulo já não é greenfield. `core/catalogo.py` já implementa
`catalogo_produtos` como "Catalogo SSOT — Fonte única de verdade para Produtos", populada por sync do Bling
(`bling_erp.py::sincronizar_produtos()`) e consumida por **17 arquivos**: `core/estoque.py`,
`core/estoque_aprovacoes.py`, `core/estoque_contagem.py`, `core/estoque_transferencias.py`, `core/pdv.py`,
`core/bi.py`, `core/relatorios.py`, `core/repositories_postgres.py`, `core/entidades.py`, `routes/estoque.py`,
`routes/shopee.py`, `shopee/kits.py`, `shopee/pricing.py`, `shopee/regras/produto_parado.py`,
`shopee/replication.py`, `athena_bridge.py`, `bling_erp.py`. Já tem SKU, NCM/CEST/CFOP padrão, categoria/marca
(texto livre), dimensões, imagens (JSONB), fornecedor, preço custo/venda, estoque mín/máx, localização,
hierarquia pai/filho de variação (`sku_pai`/`atributo`/`id_bling`), estrutura JSONB (BOM), `variacoes_detalhe`
JSONB, `campos_customizados` JSONB.

**Decisão de arquitetura registrada (não implementada nesta fase):** o usuário decidiu que o PIM nativo deve
virar fonte de verdade, com o Bling passando a satélite — usado só para emissão de nota fiscal. Isso inverte o
fluxo atual (hoje é só leitura Bling → nosso banco, conforme registrado no spec de 07-15). A implementação dessa
inversão (write-back pro Bling, resolução de conflito de edição concorrente, etc.) fica para a fase Fiscal
(#4), não para o Core.

## Decisões (validadas com o usuário)

1. **Evoluir `catalogo_produtos` in-place.** Sem tabela paralela (`produtos_v2`), sem migração dos 17 arquivos
   dependentes. Todas as mudanças desta fase são aditivas (novas colunas/tabelas), nada é removido ou renomeado.
2. **Classificação comercial via nova coluna `classificacao`** (`simples` | `variavel` | `kit` | `combo`) —
   **não reaproveita** a coluna `tipo` existente, que já é usada por `core/producao.py` para classificação de
   produção (`materia_prima` | `semiacabado` | `acabado`). Reaproveitar quebraria o módulo de produção.
3. **`classificacao = 'kit'` ou `'combo'` só cadastra o tipo agora** — o construtor de composição (itens do
   kit, quantidade, obrigatório/opcional, preço automático) é a fase #8 (Kits/BOM), fora de escopo aqui.
4. **Marca, Fabricante e Categoria viram tabelas normalizadas**, porque o usuário confirmou que fabricante pode
   divergir de marca (marca própria fabricada por terceiro) — não dá para assumir fabricante == marca.
   Categoria/Subcategoria usa hierarquia self-referencing (`categoria_pai_id`), como já pedido no escopo
   original.
5. **Colunas de texto livre existentes (`marca`, `categoria`) não são removidas nesta fase.** Ficam como estão;
   os novos campos `*_id` convivem com elas. Remover as colunas antigas exigiria auditar todo consumidor que já
   lê `.marca`/`.categoria` direto — fora de escopo, fica registrado como dívida técnica para quando as fases
   de Preços/Fiscal tocarem nesses módulos de novo.
6. **Tags são N:N novo** — não existe hoje nenhuma estrutura de tag em `catalogo_produtos`.
7. **Auditoria e RBAC reaproveitam infraestrutura existente**, sem tabela nova: `core/seguranca.py::auditar_alteracao()`/`auditar_exclusao()` (grava em `audit_log`, já genérica) e `core/rbac.py::requer_permissao()`.

## Modelo de dados

**Novas colunas em `catalogo_produtos`:**

```sql
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS classificacao VARCHAR(20) DEFAULT 'simples';
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS nome VARCHAR(300);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS nome_reduzido VARCHAR(100);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS nome_impressao VARCHAR(100);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS codigo_interno VARCHAR(50);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS codigo_erp VARCHAR(50);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS ex_tipi VARCHAR(10);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS modelo VARCHAR(100);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS linha VARCHAR(100);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS colecao VARCHAR(100);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS marca_id INT;
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS fabricante_id INT;
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS categoria_id_norm INT;
```

**Tabelas novas:**

```sql
CREATE TABLE IF NOT EXISTS catalogo_marcas (
  id SERIAL PRIMARY KEY, nome VARCHAR(150) NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS catalogo_fabricantes (
  id SERIAL PRIMARY KEY, nome VARCHAR(150) NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS catalogo_categorias (
  id SERIAL PRIMARY KEY, nome VARCHAR(150) NOT NULL,
  categoria_pai_id INT REFERENCES catalogo_categorias(id),
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS catalogo_tags (
  id SERIAL PRIMARY KEY, nome VARCHAR(60) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS catalogo_produto_tags (
  produto_id INT REFERENCES catalogo_produtos(id) ON DELETE CASCADE,
  tag_id INT REFERENCES catalogo_tags(id) ON DELETE CASCADE,
  PRIMARY KEY (produto_id, tag_id)
);

ALTER TABLE catalogo_produtos ADD CONSTRAINT fk_catalogo_marca FOREIGN KEY (marca_id) REFERENCES catalogo_marcas(id);
ALTER TABLE catalogo_produtos ADD CONSTRAINT fk_catalogo_fabricante FOREIGN KEY (fabricante_id) REFERENCES catalogo_fabricantes(id);
ALTER TABLE catalogo_produtos ADD CONSTRAINT fk_catalogo_categoria FOREIGN KEY (categoria_id_norm) REFERENCES catalogo_categorias(id);
```

Seguindo o padrão existente em `core/catalogo.py::_ensure_tables()` (idempotente, `IF NOT EXISTS`, chamado no
import do módulo).

## Migração de dados existentes

Na primeira execução após o deploy (dentro de `_ensure_tables()`, guardada por
`SELECT COUNT(*) FROM catalogo_marcas` — só roda a migração se a tabela estiver vazia, mesmo padrão de seed
condicional já usado em `core/cadastros.py`):

1. `SELECT DISTINCT marca FROM catalogo_produtos WHERE marca IS NOT NULL AND marca != ''` → insere em
   `catalogo_marcas` (dedup via `ON CONFLICT (nome) DO NOTHING`), depois
   `UPDATE catalogo_produtos SET marca_id = (SELECT id FROM catalogo_marcas WHERE nome = catalogo_produtos.marca)`.
2. Mesmo padrão para `categoria` → `catalogo_categorias` (sem hierarquia nesta migração — tudo entra como
   categoria raiz, `categoria_pai_id = NULL`; organizar em subcategorias é trabalho manual do usuário depois).
3. `fabricante` não migra nada (coluna não existia antes) — tabela começa vazia, populada pelo cadastro daqui
   pra frente.

Migração não apaga nem sobrescreve as colunas de texto originais.

## Backend — API

Novo blueprint `hermes_agents/routes/produtos.py` (`/api/produtos`), seguindo o padrão de
`routes/cadastros.py`:

- `GET /api/produtos` — lista (já existe, mantido como está — lê `catalogo_produtos`).
- `GET /api/produtos/<sku>` — detalhe (já existe, mantido).
- `POST /api/produtos` — criar (já existe via `criar()` em `core/catalogo.py`; passa a chamar
  `auditar_alteracao("criar", "produtos", "catalogo_produtos", id, dados_depois=...)` e exigir
  `requer_permissao("produtos.criar")`).
- `PUT /api/produtos/<id>` — editar (mesmo padrão, `produtos.editar`, audita antes/depois).
- `DELETE /api/produtos/<id>` — excluir (`produtos.excluir`, audita).
- `GET/POST /api/produtos/marcas`, `/fabricantes`, `/categorias`, `/tags` — CRUD simples das tabelas de apoio
  (`produtos.visualizar` para GET, `produtos.editar` para POST).
- `POST /api/produtos/<id>/tags` / `DELETE /api/produtos/<id>/tags/<tag_id>` — vincular/desvincular tag.

Novas permissões RBAC (registradas onde as demais já são definidas, ex.: seed em `core/cadastros.py` ou
equivalente para o módulo produtos): `produtos.visualizar`, `produtos.criar`, `produtos.editar`,
`produtos.excluir`, `produtos.duplicar` (reservada, sem uso nesta fase), `produtos.alterar_preco` (reservada),
`produtos.alterar_fiscal` (reservada).

## Frontend

- `web/src/app/produtos/[sku]/_components/CadastroTab.tsx`: ganha os campos novos (nome, nome reduzido, nome
  impressão, código interno, código ERP, EX TIPI, modelo, linha, coleção, classificação, marca — select com
  opção de criar nova —, fabricante — idem —, categoria — select hierárquico —, tags — multi-select com opção
  de criar).
- Novo componente compartilhado de "select com criação inline" (usado pelos três selects de marca/fabricante/
  categoria) — evita triplicar a mesma lógica de "buscar, ou criar se não existir".

## Compatibilidade

`buscar_por_sku_ou_criar()` (usada pelo sync do Bling e por outros módulos para resolver/criar produto por SKU)
mantém a assinatura atual. Nenhum dos 17 arquivos dependentes precisa de alteração nesta fase — todos continuam
lendo as colunas que já usavam.

## Testes

- Unitário: CRUD de `catalogo_marcas`/`catalogo_fabricantes`/`catalogo_categorias`/`catalogo_tags`.
- Unitário: migração de dedup (`marca` texto → `catalogo_marcas` + `marca_id`) não perde produto nem duplica
  marca quando há capitalização/espaços diferentes (ex.: `"Nike"` vs `"nike "`).
- Integração: criar produto sem permissão `produtos.criar` retorna 403; criar com permissão grava linha em
  `audit_log` com `dados_depois` correto.
- Integração: editar produto grava `dados_antes`/`dados_depois` corretos em `audit_log`.
- Regressão: após a migração, `core/estoque.py`, `core/pdv.py` e `shopee/pricing.py` (os três consumidores mais
  sensíveis de `catalogo_produtos`) continuam com os testes existentes passando sem alteração.

## Fora de escopo (fica para fases futuras)

- Inversão do fluxo de sync com o Bling (Athena como fonte de verdade, Bling como satélite de NF-e) — decisão
  registrada acima, implementação na fase Fiscal (#4).
- Remoção das colunas de texto livre `marca`/`categoria` — dívida técnica registrada, sem prazo.
- Estoque por loja/depósito, preços/margem, fiscal completo, mídia em galeria, kit/BOM funcional, duplicação,
  importação em massa, marketplace por canal, SEO, API pública versionada, performance — cada um é uma fase
  própria já listada no Contexto.
