# Documentação Técnica: Integração Hermes ↔ Athena OS

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        ATHENA OS                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Frontend    │  │  GraphQL     │  │  REST API    │         │
│  │  (React)     │  │  API         │  │  Routes      │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                   │                │
│         └─────────────────┴───────────────────┘                │
│                           │                                      │
│                    ┌──────▼──────┐                               │
│                    │  Hermes     │                               │
│                    │  Sync       │                               │
│                    │  (TypeScript)│                              │
│                    └──────┬──────┘                               │
└───────────────────────────┼────────────────────────────────────┘
                            │ HTTP REST
                            │
                    ┌──────▼──────┐
                    │  Hermes     │
                    │  Bridge     │
                    │  (Python)   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Hermes     │
                    │  Agents     │
                    │  (Python)   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  PostgreSQL │
                    │  (hermes_   │
                    │   factory)  │
                    └─────────────┘
```

## Componentes

### 1. Hermes Bridge (Python)

**Arquivo:** `hermes_agents/athena_bridge.py`

**Funções principais:**
- `health()` - Health check Athena
- `kpi_summary()` - KPIs consolidados
- `list_orders()`, `get_order()` - Pedidos
- `list_stock_items()`, `update_stock_quantity()` - Estoque
- `list_molds()`, `list_production_runs()` - Produção
- `cashflow()`, `revenue_by_channel()` - Financeiro
- `execute_hermes_agent()` - Executa agente específico
- `sync_hermes_to_athena()` - Sincronização bidirecional
- `generate_hermes_report()` - Relatório completo

**Endpoints suportados:**
- GraphQL queries
- REST API endpoints
- Webhooks para eventos

### 2. Hermes Sync (TypeScript)

**Arquivo:** `athena/src/shared/infrastructure/integrations/hermes-sync.ts`

**Funções principais:**
- `initHermesTables()` - Cria tabelas PostgreSQL
- `registerHermesAgent()` - Registra agente Hermes
- `getHermesAgents()` - Lista agentes
- `executeHermesAgentAction()` - Executa ação de agente
- `syncHermesOpportunities()` - Sincroniza oportunidades
- `getHermesOpportunities()` - Lista oportunidades
- `getHermesAlerts()` - Lista alertas
- `getHermesExecutions()` - Lista execuções
- `resolveHermesAlert()` - Resolve alerta
- `getHermesStats()` - Estatísticas

### 3. Hermes Routes (Express)

**Arquivo:** `athena/src/server/routes/hermesRoutes.ts`

**Rotas:**

```
GET  /api/hermes/agents           - Lista agentes Hermes
GET  /api/hermes/opportunities    - Lista oportunidades
GET  /api/hermes/alerts           - Lista alertas
GET  /api/hermes/executions       - Lista execuções
GET  /api/hermes/stats            - Estatísticas

POST /api/hermes/register         - Registra agente
POST /api/hermes/execute          - Executa agente
POST /api/hermes/sync-all         - Sincroniza tudo
POST /api/hermes/alerts/:id/resolve - Resolve alerta
POST /api/hermes/webhook          - Recebe eventos

