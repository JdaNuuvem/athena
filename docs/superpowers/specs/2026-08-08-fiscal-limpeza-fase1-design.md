# Fiscal — Limpeza e Fundação Real (Fase 1 de 3)

**Data:** 2026-08-08

## Contexto

`/fiscal` hoje mistura dado real com dado fabricado disfarçado de real, e tem andaime morto de features que nunca foram construídas. Investigação completa (código + conversa com o usuário) estabeleceu o quadro real do negócio, que o código sozinho não deixava claro:

- **Saída Virtual** (lojas online, integradas via Bling): Bling emite a NF-e/NFC-e junto à SEFAZ de verdade. O Hermes já sincroniza isso com solidez — nota, itens, impostos, XML, DANFE (`/fiscal/notas`, `core/fiscal.py::sincronizar_notas_fiscais_bling`/`sincronizar_uma_nota_fiscal`). Bling **não é usado nas lojas físicas**.
- **Saída Física** (vendas no PDV): o documento fiscal (NFCe/cupom) sai na hora, mas por um sistema/equipamento **fora do Hermes**. A tabela `pdv_nfce` existe no schema mas nunca é populada — o PDV do Hermes não tem nenhuma visão real do que foi emitido fiscalmente numa venda física.
- **Entrada** (compras, todas as lojas): nota física em papel, digitada manualmente pelo contador direto no i9Logic. Não passa pelo Hermes hoje (existe `compras_notas_entrada` no módulo Compras, mas preso a um pedido de compra formal, sem nenhuma ligação com o módulo Fiscal).
- **i9Logic**: sistema do escritório de contabilidade terceirizado, onde a apuração fiscal oficial de verdade acontece. O Hermes já tem uma role "Contador" cadastrada no RBAC (`fiscal.ver/criar/editar/exportar`) sem nenhuma tela pensada para ela.

Diante disso, `/fiscal` como está hoje tem três problemas concretos:

1. **Dado fabricado disfarçado de real**: `fiscal_tributos` é seed de alíquota genérica de mercado (ICMS 18%, PIS 1.65%...), não a alíquota real da empresa. `fiscal_obrigacoes` é um calendário de vencimentos calculado uma única vez no primeiro boot (`hoje() + N dias` no momento do seed) — nunca mais recalculado, hoje mostra datas relativas a um deploy passado, não ao mês corrente.
2. **Andaime morto**: `certificado_digital`/`csc_nfce`/`token_fiscal`/`serie_nfe`/`serie_nfce`/`ambiente_fiscal` em `lojas.*` (aba Fiscal de `/lojas/[id]`) — nenhum consumidor real, porque não existe emissão própria (nem física nem virtual passa por aqui). `pdv_nfce` — nunca populada, mesmo motivo. `fiscal_contas_receber_bling`/`fiscal_contas_pagar_bling` — órfãs, dados já migraram para `fin_contas_receber`/`fin_contas_pagar` há tempo (`core/entidades.py::migrar_contas_fiscal_para_financeiro`). `calcular_tributos_nota` — rota exposta, mas o próprio comentário no código confirma "não há nenhuma tela usando esse endpoint hoje", e a lógica é inutilizável (soma todos os tributos cegamente, sem distinguir regime/tipo de operação). `/fiscal/tabelas` (CFOP/NCM/CEST) não é catálogo de referência oficial — é só `SELECT DISTINCT` das suas próprias notas já sincronizadas, com NCM/CEST sempre com descrição vazia (hardcoded `'' as descricao` no SQL).
3. **Bugs ativos**: `/fiscal/tabelas` e `/fiscal/obrigacoes` fazem `fetch()` cru sem o header de autenticação que o resto do app injeta via `lib/api.ts` — a primeira provavelmente quebra em runtime (`.map is not a function` sobre um objeto de erro 403), a segunda falha silenciosamente (seção "Todas" sempre vazia, sem indicar erro).

Este é o **sub-projeto 1 de 3** do redesenho da área Fiscal. Estabelece uma fundação real e limpa antes de construir o Registro de Entrada (fase 2) e o Export de período para o contador (fase 3) — ambos dependem de dado limpo, não faz sentido construir em cima do que sai aqui.

## O que fica intocado

`/fiscal/notas` e `/fiscal/apuracao` — já sólidos, testados, refletem dado real do Bling. Nenhuma mudança nesta fase.

## O que sai (remoção)

