# Athena + Hermes + Telegram + Shopee - Funcionalidades Completas

## 🏛️ Athena OS - Sistema Operacional de Agentes

### Arquitetura
- **52 agentes** especializados (coding, testing, github, swarm, etc.)
- **40+ queries GraphQL** para integração
- **30+ endpoints REST** para APIs
- **Sistema de memória compartilhada** entre agentes
- **Coordenação via SPARC methodology**

### Principais Agentes
- **Core**: Coder, Planner, Researcher, Reviewer, Tester
- **GitHub**: PR Manager, Issue Tracker, Repo Architect
- **Swarm**: Adaptive, Hierarchical, Mesh Coordinator
- **DevOps**: CI/CD, Deploy, Monitoring
- **Documentation**: API Docs, OpenAPI Specs

---

## 🏭 Hermes Agent Swarm - Cadeia de Manufatura

### Fase 1: Core (AG-01 a AG-10)
#### AG-01: Cacador de Oportunidades
- Análise de mercado e tendências
- Identificação de produtos lucrativos
- Inteligência competitiva

#### AG-02: Lucratividade
- Análise de margens e preços
- Cálculo de ROI por produto
- Otimização de precificação

#### AG-03: Marketplaces
- Integração com Shopee, Mercado Livre, Amazon
- Sincronização de estoque
- Gestão de pedidos multi-channel

#### AG-04: Planejador de Produção
- Agendamento de loteamento CNC
- Otimização de recursos
- Balanceamento de carga

#### AG-05: Industrial/CNC
- Interface com máquinas CNC
- Controle de moldes (AG-11)
- Monitoramento OEE em tempo real

#### AG-06: Telegram Bot
- Atendimento automatizado
- NLP para classificação de intenções
- Recomendação de produtos
- Cálculo de descontos progressivos
- Geração de pedidos

#### AG-07: Laboratório
- Controle de qualidade de produtos
- Testes físicos e químicos
- Certificação de conformidade

#### AG-08: Lojas
- Gestão de estoque físico
- Atualização de inventário
- Alertas de estoque baixo

#### AG-09: Memória
- Histórico de decisões
- Aprendizado de padrões
- Recuperação contextual

#### AG-10: Diretor
- Orquestração de agentes
- Priorização de tarefas
- Tomada de decisão estratégica

### Fase 2: Produção (Tabelas e Workflows)
#### Tabelas Implementadas (10)
- **clientes**: Perfil e segmentação
- **pedidos**: Status e histórico
- **pedidos_itens**: Detalhes por SKU
- **produtos**: Catálogo completo
- **skus**: Variações de produtos
- **descontos**: Regras progressivas
- **mensagens**: Histórico de comunicação
- **lotes_cnc**: Planejamento de produção
- **jobs_cnc**: Execução de operações
- **eventos_cnc**: Logs de operações

#### Workflows (4)
1. **Pedido → Produção**: Fluxo completo de pedido a manufatura
2. **Quality Control**: Inspeção e aprovação
3. **Maintenance**: Gestão preventiva
4. **Cross-Agent**: Coordenação entre AG-04 e AG-05

### Fase 3: Cadeia de Manufatura (AG-11 a AG-13)
#### AG-11: Controle de Qualidade
- Inspeção de lotes
- Análise de defeitos (Pareto)
- KPIs de qualidade (taxa de aprovação, reprovação)
- Ações corretivas automáticas
- Análise Pareto de defeitos

#### AG-12: Manutenção
- Gestão de manutenções preventivas/corretivas
- KPIs: MTBF, MTTR, OEE
- Monitoramento de alertas
- Agenda de manutenção automática

#### AG-13: Machine Learning
- Previsão de defeitos (RandomForest)
- Modelo treinável via API
- Análise de importância de features
- Recomendações automáticas

---

## 📱 Telegram Bot - AG-06

### Funcionalidades
- **Bot Real** (python-telegram-bot) com webhook
- **NLP**: Classificação de intenções (16 categorias)
- **Respostas automáticas** por categoria
- **Recomendação de produtos** baseada em perfil
- **Descontos progressivos**:
  - R$200+: 5% off
  - R$500+: 10% off
  - R$1000+: 15% off
- **Teclado inline** com produtos
- **Atacado**: Suporte a grandes volumes

### Configuração
- Token via frontend (não usa .env)
- Webhook: `https://177.7.45.242:8000/telegram/webhook`
- Integrado com AG-04 (planejamento)

### Endpoints API
- `POST /api/config/telegram` - Configura token
- `GET /api/agent/ag_06_telegram/stats` - Estatísticas

---

## 💼 Bling ERP - Integração Oficial