GET  /api/hermes/agent/ag_01/cacar       - Executa AG-01
GET  /api/hermes/agent/ag_02/alertas     - Executa AG-02
GET  /api/hermes/agent/ag_03/monitorar   - Executa AG-03
GET  /api/hermes/agent/ag_09/stats       - Executa AG-09
```

### 4. Frontend Hermes Integration

**Arquivo:** `frontend/src/pages/HermesIntegration.tsx`

**Componentes:**
- Cards de KPIs (Agents Ativos, Oportunidades, Alertas, Execuções)
- Lista de agentes Hermes com ações
- Tabs para Oportunidades e Alertas
- Tabela de Execuções Recentes
- Botões para executar agentes
- Links para documentação

## Schema do Banco de Dados

### Tabelas Hermes (PostgreSQL)

```sql
-- Oportunidades
CREATE TABLE "HermesOpportunity" (
  id SERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  marketplace_origem TEXT NOT NULL,
  url TEXT,
  data_descoberta DATE NOT NULL,
  preco_medio DECIMAL(12,2) NOT NULL,
  volume_vendas_estimado INTEGER NOT NULL,
  concorrentes_diretos INTEGER NOT NULL,
  nivel_concorrencia TEXT NOT NULL,
  fabricavel BOOLEAN NOT NULL,
  complexidade_molde INTEGER NOT NULL,
  custo_molde_estimado DECIMAL(12,2),
  custo_producao_unitario DECIMAL(12,4),
  margem_estimada_pct DECIMAL(5,1),
  tempo_lancamento_dias INTEGER,
  tendencia TEXT NOT NULL,
  score_final INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'analisar',
  tags TEXT[],
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

-- Alertas
CREATE TABLE "HermesAlert" (
  id SERIAL PRIMARY KEY,
  agente_origem TEXT NOT NULL,
  tipo TEXT NOT NULL,
  sku TEXT,
  marketplace TEXT,
  mensagem TEXT NOT NULL,
  gravidade TEXT NOT NULL,
  dados_adicionais JSONB,
  resolvido BOOLEAN NOT NULL DEFAULT false,
  data_ocorrencia DATE NOT NULL,
  data_resolucao DATE,
  acao_tomada TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

-- Agentes
CREATE TABLE "HermesAgent" (
  id SERIAL PRIMARY KEY,
  agente_id TEXT UNIQUE NOT NULL,
  nome TEXT NOT NULL,
  descricao TEXT,
  categoria TEXT NOT NULL,
  modelo TEXT,
  provider TEXT,
  status TEXT NOT NULL DEFAULT 'ativo',
  intervalo_minutos INTEGER NOT NULL DEFAULT 60,
  configuracao JSONB,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

-- Execuções
CREATE TABLE "HermesAgentExecution" (
  id SERIAL PRIMARY KEY,
  agente_id TEXT NOT NULL,
  action TEXT NOT NULL,
  params JSONB,
  status TEXT NOT NULL DEFAULT 'em_execucao',
  resultado JSONB,
  erro TEXT,
  inicio_execucao TIMESTAMPTZ NOT NULL,
  fim_execucao TIMESTAMPTZ,
  duracao_segundos INTEGER,
  created_at TIMESTAMPTZ NOT NULL
);

-- Memória Corporativa
CREATE TABLE "HermesCorporateMemory" (
  id SERIAL PRIMARY KEY,
  tipo TEXT NOT NULL,
  dados JSONB NOT NULL,
  tags TEXT[],
  criado_por TEXT DEFAULT 'ag_09_memoria',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
```

## Agentes Hermes

### AG-09: Memória Corporativa

**Ações:**
- `listar_moldes(status)` - Lista moldes
- `buscar_molde(codigo)` - Busca molde específico
- `produtos_do_molde(codigo)` - SKUs de um molde
- `buscar_ficha(sku)` - Ficha técnica
- `listar_fichas(material)` - Lista fichas
- `buscar_fornecedor(categoria)` - Busca fornecedores
- `fornecedor_mais_barato(material)` - Fornecedor mais barato
- `listar_materias_primas()` - Matérias-primas
- `alertas_estoque_baixo()` - Alertas de estoque
- `historico_custo_sku(sku, meses)` - Histórico de custo
- `buscar_solucoes(palavra)` - Soluções de problemas
- `buscar_similar(descricao)` - Produtos similares
- `stats()` - Estatísticas da base

### AG-01: Caçador de Produtos

**Ações:**
- `executar_cacada(categoria)` - Caçada completa
- `top_oportunidades(n)` - Top N oportunidades
- `coletar_tendencias()` - Tendências Google/Pinterest
- `pesquisar_marketplace(mp, cat)` - Pesquisa marketplace
- `analisar_viabilidade(produto)` - Analisa viabilidade

### AG-02: Analista de Lucratividade

**Ações:**
- `calcular_lucro_real(preco, custo, taxa, frete)` - Cálculo isolado
- `analisar_sku(sku, dias)` - Análise completa
- `top_lucrativos(n)` - Top lucrativos
- `bottom_deficitarios(n)` - Deficitários
- `relatorio_diario()` - Relatório do dia
- `verificar_alertas()` - SKUs abaixo margem mínima

### AG-03: Gerente de Marketplaces

**Ações:**
- `verificar_posicoes()` - Posições dos anúncios
- `anuncios_caindo()` - Anúncios fora top 10
- `comparar_precos_concorrentes(sku)` - Comparar preços
- `gerar_sugestao_titulo(sku, kws, mp)` - Sugestão de título
- `gerar_sugestao_preco(sku, mp)` - Sugestão de preço
- `gerar_sugestao_kit(skus)` - Sugestão de kit
- `executar_monitoramento()` - Monitoramento completo

## Fluxo de Sincronização

```
1. Athena Frontend
   ↓
2. REST API (/api/hermes/execute)
   ↓
3. HermesSync (TypeScript)
   ↓
4. HermesBridge (Python)
   ↓
5. Hermes Agent (Python)
   ↓
6. PostgreSQL (hermes_factory)
   ↓
7. HermesBridge retorna dados
   ↓
8. HermesSync salva em Athena DB
   ↓
9. REST API retorna resultado
   ↓
10. Frontend atualiza UI
```

## Webhooks

### Eventos Hermes → Athena

**Endpoint:** `POST /api/hermes/webhook`

**Payload:**
```json
{
  "event_type": "opportunity_discovered|margin_alert|stock_low",
  "data": {
    "sku": "ORG001",
    "mensagem": "Alerta de margem baixa",
    "gravidade": "critico",
    "timestamp": "2026-07-06T20:00:00Z"
  }
}
```

**Eventos suportados:**
- `opportunity_discovered` - Nova oportunidade encontrada
- `margin_alert` - Margem abaixo do mínimo
- `stock_low` - Estoque baixo
- `competitor_price_change` - Concorrente alterou preço
- `production_ready` - Produção concluída
- `quality_issue` - Problema de qualidade detectado

## Monitoramento

### Logs

**Athena:**
```
logs/athena.log
logs/hermes_sync.log
```

**Hermes:**
```
hermes_agents/logs/agents.log
hermes_agents/logs/sync.log
```

### Métricas

Via GraphQL:

```graphql
{
  healthCheck {
    status
    uptime
    infrastructure {
      name
      connected
    }
  }
  kpiSummary {
    totalOrders
    totalRevenue
    activeListings
    lowStockAlerts
  }
}
```

## Segurança

### Autenticação

- Athena usa JWT tokens
- Hermes Bridge usa API Keys (configurável)
- Webhooks devem ser validados

### Rate Limiting

- 100 requisições/por minuto por usuário
- 1000 requisições/por minuto por organização

### CORS

Configurado para aceitar requisições de origens específicas.

## Performance

### Cache

- Oportunidades: cache 30 minutos
- Stats: cache 15 minutos
- Alertas: cache 5 minutos

### Indexes

Índices criados automaticamente:
- `idx_hermes_opportunity_status`
- `idx_hermes_opportunity_score`
- `idx_hermes_alert_resolvido`
- `idx_hermes_agent_status`
- `idx_hermes_execucao_agente`

## Escalabilidade

### Horizontal Scaling

- Athena pode ser rodado em múltiplas instâncias
- Hermes Agents podem ser distribuídos
- PostgreSQL pode usar clustering

### Queue

Requisições podem ser enfileiradas para processamento assíncrono:
```
Request → Queue → Worker → Hermes → Response
```

## Backup

### Dados Hermes

```bash
pg_dump -U postgres hermes_factory > hermes_backup.sql
```

### Configurações

```bash
cp ~/.hermes/factory_config.json ~/.hermes/factory_config.json.backup
```

## Recuperação de Desastres

### Restaurar Dados

```bash
psql -U postgres hermes_factory < hermes_backup.sql
```

### Verificar Integridade

```bash
cd hermes_agents
python athena_bridge.py
```

## Testes

### Unit Tests

```bash
cd athena
npm test -- hermes-sync.test.ts
```

### Integration Tests

```bash
cd hermes_agents
python -m pytest tests/test_athena_bridge.py
```

### Manual Tests

```bash
# Testar saúde
curl http://localhost:4000/api/health

# Testar agentes Hermes
curl http://localhost:4000/api/hermes/agents

# Testar execução
curl -X POST http://localhost:4000/api/hermes/execute \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"ag_09_memoria","action":"stats","params":{}}'
```

## Troubleshooting

### Problema: Erro de conexão

**Solução:**
```bash
# Verificar se Athena está rodando
curl http://localhost:4000/api/health

# Verificar URL Hermes
echo $ATHENA_URL
```

### Problema: Dados não sincronizados

**Solução:**
```bash
# Verificar logs
tail -f logs/hermes_sync.log

# Forçar sincronização
curl -X POST http://localhost:4000/api/hermes/sync-all
```

### Problema: Agente falha

**Solução:**
```bash
# Testar agente isolado
cd hermes_agents
python -c "from ag_09_memoria import stats; print(stats())"

# Verificar logs Hermes
tail -f logs/agents.log
```

## Contribuindo

Para adicionar novos agentes:

1. Criar módulo em `hermes_agents/`
2. Registrar em `hermes_agents/__init__.py`
3. Adicionar ações em `athena_bridge.py`
4. Atualizar `hermesRoutes.ts`
5. Documentar em HermesIntegration.tsx

## Licença

MIT License - Ver arquivo LICENSE para detalhes.