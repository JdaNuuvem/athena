# Produtos — hierarquia pai/filho do Bling na aba /produtos

**Data:** 2026-07-15
**Status:** Aprovado para implementação
**Supersede:** [2026-07-14-bling-produtos-completo-design.md](2026-07-14-bling-produtos-completo-design.md) (tabela `bling_produtos` separada — nunca implementada, descartada em favor de consolidar tudo em `catalogo_produtos`)

## Contexto

A aba `/produtos` (`web/src/app/produtos/page.tsx`) lista produtos de `catalogo_produtos` (tabela SSOT criada em
`hermes_agents/core/catalogo.py`, populada pelo sync do Bling em `hermes_agents/bling_erp.py::sincronizar_produtos()`).
Hoje a lista é achatada: produtos pai e produtos filho (variações) do Bling aparecem juntos, sem hierarquia,
com colunas SKU/Nome/Margem/Receita 30d/Vendidos/Lojas.

No Bling, um produto com variações (ex: cores diferentes) tem um produto pai (`formato: "V"`) e N produtos
filhos, cada um com `idProdutoPai` apontando pro pai. Produtos sem variação (avulsos) não têm pai nem filhos.
Isso já é usado por `bling_erp.py::listar_produtos_agrupados()`, mas essa função busca ao vivo direto no Bling
(não persiste, não é usada por nenhuma tela hoje) e é o modelo de referência para a lógica de agrupamento.

A página de detalhe `/produtos/[sku]` já tem uma aba "Variações" (`_components/VariacoesTab.tsx`), hoje 100%
mockada com dados fake — nunca foi conectada a dado real.

**Inconsistência encontrada (corrigir como parte deste trabalho):** `GET /api/produtos` (listagem) já lê de
`catalogo_produtos`, mas `GET /api/produtos/<sku>` (detalhe) ainda lê de `fichas_tecnicas`. Padronizar os dois
em `catalogo_produtos`.

## Decisões (validadas com o usuário)

1. **Hierarquia persistida no banco**, não buscada ao vivo no Bling a cada carregamento — rápido e não depende
   do Bling estar no ar.
2. **Colunas da lista principal:** substituem as atuais por `SKU`, `Nome`, `Valor` (Margem/Receita/Vendidos/Lojas
   saem da lista; continuam disponíveis na página de detalhe do produto).
3. **"Valor" do produto pai** = preço do próprio produto pai no Bling (não faixa de preço dos filhos).
4. **Lista principal mostra só produtos pai** (`sku_pai IS NULL`) — inclui avulsos (sem variação), que
   tecnicamente são "pai" sem filhos.
5. **Clique no produto pai** continua navegando para `/produtos/[sku]` (comportamento já existente) — a aba
   Variações passa a mostrar os filhos reais.
6. **Atributos de variação** (`Cor:Roxo`, etc.) são buscados mesmo com o risco de rate-limit do Bling (ver
   Sincronização, passo 3), com fallback silencioso quando falhar — não bloqueia o sync nem quebra a tela.

## Modelo de dados

Três colunas novas em `catalogo_produtos` (sem criar tabela nova):

```sql
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS id_bling BIGINT;
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS sku_pai VARCHAR(50);
ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS atributo VARCHAR(200);
CREATE INDEX IF NOT EXISTS idx_catalogo_produtos_sku_pai ON catalogo_produtos (sku_pai);
```

- `id_bling`: ID interno do produto no Bling. Necessário porque `idProdutoPai` (vindo do Bling) é um ID
  numérico, não um SKU — precisamos resolver ID → SKU depois de sincronizar.
- `sku_pai`: SKU do produto pai. `NULL` = é pai ou avulso.
- `atributo`: string bruta `"Atributo:Valor"` (ex: `"Cor:Transparente"`) vinda de `variacao.nome` do Bling,
  preenchida só em produtos filhos quando a busca do passo 3 tiver sucesso.

Adicionar `_ensure_tables()` em `core/catalogo.py` para rodar esses `ALTER TABLE ... IF NOT EXISTS` (mesmo
padrão já usado ali para a criação da tabela).

## Sincronização (`sincronizar_produtos()` em `bling_erp.py`)

**Passo 1 — sync base (como já existe hoje, estendido):** percorre as páginas de `/produtos`, upsert em
`fichas_tecnicas`, `catalogo_produtos` (agora gravando `id_bling`) e `anuncios`. Durante a iteração, mantém em
memória um mapa `{id_bling: sku}` de tudo que foi visto (todas as páginas).

