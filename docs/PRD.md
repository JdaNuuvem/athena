# ATHENA — Product Requirements Document (PRD)

**Data:** 2026-07-16 | **Versão:** 1.0 | **110 páginas | 16 módulos core | 45 testes**

---

## 1. Dashboard

**Propósito:** Visão consolidada do negócio em tempo real. KPIs financeiros, vendas, estoque, agentes e alertas.

**Funcionalidades:**
- [x] KPIs: vendas dia/mês, ticket médio, receita 30d, fluxo caixa, estoque crítico
- [x] Gráfico de vendas do mês (LineChart Recharts)
- [x] Lista de agentes ativos com status
- [ ] Filtro por loja/depósito
- [ ] Alertas dinâmicos (estoque baixo, vencimentos)
- [ ] Widgets customizáveis por usuário

**Backend:** `GET /api/kpi/overview`, `GET /api/relatorios/vendas`, `GET /api/relatorios/estoque`, `GET /api/relatorios/fluxo-caixa`
**Frontend:** `web/src/app/dashboard/page.tsx` (2.91 KB)
**Status:** 🟢 Funcional com dados reais

---

## 2. Cadastros

**Propósito:** CRUD de entidades base do sistema: empresas, clientes, fornecedores, transportadoras, vendedores.

**Funcionalidades:**
- [x] Empresas (multiempresa com vínculos)
- [x] Clientes (com endereços, contatos, tags, histórico)
- [x] Fornecedores (com endereços, contatos, tags)
- [x] Transportadoras (com fretes, contatos)
- [x] Vendedores (com metas e comissões)
- [ ] Usuários e grupos (migrado para RBAC)
- [ ] Permissões (migrado para RBAC)

**Backend:** `core/cadastros.py` — 17 tabelas, CRUD genérico + queries especiais
**Frontend:** `web/src/app/cadastros/page.tsx` (5.58 KB)
**Status:** 🟢 Completo

---

## 3. Produtos

**Propósito:** Catálogo de produtos com hierarquia pai/filho (variações), integração Bling, edição inline.

**Funcionalidades:**
- [x] Listagem com busca por SKU/nome
- [x] Hierarquia pai/filho (variações: cor, tamanho)
- [x] Badge de variações ("N variações")
- [x] Página de detalhe com 7 abas (Visão Geral, Cadastro, Variações, Kits/BOM, Lotes, Localização, Controle)
- [x] Edição de cadastro (descrição, categoria, marca, NCM, tipo)
- [x] Sync com Bling (produtos + variações + atributos)
- [x] SSOT via `catalogo_produtos` (single source of truth)
- [ ] Push de edições para Bling (two-way sync)
- [ ] Upload de imagens
- [ ] Carrinho de compras (link com PDV)

**Backend:** `core/catalogo.py`, `bling_erp.py`, `GET/PUT /api/produtos`, `GET /api/bling/produtos/agrupados`
**Frontend:** `web/src/app/produtos/page.tsx` (3.01 KB), `web/src/app/produtos/[sku]/` (7 abas)
**Status:** 🟢 Funcional — pendente push Bling

---

## 4. Estoque

**Propósito:** Gestão de inventário multidepósito com integração Bling, filtros avançados e edição inline.

**Funcionalidades:**
- [x] Visualização por depósito (seletor multiloja)
- [x] Filtros: SKU, nome, ID, status, nível estoque
- [x] Edição inline com botões +/- 1/10
- [x] Modal de estoque por depósito com "Dividir Igualmente"
- [x] Sincronização com Bling (saldo por depósito)
- [x] Indicadores coloridos (verde/amarelo/vermelho)
- [x] Imagens dos produtos
- [x] Visualização agrupada (pai/filho) ou flat
- [ ] Transferência entre depósitos
- [ ] Histórico de movimentações
- [ ] Alertas de estoque mínimo

**Backend:** `bling_erp.py`, `GET /api/bling/estoque`, `PUT /api/bling/estoque`, `GET /api/bling/depositos`
**Frontend:** `web/src/app/estoque/page.tsx` (4.5 KB) + sub-páginas
**Status:** 🟢 Funcional

---

## 5. Compras

