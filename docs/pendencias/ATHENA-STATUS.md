# ATHENA OS — Relatório de Construção

> **Data:** 2026-07-03
> **Status:** typecheck 0 | build OK | testes 19/19
> **Modo:** ponytail full (lazy senior dev)

---

## 1. Visão Geral

**ATHENA** é um sistema operacional de inteligência empresarial multi-agente para a indústria de transformação plástica. 51 agentes especializados em 15 bounded contexts orquestrados via Kafka + DAG workflow engine.

| Métrica | Valor |
|---|---|
| Agentes implementados | 51/52 (AG-001 com imports quebrados do legado) |
| Bounded contexts | 15/15 |
| Domain event handlers | 36 |
| WebSocket clients | ilimitado |
| Endpoints REST | 12 |
| Métricas Prometheus | 10 |
| Testes | 19 (4 suites) |

---

## 2. Estrutura do Projeto

```
athena/
├── src/
│   ├── agents/                    # Agent framework
│   │   ├── core/                  # Runtime, context, protocol, LLM provider, types
│   │   ├── instances/             # 51 concrete agents
│   │   │   ├── observers/         # stock-level-monitor, defect-detector, revision-tracker
│   │   │   ├── decision-makers/   # order-router, fraud-detector, carrier-selector, bom-validator
│   │   │   ├── executors/         # conversational-seller, listing-sync, executive-digest (real)
│   │   │   ├── production-agents.ts      # Mold making + CNC agents
│   │   │   ├── production-agents-2.ts    # Injection + Plastisol agents
│   │   │   ├── commercial-agents.ts      # Catalog + Marketplace + Retail + Telegram
│   │   │   ├── operations-agents.ts      # Inventory + Customer + Shipping
│   │   │   └── intelligence-agents.ts    # Analytics + Coordination
│   │   ├── memory/                # 3-tier: Redis (ST), Qdrant (LT), Postgres (episodic)
│   │   ├── tools/                 # Tool registry, executor, MCP bridge, real integration tools
│   │   ├── registry/              # Agent registry + health check
│   │   └── orchestration/         # DAG engine + event-to-task bridge + workflow definitions
│   ├── api/
│   │   └── rest/                  # Fastify server + business routes + dashboard HTML
│   ├── bootstrap/                 # Startup: infra init + agents + workflows + Kafka + dashboard
│   ├── contexts/                  # 15 bounded contexts
│   │   ├── inventory/             # StockItem entity + repo + 4 event handlers
│   │   ├── order-management/      # Order entity + repo + 7 event handlers
│   │   ├── product-engineering/   # Product entity + BOM + Revision + 4 event handlers
│   │   ├── mold-making/           # Mold entity + repo
│   │   ├── manufacturing/         # CNCJob + ProductionRun + QualityCheck + Plastisol repos + 13 handlers
│   │   ├── shared/                # Catalog + Customer + Shipping + Pricing handlers
│   │   └── catalog/               # ProductCard (domain entity only)
│   └── shared/
│       ├── domain/                # BaseEntity, AggregateRoot, ValueObjects, DomainEvents
│       └── infrastructure/
│           ├── config/            # AppConfig (Zod + dotenv)
│           ├── persistence/       # Prisma client, Redis client, Qdrant client, repositories (raw SQL)
│           ├── messaging/         # Kafka connection manager, publisher, consumer, event publisher
│           ├── http/              # HTTP client with retry + circuit breaker
│           ├── integrations/      # Telegram Bot, Mercado Livre, Shopee, Email (real API)
│           ├── auth/              # JWT (crypto nativo), password (scrypt), RBAC, rate limiter, API key
│           ├── observability/     # Pino logger, Prometheus metrics, OpenTelemetry tracing
│           └── websocket/         # WebSocket event bus + broadcast
├── prisma/
│   ├── schema.prisma              # 36 modelos completos
│   └── seed.ts                    # Seed: warehouses, stock, products, cards, customers, prices
├── docker/
│   ├── development/               # docker-compose.yml (Kafka, Postgres, Redis, Qdrant, Athena)
│   └── production/                # Multi-stage Dockerfile
├── .github/workflows/
│   ├── ci.yml                     # Test + build + lint on push/PR
│   └── cd.yml                     # Docker build + push GHCR + deploy SSH
├── .env                           # Variáveis de ambiente
└── package.json                   # Scripts: build, test, typecheck, seed, migrate, docker:up
```

