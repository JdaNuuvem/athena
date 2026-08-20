# Módulo Bling — Design

**Data:** 2026-08-20
**Status:** Aprovado para plano de implementação

## Contexto

A integração Bling hoje vive só em `web/src/app/integracoes/bling/page.tsx`, uma tela com
abas (Dashboard/Produtos/Vendas/Pedidos/Financeiro/Config), cobrindo produtos, pedidos de
venda, contatos, categorias, contas a pagar/receber, NF-e, formas de pagamento, depósitos,
estoque, webhooks e notificações.

Levantamento do estado atual (2026-08-20) encontrou:
- Duas gerações de rotas HTTP coexistindo (`integrations_bp` legado + `bling_bp` novo) para
  as mesmas operações.
- Duas implementações divergentes de sync de pedidos de venda: `bling_erp.sincronizar_pedidos()`
  (grava só em `vendas`, tabela legada, e tem bug — é chamada com argumentos `pagina`/`limite`
  que sua assinatura não aceita, gerando `TypeError`) vs `core.vendas.sincronizar_pedidos_bling()`
  (SSOT completo em `vendas_pedidos`/`vendas_itens`/`vendas_pagamentos`).
- Scheduler com quase todos os jobs Bling comentados/desativados — só sync de contatos roda
  automático hoje.
- `core/bling_logger.py` praticamente código morto.
- Três endpoints de webhook de pedido coexistindo sem clareza de qual está registrado em
  produção no Bling.

O pedido agora é expandir a integração para um módulo completo e dedicado no menu principal,
cobrindo também recursos da API Bling v3 ainda não implementados: pedidos de compra,
situações (status customizados), lojas/canais de venda do Bling, NFC-e, NFS-e, contas
contábeis e ambiente de homologação. Ao mesmo tempo, a reforma resolve as inconsistências
acima em vez de empilhar mais código sobre elas.

## Objetivo

Substituir a tela `/integracoes/bling` por um módulo "Bling" no menu principal, com submenu
lateral, cobrindo os recursos existentes consolidados (sem duplicidade) mais os 7 recursos
novos solicitados.

## Fora de escopo

- Físicas/lojas físicas (adiado em decisão anterior do usuário, não relacionado).
- CRUD completo de propostas comerciais, ordens de produção e contratos Bling — não pedidos
  pelo usuário nesta rodada.
- Reescrita do módulo Shopee ou qualquer outra integração — este documento cobre só Bling.

## Navegação

Item "Bling" no menu principal, expansível em submenu:

```
Bling
├── Dashboard          /bling                  (visão geral: status conexão, KPIs de sync)
├── Produtos           /bling/produtos          (existente, mantido)
├── Pedidos de Venda   /bling/pedidos-venda     (existente, sync consolidado)
├── Pedidos de Compra  /bling/pedidos-compra    (novo)
├── Situações          /bling/situacoes         (novo, CRUD)
├── Lojas/Canais       /bling/canais            (novo)
├── Financeiro         /bling/financeiro        (contas a pagar/receber, existente)
├── Notas Fiscais      /bling/notas             (NF-e existente + NFC-e + NFS-e novos, abas internas por tipo)
├── Contas Contábeis   /bling/plano-contas      (novo, sincroniza com fin_plano_contas existente)
└── Configurações      /bling/config            (credenciais, toggle homologação/produção, webhooks)
```

`/integracoes/bling` é removida. `/integracoes` (visão geral de todas as integrações) passa a
conter só um card de status ("conectado"/"desconectado", último sync) linkando para `/bling`.

## Backend

### Consolidação de rotas

- `bling_bp` (prefixo `/api/bling`) passa a ser o único blueprint Bling. As rotas equivalentes
  em `integrations_bp` (`/api/bling/auth`, `/status`, `/sync`, `/products`, `/orders`, etc —
  a geração antiga listada no levantamento) são removidas.
- `routes/webhooks.py` mantém um único endpoint de webhook de pedido: `/webhook/bling`
  (o que já valida HMAC e roteia por tipo de evento). `/webhook/bling/pedido` e
  `/webhook/bling/pedido/v2` são removidos após confirmar nos logs/Bling qual está de fato
  cadastrado como callback ativo — se nenhum dos dois estiver registrado no painel Bling em
  produção, remoção é direta; se um estiver, seu comportamento é portado para o endpoint único
  antes da remoção.

### Sync de pedidos de venda

- Única implementação: `core.vendas.sincronizar_pedidos_bling()`. `bling_erp.sincronizar_pedidos()`
  e toda referência a ela (rotas, `migrar_tudo()`) são removidas ou redirecionadas para a
  função SSOT.
- Isso corrige o bug de assinatura (`TypeError` em `api_sincronizar_pedidos` e `migrar_tudo`)
  como efeito colateral da consolidação, não como patch isolado.

### Pedidos de compra (novo)

- Tabelas novas `compras_pedidos` / `compras_itens`, espelhando o padrão SSOT de
  `vendas_pedidos`/`vendas_itens` (mesmo formato de colunas onde fizer sentido: fornecedor em
  vez de cliente, sem vendedor/transportadora se a API não expuser equivalente para compra).
- Sync via `pedidos/compras` (GET listagem + GET detalhe) e ação de recebimento via
  `pedidos/compras/{id}/receber` (endpoint já mapeado no levantamento anterior, hoje sem uso).
- Rota `/api/bling/pedidos-compra` (GET listar, GET detalhar, POST sincronizar, POST
  `{id}/receber`).

### Situações (novo, CRUD)