**Propósito:** Pipeline de compras: Solicitação → Cotação → Pedido → Recebimento → Nota Entrada.

**Funcionalidades:**
- [x] Fornecedores (CRUD completo)
- [x] Solicitações de compra com aprovação
- [x] Cotações vinculadas a fornecedor
- [x] Pedidos de compra com itens
- [x] Recebimento com conferência
- [x] Notas de entrada
- [ ] Integração com Bling (fornecedores → contatos)
- [ ] Workflow de aprovação multi-etapa
- [ ] Dashboard de compras com KPIs

**Backend:** `core/compras.py` — 7 tabelas, CRUD, `POST /api/compras/solicitacoes/{id}/aprovar`
**Frontend:** `web/src/app/compras/` — dashboard + 6 sub-páginas
**Status:** 🟢 Funcional

---

## 6. Vendas

**Propósito:** Gestão de pedidos de venda, faturamento, integração com Bling.

**Funcionalidades:**
- [x] Listagem de pedidos com filtros e DataTable
- [x] Cards KPIs resumindo vendas
- [x] Dados reais via Bling API
- [ ] CRUD de pedidos local
- [ ] Status customizável
- [ ] Vinculação com PDV
- [ ] Comissões por vendedor

**Backend:** `bling_erp.py` (listar_pedidos), `core/relatorios.py` (agregações)
**Frontend:** `web/src/app/vendas/page.tsx` (4.79 KB)
**Status:** 🟡 Parcial — dados Bling, sem CRUD local

---

## 7. PDV (Ponto de Venda)

**Propósito:** Frente de caixa para loja física. Venda rápida, múltiplos pagamentos, gestão de caixa.

**Funcionalidades:**
- [x] Carrinho de vendas com busca por código/SKU
- [x] Atalhos de teclado (F2=buscar, F4=desconto, F5=dinheiro, F6=PIX, Enter=finalizar)
- [x] Múltiplas formas de pagamento (dinheiro, PIX, cartão, vale, voucher, crediário)
- [x] Abertura/fechamento de caixa com saldo
- [x] Sangria e suprimento
- [x] Histórico de vendas com status
- [x] Cancelamento de venda
- [ ] Emissão NFC-e / SAT
- [ ] Leitor de código de barras
- [ ] Modo offline com sync
- [ ] Impressão de comprovante

**Backend:** `core/pdv.py` — 10 tabelas, `realizar_venda()`, `abrir_caixa()`, `fechar_caixa()`
**Frontend:** `web/src/app/pdv/page.tsx` (4.21 KB)
**Status:** 🟢 Fase 1 funcional — pendente fiscal/offline

---

## 8. Financeiro

**Propósito:** Controle financeiro completo: fluxo de caixa, contas a pagar/receber, DRE, conciliação, PIX, boletos.

**Funcionalidades:**
- [x] Fluxo de caixa (CRUD + resumo)
- [x] Contas a pagar e receber
- [x] DRE (Demonstrativo de Resultados)
- [x] Bancos e contas
- [x] Conciliação bancária
- [x] Boletos e PIX
- [x] Centro de custo e plano de contas
- [ ] Integração Bling (contas a pagar/receber)
- [ ] Dashboard financeiro com gráficos
- [ ] Previsão de fluxo de caixa

**Backend:** `core/financeiro.py` — 10 tabelas, CRUD, `fluxo_caixa_resumo()`, `dre_resumo()`
**Frontend:** `web/src/app/financeiro/page.tsx` (3.46 KB) — 8 tabs
**Status:** 🟢 Funcional — pendente integração Bling

---

## 9. Fiscal

**Propósito:** Gestão tributária: notas fiscais, obrigações, tributos, tabelas, apuração.

**Funcionalidades:**
- [x] Notas fiscais (via Bling com download XML/DANFE)
- [x] Obrigações fiscais
- [x] Tabelas de impostos
- [x] Tributos
- [x] Apuração de impostos
- [ ] Emissão de NF-e própria
- [ ] SPED Fiscal/Contribuições
- [ ] Integração com contador