---

## 3. Checklist — O que foi feito

### Fase 1: Fundação
- [x] PRD + Arquitetura (`ARCHITECTURE.md`, 736 linhas)
- [x] Estrutura do monorepo (`package.json` com workspaces)
- [x] Shared kernel: `BaseEntity`, `AggregateRoot`, `ValueObject`, `Money`, `Quantity`
- [x] Config loader (`AppConfig` com Zod validation + `.env`)
- [x] Prisma schema (36 modelos) + client singleton
- [x] Redis client (ioredis)
- [x] Qdrant client + collection auto-create

### Fase 2: Agent Framework
- [x] Core types: `AgentId`, `AgentRole`, `AgentStatus`, `AgentDefinition`, `AgentConfig`
- [x] `AgentRuntime`: lifecycle (start/pause/resume/stop), LLM provider, task handling with graceful degradation
- [x] `AgentContext`: sandbox isolado (memory + tools + state + conversation history)
- [x] `AgentProtocol`: mensageria entre agentes (InMemory)
- [x] LLM Provider: OpenAI, Anthropic, Groq — fallback graceful quando offline

### Fase 3: 51 Agentes Concretos
| Contexto | IDs | Qtd |
|---|---|---|
| Product Engineering | AG-002, AG-003 | 2 |
| Mold Making | AG-004, AG-005, AG-006, AG-017 | 4 |
| CNC Machining | AG-007, AG-008, AG-009, AG-018 | 4 |
| Injection Molding | AG-010, AG-011, AG-012, AG-013 | 4 |
| Plastisol Processing | AG-014, AG-015, AG-016 | 3 |
| Catalog | AG-019, AG-020, AG-021 | 3 |
| Marketplace | AG-022, AG-023, AG-024, AG-025 | 4 |
| Retail | AG-026, AG-027 | 2 |
| Telegram | AG-028, AG-029, AG-030 | 3 |
| Inventory | AG-031, AG-032, AG-033, AG-034 | 4 |
| Order Management | AG-035, AG-036, AG-037, AG-038 | 4 |
| Customer | AG-039, AG-040, AG-041 | 3 |
| Shipping | AG-042, AG-043, AG-044 | 3 |
| Analytics | AG-045, AG-046, AG-047, AG-048, AG-049, AG-050 | 6 |
| Coordination | AG-051, AG-052 | 2 |
| **TOTAL** | | **51** |

### Fase 4: Memória (3 camadas)
- [x] **Short-term**: Redis (`RedisShortTerm`) com fallback `InMemoryShortTerm`
- [x] **Long-term**: Qdrant (`QdrantLongTerm`) com busca vetorial + fallback `InMemoryLongTerm`
- [x] **Episodic**: Postgres (`PostgresEpisodic`) com replay por agente + fallback `InMemoryEpisodic`
- [x] `MemoryManager` unificado com hybrid search

### Fase 5: Ferramentas + MCP
- [x] `ToolRegistry` + `ToolExecutor` (retry, timeout, Zod validation)
- [x] `MCPBridge`: spawn de processos + JSON-RPC 2.0 + descoberta de tools
- [x] `RealMCPBridge`: stdin/stdout communication com servidores MCP
- [x] Ferramentas reais: Telegram Bot API, Mercado Livre API, Shopee API, Email SMTP, Database queries

### Fase 6: Orquestrador
- [x] `DAGOrchestrationEngine`: execução paralela com dependências
- [x] `WorkflowDefinition` com trigger por evento Kafka
- [x] `EventTaskBridge`: eventos Kafka → tarefas para agentes (5 mapeamentos padrão)
- [x] Persistência de workflow/execução no Postgres

