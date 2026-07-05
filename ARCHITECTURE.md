# ATHENA — Arquitetura do Sistema Operacional de Inteligência Empresarial

## 1. Visão Geral

ATHENA é um sistema operacional de inteligência empresarial para a indústria de transformação plástica. Opera sobre 4 pilares:

| Pilar | Descrição |
|---|---|
| **Domain-Driven Design** | 15 Bounded Contexts isolados com linguagem ubíqua própria |
| **Clean Architecture** | Camadas domain/application/infrastructure com dependência unidirecional para dentro |
| **Event-Driven** | Comunicação assíncrona entre contextos via fila de eventos (Kafka/RabbitMQ) |
| **Agent-Based Intelligence** | 42+ agentes especializados independentes com prompt, memória, ferramentas, tarefas, logs e configurações próprias |

---

## 2. Estrutura Completa de Diretórios

```
athena/
│
├── docker/                                    # Infraestrutura containerizada
│   ├── development/
│   │   └── docker-compose.yml                 # Ambiente dev: hot-reload, volumes locais
│   ├── production/
│   │   └── docker-compose.yml                 # Ambiente prod: replicas, healthchecks, secrets
│   ├── api/
│   │   └── Dockerfile                         # API Gateway + GraphQL + WebSocket
│   ├── agent-runtime/
│   │   └── Dockerfile                         # Runtime isolado para execução de agentes
│   ├── eventbus/
│   │   └── Dockerfile                         # Broker de eventos (Kafka)
│   ├── database/
│   │   └── Dockerfile                         # Bancos (Postgres + Mongo + Redis + Vector Store)
│   └── observability/
│       └── Dockerfile                         # Grafana + Prometheus + ELK
│
├── src/
│   │
│   ├── shared/                                # KERNEL COMPARTILHADO (Shared Kernel DDD)
│   │   ├── domain/
│   │   │   ├── value-objects/                 # Money, Dimensions, Weight, MaterialType, Email, Phone, SKU, Address
│   │   │   ├── entities/                      # BaseEntity, AggregateRoot (classes base abstratas)
│   │   │   ├── events/                        # DomainEvent, IntegrationEvent (classes base)
│   │   │   ├── enums/                         # UnitOfMeasure, MaterialCategory, OrderStatus, ChannelType
│   │   │   ├── specifications/                # Specification<T> pattern (AND, OR, NOT combinators)
│   │   │   └── exceptions/                    # DomainException, ValidationException, NotFoundException
│   │   ├── application/
│   │   │   ├── ports/                         # CONTRATOS (interfaces/abstract classes)
│   │   │   │   ├── repositories/              # IRepository<T>, IUnitOfWork
│   │   │   │   ├── messaging/                 # IEventBus, IEventPublisher, IEventHandler<T>
│   │   │   │   ├── cache/                     # ICacheService, IDistributedLock
│   │   │   │   ├── storage/                   # IFileStorage (S3/local abstração)
│   │   │   │   └── external-apis/             # Interfaces para APIs externas
│   │   │   ├── use-cases/                     # BaseUseCase<TInput, TOutput> abstrato
│   │   │   ├── commands/                      # ICommand, ICommandHandler<T> — CQRS Command base
│   │   │   └── queries/                       # IQuery, IQueryHandler<T> — CQRS Query base
│   │   └── infrastructure/
│   │       ├── persistence/
│   │       │   ├── postgres/                  # TypeORM/Prisma — dados transacionais, relacionais
│   │       │   ├── mongodb/                   # Mongoose — documentos, catálogo, dados semi-estruturados
│   │       │   ├── redis/                     # Cache, filas leves, pub/sub, rate limiting
│   │       │   └── vector-store/              # Pinecone/Qdrant/Weaviate — memória de longo prazo dos agentes
│   │       ├── messaging/
│   │       │   ├── rabbitmq/                  # Filas para comandos assíncronos entre contextos
│   │       │   └── kafka/                     # Event streaming para analytics e event sourcing
│   │       ├── http/                          # Axios/fetch wrapper, retry, circuit breaker
│   │       ├── logging/                       # Winston/Pino — structured JSON logging
│   │       ├── telemetry/                     # OpenTelemetry — traces, metrics, spans
│   │       └── auth/                          # JWT, RBAC, OAuth2 providers
│   │
│   ├── api/                                   # API GATEWAY (entrada externa única)
│   │   ├── rest/
│   │   │   ├── routes/                        # Definições de rotas por contexto
│   │   │   ├── controllers/                   # Thin controllers — delegam para Application Layer
│   │   │   ├── middleware/                    # Auth, rate-limit, request-validation, correlation-id
│   │   │   ├── dtos/                          # Data Transfer Objects (entrada/saída)
│   │   │   └── validators/                    # class-validator / zod schemas
│   │   ├── graphql/
│   │   │   ├── schema/                        # Type definitions, queries, mutations, subscriptions
│   │   │   ├── resolvers/                     # Resolvers delegando para Application Layer
│   │   │   └── directives/                    # @auth, @deprecated, @rateLimit
│   │   └── websocket/
│   │       ├── handlers/                      # Eventos real-time: pedidos, produção, alertas
│   │       └── rooms/                         # Agrupamento por tenant, contexto, loja
│   │
│   ├── contexts/                              # BOUNDED CONTEXTS (15 contextos)
│   │   │
│   │   ├── product-engineering/               # ENGENHARIA DE PRODUTO
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # Product, Component, BOM, CADFile, Specification, Revision
│   │   │   │   ├── value-objects/             # MaterialSpec, Tolerance, RevisionNumber, DrawingNumber
│   │   │   │   ├── events/                    # ProductDesigned, BOMUpdated, SpecificationApproved, RevisionCreated
│   │   │   │   ├── services/                  # BOMValidator, SpecificationChecker, RevisionComparer
│   │   │   │   └── repositories/              # IProductRepository, IBOMRepository (interfaces)
│   │   │   ├── application/
│   │   │   │   ├── use-cases/                 # CreateProduct, UpdateBOM, ApproveSpecification, ArchiveRevision
│   │   │   │   ├── commands/                  # CreateProductCommand, UpdateBOMCommand
│   │   │   │   ├── queries/                   # GetProductQuery, ListRevisionsQuery
│   │   │   │   └── event-handlers/            # Reage a eventos de outros contextos
│   │   │   ├── infrastructure/
│   │   │   │   ├── persistence/               # Implementação concreta dos repositórios
│   │   │   │   ├── cad-integration/           # Integração com software CAD (SolidWorks, Fusion 360)
│   │   │   │   ├── file-storage/              # Armazenamento de arquivos CAD, PDF, STEP
│   │   │   │   └── messaging/                 # Publicadores/consumidores de eventos
│   │   │   └── agents/                        # Agentes deste contexto
│   │   │       ├── definitions/               # YAML/JSON com prompt, toolset, schedule de cada agente
│   │   │       └── tools/                     # Ferramentas específicas (ex: CAD file parser tool)
│   │   │
│   │   ├── mold-making/                       # FABRICAÇÃO DE MOLDES
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # Mold, MoldComponent, MoldAssembly, MaintenanceRecord
│   │   │   │   ├── value-objects/             # CavityCount, SteelType, CycleLife, CoolingConfig, EjectorType
│   │   │   │   ├── events/                    # MoldDesigned, MoldFabricated, MoldDelivered, MaintenancePerformed
│   │   │   │   ├── services/                  # MoldLifeCalculator, CoolingSimulator, MaintenanceScheduler
│   │   │   │   └── repositories/              # IMoldRepository, IMoldComponentRepository
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── cnc-machining/                     # USINAGEM CNC 3 EIXOS
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # CNCMachine, Tool, NCProgram, MachiningJob, SetupSheet
│   │   │   │   ├── value-objects/             # FeedRate, SpindleSpeed, ToolPath, Coordinates3D, WorkOffset
│   │   │   │   ├── events/                    # JobScheduled, ProgramUploaded, MachiningStarted, MachiningCompleted
│   │   │   │   ├── services/                  # ToolPathOptimizer, ToolWearCalculator, FeedRateOptimizer
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── injection-molding/                 # INJEÇÃO PLÁSTICA
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # InjectionMachine, ProductionRun, CycleRecord, QualityCheck, Batch
│   │   │   │   ├── value-objects/             # MeltTemperature, InjectionPressure, ShotWeight, CycleTime, ScrapRate
│   │   │   │   ├── events/                    # RunStarted, CycleCompleted, DefectDetected, BatchCompleted, MachineStopped
│   │   │   │   ├── services/                  # CycleOptimizer, DefectClassifier, OEE_Calculator
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── plastisol-processing/              # PROCESSAMENTO DE PLASTISOL
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # PlastisolFormulation, DippingLine, CuringCycle, CoatingBatch
│   │   │   │   ├── value-objects/             # Viscosity, GelTemperature, CuringProfile, CoatingThickness, Hardness
│   │   │   │   ├── events/                    # FormulationMixed, DippingStarted, CuringCompleted, BatchQC_Result
│   │   │   │   ├── services/                  # FormulationOptimizer, CuringProfileCalculator, AdhesionTester
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── catalog/                           # CATÁLOGO DE PRODUTOS
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # ProductCard, Category, Media, Attribute, Variant, SEOMetadata
│   │   │   │   ├── value-objects/             # GTIN, NCM, Weight, Dimensions, PriceRange
│   │   │   │   ├── events/                    # ProductPublished, MediaAdded, VariantCreated, CategoryReorganized
│   │   │   │   ├── services/                  # SEOMetadataGenerator, VariantMatrixBuilder, MediaOrganizer
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── marketplace-integration/           # INTEGRAÇÃO COM MARKETPLACES
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # Channel, Listing, SyncJob, ChannelOrder, ChannelAccount
│   │   │   │   ├── value-objects/             # ChannelSKU, ListingStatus, SyncStatus, MarketplaceFee
│   │   │   │   ├── events/                    # ListingPublished, ListingUpdated, ChannelOrderReceived, SyncCompleted
│   │   │   │   ├── services/                  # ListingMapper, FeeCalculator, ChannelHealthChecker
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   ├── adapters/
│   │   │   │   │   ├── mercadolivre/          # Adapter Mercado Livre API
│   │   │   │   │   ├── shopee/                # Adapter Shopee API
│   │   │   │   │   ├── amazon/                # Adapter Amazon SP-API
│   │   │   │   │   └── magalu/                # Adapter Magazine Luiza API
│   │   │   │   └── sync-engines/              # Estratégias de sincronização (full, incremental, event-driven)
│   │   │   └── agents/
│   │   │
│   │   ├── retail-operations/                 # LOJAS FÍSICAS
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # Store, POSSession, SaleTransaction, InStoreInventory, CashRegister
│   │   │   │   ├── value-objects/             # StoreLocation, OperatingHours, RegisterBalance
│   │   │   │   ├── events/                    # SaleCompleted, RegisterOpened, RegisterClosed, InventoryCounted
│   │   │   │   ├── services/                  # SalesAggregator, ShiftReconciler, FootTrafficAnalyzer
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── telegram-commerce/                 # VENDAS VIA TELEGRAM
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # BotSession, ChatUser, ChatOrder, ProductCard, PaymentIntent
│   │   │   │   ├── value-objects/             # TelegramID, ChatState, ConversationStep
│   │   │   │   ├── events/                    # ConversationStarted, ProductShown, OrderConfirmedViaChat, PaymentCompleted
│   │   │   │   ├── services/                  # ConversationFlow, ProductRecommender, CartBuilder
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   └── bot/                       # Telegram Bot API integration, webhook handler
│   │   │   └── agents/
│   │   │
│   │   ├── inventory/                         # ESTOQUE UNIFICADO
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # StockItem, Warehouse, StockMovement, Reservation, ReorderPoint
│   │   │   │   ├── value-objects/             # Quantity, Location, BinCode, BatchLot
│   │   │   │   ├── events/                    # StockReceived, StockReserved, StockShipped, LowStockAlert, StockAdjusted
│   │   │   │   ├── services/                  # StockAggregator, ReservationManager, ReorderCalculator, FIFO_LIFO_Engine
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── order-management/                  # GESTÃO DE PEDIDOS
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # Order, OrderLine, Fulfillment, Invoice, Return, Refund
│   │   │   │   ├── value-objects/             # OrderStatus, PaymentStatus, FulfillmentType, ChannelOrigin
│   │   │   │   ├── events/                    # OrderPlaced, OrderConfirmed, OrderShipped, OrderDelivered, ReturnRequested
│   │   │   │   ├── services/                  # OrderAggregator, FulfillmentRouter, InvoiceGenerator
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── customer/                          # CLIENTES & CRM
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # Customer, CustomerSegment, Interaction, LoyaltyAccount
│   │   │   │   ├── value-objects/             # CustomerTier, LoyaltyPoints, RFM_Score
│   │   │   │   ├── events/                    # CustomerRegistered, ProfileUpdated, TierChanged, PointsEarned
│   │   │   │   ├── services/                  # Segmenter, RFM_Analyzer, LifetimeValueEstimator, ChurnPredictor
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── pricing/                           # PRECIFICAÇÃO
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # PriceList, PriceRule, Discount, Promotion, TaxRule, MarginPolicy
│   │   │   │   ├── value-objects/             # Money, Percentage, PriceTier, ChannelPrice
│   │   │   │   ├── events/                    # PriceUpdated, PromotionCreated, PromotionExpired, DiscountApplied
│   │   │   │   ├── services/                  # PriceCalculator, MarginAnalyzer, PromotionEvaluator, ElasticityModel
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   ├── shipping/                          # LOGÍSTICA & ENVIO
│   │   │   ├── domain/
│   │   │   │   ├── entities/                  # Shipment, Carrier, TrackingEvent, ShippingRate, PackagingRule
│   │   │   │   ├── value-objects/             # Dimensions, Weight, TrackingCode, DeliveryEstimate, FreightCost
│   │   │   │   ├── events/                    # ShipmentCreated, LabelGenerated, CarrierPickedUp, Delivered, DeliveryFailed
│   │   │   │   ├── services/                  # CarrierSelector, RateCalculator, PackagingOptimizer, DeliveryTracker
│   │   │   │   └── repositories/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── agents/
│   │   │
│   │   └── analytics/                         # ANALYTICS & BUSINESS INTELLIGENCE
│   │       ├── domain/
│   │       │   ├── entities/                  # Report, Dashboard, Metric, Insight, Prediction, Alert
│   │       │   ├── value-objects/             # TimeRange, AggregationType, MetricValue, ConfidenceInterval
│   │       │   ├── events/                    # ReportGenerated, InsightDetected, AlertTriggered, ForecastUpdated
│   │       │   ├── services/                  # AnomalyDetector, ForecastEngine, TrendAnalyzer, Correlator
│   │       │   └── repositories/
│   │       ├── application/
│   │       ├── infrastructure/
│   │       └── agents/
│   │
│   ├── agents/                                # AGENT FRAMEWORK (cross-cutting)
│   │   ├── core/
│   │   │   ├── agent-runtime.ts               # Lifecycle: spawn, start, pause, resume, stop, destroy
│   │   │   ├── agent-context.ts               # Sandbox isolado por instância: memória, tools, state
│   │   │   ├── agent-protocol.ts              # Protocolo de comunicação inter-agente (ACL)
│   │   │   └── agent-types.ts                 # AgentId, AgentRole, AgentStatus, AgentCapability
│   │   ├── prompt/
│   │   │   ├── prompt-manager.ts              # Engine de templates com variáveis dinâmicas
│   │   │   ├── prompt-builder.ts              # Montagem dinâmica: system + context + tools + examples
│   │   │   └── prompt-store.ts                # Versionamento de prompts (Git-based)
│   │   ├── memory/
│   │   │   ├── short-term/                    # Memória de curto prazo: contexto da conversa/tarefa atual
│   │   │   ├── long-term/                     # Memória de longo prazo: vector store (embeddings)
│   │   │   ├── episodic/                      # Memória episódica: histórico de tarefas e decisões
│   │   │   └── memory-manager.ts              # Interface unificada de memória (CRUD + search)
│   │   ├── tools/
│   │   │   ├── tool-registry.ts               # Registro e descoberta de ferramentas (schema + handler)
│   │   │   ├── tool-executor.ts               # Sandbox de execução segura de ferramentas
│   │   │   ├── context-tools/                 # Ferramentas de acesso a contextos de domínio
│   │   │   └── external-tools/                # Ferramentas de integração externa (email, API, webhook)
│   │   ├── tasks/
│   │   │   ├── task-definition.ts             # Schema: id, type, priority, input, deadline, retry policy
│   │   │   ├── task-scheduler.ts              # Cron + event-driven scheduling (BullMQ)
│   │   │   ├── task-queue.ts                  # Fila de prioridade com dead letter queue
│   │   │   └── task-dispatcher.ts             # Roteamento de tarefas para agentes por capability match
│   │   ├── logging/
│   │   │   ├── agent-logger.ts                # Structured logging por agente (Winston child loggers)
│   │   │   ├── audit-trail.ts                 # Trilha de auditoria imutável (todas as decisões do agente)
│   │   │   └── log-aggregator.ts              # Agregação centralizada (ElasticSearch)
│   │   ├── config/
│   │   │   ├── agent-config.ts                # Schema: model, temperature, maxTokens, tools, schedule
│   │   │   ├── config-loader.ts               # Carrega de YAML/JSON/env vars por ambiente
│   │   │   └── config-validator.ts            # Validação de configuração (Zod schema)
│   │   ├── registry/
│   │   │   ├── agent-registry.ts              # Descoberta central: quais agentes estão ativos?
│   │   │   ├── capability-registry.ts         # Catálogo de capabilities: "pode_analisar_preco", etc.
│   │   │   └── health-check.ts                # Heartbeat, watchdog, auto-restart de agentes mortos
│   │   ├── orchestration/
│   │   │   ├── orchestration-engine.ts        # Workflows multi-agente (DAG-based)
│   │   │   ├── workflow-definitions.ts        # DSL para definição de workflows
│   │   │   ├── saga-coordinator.ts            # Saga pattern para transações distribuídas entre agentes
│   │   │   └── conflict-resolver.ts           # Resolução de conflitos quando agentes divergem
│   │   └── instances/                         # INSTÂNCIAS CONCRETAS DE AGENTES
│   │       ├── observers/                     # Monitoram eventos, detectam padrões (read-only)
│   │       ├── analysts/                      # Analisam dados, geram insights (read + compute)
│   │       ├── decision-makers/               # Recomendam ações, acionam alertas (decide)
│   │       ├── executors/                     # Executam ações, chamam APIs (write)
│   │       └── coordinators/                  # Orquestram múltiplos agentes em workflows complexos
│   │
│   └── bootstrap/                             # INICIALIZAÇÃO DA APLICAÇÃO
│       ├── module-loader.ts                   # Carrega módulos por contexto, ordem de dependência
│       ├── dependency-injection.ts            # Container DI (tsyringe/Inversify)
│       └── startup.ts                         # Orquestra startup: DB connect → event bus → agents → API
│
├── config/                                    # CONFIGURAÇÕES EXTERNAS
│   ├── agents/
│   │   ├── production/                        # Configs de agentes para produção
│   │   ├── staging/                           # Configs de agentes para staging
│   │   └── development/                       # Configs de agentes para desenvolvimento
│   ├── shared/
│   │   ├── app.config.yaml                    # Portas, hosts, timeouts globais
│   │   ├── database.config.yaml               # Connection strings por ambiente
│   │   ├── messaging.config.yaml              # Tópicos, filas, consumer groups
│   │   └── logging.config.yaml                # Níveis de log, formato, destinos
│   └── docker/
│       ├── .env.example                       # Template de variáveis de ambiente
│       └── .env.production                    # Variáveis de produção (não commitado)
│
├── tests/                                     # TESTES
│   ├── unit/                                  # Testes unitários (Jest)
│   │   ├── shared/                            # Testes do kernel compartilhado
│   │   ├── contexts/                          # Testes por contexto
│   │   └── agents/                            # Testes do agent framework
│   ├── integration/                           # Testes de integração
│   │   ├── api/                               # Testes de API (supertest)
│   │   ├── contexts/                          # Testes de integração entre camadas
│   │   └── messaging/                         # Testes de filas e eventos
│   ├── e2e/                                   # Testes end-to-end
│   │   ├── scenarios/                         # Cenários de negócio completos
│   │   └── fixtures/                          # Dados de teste reutilizáveis
│   └── performance/                           # Testes de carga (k6/Artillery)
│
├── scripts/                                   # SCRIPTS OPERACIONAIS
│   ├── dev/                                   # Scripts de desenvolvimento (seed, reset, mock)
│   ├── deploy/                                # Scripts de deploy (CI/CD hooks)
│   ├── seed/                                  # Scripts de seed de dados
│   └── migrate/                               # Scripts de migração de banco
│
├── docs/                                      # DOCUMENTAÇÃO
│   ├── architecture/
│   │   ├── ADR/                               # Architecture Decision Records
│   │   ├── C4/                                # Diagramas C4 (Context, Container, Component, Code)
│   │   └── diagrams/                          # Diagramas diversos (sequência, estado, fluxo)
│   ├── domains/
│   │   └── event-storming/                    # Saídas de event storming por contexto
│   ├── api/
│   │   └── openapi/                           # Especificações OpenAPI 3.1
│   └── agents/
│       ├── agent-catalog.md                   # Catálogo completo de agentes
│       └── agent-interactions.md              # Diagramas de interação entre agentes
│
├── .gitignore
├── package.json
├── tsconfig.json
├── jest.config.ts
├── .eslintrc.js
└── README.md
```