**Passo 2 — resolver hierarquia:** depois que todas as páginas foram processadas, para cada produto que tinha
`idProdutoPai` no Bling, resolve o SKU do pai usando o mapa da passada 1 (se o pai não apareceu em nenhuma
página — caso raro — fica sem `sku_pai` resolvido e o produto aparece como avulso; não é tratado como erro
fatal). Faz `UPDATE catalogo_produtos SET sku_pai = ? WHERE sku = ?` para cada filho resolvido.

**Passo 3 — buscar atributos dos filhos:** para cada produto identificado como pai com variação
(`formato == "V"`), faz **uma chamada extra** `GET /produtos/{id}` no Bling para pegar `variacoes[]` (contém
`variacao.nome` por filho). Grava em `atributo` de cada filho correspondente via
`UPDATE catalogo_produtos SET atributo = ? WHERE sku = ?`.
- Retry com backoff simples em erro 429 (até 2 tentativas extras, espera crescente entre elas).
- Falha em um produto pai específico (mesmo após retry) só é registrada em `erros` — não interrompe o
  processamento dos demais produtos pai.

O retorno de `sincronizar_produtos()` ganha `pais_resolvidos` e `atributos_buscados` nas estatísticas, além do
`sincronizados`/`erros` já existentes.

## Backend — endpoints

- `GET /api/produtos`: WHERE passa a incluir `c.sku_pai IS NULL`. Resposta troca `margem_pct`/`receita_30d`/
  `vendidos_30d` por `valor` (de `anuncios.preco` WHERE `marketplace='bling'`) e `total_variacoes` (contagem de
  filhos via `COUNT(*) FROM catalogo_produtos WHERE sku_pai = c.sku`).
- `GET /api/produtos/<sku>`: passa a consultar `catalogo_produtos` em vez de `fichas_tecnicas` (resolve a
  inconsistência do Contexto). Resposta ganha `variacoes: [{sku, nome, valor, atributo}]` com os filhos
  (`WHERE sku_pai = <sku>`).

## Frontend

**`web/src/app/produtos/page.tsx`:**
- Tabela passa a ter só `SKU`, `Nome`, `Valor`.
- Badge ao lado do nome (ex: "6 variações") quando `total_variacoes > 0`.
- Tipo `Product` em `web/src/lib/types/domain.ts` atualizado: remove `margem_pct`/`receita_30d`/`vendidos_30d`/
  `estoque_lojas`/`total_lojas`, adiciona `valor: number` e `total_variacoes: number`.

**`web/src/app/produtos/[sku]/_components/VariacoesTab.tsx`:**
- Remove os dados mockados (`variacoesMock`).
- Recebe `variacoes` como prop (vindo de `detalheProduto`, já carregado por `client.tsx`).
- Tabela de combinações usa os filhos reais: SKU, Nome, Preço (Estoque e Status ficam de fora nesta primeira
  versão — não há dado de estoque sincronizado por SKU hoje; fica para uma iteração futura se for pedido).
- Grid de "Atributos Variáveis" no topo: agrupa os valores distintos de `atributo` parseando `"Nome:Valor"` de
  todos os filhos. Se nenhum filho tiver `atributo` preenchido (rate-limit do passo 3 falhou pra esse produto),
  o grid inteiro não aparece — sem erro na tela.
- Produto sem variações (`variacoes.length === 0`): aba mostra uma mensagem simples "Este produto não tem
  variações cadastradas no Bling", sem tabela vazia.

## Fora de escopo (fica para specs futuros)

- **Sync automático/agendado.** Hoje o sync só roda quando alguém clica em "Sync Bling". Um agendador
  (cron/scheduler) para rodar sozinho periodicamente é um sub-projeto separado.
- **Edição no nosso sistema com envio de volta pro Bling (push).** Hoje o fluxo é só Bling → nosso banco
  (leitura). Editar um produto na nossa interface e mandar a atualização pro Bling via `PUT /produtos/{id}` é
  um sub-projeto separado, com decisões próprias sobre conflito de edição concorrente, quais campos são
  editáveis localmente, e tratamento de erro quando o Bling rejeitar a atualização.
- **Consolidação da página `/integracoes/bling`** para usar `catalogo_produtos` em vez do passthrough direto
  que tem hoje — decidido como direção (ver Supersede acima), mas a implementação dessa página fica para
  quando ela for trabalhada de novo.
- Estoque por variação na aba Variações (ver nota acima).