**Backend:** `bling_erp.py` (listar_notas_fiscais, get_nfe_xml), `core/fiscal.py`
**Frontend:** `web/src/app/fiscal/` — 5 sub-páginas
**Status:** 🟡 Parcial — dados Bling, sem emissão própria

---

## 10. CRM

**Propósito:** Gestão de relacionamento com clientes: funil de vendas, leads, contatos, negociações, propostas, contratos.

**Funcionalidades:**
- [x] Funil de vendas com gráfico de barras
- [x] Leads (CRUD + status)
- [x] Contatos (CRUD)
- [x] Empresas (CRUD)
- [x] Negociações com pipeline (etapas: captação → fechamento)
- [x] Atividades/Follow-ups
- [x] Propostas comerciais
- [x] Contratos
- [ ] Importar contatos do Bling (endpoint pronto)
- [ ] Segmentação e tags
- [ ] Email marketing
- [ ] Relatórios de conversão

**Backend:** `core/crm.py` — 7 tabelas, CRUD, `funil()`
**Frontend:** `web/src/app/crm/` — dashboard + 7 sub-páginas
**Status:** 🟢 Funcional — pendente importação Bling

---

## 11. Atendimento

**Propósito:** Central de atendimento multicanal: tickets, chat, WhatsApp, Telegram, Instagram, Facebook, SLA, base de conhecimento.

**Funcionalidades:**
- [x] Tickets com status e prioridade
- [x] Canais (WhatsApp, Telegram, Instagram, Facebook, Chat, Email)
- [x] SLA por prioridade (baixa/normal/alta/urgente)
- [x] Base de conhecimento com busca
- [ ] Chat em tempo real
- [ ] Integração WhatsApp Business API
- [ ] Bot de atendimento automático
- [ ] Relatórios de atendimento

**Backend:** `core/atendimento.py` — 6 tabelas, CRUD
**Frontend:** `web/src/app/atendimento/` — dashboard + 5 sub-páginas
**Status:** 🟢 Funcional

---

## 12. Produção

**Propósito:** Gestão fabril: OPs (ordens de produção), BOM (lista de materiais), máquinas, apontamentos, custos, perdas.

**Funcionalidades:**
- [x] Ordens de produção (CRUD + iniciar/finalizar)
- [x] Lista de materiais (BOM)
- [x] Máquinas (CRUD + parar/liberar)
- [x] Apontamentos de produção (bom/refugo/horas)
- [x] Consumo de materiais (previsto vs real)
- [x] Custos de produção
- [x] Perdas e refugos
- [ ] Planejamento de produção (PCP)
- [ ] Integração com CNC (mock atual)
- [ ] Dashboard de OEE

**Backend:** `core/producao.py` — 7 tabelas, CRUD + operações
**Frontend:** `web/src/app/producao/` — dashboard + 7 sub-páginas
**Status:** 🟢 Funcional — CNC mockado

---

## 13. RH

**Propósito:** Gestão de recursos humanos: funcionários, ponto, férias, escala, folha, benefícios.

**Funcionalidades:**
- [x] Funcionários (CRUD)
- [x] Ponto eletrônico
- [x] Férias
- [x] Escala de trabalho
- [x] Folha de pagamento
- [x] Benefícios
- [ ] Frontend completo (atualmente placeholder)
- [ ] Cálculo automático de encargos
- [ ] Portal do funcionário

**Backend:** `core/rh.py` — 7 tabelas, CRUD, `ponto_por_data()`, `folha_resumo()`, `beneficios_resumo()`
**Frontend:** `web/src/app/rh/` — placeholder + 6 sub-páginas
**Status:** 🟡 Backend completo, frontend parcial

---

## 14. BI (Business Intelligence)

**Propósito:** Dashboards analíticos: forecast, indicadores, ML, vendas.

**Funcionalidades:**
- [x] Forecast (previsão de vendas)
- [x] Indicadores de desempenho
- [x] ML (machine learning)
- [x] Vendas históricas
- [ ] Conexão com dados reais (parcialmente mock)
- [ ] Exportação de relatórios
- [ ] Dashboards customizáveis

**Backend:** `GET /api/relatorios/*` (dados reais)
**Frontend:** `web/src/app/bi/` — 4 sub-páginas (parcialmente mock)
**Status:** 🟡 Parcial — APIs reais, frontend com alguns mocks