---

## 3. Organização dos Módulos

### 3.1 Camadas por Módulo (Clean Architecture)

Cada contexto e o shared kernel seguem a mesma estrutura de 3 camadas:

```
┌──────────────────────────────────────────────┐
│                  API LAYER                    │  ← REST, GraphQL, WebSocket
│        (src/api/)                             │
├──────────────────────────────────────────────┤
│              APPLICATION LAYER                │  ← Use Cases, Commands, Queries
│   (src/shared/application + context/application)│    Event Handlers, DTOs, Ports
├──────────────────────────────────────────────┤
│                DOMAIN LAYER                   │  ← Entities, Value Objects, Aggregates
│     (src/shared/domain + context/domain)       │    Domain Events, Domain Services, Repositories (interfaces)
├──────────────────────────────────────────────┤
│           INFRASTRUCTURE LAYER                │  ← Persistence, Messaging, HTTP, Cache
│  (src/shared/infrastructure + context/infrastructure)│  External APIs, File Storage
└──────────────────────────────────────────────┘
```

**Regra de dependência**: Application → Domain. Infrastructure → Application & Domain. API → Application. Nenhuma dependência reversa.

### 3.2 Fluxo de uma Requisição Típica

```
Client → API Gateway → Controller → Command/Query → Use Case → Domain Service → Repository Interface
                                                                                      ↓
                                                                          Infrastructure (Postgres, etc.)
```