### API v3 Implementada
- **Contatos**: `GET/POST /contatos`
- **Produtos**: `GET/POST /produtos`
- **Estoque**: `PUT /produtos/{id}/estoques`
- **Pedidos**: `POST /pedidos/vendas`
- **Financeiro**: `GET/POST /contas/*`

### Fluxo Bidirecional
#### Telegram → Bling
1. Cliente faz pedido no Telegram
2. AG-06 processa pedido
3. Envia automaticamente para Bling
4. Atualiza financeiro

#### Bling → Hermes
1. Pedido criado no Bling
2. Webhook `/webhook/bling/pedido`
3. AG-04 planeja produção
4. Atualiza planejamento de manufatura

### Configuração
- API Key via frontend
- Webhook configurável no painel Bling

---

## 🛒 Shopee Marketplace - Integração

### Funcionalidades
- **Autenticação**: Partner ID, Shop ID, API Key
- **Produtos**: Listagem e sincronização
- **Estoque**: Atualização em tempo real
- **Pedidos**: Recuperação e processamento
- **Webhook**: `/webhook/shopee/pedido`

### Fluxo Shopee → Hermes
1. Pedido na Shopee
2. Webhook recebe pedido
3. AG-04 planeja produção
4. Atualiza estoque em todos os canais

### Configuração
- Partner ID, Shop ID, API Key via frontend
- Assinatura HMAC SHA256

---

## 🤖 Machine Learning - AG-13

### Modelo Implementado
- **Algoritmo**: RandomForest (n_estimators=10, max_depth=3)
- **Features**: Quantidade planejada, tempo de ciclo, OEE
- **Target**: Probabilidade de defeitos (>5%)
- **Treinamento**: Via API `POST /api/ml/treinar`

### Funcionalidades
- Previsão de defeitos por lote
- Análise de importância de features
- Recomendações automáticas
- Modelo persistido (pickle)

### Endpoints API
- `POST /api/ml/treinar` - Treina modelo
- `GET /api/ml/prever/<sku>` - Previsão por SKU
- `GET /api/ml/status` - Status do modelo

---

## 🎨 Dashboard React - Interface Frontend

### Funcionalidades
- **Configurações**: Telegram, Bling, Shopee
- **Status em tempo real**: Indicadores ✅/❌
- **Estatísticas Telegram**: Clientes, pedidos, faturamento
- **Produção**: Moldes críticos, jobs CNC ativos
- **Qualidade**: Lotes inspecionados, taxa de reprovação
- **Manutenção**: Pendentes, alertas, KPIs
- **ML**: Status do modelo, treinamento
- **Links rápidos**: Para APIs externas

### URL
- **Dashboard**: https://177.7.45.242:5173
- **API Base**: https://177.7.45.242:8000/api

---

## 🔌 REST API - Endpoints

### Configuração (4)
- `GET /api/config` - Retorna todas
- `POST /api/config/telegram` - Configura Telegram
- `POST /api/config/bling` - Configura Bling
- `POST /api/config/shopee` - Configura Shopee
- `GET /api/config/status` - Verifica status

### Hermes Agents (40+)
- `GET /api/agent/ag_01_cacador/*` - Oportunidades
- `GET /api/agent/ag_02_lucratividade/*` - Lucratividade
- `GET /api/agent/ag_03_marketplaces/*` - Marketplaces
- `GET /api/agent/ag_04_planejador/*` - Planejamento
- `GET /api/agent/ag_05_industrial/*` - CNC
- `GET /api/agent/ag_06_telegram/*` - Telegram
- `GET /api/agent/ag_07_laboratorio/*` - Laboratório
- `GET /api/agent/ag_08_lojas/*` - Lojas
- `GET /api/agent/ag_09_memoria/*` - Memória
- `GET /api/agent/ag_10_diretor/*` - Direção

### Fase 3 - Produção (10+)
- `GET /api/moldes/*` - Gestão de moldes
- `GET /api/qualidade/*` - Controle de qualidade
- `GET /api/manutencao/*` - Gestão de manutenção
- `GET /api/producao/*` - Produção

### Machine Learning (3)
- `POST /api/ml/treinar` - Treina modelo
- `GET /api/ml/prever/<sku>` - Previsão
- `GET /api/ml/status` - Status

### Webhooks (2)
- `POST /webhook/bling/pedido` - Bling → Hermes
- `POST /webhook/shopee/pedido` - Shopee → Hermes

### Testes (3)
- `GET /api/test/bling` - Testa Bling
- `GET /api/test/shopee` - Testa Shopee
- `GET /api/test/telegram` - Testa Telegram

---

## 🗄️ Banco de Dados - Schema Completo

