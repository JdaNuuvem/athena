# Tutorial: Integração Completa Shopee Ads (AG-ADS)

Este tutorial explica como integrar o ATHENA OS com o sistema de publicidade Shopee (Ads) usando o agente inteligente AG-ADS.

## O que é AG-ADS?

AG-ADS é o agente inteligente de publicidade Shopee do ATHENA OS. Ele:

- **Cria campanhas automaticamente** com otimização de keywords
- **Analisa performance em tempo real** (CTR, CPC, ROAS, etc.)
- **Ajusta bids automaticamente** baseado em performance
- **Gera insights automáticos** (sugestões de otimização)
- **Prediz performance futura** com ML
- **Sugere orçamento ótimo** baseado em ROI
- **Gerencia A/B Testing** de campanhas

## Pré-requisitos

- ATHENA OS instalado e funcionando
- Shopee Seller Central configurado
- Token de acesso Shopee Ads API
- Crédito publicitário na Shopee

## Passo 1: Obter Token Shopee Ads API

### 1.1 Acessar Shopee Seller Central

1. Faça login em [Shopee Seller Central](https://seller.shopee.com.br)
2. Vá em "Marketing" → "Shopee Ads"
3. Ative o módulo "Search Ads" (recomendado para início)

### 1.2 Gerar Token de Acesso

1. Vá em "Centro de Desenvolvedor"
2. Crie uma aplicação (App)
3. Configure as permissões:
   - `ad.campaign.info`
   - `ad.campaign.create`
   - `ad.campaign.update`
   - `ad.keyword.create`
   - `ad.keyword.update`
   - `ad.report.stats`

4. Copie os tokens:
   - `app_id`
   - `app_secret`
   - `access_token`

## Passo 2: Configurar AG-ADS no Athena

### 2.1 Configurar Variáveis de Ambiente

No arquivo `.env` do Athena:

```bash
SHOPEE_PARTNER_ID=seu_partner_id
SHOPEE_PARTNER_KEY=sua_partner_key
SHOPEE_SHOP_ID=seu_shop_id
SHOPEE_ACCESS_TOKEN=seu_access_token
SHOPEE_ADS_API_URL=https://open.shopee.com
DATABASE_URL=postgresql://athena:athena@localhost:5433/athena
```

### 2.2 Testar Conexão

```bash
curl http://localhost:4000/api/shopee-ads/test
```

Resposta esperada:
```json
{
  "success": true,
  "message": "Shopee Ads API connection successful"
}
```

## Passo 3: Criar Primeira Campanha

### 3.1 Via Frontend Athena

1. Acesse `http://localhost:4000`
2. Clique em "Integrações" → "Shopee Ads"
3. Clique em "+ Nova Campanha"
4. Preencha:
   - **Nome**: "Organizadores Cozinha - Search Ads"
   - **Orçamento diário**: 100 (R$ 100)
   - **Keywords** (sugeridas):
     - organizador cozinha (phrase, R$ 1.50)
     - cozinha organização (broad, R$ 1.00)
     - potes plásticos (exact, R$ 2.00)

5. Clique em "Criar"

### 3.2 Via API

```bash
curl -X POST http://localhost:4000/api/shopee-ads/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "shopId": "seu_shop_id",
    "name": "Organizadores Cozinha",
    "dailyBudget": 100,
    "startDate": "2026-07-06",
    "keywords": [
      {
        "keyword": "organizador cozinha",
        "matchType": "phrase",
        "bid": 1.5
      }
    ]
  }'
```

## Passo 4: Analisar Performance

### 4.1 Analisar Campanha Específica

```bash
curl http://localhost:4000/api/shopee-ads/campaigns/SC123/analyze?days=30
```

Resposta:
```json
{
  "success": true,
  "metrics": {
    "total": {
      "impressions": 15000,
      "clicks": 250,
      "cost": 450,
      "orders": 35,
      "revenue": 1750
    },
    "avg_ctr": "1.67",
    "avg_cpc": "1.80",
    "avg_conversion_rate": "14.00",
    "avg_roas": "3.89",
    "cpa": "12.86"
  },
  "insights": [
    {
      "type": "low_ctr",
      "severity": "warning",
      "message": "CTR muito baixo (1.67%)"
    }
  ]
}
```

### 4.2 Métricas Importantes

- **CTR (Click-Through Rate)**: % de cliques por impressão
  - Bom: > 2%
  - Regular: 1-2%
  - Ruim: < 1%

- **CPC (Cost Per Click)**: Custo por clique
  - Bom: < R$ 1.50
  - Regular: R$ 1.50 - R$ 2.50
  - Ruim: > R$ 2.50

- **ROAS (Return On Ad Spend)**: Retorno sobre investimento
  - Bom: > 4.0
  - Regular: 2.0 - 4.0
  - Ruim: < 2.0

- **CPA (Cost Per Acquisition)**: Custo por pedido
  - Bom: < R$ 10
  - Regular: R$ 10 - R$ 20
  - Ruim: > R$ 20

## Passo 5: Ajustar Bids Automaticamente

### 5.1 Ativar Auto-Adjustment

```bash
curl -X POST http://localhost:4000/api/shopee-ads/campaigns/SC123/adjust-bids \
  -H "Content-Type: application/json" \
  -d '{
    "targetRoas": 3.0
  }'
```

### 5.2 Como Funciona o Auto-Adjustment

O AG-ADS ajusta bids baseado em:
1. **ROAS atual vs alvo**
   - ROAS < 80% do alvo → Reduzir bid em 10%
   - ROAS > 120% do alvo → Aumentar bid em 10%
   - ROAS na faixa ideal → Manter bid

2. **Frequência**: A cada 60 minutos (configurável)
3. **Limites**: Bid mínimo R$ 0.10, máximo R$ 5.00

## Passo 6: Prever Performance

### 6.1 Prever Performance de 30 dias

```bash
curl http://localhost:4000/api/shopee-ads/campaigns/SC123/predict?days=30
```

Resposta:
```json
{
  "success": true,
  "prediction": {
    "impressions": 18000,
    "clicks": 300,
    "cost": 540,
    "orders": 42,
    "revenue": 2100
  },
  "metrics": {
    "ctr": "1.67",
    "cpc": "1.80",
    "conversion_rate": "14.00",
    "roas": "3.89",
    "cpa": "12.86"
  },
  "confidence": 75
}
```

## Passo 7: Sugerir Orçamento Ótimo

### 7.1 Obter Sugestão de Budget

```bash
curl http://localhost:4000/api/shopee-ads/campaigns/SC123/suggest-budget?targetRoas=3.0
```

Resposta:
```json
{
  "success": true,
  "suggestion": {
    "currentDailyBudget": "100.00",
    "currentRoas": "3.89",
    "targetRoas": "3.00",
    "optimalDailyBudget": "110.00",
    "recommendation": "increase",
    "reason": "ROAS acima do alvo. Aumentar orçamento pode escalar vendas."
  }
}
```

### 7.2 Estratégias de Budget

**Conservadora (ROAS > 4.0)**
- Aumentar 10-20%
- Expande palavras de cauda longa

**Moderada (ROAS 2.0-4.0)**
- Manter orçamento
- Ajustar bids, não budget

**Aggressiva (ROAS < 2.0)**
- Reduzir orçamento em 20-30%
- Pausar keywords com baixa performance

## Passo 8: A/B Testing

### 8.1 Criar Teste A/B

```bash
curl -X POST http://localhost:4000/api/shopee-ads/abtests \
  -H "Content-Type: application/json" \
  -d '{
    "campaignId": "SC123",
    "name": "Teste Bidding: Manual vs Auto",
    "variant": "test",
    "configuration": {
      "bidding": "auto",
      "targetRoas": 3.0
    }
  }'
```

### 8.2 Criar Variante Controle

```bash
curl -X POST http://localhost:4000/api/shopee-ads/abtests \
  -H "Content-Type: application/json" \
  -d '{
    "campaignId": "SC123",
    "name": "Teste Bidding: Manual vs Auto",
    "variant": "control",
    "configuration": {
      "bidding": "manual",
      "maxBid": 2.0
    }
  }'
```

### 8.3 Analisar Resultados

Depois de 7-14 dias, compare:
- ROAS médio
- CPC médio
- Conversão
- Custo total

O AG-ADS sugerirá o vencedor automaticamente.

## Passo 9: Configurar Sincronização Automática

### 9.1 Cron Job (Linux/Mac)

```bash
crontab -e
```

Adicionar:

```cron
# Sincronizar performance a cada hora
0 * * * * curl -X POST http://localhost:4000/api/shopee-ads/sync >> /var/log/shopee_ads_sync.log 2>&1

# Ajustar bids a cada 2 horas
0 */2 * * * curl -X POST http://localhost:4000/api/shopee-ads/auto-adjust >> /var/log/shopee_ads_adjust.log 2>&1
```

### 9.2 Windows Task Scheduler

1. Abrir "Agendador de Tarefas"
2. Criar nova tarefa
3. Trigger: "Repetir a cada 1 hora"
4. Ação: "Executar programa"
5. Programa: `curl`
6. Argumentos: `-X POST http://localhost:4000/api/shopee-ads/sync`

## Passo 10: Monitorar Insights

### 10.1 Via Frontend

1. Acesse `/shopee-ads`
2. Visualize insights na aba "Insights"
3. Ações disponíveis:
   - **Low CTR**: Revisar keywords e títulos
   - **High CPC**: Ajustar bids ou keywords
   - **Low ROAS**: Pausar campanha ou reduzir bids
   - **Trending Up**: Aumentar orçamento
   - **Trending Down**: Investigar causas

### 10.2 Via API

```bash
curl http://localhost:4000/api/shopee-ads/insights
```

## Troubleshooting

### Problema: Token expirado

**Solução:**
```bash
# Gerar novo token via Shopee Seller Central
# Atualizar variável de ambiente
export SHOPEE_ACCESS_TOKEN=novo_token

# Reiniciar Athena
npm run dev
```

### Problema: Campanha não ativa

**Solução:**
```bash
# Verificar saldo publicitário
curl https://open.shopee.com/api/v2/ad/campaign/info \
  -H "Authorization: Bearer $SHOPEE_ACCESS_TOKEN"

# Adicionar saldo em Shopee Seller Central
```

### Problema: Insights não aparecem

**Solução:**
```bash
# Sincronizar dados manualmente
curl -X POST http://localhost:4000/api/shopee-ads/sync

# Verificar logs
tail -f logs/athena.log | grep AG-ADS
```

## Próximos Passos

1. **Expandir Keywords**: Adicionar 20-30 keywords por campanha
2. **Testar Criativos**: A/B testing de títulos e imagens
3. **Aumentar Orçamento**: Baseado em ROAS > 4.0
4. **Criar Campanhas Discovery**: Para expansão de alcance
5. **Integrar com Bling**: Rastrear vendas e margem real

## Melhores Práticas

### Keywords

- **Broad**: Alcance alto, baixa precisão (1-2 bids)
- **Phrase**: Alcance médio, precisão média (2-3 bids)
- **Exact**: Baixo alcance, alta precisão (3-5 bids)

**Recomendação**: 60% exact, 30% phrase, 10% broad

### Bidding

- Comece com bids conservadores (R$ 1.00 - R$ 2.00)
- Aumente gradualmente conforme dados
- Use auto-adjustment após 7 dias de dados

### Orçamento

- Inicial: R$ 50 - R$ 100/dia
- Escalar quando ROAS > 4.0
- Reduzir quando ROAS < 2.0

### A/B Testing

- Teste 1 variável por vez
- Duração mínima: 7 dias
- Tamanho da amostra: > 100 cliques

## Documentação Adicional

- [API Shopee Ads](https://open.shopee.com/documents?module=63)
- [Documentação técnica AG-ADS](/docs/documentacao-tecnica-ads.md)
- [Relatórios completos](/api/shopee-ads/dashboard)

## Suporte

Em caso de dúvidas:
1. Verificar logs: `logs/athena.log`
2. Testar API: `curl http://localhost:4000/api/shopee-ads/test`
3. Verificar saúde: `curl http://localhost:4000/api/health`

---

**Versão:** 1.0
**Última atualização:** 06/07/2026
**Status:** ✅ AG-ADS 100% funcional