### 3.3 Comunicação Entre Contextos

Contextos NUNCA se comunicam diretamente. Toda comunicação é via **eventos**:

```
[Contexto A] ──publica──→ [Kafka Topic] ──consome──→ [Contexto B]
                                                          ↓
                                                    Event Handler
                                                          ↓
                                                    Atualiza Read Model
                                                          ↓
                                                (opcional) Publica evento de resposta
```

**Padrão**: Cada contexto mantém seu próprio **read model** (projeção) dos dados de outros contextos que precisa consumir, atualizado assincronamente via eventos.

### 3.4 Context Map (Relações entre Bounded Contexts)

```
                    ┌──────────────────┐
                    │ Product          │
                    │ Engineering      │─── Publica ProductDesigned ─────────────────────┐
                    └────────┬─────────┘                                                │
                             │                                                          │
              ┌──────────────┼──────────────┐                                           │
              ▼              ▼              ▼                                           │
    ┌──────────┐    ┌──────────┐    ┌──────────────┐                                    │
    │ Mold     │    │ CNC      │    │ Catalog      │◄── Consome ProductDesigned         │
    │ Making   │    │ Machining│    └──────┬───────┘                                    │
    └────┬─────┘    └────┬─────┘           │                                            │
         │               │                 │ Publica ProductPublished                   │
         │               │                 ▼                                            │
         │               │    ┌──────────────────────┐                                  │
         │               │    │ Marketplace          │                                  │
         │               │    │ Integration         │─── ChannelOrderReceived ───┐      │
         │               │    └──────────────────────┘                          │      │
         │               │                                                      ▼      │
         │               │              ┌──────────────────────┐    ┌──────────────────┐│
         │               │              │ Order Management     │◄───│ Retail Operations ││
         │               └──────────────┤ (aggregador central) │    └──────────────────┘│
         │                              └──────────┬───────────┘                        │
         │                                         │                                    │
         │                    ┌────────────────────┼────────────────────┐               │
         │                    ▼                    ▼                    ▼               │
         │            ┌──────────┐        ┌──────────┐        ┌──────────────┐         │
         └───────────►│ Inventory│        │ Pricing  │        │ Shipping     │         │
                      └────┬─────┘        └──────────┘        └──────────────┘         │
                           │                                                           │
                           ▼                                                           │
                    ┌──────────────┐                                                    │
                    │ Analytics    │◄── Consome TODOS os eventos ──────────────────────┘
                    └──────────────┘
```

