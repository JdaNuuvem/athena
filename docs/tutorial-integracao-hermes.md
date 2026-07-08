# Tutorial: Integração Completa com Hermes Agents

Este tutorial explica como integrar o ATHENA OS com o sistema Hermes Agents de forma completa e funcional.

## O que é Hermes Agents?

Hermes Agents é um sistema multi-agente Python especializado para indústria de manufatura. Ele consiste em 10 agentes inteligentes:

- **AG-09: Memória Corporativa** - Bibliotecário técnico da fábrica
- **AG-01: Caçador de Produtos** - Descobre oportunidades em marketplaces
- **AG-02: Analista de Lucratividade** - Calcula margens reais
- **AG-03: Gerente de Marketplaces** - Monitora anúncios e concorrência
- **AG-04: Planejador de Produção** - Planeja produção e materiais
- **AG-05: Industrial** - Controla linha de produção
- **AG-06: Telegram** - Notificações e alertas
- **AG-07: Laboratório** - Análise de qualidade
- **AG-08: Lojas** - Gestão de lojas físicas
- **AG-10: Diretor** - Coordenação geral

## Pré-requisitos

- Athena OS instalado e funcionando
- PostgreSQL com banco `hermes_factory`
- Python 3.9+ instalado
- Acesso ao diretório `hermes_agents/`

## Passo 1: Configurar Banco de Dados Hermes

### 1.1 Criar o banco de dados

```bash
psql -U postgres -c "CREATE DATABASE hermes_factory;"
```

### 1.2 Criar o schema Hermes

```bash
cd hermes_agents
python init_db.py
```

Ou manualmente:

```bash
psql -U postgres -d hermes_factory -f sql/schema.sql
```

Isso criará todas as tabelas necessárias:
- `moldes`
- `fichas_tecnicas`
- `fornecedores`
- `materias_primas`
- `historico_custos`
- `produtos_descobertos`
- `vendas`
- `anuncios`
- `concorrentes`
- `alertas`
- E mais...

## Passo 2: Configurar Conexão Athena → Hermes

### 2.1 Editar arquivo de configuração

Crie ou edite `~/.hermes/factory_config.json`:

```json
{
  "db_host": "localhost",
  "db_port": 5432,
  "db_name": "hermes_factory",
  "db_user": "postgres",
  "db_password": "sua_senha",

  "mercado_livre_authorization": "",
  "shopee_partner_id": "",
  "shopee_partner_key": "",

  "telegram_bot_token": "",

  "margem_minima_pct": 15.0,
  "ruptura_estoque_dias": 7
}
```

### 2.2 Configurar URL do Athena

No arquivo `hermes_agents/athena_bridge.py`, altere:

```python
ATHENA_URL = os.environ.get("ATHENA_URL", "http://localhost:4000")
```

Ou use variável de ambiente:

```bash
export ATHENA_URL="http://localhost:4000"
```

## Passo 3: Testar Integração

### 3.1 Testar bridge Hermes → Athena

```bash
cd hermes_agents
python athena_bridge.py
```

Você deve ver:
```
🔗 Athena Bridge — Teste de Conexão
==================================================

Health: ✓ ok
Agents Athena: 52 agentes
Stats Hermes: ✓

==================================================
🏭️ HERMES AGENTS → ATHENA OS — Relatório de Integração
==========================================================
...
```

### 3.2 Testar endpoint do Athena

No browser, acesse:
```
http://localhost:4000/api/hermes/agents
```

Você deve ver os agentes Hermes registrados.

## Passo 4: Registrar Agentes Hermes

### 4.1 Via API do Athena

```bash
curl -X POST http://localhost:4000/api/hermes/register \
  -H "Content-Type: application/json" \
  -d '{
    "agente_id": "ag_09_memoria",
    "nome": "AG-09 Memória Corporativa",
    "descricao": "Bibliotecário técnico da fábrica",
    "categoria": "memoria",
    "modelo": "claude-sonnet-4-20250514",
    "provider": "anthropic",
    "intervalo_minutos": 60
  }'
```

### 4.2 Registrar todos os agentes

```bash
curl -X POST http://localhost:4000/api/hermes/register \
  -H "Content-Type: application/json" \
  -d '{
    "agente_id": "ag_01_cacador",
    "nome": "AG-01 Caçador de Produtos",
    "descricao": "Descobre produtos em alta nos marketplaces",
    "categoria": "cacador",
    "intervalo_minutos": 60
  }'

curl -X POST http://localhost:4000/api/hermes/register \
  -H "Content-Type: application/json" \
  -d '{
    "agente_id": "ag_02_lucratividade",
    "nome": "AG-02 Analista de Lucratividade",
    "descricao": "Calcula margens reais por SKU",
    "categoria": "lucratividade",
    "intervalo_minutos": 60
  }'

curl -X POST http://localhost:4000/api/hermes/register \
  -H "Content-Type: application/json" \
  -d '{
    "agente_id": "ag_03_marketplaces",
    "nome": "AG-03 Gerente de Marketplaces",
    "descricao": "Monitora anúncios e concorrência",
    "categoria": "marketplaces",
    "intervalo_minutos": 60
  }'
```

## Passo 5: Executar Agentes Hermes

