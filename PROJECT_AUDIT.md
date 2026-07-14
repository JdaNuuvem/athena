# PROJECT AUDIT — ATHENA / HERMES Agent Swarm

**Data:** 2026-07-14 (atualizado 23:27)  
**Repositório:** `D:\JORGE CHARME E LEON\SISTEMAS\N8N AUTOMACOES`  
**Versão auditada:** `HEAD` do branch atual

---

# 1. Visão Geral do Projeto

## Objetivo do Sistema

ATHENA é um ERP inteligente multi-agente para gestão industrial (injeção plástica/plastisol), integrado com canais de venda (Telegram, WhatsApp, Shopee, marketplaces), ERP financeiro (Bling), e-commerce próprio (multiloja) e automação de workflows via n8n. O Hermes Agent Swarm fornece 14 agentes especializados que tomam decisões autônomas em produção, vendas, qualidade, manutenção e pricing.

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────┐
│                        COOLIFY (177.7.45.242)                    │
│                                                                  │
│  ┌──────────────────────┐   ┌──────────────────────┐            │
│  │  web/ (Next.js 15)   │   │  hermes_agents/      │            │
│  │  Static SPA Export   │   │  Flask 3.x Monolith  │            │
│  │  port 3000 (dev)     │   │  port 5000 (prod)    │            │
│  └──────────┬───────────┘   └──────────┬───────────┘            │
│             │                          │                         │
│             │  /api/* (fetch)          │   PostgreSQL (asyncpg)  │
│             └──────────────────────────┤   hermes_factory        │
│                                        │                         │
│  ┌──────────────────────┐             │                         │
│  │  athena/ (Node.js)   │─────────────┤                         │
│  │  Fastify + GraphQL   │             │   PostgreSQL (Prisma)   │
│  │  + Kafka + Qdrant    │             │   athena                │
│  └──────────────────────┘             │                         │
│                                        │                         │
│  Redis ─── Kafka ─── Qdrant ─── n8n ──┤                         │
│  Evolution-API (WhatsApp)             │                         │
└──────────────────────────────────────────────────────────────────┘
```

- **Frontend:** Next.js 15 + React 19 + Tailwind CSS 4 + Recharts (SPA estático, `output: "export"`)
- **Backend principal:** Python 3.11 + Flask 3.x monolítico (`athena_bridge.py`, 2299 linhas), em migração para Blueprints modulares
- **ATHENA OS:** TypeScript + Fastify + GraphQL (Mercurius) + Kafka + DDD (sistema separado)
- **Database:** PostgreSQL 16 como banco relacional principal para ambas as stacks
- **Message Broker:** Apache Kafka (somente ATHENA OS)
- **Cache:** Redis 7
- **Vector DB:** Qdrant v1.13 (ATHENA OS)
- **Automação:** n8n (2 workflows de WhatsApp)
- **Observabilidade:** Prometheus + Grafana + Jaeger (ATHENA OS)

## Tecnologias

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| Frontend | Next.js | 15.3.2 |
| Frontend | React | 19.2.7 |
| Frontend | Tailwind CSS | 4.1.6 |
| Frontend | Recharts | 3.9.2 |
| Backend (Flask) | Python | 3.11 |
| Backend (Flask) | Flask | 3.0+ |
| Backend (Flask) | asyncpg | 0.29+ |
| Backend (Flask) | psycopg2 | 2.9+ |
| Backend (ATHENA) | Node.js | 22 |
| Backend (ATHENA) | Fastify | 5.x |
| Backend (ATHENA) | GraphQL (Mercurius) | - |
| Backend (ATHENA) | Prisma | 7.8+ |
| Database | PostgreSQL | 16 |
| Message Broker | Apache Kafka | 7.6 (Confluent) |
| Cache | Redis | 7 |
| Vector DB | Qdrant | 1.13 |
| Workflow | n8n | latest |

## Banco de Dados

**Duas instâncias PostgreSQL coexistem:**

1. **`hermes_factory`** — Banco principal do Hermes Agent Swarm
   - Acessado via `asyncpg` (assíncrono) e `psycopg2` (síncrono para dashboards KPI)
   - **Sem ORM** — SQL puro com queries parametrizadas
   - Tabelas criadas via `CREATE TABLE IF NOT EXISTS` ao importar módulos core
   - Host: `postgresql-database-h3bdeft4hgsbg9rcxklxidwt` (Coolify interno)

2. **`athena`** — Banco do ATHENA OS (TypeScript)
   - Acessado via **Prisma ORM**
   - Com migrations versionadas (`prisma/migrations/`)
   - Host: `localhost:5433` (dev) / `postgres:5432` (docker)

## Autenticação

- **Frontend:** JWT armazenado em `localStorage`, enviado como `Authorization: Bearer`
- **Auto-login bypass:** Se não houver token, o layout automaticamente injeta `"athena-token-123456789"` e cria usuário Admin. Login é efetivamente opcional.
- **Backend:** Dois sistemas coexistem:
  1. **Antigo (athena_bridge.py):** Usuários hardcoded em dicionário Python, cookie `auth_token`
  2. **Novo (routes/auth.py):** JWT com PyJWT, `werkzeug` para hash de senhas, decorator `require_role()` (definido mas **não aplicado** a nenhuma rota)
- **Nenhuma proteção efetiva em rotas de API** — o decorator `require_role()` existe mas não é usado

## Serviços em Background

- **Agendamentos:** Tabela `autom_agendamentos` definida com campo `cron_expressao`, mas **nenhum scheduler/runner implementado** no código Python. A estrutura de dados existe, o executor não.
- **Filas:** Tabela `autom_filas` existe, mas **nenhum consumer/worker** implementado.
- **n8n fornece scheduling real** — o workflow `whatsapp-remarketing.json` tem trigger cron a cada 6 horas.
- **Kafka** provê event streaming no ATHENA OS (não no Hermes).

---

# 2. Funcionalidades — Módulos

## 2.1 Dashboard (`/dashboard`)

- **Frontend:** 🟡 Parcial — KPI overview + agentes vêm da API real, mas 90% dos widgets (gráficos, alertas, tabelas) são `kpisMock`/`vendasMesChart`/`alertasMock` hardcoded
- **Backend:** ✅ API `/api/kpi/overview` funcional
- **Banco:** ✅
- **APIs:** ✅ (kpi, agents, health)
- **Mocks:** 🟡 Dados mockados nos widgets visuais
- **Pendências:** Conectar gráficos do dashboard a dados reais de vendas/produção

## 2.2 Login

- **Frontend:** ✅ Completo
- **Backend:** 🟡 Parcial — dois sistemas de auth coexistindo, JWT definido mas sem enforcement
- **Pendências:** Remover auto-login bypass, aplicar `require_role()` nas rotas, unificar sistema de auth

## 2.3 Cadastros (`/cadastros`)

- **Frontend:** ✅ Completo — 6 tabs (Empresas, Usuários, Clientes, Fornecedores, Transportadoras, Vendedores) com CRUD completo via `CrudPanel`
- **Backend:** ✅ Completo — 17 tabelas, CRUD genérico, queries especiais (permissoes, vendedor_comissao, vendedor_metas, fornecedor_resumo)
- **Banco:** ✅ Dados seedados
- **APIs:** ✅ `GET/POST/PUT/DELETE /api/cadastros/{tabela}` + 4 endpoints especiais
- **Mocks:** ❌ Dados reais

## 2.4 Produtos (`/produtos`)

- **Frontend:** ✅ Completo — listagem com busca, SKU, margem, receita, vendas; página de detalhe com 7 tabs
- **Backend:** ✅ API `/api/produtos` e `/api/produtos/{sku}` funcional
- **Banco:** ✅ Conectado à tabela `vendas` (psycopg2 direto)
- **Mocks:** ❌ Dados reais via psycopg2

## 2.5 Financeiro (`/financeiro`)

- **Frontend:** ✅ Completo — 8 tabs (Fluxo de Caixa, DRE, Bancos, Conciliação, PIX, Boletos, Contas a Pagar, Contas a Receber) com CRUD
- **Backend:** ✅ 10 tabelas, CRUD completo, `fluxo_caixa_resumo()`, `dre_resumo()`
- **Banco:** ✅ Dados seedados
- **APIs:** ✅
- **Mocks:** ❌

## 2.6 Compras (`/compras`)

- **Frontend:** ✅ Completo — Dashboard com KPIs + 6 sub-páginas (Fornecedores, Solicitações, Cotações, Pedidos, Recebimentos, Notas)
- **Backend:** ✅ 7 tabelas, CRUD completo
- **Banco:** ✅
- **APIs:** ✅
- **Mocks:** ❌

## 2.7 PDV (`/pdv`)

- **Frontend:** ✅ Completo — Carrinho, formas de pagamento, abertura/fechamento de caixa, sangria/suprimento
- **Backend:** ✅ 7 tabelas, operações: `abrir_caixa()`, `fechar_caixa()`, `realizar_venda()`
- **Banco:** ✅
- **APIs:** ✅
- **Mocks:** ❌

## 2.8 CRM (`/crm`)

- **Frontend:** ✅ Completo — Funil de vendas com gráfico + 7 sub-páginas (Empresas, Leads, Contatos, Negociações, Atividades, Propostas, Contratos)
- **Backend:** ✅ 7 tabelas, CRUD + `funil()` pipeline
- **Banco:** ✅
- **APIs:** ✅
- **Mocks:** ❌

## 2.9 Produção (`/producao`)

- **Frontend:** ✅ Completo — Dashboard com KPIs + 6 sub-páginas (OPs, BOM, Máquinas, Apontamentos, Consumo, Custos, Perdas)
- **Backend:** ✅ 7 tabelas, CRUD + operações (iniciar_op, finalizar_op, parar_maquina)
- **Banco:** ✅
- **APIs:** ✅
- **Mocks:** ❌

## 2.10 Atendimento (`/atendimento`)

- **Frontend:** ✅ Completo — Dashboard de tickets + 4 sub-páginas (Tickets, SLA, Canais, KB)
- **Backend:** ✅ 6 tabelas, CRUD completo
- **Banco:** ✅ Dados seedados (SLA defaults, 6 canais)
- **APIs:** ✅
- **Mocks:** ❌

## 2.11 Automações (`/automacoes`)

- **Frontend:** ✅ Completo — Dashboard com KPIs + 7 sub-páginas (Webhooks, Filas, Eventos, Agendamentos, Integrações, Bots, IA)
- **Backend:** ✅ 7 tabelas definidas, CRUD completo
- **Banco:** ✅ Tabelas criadas
- **APIs:** ✅
- **Mocks:** ❌
- **⚠️ ALERTA:** CRUD completo disponível. Executor/consumer de filas e scheduler de agendamentos ainda não implementados (rodam via n8n e Flask rotas).

## 2.12 RH (`/rh`)

- **Frontend:** 🟡 Placeholder — Card de "Em construção" com submenus
- **Backend:** ✅ Completo — 7 tabelas, CRUD, `ponto_por_data()`, `folha_resumo()`, `beneficios_resumo()`
- **Banco:** ✅ Dados seedados (4 funcionários com ponto, férias, escala, folha, benefícios)
- **APIs:** ✅ (8 endpoints)
- **Pendências:** Construir frontend completo com tabs (Funcionários, Ponto, Férias, Escala, Folha, Benefícios)

## 2.13 BI (`/bi`)

- **Frontend:** 🟡 Parcial — Dashboard com KPIs + 4 sub-páginas (Forecast, Indicadores, ML, Vendas). Dados parcialmente hardcoded.
- **Backend:** 🟡 Parcial — Algumas queries de vendas reais, dados mock nos visuais
- **Pendências:** Conectar a APIs reais de vendas/estoque

## 2.14 Fiscal (`/fiscal`)

- **Frontend:** ✅ Completo — Dashboard com KPIs + 4 sub-páginas (Notas, Obrigações, Tabelas, Tributos) com CRUD via Bling NF-e
- **Backend:** ✅ API via Bling (`/api/bling/financeiro/notas-fiscais`) com download XML/DANFE
- **Pendências:** Integração fiscal além do Bling (tributos, obrigações acessórias)

## 2.15 Documentos (`/documentos`)

- **Frontend:** 🟡 Placeholder — Página de entrada com card "Em construção"
- **Backend:** 🔴 Não iniciado
- **Pendências:** Implementar gestão documental com upload/storage

## 2.16 Vendas (`/vendas`)

- **Frontend:** ✅ Completo — Dashboard com DataTable, filtros, cards KPIs resumindo vendas reais via Bling
- **Backend:** ✅ Dados via Bling API (`/api/bling/vendas`), relatórios agregados
- **Mocks:** ❌ Dados reais

## 2.17 Estoque (`/estoque`)

- **Frontend:** ✅ Completo — Seletor multiloja, filtros (SKU/nome/ID/status/estoque), bulk edit com +/- em massa, modal de estoque por depósito com botão "Dividir Igualmente", sincronização Bling
- **Backend:** ✅ Dados via Bling API (`/api/bling/produtos`, `/api/bling/depositos`, `/api/bling/estoque`)
- **Mocks:** ❌ Dados reais

## 2.18 Relatórios (`/relatorios`)

- **Frontend:** ✅ Completo — Dashboard com 20 cards (Vendas, Lucro, Margem, Estoque, DRE, Fluxo Caixa, Ticket Médio, Previsão, etc.) com previews ao vivo dos KPIs. 10 relatórios com dados reais e filtro de período.
- **Backend:** ✅ `core/relatorios.py` com 10 funções de agregação (vendas, lucro_margem, estoque, clientes, fornecedores, dre, fluxo_caixa, ticket_medio, aging, previsao)
- **APIs:** ✅ 10 endpoints REST
- **Mocks:** ❌ Dados reais (PDV, Bling, módulos core)

## 2.19 Integrações (`/integracoes`)

- **Frontend:** ✅ Completo — Lista de integrações agrupadas por categoria com status badges; sub-páginas: Bling (dashboard + 5 tabs), Hermes, Shopee, Shopee Ads
- **Backend:** ✅ ATHENA OS fornece integrações; Bling OAuth2, Shopee API, Telegram webhook
- **Mocks:** ❌ Dados reais

## 2.20 Agentes (Agents)

- **Frontend:** ✅ Completo — Lista de 14 agentes, status, link para detalhe
- **Backend:** ✅ 14 módulos agent (ag_01 a ag_14)
- **Mocks:** 🟡 Agentes reais, mas algumas respostas são simuladas (ex: `cnc_interface.py` marca mock explícito)
- **Pendências:** Integração real com máquinas CNC

## 2.21 Workflows

- **Frontend:** ✅ Funcional — 7 workflows hardcoded com execução via API real
- **Backend:** ✅ Workflows Fase 1 (`workflows.py`) e Fase 3 (`workflows_fase3.py`)
- **Mocks:** 🟡 Alguns workflows retornam dados mock (marcado com comentários `# mock`)



## 2.24 Segurança & Governança (`/seguranca`)

- **Frontend:** ✅ Completo — Dashboard com últimas ações + 4 sub-páginas (Auditoria, Logs, Histórico, RBAC)
- **Backend:** ✅ `core/seguranca.py` — 3 tabelas (audit_log, system_logs, change_history), hooks de auditoria no login, função `auditar()` para ações CRUD
- **Banco:** ✅ Dados registrados em tempo real
- **APIs:** ✅ `/api/auditoria`, `/api/logs`, `/api/historico/{entidade}/{id}`
- **Mocks:** ❌ Dados reais

## 2.23 RBAC — Controle de Acesso (`/seguranca/rbac`)

- **Frontend:** ✅ Completo — Página de gestão de papéis e permissões com tabela e CRUD
- **Backend:** ✅ `core/rbac.py` — 4 tabelas (rbac_permissoes, rbac_roles, rbac_role_permissoes, rbac_usuarios), seed automático (81 permissões, 4 papéis, 4 usuários), `@requer_permissao()` decorator
- **Banco:** ✅ Dados seedados
- **APIs:** ✅ CRUD roles, permissoes, usuarios + login integrado
- **Frontend libs:** `AuthProvider`, `usePermissao()`, `<Permitido>` component
- **Mocks:** ❌ Dados reais

## 2.22 Chat Hermes (`/hermes`)

- **Frontend:** ✅ Completo — Chat UI com bolhas, chips de sugestão, indicador de digitação
- **Backend:** ✅ `/api/hermes/chat` funcional com memória e roteamento entre agentes
- **Mocks:** ❌ Dados reais

---

# 3. Backend — Mapeamento Completo

## Estrutura

```
hermes_agents/
├── athena_bridge.py        ★ Monolito Flask (2299 linhas, 100+ endpoints)
├── bling_erp.py            ★ Bling SDK (OAuth2, produtos, pedidos, webhooks)
├── shopee.py / shopee_sync.py  ★ Shopee SDK + sincronização
├── workflows.py             Workflows Fase 1 (cross-agent)
├── workflows_fase3.py       Workflows Fase 3 (manufacturing chain)
├── start_telegram_bot.py    Telegram bot launcher
│
├── core/                     ★ Camada de domínio (14 módulos)
│   ├── __init__.py           DB pool (asyncpg), FactoryConfig, run_async
│   ├── config.py             API config store (JSON file-based)
│   ├── memory.py             Memória conversacional (store/recall/history)
│   ├── atendimento.py        Tickets, SLA, canais, KB
│   ├── automacoes.py         Webhooks, filas, eventos, agendamentos
│   ├── cadastros.py          Empresas, usuários, clientes, fornecedores, transp, vendedores
│   ├── compras.py            Fornecedores, solicitações, cotações, pedidos, recebimentos
│   ├── crm.py                Empresas, leads, contatos, negociações, pipeline
│   ├── financeiro.py         Fluxo caixa, contas, boletos, PIX, conciliação, DRE
│   ├── lojas.py              Lojas CRUD simples
│   ├── pdv.py                PDV completo (caixas, vendas, pagamentos, NFCe)
│   ├── producao.py           OPs, BOM, máquinas, apontamentos, custos
│   └── rh.py                 Funcionários, ponto, férias, folha, benefícios
│
├── routes/                   ★ Blueprints Flask (nova arquitetura)
│   ├── auth.py               JWT auth (login, me, require_role)
│   ├── integrations.py       Bling, Shopee APIs OAuth
│   ├── webhooks.py           WhatsApp, Bling, Shopee webhooks
│   └── ...
│
├── ag_01_cacador/            ★ Agentes IA (14 módulos)
├── ag_02_lucratividade/
├── ag_03_marketplaces/
├── ag_04_planejador/
├── ag_05_industrial/         (cnc_interface.py, mold_lifecycle.py)
├── ag_06_telegram/           (nlp.py, bot_real.py)
├── ag_07_laboratorio/
├── ag_08_lojas/
├── ag_09_memoria/
├── ag_10_diretor/
├── ag_11_qualidade/
├── ag_12_manutencao/
├── ag_13_ml/
├── ag_14_whatsapp/
│
├── finance/                   Agentes financeiros
│   ├── ag_201_cashflow.py
│   ├── ag_202_revenue.py
│   ├── ag_203_cost.py
│   ├── ag_204_controller.py
│   └── ag_205_profitability.py
│
├── sql/                       Schemas SQL
│   ├── schema.sql             Fase 1 (14 tabelas)
│   ├── create_tables_fase2.sql Fase 2 (11 tabelas)
│   └── create_tables_fase3.sql Fase 3 (11 tabelas)
│
└── dashboard/                 Static SPA (Next.js export)
```

## Controllers / Handlers

**Padrão monolítico (athena_bridge.py):**
- Todas as rotas registradas diretamente via `@app.route()`
- 100+ endpoints em um único arquivo
- CORS global (`CORS(app)`) sem restrições

**Padrão Blueprint (routes/):**
- `auth_bp` — Login, me
- `integrations_bp` — Bling, Shopee — `/api/integrations`, `/api/bling/*`
- `webhooks_bp` — WhatsApp, Bling, Shopee — `/webhook/*`

**⚠️ DUPLICAÇÃO:** Múltiplas rotas registradas duas vezes (ex: `/api/auth/login`, `/webhook/bling/pedido`). O código está no meio de uma migração de monolito → Blueprints. As rotas antigas não foram removidas.

## Services / Use Cases

Cada módulo `core/*.py` implementa:
- `_ensure_tables()` — DDL executado no import
- `_list(tabela, cols, order, limit)` → lista genérica
- `_get(tabela, id)` → registro único
- `_create(tabela, dados)` → insert com RETURNING *
- `_update(tabela, id, dados)` → update com RETURNING *
- `_delete(tabela, id)` → delete
- Funções especiais por domínio (ex: `funil()`, `fluxo_caixa_resumo()`, `realizar_venda()`)

**Padrão comum:** `core/*.py` exporta funções síncronas que internamente usam `run_async()` para executar queries asyncpg.

## Middlewares

- **CORS:** `flask-cors` com padrão allow-all
- **Auth:** Nenhum middleware global aplicado. O decorator `require_role()` de `routes/auth.py` existe mas não é usado em nenhuma rota de produção.
- **Rate limiting:** Inexistente
- **CSRF:** Inexistente
- **Logging:** Apenas `log(agent, msg)` inline

## Jobs / Queues / Workers / Cron

| Componente | Status |
|-----------|--------|
| Tabela `autom_filas` | ✅ Schema existe |
| Consumer de filas | 🔴 Não implementado |
| Tabela `autom_agendamentos` | ✅ Schema existe (campo `cron_expressao`) |
| Scheduler / Cron runner | 🔴 Não implementado |
| n8n Cron trigger | ✅ Funcional (remarketing a cada 6h) |
| Kafka consumers | ✅ ATHENA OS apenas |
| Redis queues | 🔴 Não implementado |

---

# 4. Banco de Dados

## Instância 1: `hermes_factory` (PostgreSQL, Hermes Agent Swarm)

### Tabelas criadas via core modules (auto-create no import):

| Módulo | Tabela | Schema | FK |
|--------|--------|--------|----|
| **cadastros** | `cad_empresas` | razao_social, cnpj, ie, im, regime, porte, tipo, status | empresa_mae_id → cad_empresas |
| | `cad_multiempresa` | empresa_id, tipo_vinculo | empresa_id → cad_empresas |
| | `cad_usuarios` | nome, email, senha_hash, perfil, grupo_id, mfa_ativo, status | grupo_id → cad_grupos |
| | `cad_permissoes` | perfil, modulo, acesso | — |
| | `cad_grupos` | nome, perfil_padrao | — |
| | `cad_historico_acessos` | usuario_id, acao, ip | usuario_id → cad_usuarios |
| | `cad_clientes` | nome, tipo, documento, ie, im, limite_credito, score, status | — |
| | `cad_cliente_enderecos` | cliente_id + endereço | cliente_id → cad_clientes |
| | `cad_cliente_contatos` | cliente_id + contato | cliente_id → cad_clientes |
| | `cad_cliente_historico` | cliente_id, descricao | cliente_id → cad_clientes |
| | `cad_cliente_tags` | cliente_id, tag | cliente_id → cad_clientes |
| | `cad_fornecedores` | nome, tipo, documento, ie, im, limite_credito, score, status | — |
| | `cad_fornecedor_enderecos` | fornecedor_id + endereço | fornecedor_id → cad_fornecedores |
| | `cad_fornecedor_contatos` | fornecedor_id + contato | fornecedor_id → cad_fornecedores |
| | `cad_fornecedor_historico` | fornecedor_id, descricao, valor_total | fornecedor_id → cad_fornecedores |
| | `cad_fornecedor_tags` | fornecedor_id, tag | fornecedor_id → cad_fornecedores |
| | `cad_transportadoras` | nome, cnpj, frota, regiao, status | — |
| | `cad_transp_frete` | transportadora_id, origem, destino, valor, prazo | transportadora_id → cad_transportadoras |
| | `cad_transp_contatos` | transportadora_id, nome, telefone, email | transportadora_id → cad_transportadoras |
| | `cad_vendedores` | nome, email, regiao, comissao_pct | — |
| | `cad_vendedor_metas` | vendedor_id, mes, meta_valor, realizado | vendedor_id → cad_vendedores |
| **financeiro** | `fin_fluxo_caixa` | tipo, descricao, valor, data, categoria, conta_id | — |
| | `fin_contas_receber` | cliente, descricao, valor, vencimento, status, forma_pagamento | — |
| | `fin_contas_pagar` | fornecedor, descricao, valor, vencimento, status, forma_pagamento | — |
| | `fin_boletos` | conta_id, nosso_numero, codigo_barras, linha_digitavel, status | — |
| | `fin_pix` | conta_id, chave, tipo_chave, qrcode, status | — |
| | `fin_conciliacao` | banco_id, data, descricao, valor, status | — |
| | `fin_bancos` | nome, codigo, agencia, conta, saldo | — |
| | `fin_centro_custo` | nome, tipo, orcamento | — |
| | `fin_plano_contas` | codigo, nome, tipo, natureza | — |
| | `fin_dre` | mes, receita_total, custo_total, despesa_total, resultado | — |
| **RH** | `rh_funcionarios` | nome, cpf, cargo, salario, data_admissao, status | — |
| | `rh_ponto` | funcionario_id, data, entrada, saida, horas_extras | funcionario_id → rh_funcionarios |
| | `rh_ferias` | funcionario_id, data_inicio, data_fim, status | funcionario_id → rh_funcionarios |
| | `rh_escala` | funcionario_id, dia_semana, horario_inicio, horario_fim | funcionario_id → rh_funcionarios |
| | `rh_folha` | funcionario_id, mes, salario_base, descontos, beneficios, liquido | funcionario_id → rh_funcionarios |
| | `rh_beneficios` | nome, tipo, valor_empresa, valor_funcionario | — |
| | `rh_funcionario_beneficio` | funcionario_id, beneficio_id | FK dupla |
| **CRM** | `crm_empresas` | nome, cnpj, segmento, porte, status | — |
| | `crm_leads` | nome, origem, status, empresa_id, pontuacao | empresa_id → crm_empresas |
| | `crm_contatos` | nome, cargo, telefone, email, empresa_id | empresa_id → crm_empresas |
| | `crm_negociacoes` | titulo, valor, status, empresa_id, contato_id | FK dupla |
| | `crm_atividades` | tipo, descricao, data, negociacao_id | negociacao_id → crm_negociacoes |
| | `crm_propostas` | negociacao_id, valor, validade, status | negociacao_id → crm_negociacoes |
| | `crm_contratos` | negociacao_id, valor, data_inicio, data_fim | negociacao_id → crm_negociacoes |
| **Compras** | `compras_fornecedores` | nome, cnpj, contato, email, status | — |
| | `compras_solicitacoes` | descricao, quantidade, urgente, status | — |
| | `compras_cotacoes` | solicitacao_id, fornecedor_id, valor, prazo | FK dupla |
| | `compras_pedidos` | fornecedor_id, valor_total, status | fornecedor_id → compras_fornecedores |
| | `compras_itens` | pedido_id, descricao, quantidade, valor_unitario | pedido_id → compras_pedidos |
| | `compras_recebimentos` | pedido_id, quantidade, data | pedido_id → compras_pedidos |
| | `compras_notas_entrada` | fornecedor_id, numero, valor, data | fornecedor_id → compras_fornecedores |
| **Produção** | `producao_ops` | numero, produto, quantidade, status | — |
| | `producao_bom` | op_id, componente, quantidade, unidade | op_id → producao_ops |
| | `producao_maquinas` | nome, tipo, status, ultima_manutencao | — |
| | `producao_apontamentos` | op_id, maquina_id, quantidade, data | FK dupla |
| | `producao_consumo` | op_id, componente, quantidade | op_id → producao_ops |
| | `producao_perdas` | op_id, motivo, quantidade | op_id → producao_ops |
| | `producao_custos` | op_id, tipo, valor | op_id → producao_ops |
| **PDV** | `pdv_caixas` | nome, operador, status | — |
| | `pdv_vendas` | caixa_id, total, desconto, forma_pagamento, status | caixa_id → pdv_caixas |
| | `pdv_itens` | venda_id, produto, quantidade, valor_unitario | venda_id → pdv_vendas |
| | `pdv_pagamentos` | venda_id, forma, valor | venda_id → pdv_vendas |
| | `pdv_sangrias` | caixa_id, valor, motivo | caixa_id → pdv_caixas |
| | `pdv_suprimentos` | caixa_id, valor, motivo | caixa_id → pdv_caixas |
| | `pdv_nfce` | venda_id, numero, chave, status | venda_id → pdv_vendas |
| **Atendimento** | `atend_tickets` | titulo, descricao, prioridade, status, canal_id | canal_id → atend_canais |
| | `atend_mensagens` | ticket_id, remetente, texto | ticket_id → atend_tickets |
| | `atend_chat_sessoes` | cliente, status, ultimo_acesso | — |
| | `atend_canais` | nome, tipo, ativo | — |
| | `atend_sla` | nome, tempo_resposta, tempo_resolucao | — |
| | `atend_kb_artigos` | titulo, conteudo, categoria, tags | — |
| **Automações** | `autom_webhooks` | nome, url, evento, ativo | — |
| | `autom_filas` | nome, tipo, tamanho_max | — |
| | `autom_eventos` | nome, descricao, ativo | — |
| | `autom_agendamentos` | nome, cron_expressao, acao, ativo | — |
| | `autom_integracoes` | nome, tipo, config, ativo | — |
| | `autom_bots` | nome, tipo, status | — |
| | `autom_ia` | nome, provider, modelo, api_key | — |
| **Outros** | `lojas` | nome, ativa | — |
| | `memoria_interacoes` | session_id, agente, mensagem, resposta, embedding, metadata | auto-create |
| | `hermes_execucoes` | agent_id, action, params, result, status, timestamp | criada via migrations |

### Tabelas via SQL (schema.sql / create_tables_fase*.sql):

| Fase | Tabelas |
|------|---------|
| **Fase 1** | `moldes`, `fichas_tecnicas`, `fornecedores`, `materias_primas`, `historico_custos`, `problemas_resolvidos`, `produtos_descobertos`, `tendencias`, `vendas`, `margens_diarias`, `anuncios`, `concorrentes`, `sugestoes_otimizacao`, `alertas` |
| **Fase 2** | `pedidos_producao`, `plano_producao_diario`, `status_maquinas`, `ferramentas_cnc`, `clientes_telegram`, `sessoes_telegram`, `pedidos_telegram`, `pipeline_lancamentos`, `componentes_bom`, `historico_custos_simulados` |
| **Fase 3** | `moldes_eventos`, `cnc_jobs`, `producao_lotes`, `inspecao_qualidade`, `defeitos`, `inspecao_defeitos`, `capa_registros`, `manutencoes`, `manutencoes_historico`, `estoque_produtos`, `transferencias_estoque` |

### ⚠️ Problemas:

- **Sem migrations versionadas** — DDL executado via `CREATE TABLE IF NOT EXISTS` no import. Sem rollback, sem versionamento.
- **Tabelas órfãs:** `vendas`, `anuncios`, `fichas_tecnicas`, `margens_diarias`, `alertas`, `hermes_execucoes`, `produtos_descobertos` — referenciadas em queries mas sem `_ensure_tables()` correspondente nos módulos core atuais. Criadas apenas via SQL scripts.
- **Duplicação de tabelas:** `moldes` aparece em Fase 1 e Fase 2 (definições ligeiramente diferentes). `materias_primas` também.

## Instância 2: `athena` (PostgreSQL, ATHENA OS)

- 53 modelos Prisma em `athena/prisma/schema.prisma` (824 linhas)
- Migration versionada: `20260703000000_init/migration.sql` (506 linhas)
- Seeds: `prisma/seed.sql` (106 linhas)
- Domínios: Agents, Products (BOM, Mold, CNC, Quality), Inventory, Orders, Customers, Channels, Commerce, Pricing, Analytics, Auth

---

# 5. APIs

## REST — Rotas do Hermes Agent Swarm

### Auth

| Método | Endpoint | Controller | Status | Auth |
|--------|----------|-----------|--------|------|
| POST | `/api/auth/login` | athena_bridge.py + routes/auth.py (duplicado) | ✅ | ❌ Aberto |
| GET | `/api/me` | athena_bridge.py + routes/auth.py (duplicado) | ✅ | Token |
| POST | `/api/auth/logout` | athena_bridge.py | ✅ | Token |

### Health & Agents

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/health` | ✅ |
| GET | `/api/health/real` | ✅ |
| GET | `/api/agents` | ✅ |

### Agentes (AG-04 a AG-14)

| Método | Endpoint | Status | Observação |
|--------|----------|--------|------------|
| POST | `/api/agent/ag_04_planejador/plano_diario` | ✅ | |
| POST | `/api/agent/ag_04_planejador/adicionar_pedido` | ✅ | |
| GET | `/api/agent/ag_05_industrial/relatorio` | ✅ | |
| GET | `/api/agent/ag_05_industrial/oee/{id}` | ✅ | |
| GET | `/api/agent/ag_05_industrial/alertas` | ✅ | |
| POST | `/api/agent/ag_06_telegram/processar` | ✅ | |
| POST | `/api/agent/ag_06_telegram/pedido` | ✅ | |
| GET | `/api/agent/ag_06_telegram/stats` | ✅ | |
| POST | `/api/agent/ag_07_laboratorio/analisar` | ✅ | |
| GET | `/api/agent/ag_07_laboratorio/pipeline/{status}` | ✅ | |
| POST | `/api/agent/ag_07_laboratorio/pipeline/{id}/status` | ✅ | |
| POST | `/api/workflows/ag07_para_ag04/{id}` | ✅ | |
| POST | `/api/workflows/ag06_para_ag04/{id}` | ✅ | |
| POST | `/api/workflows/ag05_para_ag02` | ✅ | |

### Manufacturing (Fase 3)

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/moldes` | ✅ |
| GET | `/api/moldes/criticos` | ✅ |
| GET | `/api/moldes/dashboard` | ✅ |
| POST | `/api/moldes/evento` | ✅ |
| GET | `/api/cnc/jobs` | ✅ |
| POST | `/api/cnc/jobs/iniciar` | ✅ |
| GET | `/api/qualidade/taxa_defeitos` | ✅ |
| GET/POST | `/api/qualidade/inspecoes` | ✅ |
| GET | `/api/manutencao/pendentes` | ✅ |
| GET/POST | `/api/manutencao` | ✅ |
| GET | `/api/estoque/produtos` | ✅ |
| POST | `/api/estoque/transferencia` | ✅ |
| GET | `/api/bling/produtos` | ✅ (estoque via Bling) |
| GET | `/api/bling/depositos` | ✅ |
| PUT | `/api/bling/estoque` | ✅ |

### Config

| Método | Endpoint | Status |
|--------|----------|--------|
| GET/POST | `/api/config/{sistema}` | ✅ |
| GET | `/api/config/status` | ✅ |

### ML

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/ml/status` | ✅ |
| POST | `/api/ml/treinar` | ✅ |


### Relatórios

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/relatorios/vendas?dias=30` | ✅ |
| GET | `/api/relatorios/lucro?dias=30` | ✅ |
| GET | `/api/relatorios/estoque` | ✅ |
| GET | `/api/relatorios/clientes` | ✅ |
| GET | `/api/relatorios/fornecedores` | ✅ |
| GET | `/api/relatorios/dre` | ✅ |
| GET | `/api/relatorios/fluxo-caixa` | ✅ |
| GET | `/api/relatorios/ticket-medio` | ✅ |
| GET | `/api/relatorios/previsao` | ✅ |
| GET | `/api/relatorios/aging` | ✅ |

### Memory & Chat

| Método | Endpoint | Status |
|--------|----------|--------|
| POST | `/api/hermes/chat` | ✅ |
| GET | `/api/memory/stats` | ✅ |
| GET | `/api/memory/history` | ✅ |
| GET | `/api/memory/recall` | ✅ |

### CRUD Modular (prefixos RESTful)

| Prefixo | Módulo | Endpoints | Status |
|---------|--------|-----------|--------|
| `/api/automacoes/{tabela}` | Automações | GET/POST/PUT/DELETE | ✅ |
| `/api/producao/{tabela}` | Produção | GET/POST/PUT/DELETE + operações | ✅ |
| `/api/atendimento/{tabela}` | Atendimento | GET/POST/PUT/DELETE | ✅ |
| `/api/pdv/{tabela}` | PDV | GET/POST/PUT/DELETE + operações | ✅ |
| `/api/compras/{tabela}` | Compras | GET/POST/PUT/DELETE | ✅ |
| `/api/crm/{tabela}` | CRM | GET/POST/PUT/DELETE | ✅ |
| `/api/lojas/manage` | Lojas | GET/POST/PUT/DELETE | ✅ |
| `/api/rh/{tabela}` | RH | GET/POST/PUT/DELETE + especiais | ✅ |
| `/api/cadastros/{tabela}` | Cadastros | GET/POST/PUT/DELETE + especiais | ✅ |
| `/api/financeiro/{tabela}` | Financeiro | GET/POST/PUT/DELETE + especiais | ✅ |

### Business & Hermes

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/business/alerts` | ✅ |
| GET | `/api/business/opportunities` | ✅ |
| GET | `/api/business/executions` | ✅ |
| GET/POST | `/api/hermes/agents` | ✅ |
| GET/POST | `/api/hermes/opportunities` | ✅ |
| GET | `/api/hermes/alerts` | ✅ |
| GET | `/api/hermes/executions` | ✅ |
| POST | `/api/hermes/execute` | ✅ |
| POST | `/api/hermes/sync-all` | ✅ |

### Integrações & Shopee Ads

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/integrations` | ✅ |
| GET/PUT/DELETE | `/api/integrations/{id}` | ✅ |
| GET/POST/PUT/DELETE | `/api/shopee-ads/campaigns` | ✅ |
| GET | `/api/shopee-ads/performance` | ✅ |
| GET | `/api/shopee-ads/insights` | ✅ |
| POST | `/api/shopee-ads/adjust-bid` | ✅ |
| POST | `/api/shopee-ads/budget-suggestion` | ✅ |
| POST | `/api/shopee-ads/predict-ml` | ✅ |
| POST | `/api/shopee-ads/ab-test` | ✅ |

### Shopee & Bling (externos)

| Método | Endpoint | Status |
|--------|----------|--------|
| GET/POST | `/api/shopee/*` | ✅ |
| GET/POST/PUT | `/api/bling/*` | ✅ |
| GET/POST | `/api/bling/v2/*` | ✅ |
| GET | `/webhook/bling/eventos` | ✅ |


### RBAC

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/rbac/roles` | ✅ |
| POST | `/api/rbac/roles` | ✅ |
| PUT | `/api/rbac/roles/{id}` | ✅ |
| DELETE | `/api/rbac/roles/{id}` | ✅ |
| GET | `/api/rbac/permissoes` | ✅ |
| GET | `/api/rbac/usuarios` | ✅ |
| POST | `/api/rbac/usuarios` | ✅ |
| PUT | `/api/rbac/usuarios/{id}` | ✅ |

### Segurança / Auditoria

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/auditoria?modulo=&email=` | ✅ |
| GET | `/api/logs?level=&modulo=` | ✅ |
| GET | `/api/historico/{entidade}/{id}` | ✅ |
| GET | `/api/historico/{entidade}` | ✅ |

### Webhooks

| Método | Endpoint | Status |
|--------|----------|--------|
| POST | `/webhook/whatsapp` | ✅ |
| POST | `/webhook/bling/pedido` | ✅ (duplicado) |
| POST | `/webhook/bling/pedido/v2` | ✅ |
| POST | `/webhook/shopee/pedido` | ✅ (duplicado) |
| GET/POST | `/webhook/bling` | ✅ |

### Multiloja (psycopg2 direto)

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/produtos` | ✅ |
| GET | `/api/produtos/{sku}` | ✅ |
| GET | `/api/lojas` | ✅ |
| GET | `/api/kpi/overview` | ✅ |

### SPA Fallback

| Método | Endpoint | Status |
|--------|----------|--------|
| GET | `/` | ✅ (serve dashboard/index.html) |
| GET | `/{path}` | ✅ (SPA fallback) |

## Webhooks

| Evento | Origem | Destino | Payload | Validação | Status |
|--------|--------|---------|---------|-----------|--------|
| `whatsapp.message` | Evolution API | `/webhook/whatsapp` | JSON (Evolution format) | API Key | ✅ |
| `bling.pedido` | Bling ERP | `/webhook/bling/pedido` | JSON (Bling v2/v3) | HMAC | ✅ |
| `shopee.pedido` | Shopee API | `/webhook/shopee/pedido` | JSON | Partner Key | ✅ |
| `telegram.update` | Telegram API | `/telegram/webhook` | JSON (Telegram format) | Bot Token | ✅ |

## OAuth

| Provider | Fluxo | Callback | Escopos | Refresh Token | Status |
|----------|-------|----------|---------|---------------|--------|
| **Bling ERP v3** | Authorization Code | `/api/bling/oauth/callback` | products, orders, finance | ✅ Implementado | ✅ |
| **Shopee** | Partner API Key | N/A (API Key) | products, orders | N/A | ✅ |

## Tokens

| Tipo | Geração | Validação | Expiração | Renovação |
|------|---------|-----------|-----------|-----------|
| **JWT (auth)** | `routes/auth.py` — PyJWT com secret | `require_role()` decorator (não aplicado) | 24h | ❌ Não implementado |
| **API Token (legado)** | Hardcoded `"athena-token-123456789"` | Cookie/header check simples | Nunca | N/A |
| **Bling Access Token** | `bling_erp.py` via OAuth2 | Bling API validation | Definido pelo provider | ✅ Refresh token flow |
| **Bling Refresh Token** | Resposta OAuth2 | Bling token endpoint | Longo prazo | ✅ Automático |
| **Shopee API Key** | Config estática | Shopee API | Permanente | N/A |
| **Telegram Bot Token** | Telegram BotFather | Telegram API | Permanente | N/A |
| **Evolution API Key** | Config estática `athena-evolution-key` | Evolution API | Permanente | N/A |

## SDKs

| SDK | Arquivo | Serviços | Status | Config |
|-----|---------|----------|--------|--------|
| **Bling SDK** | `hermes_agents/bling_erp.py` | Produtos, Pedidos, Financeiro, Webhooks, Notificações | ✅ | OAuth2 via env vars |
| **Shopee SDK** | `hermes_agents/shopee.py`, `shopee_sync.py` | Produtos, Pedidos, Estoque, Preços | ✅ | partner_id + shop_id |
| **Telegram Bot** | `ag_06_telegram/bot_real.py` | Vendas via Telegram | ✅ | Bot Token |
| **OpenAI** | Referenciado no schema Prisma | Embeddings/LLM (ATHENA OS) | 🟡 Configurado (schema), sem uso ativo no código Python | API Key |
| **scikit-learn** | `ag_13_ml/` | Predição de defeitos | ✅ | Library importada |

---

# 6. Integrações Externas

| Integração | Status | Ambiente | Observações |
|------------|--------|----------|-------------|
| **Bling ERP** | ✅ Ativa | Produção | OAuth2 completo, sync de produtos/pedidos/NFs/contas |
| **Shopee Marketplace** | ✅ Ativa | Sandbox | Produtos, pedidos, webhooks |
| **Shopee Ads** | ✅ Ativa | Sandbox | Campanhas, performance, A/B tests |
| **Telegram Bot** | ✅ Ativa | Produção | Bot de vendas, NLP, classificação de clientes |
| **WhatsApp (Evolution API)** | ✅ Ativa | Produção | Ponte WhatsApp via Evolution API + n8n |
| **Mercado Livre** | 🟡 Referenciado | — | Mencionado em código mas sem SDK dedicado |
| **n8n** | ✅ Ativa | Produção | 2 workflows: sales bot + remarketing |
| **Coolify** | ✅ Ativa | Produção | Deploy, DB hosting, container management |
| **GitHub Actions** | ✅ Configurado | CD | Push to GHCR, deploy SSH, Prisma migrate |
| **Prometheus + Grafana** | ✅ Configurado | Dev | Métricas ATHENA OS |
| **Jaeger** | ✅ Configurado | Dev | Tracing distribuído ATHENA OS |
| **Kafka** | ✅ Configurado | Dev | Event streaming ATHENA OS |
| **Qdrant** | ✅ Configurado | Dev | Vector embeddings ATHENA OS |

---

# 7. Dados Mockados

| Arquivo | Local | Dados | Motivo | API substituta | Prioridade |
|---------|-------|-------|--------|----------------|------------|
| `bi/data/vendas.ts` | `web/src/app/bi/data/` | Vendas diárias aleatórias | API de BI não existe | `/api/bi/vendas` (inexistente) | Média |
| `bi/data/forecast.ts` | `web/src/app/bi/data/` | Forecast aleatório | API de BI não existe | `/api/bi/forecast` (inexistente) | Média |
| `bi/data/indicadores.ts` | `web/src/app/bi/data/` | Indicadores mock | API de BI não existe | `/api/bi/indicadores` (inexistente) | Média |
| `bi/data/ml.ts` | `web/src/app/bi/data/` | Predições aleatórias | API de BI não existe | `/api/bi/ml` (inexistente) | Média |
| `fiscal/data/*.ts` | `web/src/app/fiscal/data/` | Notas, obrigações, tributos, tabelas | API fiscal não existe | `/api/fiscal/*` (inexistente) | Alta |
| `documentos/page.tsx` | `web/src/app/documentos/` | 8 arrays hardcoded | API documentos não existe | `/api/documentos/*` (inexistente) | Baixa |
| `dashboard/page.tsx` | `web/src/app/dashboard/` | `kpisMock`, `vendasMesChart`, `alertasMock` | Widgets visuais pendentes | APIs de vendas/estoque reais | Alta |
| `workflows_fase3.py:L124` | `hermes_agents/` | CNC job com dados mock | Integração real CNC pendente | Hardware real | Média |
| `cnc_interface.py:L58` | `hermes_agents/ag_05_industrial/` | `"""Atualiza status da máquina (mock)."""` | Integração real CNC pendente | Hardware real | Média |
| `workflows.py:L66` | `hermes_agents/` | `# mock - implementar query real` | Query de pedido Telegram pendente | Query real | Média |

---

# 8. Funcionalidades Pendentes

## Alta Prioridade

| Item | Complexidade | Dependências | Est. |
|------|-------------|--------------|------|
| **Aplicar autenticação nas rotas** — `require_role()` em todas as APIs | Baixa | Unificar auth systems | 4h |
| **Remover auto-login bypass** no layout | Baixa | Auth enforcement | 1h |
| **Limpar duplicação de rotas** (monolito vs Blueprints) | Média | — | 8h |
| **Módulo Vendas** — frontend + core + API | Alta | Tabela `vendas` existe | 40h |
| **Módulo Estoque** — frontend + core + API | Alta | Tabelas `estoque_produtos`, `transferencias_estoque` | 40h |
| **Módulo RH** — frontend | Média | Backend completo | 24h |
| **Conectar dashboard a dados reais** — substituir mocks | Média | APIs de vendas/estoque | 16h |
| **Remover senha hardcoded** de `init_db.py` | Baixa | Variáveis de ambiente | 1h |

## Média Prioridade

| Item | Complexidade | Dependências | Est. |
|------|-------------|--------------|------|
| **Módulo Fiscal** — backend + frontend | Alta | Regras tributárias | 60h |
| **Módulo BI** — API + substituir mocks | Alta | Dados de vendas/estoque reais | 40h |
| **Scheduler/Executor de agendamentos** — consumir `autom_agendamentos` | Média | — | 16h |
| **Consumer de filas** — consumir `autom_filas` | Média | — | 16h |
| **Implementar sistema de migrations** (Alembic ou equivalente) | Média | — | 8h |
| **Módulo de Relatórios** | Média | Módulos fonte | 24h |
| **Integração real com CNC** (substituir mocks no `cnc_interface.py`) | Alta | Hardware CNC | 40h |

## Baixa Prioridade

| Item | Complexidade | Dependências | Est. |
|------|-------------|--------------|------|
| **Módulo Documentos** — backend + storage + frontend | Alta | Storage (S3/local) | 40h |
| **Rate limiting** nas APIs | Baixa | — | 4h |
| **CSRF protection** | Baixa | — | 2h |
| **Testes unitários backend** — cobertura dos módulos core | Média | Framework de teste | 16h |
| **Testes frontend** — cobertura dos componentes | Média | Jest + Testing Library | 24h |
| **Limpar tabelas órfãs** do schema SQL Fase 1 | Baixa | — | 2h |
| **Remover root legacy scripts** (`_atend.py`, `_auto.py`, etc.) | Baixa | Verificar dependências | 4h |

---

# 9. Variáveis de Ambiente

| Nome | Utilização | Obrigatória | Padrão |
|------|-----------|-------------|--------|
| `NEXT_PUBLIC_API_URL` | Frontend — URL da API Flask | Não | `http://localhost:5000` |
| `DB_HOST` | Backend — host PostgreSQL | Sim | `postgresql-database-h3bdeft4hgsbg9rcxklxidwt` |
| `DB_PORT` | Backend — porta PostgreSQL | Não | `5432` |
| `DB_NAME` | Backend — nome do banco | Não | `hermes_factory` |
| `DB_USER` | Backend — usuário PostgreSQL | Não | `postgres` |
| `DB_PASSWORD` | Backend — senha PostgreSQL | Sim | (vazio — hardcoded no código) |
| `DATABASE_URL` | Backend — URL completa PostgreSQL | Não | — |
| `ATHENA_TOKEN` | API token global | Não | `athena-token-123456789` |
| `ATHENA_USERS` | Lista de usuários `user:hash:role` | Não | Auto-gerado (admin) |
| `JWT_SECRET` | Segredo JWT | Não | Auto-gerado (`secrets.token_hex(32)`) |
| `HERMES_HOME` | Diretório de config | Não | `~/.hermes` |
| `BLING_DOMAIN` | Domínio para callback OAuth Bling | Sim (Bling) | — |
| `BLING_CLIENT_ID` | Client ID Bling OAuth | Sim (Bling) | — |
| `BLING_CLIENT_SECRET` | Client Secret Bling OAuth | Sim (Bling) | — |
| `SHOPEE_PARTNER_ID` | Partner ID Shopee | Sim (Shopee) | — |
| `SHOPEE_SHOP_ID` | Shop ID Shopee | Sim (Shopee) | — |
| `SHOPEE_API_KEY` | API Key Shopee | Sim (Shopee) | — |
| `TELEGRAM_BOT_TOKEN` | Token do bot Telegram | Sim (Telegram) | — |
| `EVOLUTION_API_KEY` | Chave Evolution API (WhatsApp) | Sim (WhatsApp) | `athena-evolution-key` |
| `PORT` | Porta do Flask | Não | `5000` |
| `NODE_ENV` | Ambiente Node.js | Não | `development` |

---

# 10. Arquivos de Configuração

| Arquivo | Finalidade |
|---------|-----------|
| `web/package.json` | Next.js 15 + React 19 + Tailwind 4 |
| `web/tsconfig.json` | TypeScript strict, bundler module resolution, paths `@/*` |
| `web/next.config.ts` | `output: "export"` (SPA estático) |
| `web/postcss.config.mjs` | PostCSS para Tailwind 4 |
| `web/.env.local.example` | Template de variáveis de ambiente |
| `hermes_agents/requirements.txt` | Dependências Python (10 pacotes) |
| `package.json` (raiz) | Monorepo npm workspace (`athena/`) |
| `athena/package.json` | ATHENA OS — Fastify, Prisma, Kafka, etc. |
| `athena/prisma/schema.prisma` | Schema do banco `athena` (40+ models) |
| `athena/docker-compose.yml` | Infra services (Kafka, Postgres, Redis, Qdrant, Mongo) |
| `athena/docker/development/docker-compose.yml` | Stack completa dev (inclui Prometheus, Grafana, Jaeger, Evolution API) |
| `athena/docker/production/Dockerfile` | Build multi-stage Node 22 |
| `docker/production/Dockerfile` | Hermes Flask produção (Python 3.11-slim) |
| `web/Dockerfile` | Next.js build + runner |
| `.github/workflows/cd.yml` | CI/CD — Docker build → GHCR → SSH deploy → Prisma migrate |
| `.gitignore` | Mínimo: `node_modules`, `.playwright-mcp/` |
| `.gitmodules` | Git submodules |

---

# 11. Fluxos do Sistema

## Login

```
Usuário → web/login/page.tsx → api.login(username, password)
  → POST /api/auth/login → valida credenciais → retorna JWT
  → localStorage.setItem("token", jwt) → redirect /dashboard

Auto-login bypass (se não há token):
  → layout.tsx injeta "athena-token-123456789" + user Admin
```

## Cadastro (CRUD genérico)

```
Frontend (CrudPanel.tsx) → api.cadList(tabela)
  → GET /api/cadastros/{tabela} → core/cadastros.py::list(tabela)
  → _resolve(tabela) via TABLES_MAP/EXTRA_MAP → asyncpg.fetch → retorna { data: [...] }
```

## Venda (PDV)

```
Frontend (pdv/page.tsx) → carrinho → api.pdvVenda(data)
  → POST /api/pdv/vendas → core/pdv.py::realizar_venda()
  → INSERT pdv_vendas + pdv_itens + pdv_pagamentos → reduz estoque
```

## Webhook Bling (pedido novo)

```
Bling ERP → POST /webhook/bling/pedido
  → routes/webhooks.py → valida HMAC → parse payload
  → insere/atualiza pedido → notifica via log
```

## WhatsApp Sales (n8n)

```
Evolution API → webhook/whatsapp → n8n workflow (whatsapp-sales-bot.json)
  → JavaScript intent classifier → pre-scripted reply
  → ou HTTP POST /api/whatsapp/webhook → Athena OS
```

## Telegram Sales

```
Telegram API → webhook → ag_06_telegram/bot_real.py
  → nlp.py classifica intenção → ag_06_telegram/__init__.py processa
  → recomenda produtos → calcula desconto → cria pedido
```

## Chat Hermes com Memória

```
Frontend (hermes/page.tsx) → api.chat(mensagem)
  → POST /api/hermes/chat → ag_10_diretor roteia para agente
  → ag_09_memoria busca contexto → agente responde
  → core/memory.py::store() salva interação
```

## Produção (Workflow Fase 3)

```
ag_04_planejador gera plano → ag_05_industrial inicia OP
  → cnc_interface.py aciona CNC → mold_lifecycle.py rastreia molde
  → ag_11_qualidade inspeciona → ag_12_manutencao agenda preventiva
```

---

# 12. Cobertura Geral

| Área | Frontend | Backend | Banco | API | Testado | Mock | Produção | Status |
|------|----------|---------|-------|-----|---------|------|----------|--------|
| **Login** | ✅ | 🟡 | N/A | ✅ | ❌ | ❌ | 🟡 | Auth RBAC + legacy, bypass automático |
| **Dashboard** | 🟡 | 🟡 | 🟡 | 🟡 | ❌ | 🟡 90% mock | ❌ | Gráficos mockados |
| **Cadastros** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo |
| **Produtos** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo |
| **Financeiro** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo |
| **Compras** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo |
| **CRM** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo |
| **PDV** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo |
| **Produção** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo |
| **Atendimento** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo |
| **Automações** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | 🟡 | Schema OK, sem executor |
| **RH** | 🔴 | ✅ | ✅ | ✅ | ❌ | ❌ | 🟡 | Backend completo, sem frontend |
| **BI** | 🟡 | 🔴 | 🔴 | 🔴 | ❌ | 🟡 100% mock | 🔴 | Só mock data |
| **Fiscal** | 🟡 | 🔴 | 🔴 | 🔴 | ❌ | 🟡 100% mock | 🔴 | Só mock data |
| **Documentos** | 🟡 | 🔴 | 🔴 | 🔴 | ❌ | 🟡 100% mock | 🔴 | Só mock data |
| **Vendas** | ✅ | ✅ | 🟡 | ✅ | ❌ | ❌ | ✅ | Dados reais via Bling |
| **Estoque** | ✅ | ✅ | 🟡 | ✅ | ❌ | ❌ | ✅ | Completo com multiloja |
| **Relatórios** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | 20 relatórios, dados reais |
| **Integrações** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Bling OAuth2 ativo |
| **Agentes** | ✅ | ✅ | ✅ | ✅ | ✅ (test_fase*.py) | 🟡 Alguns mocks | 🟡 | CNC mockado |
| **Workflows** | ✅ | ✅ | ✅ | ✅ | ❌ | 🟡 Alguns mocks | 🟡 | Em evolução |
| **Chat Hermes** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo |
| **n8n Workflows** | N/A | N/A | N/A | ✅ | ❌ | ❌ | ✅ | 2 workflows ativos |
| **Webhooks** | N/A | ✅ | N/A | ✅ | ❌ | ❌ | ✅ | WhatsApp + Bling + Shopee |
| **RBAC** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Completo — 81 permissões, 4 papéis |
| **Segurança** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Auditoria, logs, histórico |

---

# 13. Conclusão — Diagnóstico

## Percentual Aproximado de Conclusão

| Área | % |
|------|---|
| Backend (core modules) | **90%** — 16/16 módulos core completos |
| Backend (agents) | **75%** — 14 agentes, alguns com mocks CNC |
| Frontend (páginas funcionais) | **80%** — 20/22 páginas funcionais reais |
| Frontend (CRUD completo) | **85%** — 12 módulos com CRUD completo |
| Integrações externas | **75%** — Bling, Shopee, Telegram, WhatsApp ativos |
| Infraestrutura | **65%** — Docker, Coolify, CI/CD funcional |
| Autenticação/Segurança | **60%** — RBAC completo, auditoria, logs (sem enforcement em rotas) |
| Testes | **15%** — Apenas testes básicos Fase 2/3 |
| **Geral** | **≈75%** |

## Principais Gargalos Técnicos

1. **Autenticação parcialmente aplicada** — RBAC completo (81 permissões, 4 papéis, decorator `@requer_permissao`), mas decorator ainda não aplicado às rotas. Auto-login ainda presente.
2. **Monolito `athena_bridge.py`** (2299 linhas) — Difícil manutenção, duplicação com Blueprints.
3. **Sem migrations versionadas** — DDL executado em `import`, sem rollback.
4. **Auto-login bypass** — Qualquer visitante acessa o sistema como Admin.
5. **Sem scheduler/executor** — Estrutura de agendamentos e filas existe mas não funciona.
6. **Credenciais hardcoded** — Senha PostgreSQL visível em `init_db.py`, `migrate_fase*.py`.
7. **Duas stacks de banco separadas** — `hermes_factory` vs `athena` sem sincronização.

## Funcionalidades Críticas Ausentes

- Módulo de RH (frontend completo com tabs)
- Dashboard com dados reais (substituir ~50% de mock restante)
- Módulo de Documentos (backend + storage)

## Débitos Técnicos

| Item | Severidade |
|------|-----------|
| Duplicação de rotas (monolito vs Blueprints) | Alta |
| Dois sistemas de auth coexistindo | Alta |
| Tabelas órfãs sem módulo core | Média |
| Mock data espalhado em 5+ módulos | Média |
| Arquivos legacy na raiz (`_*.py`) | Baixa |
| Arquivo `_layout_new.tsx` órfão | Baixa |
| Chunk/cache/result files na raiz (c0.txt ~ r9.txt) | Baixa |

## APIs Não Utilizadas

- `/api/rh/*` — Backend completo mas frontend é placeholder
- `/api/estoque/*` — Endpoints existem (Fase 3) mas frontend é placeholder
- Tabelas `vendas`, `anuncios`, `fichas_tecnicas` — Existem no banco mas sem API CRUD dedicada

## Arquivos Órfãos

| Arquivo | Motivo |
|---------|--------|
| `web/src/app/_layout_new.tsx` | Layout incompleto, não usado |
| `_atend.py`, `_auto.py`, `_comp.py`, `_crm.py`, `_prod.py`, `_pdv.py` (raiz) | Scripts legados, substituídos pelos módulos `core/` |
| `_atendfront.py`, `_autofront.py`, etc. (raiz) | Frontends legados |
| `_fixcad.py`, `_fixkb.py`, `_fixrh.py`, `_fixrh2.py` (raiz) | Scripts de correção pontual |
| `c0.txt` ~ `c16.txt`, `chunk0.txt` ~ `chunk2.txt`, `r0.txt` ~ `r9.txt` (raiz) | Cache/resultados de processamento, não versionáveis |
| `cmd_init.txt`, `cmd0.txt` (raiz) | Comandos de deploy legados |

## Componentes Sem Uso

- `_layout_new.tsx` — Alternativa de layout incompleta
- Dados mock em `bi/data/`, `fiscal/data/` — Serão substituídos quando APIs existirem

## Melhorias Arquiteturais Recomendadas

1. **Unificar auth** — Remover sistema antigo, aplicar `require_role()` em todas as rotas
2. **Completar migração para Blueprints** — Mover todas as rotas de `athena_bridge.py` para `routes/`
3. **Implementar Alembic** para migrations versionadas do banco Hermes
4. **Extrair credenciais** para variáveis de ambiente (sem fallback hardcoded)
5. **Adicionar middleware de logging/rate-limit/CSRF**
6. **Implementar scheduler** para ler e executar `autom_agendamentos`
7. **Unificar bancos ou criar sync** entre `hermes_factory` e `athena`
8. **Adicionar testes** — Pytest para backend, Jest para frontend

## Próximos Passos (Ordem de Prioridade)

1. **Aplicar `@requer_permissao` nas rotas** — 4h
2. **Remover auto-login bypass** — 1h
3. **Remover senhas hardcoded** — 1h
4. **Construir frontend de RH** — 24h
5. **Conectar dashboard a dados reais** — 8h
6. **Construir módulo de Documentos** — 40h
7. **Implementar scheduler de agendamentos** — 16h
8. **Limpar código legacy e duplicações** — 12h

---

*Auditoria gerada automaticamente com base na análise estática do código-fonte em 2026-07-14.*