### Fase 7: Dashboard + API
- [x] Fastify server com 12 endpoints REST
- [x] Dashboard HTML real-time com WebSocket (`/`)
- [x] Login endpoint (`POST /api/auth/login`)
- [x] Health check (`GET /api/health`)
- [x] Agent CRUD (`GET /api/agents`, `/api/agents/:id`)
- [x] Agent memory (`GET /api/agents/:id/memory`)
- [x] Workflow status (`GET /api/workflows/:id`, `POST /api/workflows/trigger`)
- [x] Business routes (`/api/business/orders`, `/inventory`, `/quality`)
- [x] Prometheus metrics (`GET /metrics`)

### Fase 8: Auth + Segurança
- [x] JWT: sign/verify com `crypto.createHmac('sha256')` (zero dependências)
- [x] Password: `crypto.scryptSync` com salt de 16 bytes
- [x] RBAC: 3 roles (admin > operator > viewer) via `preHandler` por rota
- [x] Rate limiting: sliding window 200 req/min por IP+rota
- [x] API key auth (`X-API-Key` header)

### Fase 9: Observabilidade
- [x] **Logging**: Pino estruturado com child loggers por contexto
- [x] **Metrics**: Prometheus — 10 métricas (counters, histograms, gauges)
- [x] **Tracing**: OpenTelemetry spans em agent tasks + HTTP + Kafka
- [x] `GET /metrics` endpoint formato Prometheus text

### Fase 10: Integrações Reais
- [x] **HTTP Client**: retry exponencial + circuit breaker (5 falhas → abre 30s)
- [x] **Kafka Publisher**: `publishEvent()` com envelope padrão
- [x] **Telegram Bot**: `sendProductCard`, `sendOrderStatus`, `sendAlert`, webhook setup
- [x] **Mercado Livre**: OAuth + publish/update product + getOrders + getReputation
- [x] **Shopee**: publish product + update stock/price + getOrders + getOrderDetail
- [x] **Email**: SMTP com `sendAlert` (HTML), `sendDailyDigest` (tabela), `sendReport` (anexo)

### Fase 11: Contextos de Domínio
- [x] **Inventory**: StockItem + stockMovement + warehouse — 4 event handlers
- [x] **Order Management**: Order + OrderLine + Fulfillment + Return — 7 event handlers
- [x] **Product Engineering**: Product + BOM + Component + Revision — 4 event handlers
- [x] **Mold Making**: Mold + MaintenanceRecord — 4 event handlers
- [x] **CNC Machining**: CNCJob — 3 event handlers
- [x] **Injection Molding**: ProductionRun + QualityCheck — 3 event handlers
- [x] **Plastisol Processing**: Formulation + CuringCycle — 3 event handlers
- [x] **Catalog**: ProductCard + Variant — 3 event handlers
- [x] **Customer**: 2 event handlers
- [x] **Shipping**: Shipment — 2 event handlers
- [x] **Pricing**: PriceListItem — 1 event handler
- [x] **Marketplace**: ChannelListing (schema only)
- [x] **Retail Operations**: Store + SaleTransaction (schema only)
- [x] **Telegram Commerce**: ChatOrder + ChatSession (schema only)
- [x] **Analytics**: Report + Metric + Insight (schema only)

### Fase 12: CI/CD
- [x] `.github/workflows/ci.yml`: test + build + coverage (Postgres + Redis services)
- [x] `.github/workflows/cd.yml`: docker build multi-stage → push GHCR → deploy SSH → migrate
- [x] `docker/production/Dockerfile`: multi-stage (builder/runner Alpine), HEALTHCHECK
- [x] `prisma/seed.ts`: 3 warehouses, 5 stock items, 4 products, 3 cards, 3 customers, 3 prices

### Fase 13: WebSocket + Dashboard
- [x] `@fastify/websocket`: `/ws` endpoint com auto-reconnect
- [x] `WebSocketEventBus`: broadcast + histórico 200 eventos + replay on connect
- [x] `broadcastAgentTask()` no agent-runtime
- [x] Dashboard HTML em tempo real (4 painéis: agentes, tarefas, eventos, métricas)