### 5.1 Executar AG-01 (Caçador de Produtos)

```bash
curl http://localhost:4000/api/hermes/agent/ag_01/cacar
```

### 5.2 Executar AG-02 (Alertas de Lucratividade)

```bash
curl http://localhost:4000/api/hermes/agent/ag_02/alertas
```

### 5.3 Executar AG-09 (Stats da Memória)

```bash
curl http://localhost:4000/api/hermes/agent/ag_09/stats
```

### 5.4 Executar agente genérico

```bash
curl -X POST http://localhost:4000/api/hermes/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "ag_03_marketplaces",
    "action": "executar_monitoramento",
    "params": {}
  }'
```

## Passo 6: Sincronização Completa

### 6.1 Sincronizar todos os dados Hermes → Athena

```bash
curl -X POST http://localhost:4000/api/hermes/sync-all
```

Isso irá:
1. Executar o AG-01 e salvar oportunidades
2. Executar o AG-02 e verificar alertas
3. Sincronizar stats do AG-09

### 6.2 Usar o painel Athena

1. Acesse `http://localhost:4000` no navegador
2. Clique em "Integrações"
3. Encontre "Hermes Agents" na categoria "IA & Agents"
4. Clique em "Configurar" e depois em "Acessar Painel"

No painel você pode:
- Ver todos os agentes Hermes
- Executar ações específicas
- Monitorar oportunidades encontradas
- Visualizar alertas
- Ver histórico de execuções

## Passo 7: Configurar Sincronização Automática

### 7.1 Criar cron job (Linux/Mac)

```bash
crontab -e
```

Adicionar:

```cron
# Sincronizar Hermes a cada 30 minutos
*/30 * * * * curl -X POST http://localhost:4000/api/hermes/sync-all >> /var/log/hermes_sync.log 2>&1
```

### 7.2 Criar tarefa agendada (Windows)

1. Abra "Agendador de Tarefas"
2. Crie nova tarefa
3. Trigger: Repetir a cada 30 minutos
4. Ação: Executar script
5. Script:
```powershell
curl -X POST http://localhost:4000/api/hermes/sync-all
```

## Passo 8: Webhooks (Eventos em Tempo Real)

### 8.1 Configurar webhook Hermes

No arquivo de configuração Hermes:

```json
{
  "athena_webhook_url": "http://localhost:4000/api/hermes/webhook"
}
```

### 8.2 Eventos suportados

- `opportunity_discovered` - Nova oportunidade encontrada
- `margin_alert` - Alerta de margem baixa
- `stock_low` - Estoque baixo
- `competitor_price_change` - Concorrente mudou preço
- `production_ready` - Produção concluída

## Uso Avançado

### Exemplo: Buscar similar na memória corporativa

```bash
curl -X POST http://localhost:4000/api/hermes/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "ag_09_memoria",
    "action": "buscar_similar",
    "params": {
      "descricao": "organizador cozinha"
    }
  }'
```

### Exemplo: Análise de lucratividade por SKU

```bash
curl -X POST http://localhost:4000/api/hermes/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "ag_02_lucratividade",
    "action": "analisar_sku",
    "params": {
      "sku": "ORG001",
      "dias": 30
    }
  }'
```

### Exemplo: Top produtos lucrativos

```bash
curl -X POST http://localhost:4000/api/hermes/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "ag_02_lucratividade",
    "action": "top_lucrativos",
    "params": {
      "n": 10
    }
  }'
```

## Troubleshooting

### Problema: Conexão falha com banco Hermes

**Solução:**
```bash
# Verificar se PostgreSQL está rodando
psql -U postgres -c "SELECT 1"

# Verificar conexão
psql -U postgres -d hermes_factory -c "SELECT COUNT(*) FROM moldes"
```

### Problema: Agentes não aparecem no Athena

**Solução:**
```bash
# Verificar se agentes estão registrados
curl http://localhost:4000/api/hermes/agents

# Registrar manualmente
curl -X POST http://localhost:4000/api/hermes/register -d '{...}'
```

### Problema: Erro ao executar agente

**Solução:**
```bash
# Verificar logs do Athena
tail -f logs/athena.log

# Verificar logs do Hermes
cd hermes_agents
python -c "from ag_09_memoria import stats; print(stats())"
```

## Próximos Passos

1. **Configurar Telegram Bot** - Para receber alertas em tempo real
2. **Integrar Marketplaces** - Conectar Shopee, Mercado Livre
3. **Configurar APIs** - Obter tokens de acesso
4. **Personalizar Thresholds** - Ajustar margens mínimas
5. **Automatizar** - Configurar cron jobs para execução automática

## Documentação Adicional

- [Documentação Hermes Agents](https://github.com/anthropics/hermes-agents)
- [API GraphQL Athena](http://localhost:4000/graphql)
- [Relatórios Consolidados](http://localhost:4000/api/hermes/stats)

## Suporte

Em caso de dúvidas ou problemas:
1. Verificar logs: `logs/athena.log`
2. Testar bridge: `cd hermes_agents && python athena_bridge.py`
3. Verificar saúde: `curl http://localhost:4000/api/health`

---

**Versão:** 1.0
**Última atualização:** 06/07/2026
**Status:** ✅ Integração completa e funcional