---

## 15. Documentos

**Propósito:** Gestão documental com upload, storage e vínculo com entidades.

**Funcionalidades:**
- [x] Upload drag-and-drop
- [x] Grid com preview (ícones por tipo)
- [x] Vínculo com entidades (produto, pedido, contrato, NF, etc.)
- [x] Download/visualização inline
- [x] Remoção de arquivos
- [x] Stats (total arquivos, espaço usado)
- [ ] Versionamento de arquivos
- [ ] Storage S3/cloud
- [ ] Assinatura digital

**Backend:** `core/documentos.py` — 1 tabela, storage local
**Frontend:** `web/src/app/documentos/page.tsx` (2.16 KB)
**Status:** 🟢 Funcional

---

## 16. Automações

**Propósito:** Motor de automação: webhooks, filas, eventos, agendamentos, integrações, bots, IA.

**Funcionalidades:**
- [x] Webhooks (CRUD + headers/body template)
- [x] Filas de processamento
- [x] Eventos e gatilhos
- [x] Agendamentos (cron expression)
- [x] Integrações externas
- [x] Bots
- [x] Modelos de IA
- [ ] Executor de filas (consumer)
- [ ] Scheduler de agendamentos (runner)
- [ ] Workflow builder visual

**Backend:** `core/automacoes.py` — 7 tabelas, CRUD
**Frontend:** `web/src/app/automacoes/` — dashboard + 7 sub-páginas
**Status:** 🟡 CRUD funcional, sem executor

---

## 17. Relatórios

**Propósito:** Relatórios gerenciais com dados reais: vendas, lucro, estoque, DRE, fluxo caixa, ticket médio, previsão.

**Funcionalidades:**
- [x] Vendas (total, diárias, chart)
- [x] Lucro e margem
- [x] Estoque (itens, ruptura, baixo)
- [x] Clientes (total, novos, top)
- [x] Fornecedores (total, ativos, top)
- [x] DRE (receita bruta, CMV, lucro bruto)
- [x] Fluxo de caixa
- [x] Ticket médio
- [x] Aging financeiro
- [x] Previsão de vendas
- [ ] Filtro por loja/depósito
- [ ] Exportação PDF/Excel
- [ ] Agendamento de relatórios

**Backend:** `core/relatorios.py` — 10 funções de agregação, 10 endpoints REST
**Frontend:** `web/src/app/relatorios/` — dashboard com 20 cards + 19 sub-páginas
**Status:** 🟢 Funcional

---

## 18. Agentes (Agent Swarm)

**Propósito:** 14 agentes IA especializados para tomada de decisão autônoma em produção, vendas, qualidade, manutenção e pricing.

**Funcionalidades:**
- [x] ag_01 — Caçador de produtos
- [x] ag_02 — Lucratividade
- [x] ag_03 — Marketplaces
- [x] ag_04 — Planejador de produção
- [x] ag_05 — Industrial (CNC, moldes, OEE) — parcialmente mock
- [x] ag_06 — Telegram (NLP, bot de vendas)
- [x] ag_07 — Laboratório (pipeline de lançamentos)
- [x] ag_08 — Lojas
- [x] ag_09 — Memória corporativa
- [x] ag_10 — Diretor (roteamento)
- [x] ag_11 — Qualidade
- [x] ag_12 — Manutenção
- [x] ag_13 — ML (scikit-learn)
- [x] ag_14 — WhatsApp
- [x] ag_201~205 — Financeiros

**Backend:** `hermes_agents/ag_*/`, `hermes_agents/finance/`
**Frontend:** `web/src/app/agents/` — lista + detalhe com chat
**Status:** 🟡 75% funcional — CNC mockado

---

## 19. Bling (Integração ERP)

**Propósito:** Integração completa com Bling ERP v3: OAuth2, produtos, pedidos, NF-e, contatos, financeiro, webhooks.