---

## 4. Catálogo de Agentes

Cada agente é uma unidade independente com 6 dimensões:

| Dimensão | Descrição |
|---|---|
| **Prompt** | System prompt com papel, conhecimento de domínio, restrições e formato de saída |
| **Memória** | Short-term (contexto atual), Long-term (vector store), Episodic (histórico de decisões) |
| **Ferramentas** | Conjunto de tools que o agente pode invocar (APIs, calculadoras, validadores) |
| **Tarefas** | Schedule (cron) ou event-driven triggers que ativam o agente |
| **Logs** | Toda ação do agente é logada com correlation ID e audit trail |
| **Configurações** | Modelo LLM, temperatura, max tokens, retry policy, timeout |

### 4.1 Agentes por Contexto

#### PRODUÇÃO (5 contextos, 18 agentes)

| # | Agente | Contexto | Tipo | Responsabilidade |
|---|---|---|---|---|
| AG-001 | `product-design-assistant` | Product Engineering | Observer | Auxilia designers com validação de especificações, sugere materiais alternativos, verifica completude da BOM |
| AG-002 | `bom-validator` | Product Engineering | Decision Maker | Valida consistência da BOM (Bill of Materials), detecta componentes faltantes, conflitos de revisão |
| AG-003 | `revision-tracker` | Product Engineering | Observer | Monitora ciclo de revisões, alerta sobre revisões pendentes de aprovação há mais de X dias |
| AG-004 | `mold-design-reviewer` | Mold Making | Analyst | Analisa design do molde contra regras de manufaturabilidade, ângulos de saída, espessura de parede |
| AG-005 | `mold-maintenance-predictor` | Mold Making | Decision Maker | Prediz necessidade de manutenção baseado em contagem de ciclos, material injetado, histórico de falhas |
| AG-006 | `fabrication-tracker` | Mold Making | Observer | Acompanha progresso de fabricação do molde, alerta sobre atrasos no cronograma |
| AG-007 | `cnc-scheduler` | CNC Machining | Decision Maker | Otimiza scheduling de máquinas CNC: prioridade, setup time, disponibilidade de ferramentas |
| AG-008 | `tool-wear-monitor` | CNC Machining | Observer | Monitora desgaste de ferramentas, prediz momento de troca baseado em horas de uso e material |
| AG-009 | `nc-program-validator` | CNC Machining | Decision Maker | Valida programas NC antes da execução: colisões, limites de eixo, velocidades seguras |
| AG-010 | `cycle-optimizer` | Injection Molding | Analyst | Analisa dados de ciclo e recomenda ajustes de parâmetros (temperatura, pressão, tempo) |
| AG-011 | `defect-detector` | Injection Molding | Observer | Identifica padrões de defeito (rebarba, rechupo, queima) correlacionando com parâmetros de máquina |
| AG-012 | `production-forecaster` | Injection Molding | Analyst | Prevê capacidade produtiva baseado em histórico, sazonalidade e manutenções programadas |
| AG-013 | `quality-gatekeeper` | Injection Molding | Decision Maker | Monitoramento de qualidade em tempo real, decide parada de máquina se taxa de defeito excede threshold |
| AG-014 | `formulation-optimizer` | Plastisol Processing | Analyst | Analisa formulações de plastisol, sugere ajustes de viscosidade, plastificante, estabilizante |
| AG-015 | `curing-monitor` | Plastisol Processing | Observer | Monitora ciclos de cura, detecta desvios de perfil de temperatura, alerta sobre sub-cura ou sobre-cura |
| AG-016 | `coating-qc` | Plastisol Processing | Decision Maker | Controle de qualidade de revestimento: espessura, aderência, cor, brilho, ausência de bolhas |
| AG-017 | `mold-material-matcher` | Mold Making | Decision Maker | Recomenda tipo de aço e tratamento térmico baseado no material plástico e volume de produção esperado |
| AG-018 | `setup-sheet-generator` | CNC Machining | Executor | Gera setup sheets automaticamente a partir do programa NC e do modelo 3D |

