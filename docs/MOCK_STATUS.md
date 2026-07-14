# Status do Sistema — Consolidado (Hermes + ATHENA)

## Arquitetura Atual

```
Shopee API (real)
    ↕ sync (shopee_sync.py)
Hermes PostgreSQL
    ├── AG-02 (Lucratividade) → margens, rankings, alertas
    ├── AG-03 (Marketplaces)  → preços, concorrentes, anúncios
    ├── AG-01 (Caçador)       → scoring de produtos
    └── AG-14 (WhatsApp)      → vendas WhatsApp
        ↕
Flask API (athena_bridge.py) — 95 endpoints
    ↕
Frontend React (12 páginas)
```

## Rotas Implementadas vs Frontend

| Página | Rotas | Status |
|--------|-------|--------|
| Dashboard | `/api/health`, `/api/agents` | ✅ com AG-14 adicionado |
| Agents | `/api/agents`, `/api/agents/:id` | ✅ |
| Business | `/api/business/inventory/*`, `/api/business/quality/*`, `/api/business/orders` | ✅ Novo |
| HermesIntegration | `/api/hermes/agents`, `/api/hermes/opportunities`, `/api/hermes/alerts`, `/api/hermes/execute`, `/api/hermes/sync-all` | ✅ Novo |
| ShopeeAds | `/api/shopee-ads/campaigns`, `/api/shopee-ads/performance`, `/api/shopee-ads/insights`, `/api/shopee-ads/abtests` | ✅ Novo |
| Integrations | `/api/integrations`, `/api/integrations/:id/connect` | ✅ Novo |
| Chat | `/api/hermes/chat` | ✅ Novo (rota roteia pro AG-10) |
| WhatsApp | `/api/agent/ag_14_whatsapp/*`, `/webhook/whatsapp` | ✅ Portado |
| Shopee | `/api/shopee/produtos/*`, `/api/shopee/pedidos/*`, `/api/shopee/produtos/sincronizar` | ✅ Aprimorado |

## Status de Mocks

| Módulo | Status | Detalhe |
|--------|--------|---------|
| **Shopee API** | ✅ Completo | HMAC corrigido, sync pipeline (`shopee_sync.py`) popula `anuncios` + `vendas` para AG-02/AG-03 |
| **AG-14 WhatsApp** | ✅ Portado | Evolution API, conversação, catálogo, pedidos, webhook |
| **AG-01 (Caçador)** | 🟡 Parcial | `FONTE_DADOS` default "simulada". `config/produtos.json` não existe. Roda via `/api/hermes/execute` |
| **AG-05 (CNC)** | 🔴 Mock | `random.uniform()` — usuário não precisa |
| **AG-08 (Lojas)** | 🔴 Mock | Sem integração PDV |
| **AG-06 NLP** | 🟡 Parcial | Keyword matching |
| **AG-06 Pagamento** | 🔴 Mock | Sempre "confirmado" |
| **Bling ERP** | 🟡 Parcial | Client pronto, precisa de chave |
| **AG-13 (ML)** | ✅ Real | scikit-learn RandomForest |
| **Shopee Ads** | 🟡 Esqueleto | Rotas no backend, tabelas no DB, sem dados reais (Shopee Ads API não integrada) |
| **Health** | 🟡 Parcial | `/api/health` hardcoded, `/api/health/real` consulta banco de verdade |
| **Config files** | 🔴 Ausente | `config/produtos.json`, `tendencias.json` não existem |

## Próximos passos recomendados

1. **Configurar chaves Shopee** no painel ou via env vars (`SHOPEE_PARTNER_ID`, `SHOPEE_PARTNER_KEY`, `SHOPEE_SHOP_ID`, `SHOPEE_ACCESS_TOKEN`)
2. **Rodar sync** → `POST /api/shopee/produtos/sincronizar` ou `POST /api/hermes/sync-all`
3. **Criar `config/produtos.json`** para AG-01 ter dados de entrada
4. **Adicionar Evolution API** (WhatsApp) com `EVOLUTION_API_KEY` env var
5. **Integrar Shopee Ads API real** quando precisar de campanhas pagas