---

## 4. PENDÊNCIAS

### Prioridade Alta
| # | Item | Descrição |
|---|---|---|
| 1 | **AG-001 (product-design-assistant)** | Arquivo com imports quebrados (`@agents/core`), precisa ser reescrito |
| 2 | **Prisma migrate** | `npx prisma migrate dev` — tabelas NUNCA foram criadas no banco. Schema está definido mas sem migrate |
| 3 | **Docker compose up + validação** | Subir todos os serviços (Kafka, Postgres, Redis, Qdrant, Athena) e validar fluxo ponta a ponta com infra real |
| 4 | **Testes de integração** | Testes com Docker — agent spawn + workflow run + Kafka pub/sub reais |
| 5 | **WebSocket real-time validation** | Testar dashboard HTML com WebSocket ao vivo — confirmar eventos em tempo real |

### Prioridade Média
| # | Item | Descrição |
|---|---|---|
| 6 | **Contextos de manufatura no Prisma** | Mold, CNCJob, ProductionRun, QualityCheck, Plastisol — schema existe, mas seed + repos não foram testados com DB real |
| 7 | **GraphQL** | `src/graphql/` foi renomeado para `.bak` porque não compilava. Se quiser GraphQL, precisa reescrever os resolvers |
| 8 | **Task Scheduler** | `src/agents/tasks/task-scheduler.ts` foi removido (quebrado). Cron jobs dos agentes (stock check, health check, digest) não estão ativos |
| 9 | **Rate limit stats endpoint** | `GET /api/admin/rate-limits` — expor estatísticas do rate limiter |
| 10 | **Health check detalhado** | `/api/health` atual não reporta status do Kafka, Redis, Qdrant — a informação existe no bootstrap mas não na API |

### Prioridade Baixa
| # | Item | Descrição |
|---|---|---|
| 11 | **OpenTelemetry export** | Tracing está instrumentado mas sem exporter configurado. Adicionar `OTEL_EXPORTER_OTLP_ENDPOINT` no helm/docker |
| 12 | **Grafana dashboard** | JSON de dashboard pré-configurado com as 10 métricas Prometheus |
| 13 | **Alertmanager rules** | Regras de alerta: agentes parados, taxa de erro alta, workflow falhando |
| 14 | **Documentação de API** | OpenAPI/Swagger spec gerada automaticamente |
| 15 | **Load tests** | k6 ou Artillery scripts para testar 51 agentes sob carga |
| 16 | **Purgar `.bak` files** | Vários arquivos `.bak` em `src/contexts/` e `src/graphql/` que podem ser deletados |

---

## 5. Comandos Rápidos

```bash
# Desenvolvimento
cd athena
npm run typecheck          # Verificar tipos
npm test                   # Rodar testes (19/19)
npm run build              # Compilar TypeScript
npm start                  # Iniciar servidor (dist/bootstrap/startup.js)
npm run dev                # Iniciar com ts-node

# Docker
npm run docker:up          # Subir Kafka + Postgres + Redis + Qdrant
npm run docker:down        # Parar tudo

# Database
npm run migrate            # Aplicar migrations Prisma
npm run seed               # Popular banco com dados de exemplo

# Deploy
docker build -f docker/production/Dockerfile -t athena .
docker compose -f docker/development/docker-compose.yml up -d
```

---

## 6. Credenciais Padrão

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `athena-admin-2026` |
| Operator | `operator` | `athena-op-2026` |
| Viewer | `viewer` | `athena-view-2026` |

---

## 7. Variáveis de Ambiente (.env)

```env
NODE_ENV=development
PORT=3000
HOST=0.0.0.0

DATABASE_URL=postgresql://athena:athena@localhost:5432/athena
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
KAFKA_BROKERS=localhost:9092

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk-...

JWT_SECRET=change-me-in-production
TELEGRAM_BOT_TOKEN=...
ML_ACCESS_TOKEN=...
SMTP_HOST=...
```