#### COMERCIAL (4 contextos, 12 agentes)

| # | Agente | Contexto | Tipo | Responsabilidade |
|---|---|---|---|---|
| AG-019 | `catalog-enricher` | Catalog | Executor | Enriquece fichas de produto: gera descrições, bullet points, atributos técnicos a partir de especificações |
| AG-020 | `media-organizer` | Catalog | Executor | Organiza e taggeia mídia de produto: fotos, vídeos, manuais, por tipo e ângulo |
| AG-021 | `seo-optimizer` | Catalog | Analyst | Analisa e otimiza títulos, descrições e keywords para SEO de marketplace |
| AG-022 | `listing-synchronizer` | Marketplace | Executor | Mantém listings sincronizados entre catálogo interno e canais externos, detecta divergências |
| AG-023 | `competitor-monitor` | Marketplace | Observer | Monitora preços e posicionamento de concorrentes nos marketplaces, alerta sobre undercutting |
| AG-024 | `channel-health-checker` | Marketplace | Observer | Monitora saúde das contas: reputação, métricas de vendedor, pedidos cancelados, atrasos |
| AG-025 | `repricing-agent` | Marketplace | Decision Maker | Ajusta preços dinamicamente baseado em regras de margem mínima, competição e elasticidade |
| AG-026 | `store-inventory-auditor` | Retail Operations | Observer | Reconcilia inventário físico vs sistema, identifica divergências e sugere recontagem |
| AG-027 | `sales-pattern-analyzer` | Retail Operations | Analyst | Analisa padrões de venda por loja, horário, dia da semana; sugere promoções localizadas |
| AG-028 | `conversational-seller` | Telegram Commerce | Executor | Conduz conversa de venda no Telegram: apresenta produtos, tira dúvidas, fecha pedido |
| AG-029 | `order-assistant` | Telegram Commerce | Executor | Auxilia cliente com status de pedido, rastreio, prazos, trocas e devoluções |
| AG-030 | `product-recommender` | Telegram Commerce | Analyst | Recomenda produtos baseado no histórico do cliente, preferências e contexto da conversa |