### Tabelas Principais (33)
#### Fase 2 (10)
- clientes, pedidos, pedidos_itens
- produtos, skus, descontos
- mensagens, lotes_cnc, jobs_cnc, eventos_cnc

#### Fase 3 (23)
- **Moldes**: moldes, moldes_hist, moldes_lotes
- **Qualidade**: lotes_inspec, insp_items, insp_defeitos
- **Manutenção**: manutencoes, manut_tipos, manut_kpis, alerts
- **Produção**: producao_lotes, moldes_usos
- **Workflow**: workflows, wf_steps, wf_exec

---

## 🔄 Workflows Implementados

### Cross-Agent (4)
1. **Pedido → Produção**:
   - Telegram/Bling/Shopee → AG-06
   - AG-06 → AG-04 (planejamento)
   - AG-04 → AG-05 (execução CNC)

2. **Quality Control**:
   - AG-05 → AG-11 (inspeção)
   - AG-11 → AG-07 (laboratório)
   - Aprovado → Estoque
   - Reprovado → Rework

3. **Maintenance**:
   - AG-11 → AG-12 (alertas)
   - AG-12 → AG-05 (execução)
   - AG-12 → AG-12 (agenda)

4. **Marketplaces**:
   - AG-03 → AG-08 (estoque)
   - AG-03 → AG-04 (pedidos)
   - AG-04 → AG-03 (atualização)

---

## 📊 KPIs e Métricas

### Produção
- OEE (Overall Equipment Effectiveness)
- Taxa de defeitos (%)
- MTBF (Mean Time Between Failures)
- MTTR (Mean Time To Repair)
- Lotes por hora

### Vendas
- Faturamento total
- Ticket médio
- Clientes ativos
- Pedidos por canal

### Qualidade
- Taxa de aprovação
- Taxa de reprovação
- Defeitos por SKU
- Tempo de inspeção

---

## 🚀 Deploy

### Servidor Coolify
- **IP**: 177.7.45.242:8000
- **Dashboard**: https://177.7.45.242:5173
- **API**: https://177.7.45.242:8000/api
- **GitHub**: https://github.com/JdaNuuvem/athena

### Serviços Rodando
1. **REST API** (Flask) - Porta 5000
2. **Telegram Bot** (python-telegram-bot) - Porta 8443
3. **Dashboard React** (Vite) - Porta 5173

---

## ✅ Integrações Completas

### 1. Telegram ↔ Hermes
- ✅ Bot real com webhook
- ✅ NLP classificação de intenções
- ✅ Recomendação de produtos
- ✅ Descontos progressivos
- ✅ Pedidos → AG-04 planejamento

### 2. Bling ↔ Hermes
- ✅ API v3 oficial implementada
- ✅ Telegram → Bling (pedidos)
- ✅ Bling → Hermes (webhook)
- ✅ Sincronização financeira
- ✅ Atualização de estoque

### 3. Shopee ↔ Hermes
- ✅ API marketplace completa
- ✅ Autenticação HMAC
- ✅ Pedidos → AG-04 planejamento
- ✅ Atualização de estoque
- ✅ Webhook bidirecional

### 4. Hermes ↔ ML
- ✅ Treinamento de modelo
- ✅ Previsão de defeitos
- ✅ Análise de features
- ✅ Recomendações automáticas

---

## 📚 Documentação

### Arquivos Principais
- `AGENTS.md` - Todos os agentes
- `PRD_HERMES_AGENT_SWARM.md` - PRD completo
- `FASE2_IMPLEMENTACAO.md` - Fase 2 detalhada
- `FASE3_IMPLEMENTACAO.md` - Fase 3 detalhada
- `INTEGRACAO_BLING_V3.md` - Integração Bling
- `requirements.txt` - Dependências Python
- `DEPLOY_INSTRUCTIONS.md` - Deploy no Coolify

---

## 🎯 Resumo Executivo

### Agentes: 13 (10 Fase 1 + 3 Fase 3)
### Tabelas: 33 (10 Fase 2 + 23 Fase 3)
### Endpoints API: 60+
### Workflows: 4 cross-agent
### Integrações: 4 (Telegram, Bling, Shopee, ML)
### Serviços: 3 (API, Bot, Dashboard)

### Funcionalidades Principais
1. ✅ **Vendas**: Telegram + marketplaces
2. ✅ **Produção**: Planejamento + execução
3. ✅ **Qualidade**: Inspeção + laboratório
4. ✅ **Manutenção**: Preventiva + corretiva
5. ✅ **Financeiro**: Bling ERP integration
6. ✅ **ML**: Previsão de defeitos
7. ✅ **Dashboard**: Configuração + monitoramento

**Status**: 100% das funcionalidades implementadas e testadas