- Tabela `bling_situacoes` como cache local (id_bling, nome, cor, modulo — pedido/NF/etc).
- CRUD completo propagando para o Bling via API (`situacoes` endpoints: GET listar, POST
  criar, PUT atualizar, DELETE remover), seguindo o mesmo padrão já usado para categorias
  (`bling_categorias`).
- Usada como filtro/referência nas telas de Pedidos de Venda, Pedidos de Compra e Notas
  Fiscais.

### Lojas/Canais Bling (novo)

- Tabela `bling_canais` (conceito interno do Bling — ex. "Loja Virtual", "Balcão" — distinto
  da tabela `lojas` do Athena, que já tem sentido próprio via `lojas.bling_id` mapeando
  depósitos). Não reaproveita `lojas`.
- Sync via endpoint de lojas/canais da API Bling v3.
- Rota `/api/bling/canais` (GET listar, POST sincronizar).

### NFC-e / NFS-e (novo)

- Estendem `core/fiscal.py` com sync análogo ao de NF-e (mesmo padrão de paginação em lotes
  usado para NF-e, que já existe por causa do timeout de proxy Cloudflare encontrado
  anteriormente).
- Gravam na tabela `fiscal_notas_fiscais` existente, com coluna nova `tipo_documento`
  (`'nfe'` | `'nfce'` | `'nfse'`) em vez de 3 tabelas paralelas. Migração adiciona a coluna com
  default `'nfe'` para preservar os registros já existentes.
- Rotas `/api/bling/nfce/sincronizar`, `/api/bling/nfse/sincronizar`; leitura via
  `/api/bling/notas?tipo=nfce|nfse|nfe`.

### Contas contábeis / plano de contas (novo)

- Sync do endpoint `contas/contabeis` da API Bling faz upsert em `fin_plano_contas`
  (tabela já existente no módulo financeiro, populada hoje com seed padrão).
- Migração adiciona coluna `bling_id` a `fin_plano_contas` para permitir upsert idempotente.
- Rota `/api/bling/plano-contas/sincronizar`.

### Homologação (novo)

- Config por instalação: `bling_ambiente` (`'producao'` | `'homologacao'`), persistida do
  mesmo jeito que client_id/tokens hoje (bucket `core.config`).
- Em homologação, a base URL da API Bling troca para o endpoint de sandbox e as operações de
  emissão de NF-e/NFC-e/sync não gravam nas tabelas de produção — usam as mesmas tabelas mas
  com uma coluna `ambiente` (`'producao'`/`'homologacao'`) nas tabelas fiscais afetadas
  (`fiscal_notas_fiscais`, `compras_pedidos`, `vendas_pedidos` quando a origem for sync Bling),
  e as telas do módulo Bling passam a filtrar por `ambiente = 'producao'` por padrão, com toggle
  visível para inspecionar dados de homologação.
- Trocar o toggle não afeta outras integrações (Shopee, etc), é escopado só ao Bling.

## Frontend

- Novo diretório `web/src/app/bling/` com layout próprio contendo o submenu lateral e uma
  página por sub-rota listada acima.
- Componentes hoje em `web/src/app/integracoes/bling/_components/` são movidos/adaptados para
  `web/src/app/bling/_components/`, reaproveitando o que já funciona (Dashboard, ProductsTab
  vira página própria, etc — não uma reescrita do zero das partes que já funcionam bem).
- `web/src/lib/api.ts`: consolida as ~40 chamadas do bloco antigo + bloco v2 num único
  conjunto de funções, adiciona as novas para pedidos de compra, situações, canais, NFC-e,
  NFS-e, plano de contas.
- Menu principal (componente de navegação lateral do app) ganha entrada "Bling" com submenu
  expansível.

## Testes

TDD para cada sync novo, seguindo o padrão dos testes Bling já existentes
(`test_bling_erp.py`, `test_bling_routes.py`):
- Sync de pedidos de compra (RED: teste com API mockada retornando pedido de compra fake →
  GREEN: grava em `compras_pedidos`/`compras_itens`).
- CRUD de situações (RED → GREEN para create/update/delete, incluindo propagação pro Bling).
- Sync de canais.
- Sync de NFC-e/NFS-e (reaproveita fixtures de teste de NF-e existentes, adaptando
  `tipo_documento`).
- Sync de plano de contas.
- Toggle de homologação (teste que confirma troca de base URL e filtro por `ambiente`).
- Regressão: teste que confirma que a consolidação do sync de pedidos de venda não quebrou o
  fluxo SSOT existente, e que a rota antiga removida de fato não existe mais (ou responde 404).

## Migração de dados

- Nenhum dado de produção existente é perdido: tabelas novas são aditivas; colunas novas
  (`tipo_documento`, `bling_id` em `fin_plano_contas`, `ambiente`) têm defaults que preservam
  os registros atuais como estavam antes da mudança.
- Antes de remover as rotas antigas do `integrations_bp`, confirmar que nada externo (webhook
  registrado no painel Bling, ou automações via n8n) depende delas.

## Ordem de implementação sugerida (para o plano)

1. Consolidação backend (remove duplicidade de rotas/sync de pedidos) — resolve os bugs
   conhecidos primeiro, sem features novas, para isolar risco.
2. Recursos novos "de leitura simples": Lojas/Canais, Contas Contábeis (upsert em tabela já
   existente).
3. Recursos novos "com CRUD": Situações.
4. Recursos novos "com fluxo próprio": Pedidos de Compra, NFC-e, NFS-e.
5. Homologação (depende dos recursos fiscais já estarem com a coluna `ambiente`).
6. Frontend: layout do módulo + submenu + páginas migradas/novas.
7. Remoção da tela antiga `/integracoes/bling` e ajuste do card em `/integracoes`.