#### OPERAÇÕES (5 contextos, 14 agentes)

| # | Agente | Contexto | Tipo | Responsabilidade |
|---|---|---|---|---|
| AG-031 | `stock-level-monitor` | Inventory | Observer | Monitora níveis de estoque, dispara alertas de ponto de reposição, ruptura ou excesso |
| AG-032 | `demand-forecaster` | Inventory | Analyst | Prevê demanda por SKU/canal usando séries temporais, sazonalidade e tendências |
| AG-033 | `inventory-optimizer` | Inventory | Decision Maker | Otimiza distribuição de estoque entre depósitos e lojas, sugere transferências |
| AG-034 | `dead-stock-detector` | Inventory | Analyst | Identifica estoque parado (sem giro há X dias), sugere liquidação ou descarte |
| AG-035 | `order-router` | Order Management | Decision Maker | Roteia pedido para o centro de fulfillment ótimo (menor custo, menor prazo, estoque disponível) |
| AG-036 | `fraud-detector` | Order Management | Decision Maker | Analisa pedidos em tempo real contra padrões de fraude: score, bloqueio ou liberação |
| AG-037 | `fulfillment-monitor` | Order Management | Observer | Monitora SLAs de fulfillment, alerta sobre pedidos em risco de atraso |
| AG-038 | `return-analyzer` | Order Management | Analyst | Analisa padrões de devolução: motivos, SKUs problemáticos, correlação com lotes de produção |
| AG-039 | `customer-segmenter` | Customer | Analyst | Segmenta clientes automaticamente por comportamento (RFM) e atributos demográficos |
| AG-040 | `churn-predictor` | Customer | Decision Maker | Prediz risco de churn e sugere ações de retenção (cupom, contato, oferta especial) |
| AG-041 | `lifetime-value-estimator` | Customer | Analyst | Estima LTV por segmento, canal de aquisição e coorte |
| AG-042 | `carrier-selector` | Shipping | Decision Maker | Seleciona transportadora ótima por pedido: menor custo vs prazo vs confiabilidade |
| AG-043 | `shipping-cost-optimizer` | Shipping | Analyst | Sugere otimizações de embalagem e agrupamento para reduzir custo de frete |
| AG-044 | `delivery-tracker` | Shipping | Observer | Monitora entregas em tempo real, alerta sobre atrasos ou extravios |