**Funcionalidades:**
- [x] OAuth2 (authorization code + refresh token)
- [x] Produtos (CRUD + variações pai/filho + atributos)
- [x] Pedidos/Vendas (lista + analytics + detalhe)
- [x] Depósitos + Estoque (saldo + ajuste)
- [x] NF-e (lista + download XML + DANFE)
- [x] Webhooks (registro + HMAC validation)
- [x] Notificações (lista + confirmação)
- [x] Contatos (clientes e fornecedores)
- [x] Categorias de produtos
- [x] Formas de pagamento
- [ ] Two-way sync (Athena → Bling)
- [ ] Token persistente entre deploys

**Backend:** `bling_erp.py` (748 linhas), `routes/integrations.py` (30+ endpoints), `routes/webhooks.py`
**Frontend:** `web/src/app/integracoes/bling/` — dashboard + 6 abas
**Status:** 🟢 90% funcional

---

## 20. Hermes (Chat IA)

**Propósito:** Assistente de IA com memória, roteamento entre agentes e interface de chat.

**Funcionalidades:**
- [x] Chat UI com bolhas e sugestões
- [x] Roteamento inteligente (ag_10 diretor)
- [x] Memória conversacional (recall/store/history)
- [x] Contexto de memória injetado no prompt
- [x] Indicador de digitação
- [ ] Multi-turn com contexto de conversa
- [ ] Execução de ações (não só respostas)
- [ ] Integração com WhatsApp/Telegram

**Backend:** `POST /api/hermes/chat`, `core/memory.py`
**Frontend:** `web/src/app/hermes/page.tsx` (1.83 KB)
**Status:** 🟢 Funcional

---

## 21. Segurança & Governança

**Propósito:** RBAC, auditoria, logs, histórico de alterações.

**Funcionalidades:**
- [x] RBAC — 4 tabelas, 81 permissões, 4 papéis, 4 usuários
- [x] Auditoria de ações (login, CRUD) com filtro
- [x] Logs de sistema com níveis (DEBUG/INFO/WARN/ERROR/FATAL)
- [x] Histórico de alterações por entidade
- [x] Bling Logger com Correlation ID
- [x] Health check da integração Bling
- [ ] 2FA (TOTP)
- [ ] SSO (OAuth2/OIDC)
- [ ] LGPD (export/deletion)
- [ ] Criptografia de dados sensíveis

**Backend:** `core/rbac.py`, `core/seguranca.py`, `core/bling_logger.py`
**Frontend:** `web/src/app/seguranca/` — dashboard + 4 sub-páginas
**Status:** 🟢 RBAC + Auditoria completos

---

## 22. Testes

**Propósito:** Cobertura de testes unitários para todos os módulos críticos.

**Cobertura atual:**
- [x] Bling SDK — 10 testes (auth, API, sync, webhooks)
- [x] Bling Routes — 9 testes (Flask endpoints)
- [x] Relatórios — 11 testes (todas funções de agregação)
- [x] Webhooks — 4 testes (HMAC, processamento)
- [x] Catálogo — 3 testes
- [x] Financeiro — 5 testes
- [x] Fiscal — 3 testes
- [x] CRM + Bling — 2 testes
- [ ] Testes de integração (end-to-end)
- [ ] Testes de frontend (Jest + Testing Library)
- [ ] Testes de carga/performance

**Total:** 45 testes unitários (100% pass)
**Arquivos:** `hermes_agents/tests/` — 9 arquivos de teste

---

## Resumo por Status

| Status | Módulos |
|--------|---------|
| 🟢 Completo | Dashboard, Cadastros, Produtos, Estoque, Compras, CRM, Atendimento, Produção, Documentos, Relatórios, Hermes, Segurança |
| 🟡 Parcial | Vendas, PDV, Financeiro, Fiscal, BI, Automações, RH, Agentes, Bling |
| 🔴 Não iniciado | — |

---

## Próximos Passos (Ordem de Prioridade)

1. **Bling token persistente** (env var BLING_ACCESS_TOKEN)
2. **Two-way sync estoque** (Athena ↔ Bling)
3. **Push de edições de produto** (Athena → Bling)
4. **Importar contatos Bling → CRM**
5. **Filtro por loja/depósito** em todos os módulos
6. **Frontend RH** completo
7. **Executor de automações** (filas + scheduler)
8. **NFC-e / SAT** no PDV