- **`/fiscal/tabelas`** (tela inteira) + rotas `GET /api/fiscal/tabelas/{cfop,ncm,cest}` em `routes/fiscal.py`. Não é catálogo oficial, não agrega valor sobre já ver o CFOP/NCM na própria nota em `/fiscal/notas`.
- **Config fiscal de loja**: colunas `regime_tributario`, `serie_nfe`, `serie_nfce`, `ambiente_fiscal`, `certificado_digital`, `csc_nfce`, `token_fiscal` de `lojas` — remove `hermes_agents/core/lojas_fiscal_financeiro.py` inteiro, a aba correspondente em `web/src/app/lojas/[id]/_components/FiscalFinanceiroTab.tsx`, rota `PUT` de `atualizar_fiscal()`, e os testes dedicados (`test_lojas_fiscal_financeiro.py`, e os campos fiscais especificamente em `test_lojas_manage_seguranca.py`).
- **`pdv_nfce`**: remove a tabela e `"nfce"` de `TABLES` em `core/pdv.py` (para de ser exposta via CRUD genérico).
- **`fiscal_contas_receber_bling`/`fiscal_contas_pagar_bling`**: remove as tabelas, as entradas em `TABLES` de `core/fiscal.py`, e as rotas `sync/contas-receber`/`sync/contas-pagar` (`sincronizar_contas_receber_bling`/`sincronizar_contas_pagar_bling` continuam existindo — elas gravam em `fin_contas_receber`/`fin_contas_pagar`, que é o SSOT real — só o nome/rota que hoje sugere "fiscal" é revisto para refletir que é sync financeiro, não fiscal).
- **`calcular_tributos_nota`**: remove a função e a rota `GET /tributos/calcular/<nota_id>`.
- **6 interfaces mortas** em `web/src/app/fiscal/types/index.ts` (`TributoRecord`, `Obrigacao`/`ObrigacaoStatus`, `CfopRecord`, `NcmRecord`, `CestRecord`, `IbptRecord`) — confirmar por grep que nada importa do arquivo antes de decidir se o arquivo inteiro some ou só os tipos mortos.
- **`NAV_PERMS["/fiscal"]`**: hoje é `"fiscal:view"` (formato errado, nunca bate com nada retornado por `/api/me` — é código morto). Corrige para o formato real (`fiscal.ver`).

## O que vira real

### Tributos — CRUD de verdade

A tela passa a ter criar/editar/excluir (o backend já expõe isso genericamente, atrás de `fiscal.criar`/`.editar`/`.excluir` — só falta UI). O dado deixa de ser seed fixo: quem usa cadastra as alíquotas que de fato se aplicam ao regime de cada empresa. Sem consumidor automático de cálculo (isso é responsabilidade do contador/i9Logic) — a tela é referência interna, não motor de cálculo.

### Obrigações — cadastro + ocorrência por competência

Modelo atual (uma linha = uma obrigação, com uma data de vencimento fixa desde o seed) não sobrevive a mais de um mês. Novo modelo, duas camadas:

- **Cadastro** (`fiscal_obrigacoes`, tabela existente reaproveitada): nome, sigla, periodicidade, **dia de vencimento** (não mais uma data fixa), órgão, regime aplicável, ativo. Editável via CRUD (criar nova obrigação, desativar uma que não se aplica mais).
- **Ocorrência** (`fiscal_obrigacoes_ocorrencias`, tabela nova): uma linha por competência (`YYYY-MM`) de cada obrigação ativa, com a data de vencimento já calculada pra aquele mês, status (pendente/entregue) e quem deu baixa. Gerada automaticamente e de forma idempotente (garante que a ocorrência do mês corrente existe, sem duplicar) — o "Marcar como Entregue" passa a agir sobre a ocorrência do mês, não sobre a obrigação inteira.

## Migração de banco — cuidado explícito

Remover coluna/tabela em produção com dado real não tem volta fácil. Antes de rodar qualquer `DROP COLUMN`/`DROP TABLE` desta fase, o plano deve incluir uma checagem de contagem de linhas/valores não-nulos nas tabelas/colunas candidatas à remoção — se algo inesperado aparecer preenchido (algum uso real que a investigação não capturou), para e reporta antes de apagar.

## Global Constraints

- `/fiscal/notas` e `/fiscal/apuracao` (frontend, backend e testes) não são tocados nesta fase.
- Toda remoção de schema é precedida de checagem de contagem de linhas em produção — nunca `DROP` às cegas.
- Segue a convenção RBAC já estabelecida (`fiscal.ver/criar/editar/excluir`) para tudo que for novo.
- Sem emissão própria de NF-e/NFC-e nesta fase (nem física nem virtual) — fora de escopo, não é o objetivo do redesenho.
- Sem cálculo automático de tributos — fica com o contador/i9Logic.

## Fora de escopo (fases seguintes)

- Fase 2: Registro de Entrada (nota física recebida, upload de foto/PDF, status de lançamento no i9Logic).
- Fase 3: Export de período para o contador (pacote XML de saída + registro de entrada + apuração fechada) e visão dedicada para a role Contador.

## Testes

- Regressão: rotas removidas (`tabelas/*`, `contas_receber_bling`/`contas_pagar_bling`, `tributos/calcular/<id>`) não existem mais / retornam 404.
- Tributos: CRUD via UI cobre criar/editar/excluir com a permissão certa (reaproveita padrão RBAC já testado em `test_fiscal_seguranca.py`).
- Obrigações: geração de ocorrência do mês corrente é idempotente (rodar duas vezes não duplica), cálculo de `data_vencimento` a partir de `dia_vencimento` trata meses mais curtos (ex.: dia 31 em fevereiro), "marcar entregue" afeta só a ocorrência da competência certa, RBAC de criar/editar obrigação vs marcar entregue.
- `NAV_PERMS["/fiscal"]` corrigido bate com a permissão real (`fiscal.ver`) retornada por `/api/me`.