#### INTELIGÊNCIA (1 contexto, 6 agentes)

| # | Agente | Contexto | Tipo | Responsabilidade |
|---|---|---|---|---|
| AG-045 | `business-analyst` | Analytics | Analyst | Gera relatórios executivos automáticos: vendas, margem, produção, giro de estoque |
| AG-046 | `anomaly-detector` | Analytics | Observer | Detecta anomalias estatísticas em qualquer métrica do sistema e dispara alertas |
| AG-047 | `trend-forecaster` | Analytics | Analyst | Prevê tendências de mercado, vendas e produção usando modelos estatísticos |
| AG-048 | `executive-digest` | Analytics | Executor | Gera resumo executivo diário/semanal e envia por canal configurado (email, Telegram) |
| AG-049 | `cross-context-correlator` | Analytics | Analyst | Correlaciona eventos entre contextos (ex: defeito de injeção → aumento de devoluções) |
| AG-050 | `margin-watchdog` | Analytics | Decision Maker | Monitora margem por produto/canal e alerta quando abaixo do threshold configurado |

#### COORDENAÇÃO (cross-cutting, 2 agentes)

| # | Agente | Contexto | Tipo | Responsabilidade |
|---|---|---|---|---|
| AG-051 | `workflow-orchestrator` | Agents/Orchestration | Coordinator | Orquestra workflows multi-agente: recebe gatilho → spawna agentes → coleta resultados → decide próximo passo |
| AG-052 | `system-health-monitor` | Agents/Registry | Observer | Monitora saúde de todos os agentes: heartbeats, latência, erros; reinicia agentes mortos |

---

### 4.2 Classificação por Tipo de Agente

| Tipo | Descrição | Exemplos |
|---|---|---|
| **Observer** | Somente leitura. Monitora fluxo de eventos/dados e detecta condições de alerta | stock-level-monitor, defect-detector, tool-wear-monitor |
| **Analyst** | Leitura + processamento. Analisa dados históricos e gera insights, previsões, relatórios | demand-forecaster, sales-pattern-analyzer, cycle-optimizer |
| **Decision Maker** | Decide ações baseado em regras e thresholds. Pode disparar alertas ou acionar Executors | order-router, repricing-agent, carrier-selector |
| **Executor** | Executa ações de escrita: chama APIs, gera conteúdo, envia mensagens | listing-synchronizer, catalog-enricher, conversational-seller |
| **Coordinator** | Orquestra múltiplos agentes em workflows complexos com lógica de branching/merging | workflow-orchestrator |

---

## 5. Responsabilidades Detalhadas

### 5.1 Shared Kernel (`src/shared/`)

**Responsabilidade**: Código compartilhado entre TODOS os contextos. Alterações aqui afetam todos os contextos, portanto mudanças exigem coordenação.

- `domain/value-objects/` — Value Objects universais (Money, Dimensions, Email). Imutáveis, com validação no construtor
- `domain/entities/` — BaseEntity (id, createdAt, updatedAt), AggregateRoot (domainEvents collection)
- `domain/events/` — IDomainEvent, IIntegrationEvent, IDomainEventHandler<T>
- `application/ports/` — Contratos que a camada de application espera que a infrastructure implemente
- `infrastructure/` — Implementações concretas dos contratos. Trocáveis (ex: trocar Postgres por MySQL sem alterar domínio)

### 5.2 API Gateway (`src/api/`)

**Responsabilidade**: Único ponto de entrada externo. Autenticação, rate limiting, request/response transformation. NÃO contém lógica de negócio.

- REST para operações CRUD e integrações síncronas
- GraphQL para queries complexas e clients que precisam selecionar campos
- WebSocket para notificações real-time (status de pedido, alertas de produção)

### 5.3 Agent Framework (`src/agents/`)

**Responsabilidade**: Infraestrutura para criar, gerenciar e monitorar agentes. É um framework, não contém lógica de domínio.

- `core/` — Runtime que gerencia o lifecycle do agente (spawn → running → paused → stopped → destroyed)
- `prompt/` — Sistema de templates de prompt com injeção de variáveis de contexto
- `memory/` — Três tipos de memória: curto prazo (buffer circular), longo prazo (vector search), episódica (event log)
- `tools/` — Registry de ferramentas com schema validation (Zod) e sandbox de execução
- `tasks/` — Sistema de filas com prioridade, retry, dead letter, e scheduling cron
- `logging/` — Log estruturado com correlation ID, audit trail imutável de decisões
- `config/` — Configuração por agente, por ambiente, com validação de schema
- `registry/` — Service discovery de agentes: quem está vivo, quais capabilities oferece
- `orchestration/` — Workflow engine para compor agentes em pipelines multi-etapa (DAG)
- `instances/` — Catálogo de instâncias concretas organizadas por tipo (observer, analyst, decision-maker, executor, coordinator)

### 5.4 Bounded Contexts (`src/contexts/*/`)

Cada contexto é um módulo isolado com:

- **domain/** — Regras de negócio puras. Zero dependências externas
- **application/** — Casos de uso que orquestram entidades de domínio. Depende só do domain
- **infrastructure/** — Implementações concretas (banco, filas, APIs externas). Depende de domain e application
- **agents/** — Configurações e ferramentas específicas dos agentes daquele contexto

**Contextos Core (diferencial competitivo)**:
1. **Product Engineering** — Design de produto é o core criativo
2. **Mold Making** — Fabricação de moldes é o core técnico
3. **CNC Machining** — Usinagem de precisão
4. **Injection Molding** — Produção em massa
5. **Plastisol Processing** — Processo especializado

**Contextos Supporting (suportam o core)**:
6. **Catalog** — Representação comercial dos produtos
7. **Marketplace Integration** — Distribuição multicanal
8. **Retail Operations** — Vendas presenciais
9. **Telegram Commerce** — Vendas conversacionais
10. **Inventory** — Gestão de estoque unificada
11. **Order Management** — Orquestração de pedidos omnichannel
12. **Customer** — Relacionamento com cliente
13. **Pricing** — Estratégia de precificação
14. **Shipping** — Logística de entrega
15. **Analytics** — Inteligência de negócio (consome eventos de todos)

---

## 6. Fluxo de Eventos Principal

### 6.1 Ciclo de Vida do Produto (event flow)

```
ProductDesigned → BOMValidated → MoldDesigned → MoldFabricated
                                                      ↓
                                            NCProgramGenerated → MachiningCompleted
                                                      ↓
                                            MoldDelivered → MoldInstalled
                                                      ↓
                                            ProductionRunStarted → BatchCompleted
                                                      ↓
                                            StockReceived → ProductPublished
                                                      ↓
                                            ListingPublished (multi-canal)
                                                      ↓
                                            OrderPlaced → OrderConfirmed → StockReserved
                                                      ↓
                                            ShipmentCreated → OrderDelivered
```

### 6.2 Ciclo de Venda Omnichannel (event flow)

```
[Marketplace] ChannelOrderReceived ──┐
[Loja Física]  SaleCompleted ────────┤
[Telegram]     OrderConfirmedViaChat ─┤
                                      ▼
                              OrderPlaced (order-management)
                                      │
                          ┌───────────┼───────────┐
                          ▼           ▼           ▼
                   FraudDetected  StockReserved  PriceCalculated
                          │           │
                          ▼           ▼
                   OrderConfirmed ────┤
                                      ▼
                              FulfillmentRouted
                                      │
                          ┌───────────┼───────────┐
                          ▼           ▼           ▼
                   ShipmentCreated  InvoiceGenerated  CustomerNotified
                          │
                          ▼
                   OrderDelivered → LoyaltyPointsEarned → Analytics_OrderCompleted
```

---

## 7. Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| **Runtime** | Node.js 22 + TypeScript 5.x (strict mode) |
| **API Gateway** | Fastify (REST) + Mercurius (GraphQL) + WS (WebSocket) |
| **CQRS** | Comandos: fila BullMQ; Queries: direto ao banco read-optimized |
| **Mensageria** | Kafka para event streaming; RabbitMQ para comandos assíncronos |
| **Banco Relacional** | PostgreSQL 16 — dados transacionais, write side |
| **Banco Documentos** | MongoDB 7 — catálogo, dados semi-estruturados |
| **Cache** | Redis 7 — cache, rate limiting, pub/sub, filas leves |
| **Vector Store** | Qdrant — embeddings para memória de longo prazo dos agentes |
| **LLM Provider** | Abstração multi-provider: OpenAI, Anthropic, Groq, Ollama (local) |
| **Observabilidade** | OpenTelemetry → Grafana + Prometheus + Tempo + Loki |
| **Containerização** | Docker + Docker Compose (dev) / Kubernetes (prod) |
| **CI/CD** | GitHub Actions |
| **DI** | tsyringe (leve, decorator-based) |
| **Validação** | Zod (runtime type safety em boundaries) |
| **Testes** | Jest + Supertest + k6 |

---

## 8. Princípios Arquiteturais Aplicados

| Princípio | Como se manifesta |
|---|---|
| **S**RP | Cada contexto tem 1 razão para mudar. Cada agente tem 1 responsabilidade |
| **O**CP | Novos agentes e ferramentas são adicionados sem modificar existentes (plugin architecture) |
| **L**SP | Todo repositório implementa a interface do domínio; infra pode ser trocada |
| **I**SP | Ports são enxutos: IProductRepository tem só o que Product precisa |
| **D**IP | Application depende de abstrações (ports), Infrastructure implementa os ports |
| **DDD** | 15 bounded contexts com linguagem ubíqua, aggregates, domain events, repositories |
| **Clean Architecture** | Dependência unidirecional: API → Application → Domain ← Infrastructure |
| **Event-Driven** | Contextos desacoplados via eventos. Event Sourcing para audit trail crítico |
| **CQRS** | Separação comando/consulta. Write side otimizado para consistência, Read side para performance |

---

## 9. Decisões Arquiteturais Pendentes (ADR a criar)

1. **ADR-001**: Escolha do message broker (Kafka vs RabbitMQ vs NATS)
2. **ADR-002**: Estratégia de event sourcing (full vs partial vs event notification only)
3. **ADR-003**: Orquestração vs Choreography para sagas entre contextos
4. **ADR-004**: Database per context vs shared database with schema isolation
5. **ADR-005**: LLM provider strategy (multi-provider abstraction vs single vendor)
6. **ADR-006**: Agent-to-agent communication protocol (direct call vs message passing vs blackboard)
7. **ADR-007**: Deployment topology (monolith modular vs microservices vs hybrid)
