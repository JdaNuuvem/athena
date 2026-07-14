# PRD — Hermes Agent Swarm: Fábrica Inteligente

**Versão:** 1.0  
**Data:** 2026-07-05  
**Autor:** Diretoria de Produto  
**Plataforma:** Hermes Agent (Coolify)

---

## Visão Geral

Sistema multi-agente de inteligência artificial que opera como um diretor de operações digital para uma indústria de manufatura com vendas em marketplaces e 5 lojas físicas. Cada agente é especialista em um domínio, reporta ao Diretor de Inteligência, e juntos otimizam desde a descoberta de produtos até a entrega e pós-venda.

---

## Arquitetura

```
                    ┌──────────────────────────┐
                    │  🏆 Diretor de Inteligência │
                    │     (Orquestrador)         │
                    └──────────┬───────────────┘
           ┌───────────────────┼───────────────────┐
    ┌──────┴──────┐  ┌────────┴────────┐  ┌───────┴───────┐
    │  Descoberta  │  │    Finanças     │  │   Operações   │
    │  & Inovação  │  │  & Mercado      │  │  & Produção   │
    └──────┬───────┘  └────────┬────────┘  └───────┬───────┘
           │                   │                    │
    ┌──────┴──────┐    ┌──────┴──────┐     ┌───────┴───────┐
    │🚀 Caçador   │    │💰 Analista │     │📦 Planejador  │
    │  Produtos   │    │  Lucrativ. │     │  Produção     │
    └─────────────┘    └────────────┘     └───────────────┘
           │                   │                    │
    ┌──────┴──────┐    ┌──────┴──────┐     ┌───────┴───────┐
    │💡 Laborató- │    │📊 Gerente  │     │🏭 Gerente     │
    │  rio Prod.  │    │  Marketpl. │     │  Industrial   │
    └─────────────┘    └────────────┘     └───────────────┘
                                    │                    │
                            ┌──────┴──────┐     ┌───────┴───────┐
                            │🤖 Vendedor │     │📈 Analista    │
                            │  Telegram  │     │  Lojas Físicas│
                            └────────────┘     └───────────────┘
                                               ┌───────┴───────┐
                                               │📚 Memória     │
                                               │  Corporativa  │
                                               └───────────────┘
```

**Padrão de comunicação:** Todos os agentes se comunicam via fila de mensagens interna. O Diretor de Inteligência recebe reports sumarizados e pode interrogar qualquer agente sob demanda.

---

## Agentes

### 🏆 AG-10 | Diretor de Inteligência

| Campo | Valor |
|---|---|
| **Prioridade** | 10 (último a ser ativado, depende dos demais) |
| **Gatilho** | Mensagem do usuário (chat) |
| **Frequência** | On-demand + report diário 08:00 |
| **Entrada** | Pergunta em linguagem natural |
| **Processamento** | Roteia para agentes especialistas, consolida respostas |
| **Saída** | Resposta consolidada com recomendações acionáveis |
| **Fonte de dados** | Todos os demais agentes |

**Queries de exemplo:**
- "O que devemos fabricar esta semana?"
- "Qual produto devo lançar?"
- "Onde estamos perdendo dinheiro?"
- "Qual marketplace está dando mais lucro?"
- "Qual loja está performando pior?"
- "Qual molde não está se pagando?"

**Métricas de sucesso:**
- Tempo de resposta < 30s para consultas simples
- Precisão das recomendações > 85% (validado manualmente no primeiro mês)
- Cobertura de domínios: responde perguntas de qualquer área coberta pelos sub-agentes

---

### 🚀 AG-01 | Caçador de Produtos

| Campo | Valor |
|---|---|
| **Prioridade** | 🥇 1 |
| **Gatilho** | Agendado (diário 06:00) |
| **Frequência** | 1x/dia (varredura completa) + alertas em tempo real para tendências explosivas |
| **Entrada** | APIs/raspagem dos marketplaces |
| **Processamento** | Coleta, filtra por capacidade fabril, ranqueia por potencial |
| **Saída** | Top 10 produtos recomendados com ficha de viabilidade |
| **Fonte de dados** | Shopee, Mercado Livre, Amazon, Temu, TikTok Shop, Google Trends, Pinterest |

**Campos da ficha de produto:**
```yaml
- nome
- marketplace_origem
- url
- preco_medio
- volume_vendas_estimado
- concorrentes_diretos
- nivel_concorrencia (baixa/media/alta)
- fabricavel (sim/nao)
- complexidade_molde (1-10)
- custo_molde_estimado
- custo_producao_unitario
- margem_estimada (%)
- tempo_lancamento_dias
- tendencia (subindo/estavel/caindo)
- score_final (0-100)
```

**Métricas de sucesso:**
- 1 produto novo identificado por semana com margem > 40%
- Falsos positivos < 20% (produto sugerido que não vende)
- Tempo de varredura completa < 2h

---

### 💰 AG-02 | Analista de Lucratividade

| Campo | Valor |
|---|---|
| **Prioridade** | 🥈 2 |
| **Gatilho** | Agendado (diário 07:00) + on-demand |
| **Frequência** | 1x/dia + sob demanda do Diretor |
| **Entrada** | Dados de vendas, custos, taxas |
| **Processamento** | Calcula lucro real por SKU descontando todos os custos |
| **Saída** | Ranking de lucratividade por SKU, alertas de produtos deficitários |
| **Fonte de dados** | Planilhas de custo de produção, taxas dos marketplaces, planilhas de frete, impostos (integração com ERP) |

**Cálculo de lucro real:**
```
lucro_real = receita_bruta 
  - custo_materia_prima 
  - custo_mao_obra 
  - taxa_marketplace (%) 
  - frete 
  - impostos 
  - custo_embalagem 
  - rateio_custo_fixo
```

**Métricas de sucesso:**
- Identificar SKUs com margem negativa em até 24h
- Precisão do cálculo de lucro vs. contabilidade real com erro < 5%
- Relatório diário com top 10 e bottom 10 produtos por lucratividade

---

### 📦 AG-04 | Planejador de Produção

| Campo | Valor |
|---|---|
| **Prioridade** | 4 |
| **Gatilho** | Agendado (diário 07:30) + evento (novo pedido) |
| **Frequência** | 1x/dia + reagendamento em tempo real com novos pedidos |
| **Entrada** | Pedidos pendentes, estoque atual, capacidade das máquinas |
| **Processamento** | Algoritmo de sequenciamento otimizado |
| **Saída** | Plano de produção diário ordenado por prioridade |
| **Fonte de dados** | Sistema de pedidos, controle de estoque, cadastro de máquinas e moldes |

**Algoritmo de priorização:**
```
score = (prazo_urgencia * 0.4) 
      + (margem_produto * 0.3) 
      + (cliente_tipo * 0.2) 
      + (tempo_setup * 0.1)
```

**Restrições consideradas:**
- Capacidade de cada máquina (horas/dia)
- Disponibilidade de molde
- Tempo de setup entre produtos diferentes
- Estoque de matéria-prima
- Prazos de entrega

**Métricas de sucesso:**
- Redução de 20% no tempo ocioso das máquinas
- Aderência ao plano > 80%
- Zero rupturas de estoque por falha de planejamento

---

### 📊 AG-05 | Gerente de Marketplaces

| Campo | Valor |
|---|---|
| **Prioridade** | 🥉 3 |
| **Gatilho** | Agendado (a cada 4h) + eventos de concorrência |
| **Frequência** | 6x/dia |
| **Entrada** | Dados dos anúncios ativos, preços dos concorrentes, avaliações |
| **Processamento** | Monitoramento contínuo + análise de SEO + sugestões de otimização |
| **Saída** | Alertas de mudança de posição, sugestões de melhoria de anúncios, ajustes de preço |
| **Fonte de dados** | APIs dos marketplaces, análise de concorrentes |

**Ações automatizáveis:**
- Alerta: concorrente baixou preço em produto seu
- Sugestão: novo título com keyword de alta busca
- Sugestão: criação de kit (produto A + produto B)
- Alerta: anúncio caiu de posição
- Sugestão: ajuste de preço baseado em elasticidade

**Métricas de sucesso:**
- Aumento de 15% no CTR dos anúncios
- Melhora de 10% na posição média dos anúncios
- Tempo de reação a mudança de preço do concorrente < 4h

---

### 🤖 AG-06 | Vendedor do Telegram

| Campo | Valor |
|---|---|
| **Prioridade** | 5 |
| **Gatilho** | Mensagem recebida no Telegram |
| **Frequência** | Em tempo real (24/7) |
| **Entrada** | Mensagem do cliente no Telegram |
| **Processamento** | NLP para intenção + roteamento + integração com catálogo e pedidos |
| **Saída** | Resposta personalizada, recomendação de produto, pedido gerado |
| **Fonte de dados** | Catálogo de produtos, histórico de pedidos do cliente, tabela de preços (atacado/varejo), sistema de pedidos |

**Fluxo de conversa:**
1. Identificar se o cliente é novo ou recorrente
2. Classificar: atacado ou varejo (baseado em volume perguntado ou histórico)
3. Recomendar produtos complementares (upsell/cross-sell)
4. Calcular desconto progressivo
5. Gerar link de pagamento ou pedido
6. Acompanhar status do pagamento
7. Pós-venda (avaliação, recompra)

**Métricas de sucesso:**
- Taxa de conversão > 15%
- Aumento de 20% no ticket médio via upsell
- Tempo de primeira resposta < 10s
- Automação de > 70% dos atendimentos sem intervenção humana

---

### 🏭 AG-07 | Gerente Industrial

| Campo | Valor |
|---|---|
| **Prioridade** | 6 |
| **Gatilho** | Agendado (a cada 30min) |
| **Frequência** | 48x/dia (quase tempo real) |
| **Entrada** | Sensores de máquina, relatórios de produção, consumo de ferramentas |
| **Processamento** | Análise de desvios, detecção de anomalias, previsão de falhas |
| **Saída** | Alertas de gargalos, previsão de troca de ferramentas, relatório de OEE |
| **Fonte de dados** | CNC (tempo de ciclo, paradas), controle de moldes (ciclos restantes), controle de estoque de matéria-prima, consumo de ferramentas |

**Monitoramento:**
- OEE (Overall Equipment Effectiveness) por máquina
- Ciclos restantes do molde (alerta quando < 20%)
- Consumo anômalo de ferramenta
- Desvio de tempo de ciclo padrão
- Estoque de matéria-prima abaixo do ponto de reposição

**Métricas de sucesso:**
- Redução de 15% em paradas não planejadas
- Previsão de troca de ferramenta com 48h de antecedência
- Aumento de 10% no OEE

---

### 📈 AG-08 | Analista das Lojas Físicas

| Campo | Valor |
|---|---|
| **Prioridade** | 8 |
| **Gatilho** | Agendado (diário 08:00) |
| **Frequência** | 1x/dia |
| **Entrada** | Dados de PDV das 5 lojas |
| **Processamento** | Comparação entre lojas, identificação de padrões, sugestões de redistribuição |
| **Saída** | Ranking das lojas, sugestões de transferência de estoque, promoções por loja |
| **Fonte de dados** | Sistema PDV de cada loja |

**Análise por loja:**
```yaml
- loja_id
- faturamento_dia
- ticket_medio
- taxa_conversao
- produtos_top5
- produtos_encalhados
- giro_estoque
- rupturas
- horario_pico
- comparativo_vs_media (acima/abaixo)
```

**Sugestões geradas:**
- Transferir SKU X da loja A para loja B (gira mais lá)
- Criar promoção relâmpago na loja C (estoque parado)
- Reforçar equipe no horário Y na loja D (pico de movimento)

**Métricas de sucesso:**
- Redução de 25% em rupturas de estoque
- Redução de 15% em estoque parado
- Aumento de 5% no ticket médio com promoções direcionadas

---

### 💡 AG-09 | Laboratório de Produtos

| Campo | Valor |
|---|---|
| **Prioridade** | 7 |
| **Gatilho** | Sob demanda (nova ideia de produto) + batch semanal |
| **Frequência** | On-demand + 1x/semana |
| **Entrada** | Ideia de produto (do Caçador ou humana) |
| **Processamento** | Calcula viabilidade completa cruzando dados de produção, mercado e finanças |
| **Saída** | Pipeline priorizado de lançamentos com score de viabilidade |
| **Fonte de dados** | Memória Corporativa (moldes existentes, custos históricos), Caçador de Produtos (tendências), Analista de Lucratividade (margens simuladas) |

**Ficha de viabilidade completa:**
```yaml
- nome_produto
- descricao
- investimento_total
- custo_molde
- tempo_desenvolvimento_dias
- custo_producao_unitario
- preco_venda_sugerido
- margem_estimada
- volume_vendas_projetado_mes
- payback_meses
- risco (1-10)
- score_final (0-100)
```

**Pipeline:**
- 🔥 Em análise (ideias novas)
- 🧪 Prototipagem (aprovado, molde em produção)
- 🏭 Pré-lançamento (molde pronto, produzindo lote piloto)
- 🚀 Lançamento (já no marketplace)

**Métricas de sucesso:**
- Taxa de acerto > 60% (produto lançado atinge margem projetada)
- Tempo médio ideação → lançamento reduzido em 30%
- Payback médio < 3 meses

---

### 📚 AG-10 | Memória Corporativa

| Campo | Valor |
|---|---|
| **Prioridade** | 9 |
| **Gatilho** | Sob demanda (consultas de outros agentes) |
| **Frequência** | On-demand |
| **Entrada** | Query de qualquer agente ou humano |
| **Processamento** | RAG sobre base de conhecimento da empresa |
| **Saída** | Documento, ficha técnica, histórico, contato de fornecedor |
| **Fonte de dados** | Catálogo de moldes, fichas técnicas, desenhos CAD, histórico de custos, cadastro de fornecedores, documentação de processos, histórico de problemas resolvidos |

**Base de conhecimento indexada:**
- Todos os moldes (código, produto, material, ciclos, custo)
- Fichas técnicas de cada SKU
- Desenhos técnicos
- Histórico de custos por produto/período
- Fornecedores (matéria-prima, ferramentas, serviços)
- Processos operacionais documentados
- Registro de problemas e soluções (FAQ técnica)

**Queries de exemplo:**
- "Já fabricamos algo parecido com isso?"
- "Qual molde usamos para o produto X?"
- "Quem é o fornecedor mais barato da matéria-prima Y?"
- "Quanto custava produzir o produto Z em 2025?"

**Métricas de sucesso:**
- Tempo de resposta < 5s para consultas indexadas
- Cobertura > 90% do catálogo de moldes cadastrado
- Zero perda de conhecimento quando um funcionário sai

---

## Roadmap de Implementação

### Fase 1 — Fundação (Semanas 1-4)

| Semana | Entregável |
|---|---|
| 1 | Infraestrutura base no Hermes Agent + Memória Corporativa (AG-09) |
| 2 | Caçador de Produtos (AG-01) — integração com 3 marketplaces |
| 3 | Analista de Lucratividade (AG-02) — modelo de cálculo de margem real |
| 4 | Gerente de Marketplaces (AG-03) — monitoramento e alertas |

**Go live Fase 1:** Agentes 01, 02, 03, 09 operando.

### Fase 2 — Produção (Semanas 5-8)

| Semana | Entregável |
|---|---|
| 5 | Planejador de Produção (AG-04) |
| 6 | Gerente Industrial (AG-06) — integração com CNC |
| 7 | Vendedor do Telegram (AG-05) |
| 8 | Laboratório de Produtos (AG-07) |

**Go live Fase 2:** Todos os agentes operacionais ativos.

### Fase 3 — Inteligência (Semanas 9-10)

| Semana | Entregável |
|---|---|
| 9 | Analista das Lojas Físicas (AG-08) |
| 10 | Diretor de Inteligência (AG-10) + integração total |

**Go live Fase 3:** Sistema completo. Diretor de Inteligência orquestrando todos os agentes.

---

## Requisitos Técnicos

### Infraestrutura

| Componente | Especificação |
|---|---|
| **Orquestração** | Hermes Agent (já provisionado no Coolify) |
| **LLM Principal** | Claude (Anthropic) via API — já configurado |
| **LLM Auxiliar** | OpenAI / OpenRouter — já configurados |
| **Banco de dados** | PostgreSQL (já provisionado no Coolify) |
| **Cache / fila** | Redis (já provisionado no Coolify) |
| **Storage** | Volume persistente no servidor |
| **Webserver** | Hermes WebUI (já rodando) |

### Integrações Externas Necessárias

| Sistema | Tipo | Status |
|---|---|---|
| Shopee API | Marketplace | A implementar |
| Mercado Livre API | Marketplace | A implementar |
| Amazon SP-API | Marketplace | A implementar |
| Telegram Bot API | Mensageria | A implementar |
| Google Trends API | Pesquisa | A implementar |
| Sistema PDV (lojas) | ERP | A implementar |
| Controle de produção/CNC | ERP | A implementar |

### Estrutura de Dados

Cada agente mantém seu próprio schema no PostgreSQL:

```
ag_01_cacador/
  ├── produtos_descobertos
  ├── tendencias
  └── alertas

ag_02_lucratividade/
  ├── custos_sku
  ├── margens_diarias
  └── alertas_deficit

ag_03_marketplaces/
  ├── posicao_anuncios
  ├── precos_concorrentes
  └── sugestoes_otimizacao

... (demais agentes seguem o mesmo padrão)

ag_09_memoria/
  ├── moldes
  ├── fichas_tecnicas
  ├── fornecedores
  └── historico_problemas
```

---

## Métricas de Sucesso Globais

| Indicador | Alvo | Prazo |
|---|---|---|
| Agentes operacionais ativos | 10/10 | Semana 10 |
| Uptime do sistema | 99.5% | Contínuo |
| Tempo médio de resposta do Diretor | < 30s | Semana 10 |
| Novos produtos lançados via Caçador | 4/mês | A partir do mês 2 |
| Redução de produtos deficitários | 50% | Mês 3 |
| Aumento de receita via marketplaces | 20% | Mês 3 |
| Redução de tempo ocioso de máquinas | 20% | Mês 3 |
| Automação de atendimento Telegram | 70% | Mês 2 |
| Redução de rupturas em lojas físicas | 25% | Mês 3 |

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| APIs dos marketplaces mudam/limitam acesso | Média | Alto | Monitoramento de changelogs + fallback para raspagem |
| Dados de produção/CNC não estruturados | Alta | Alto | Fase 1 inclui normalização de dados antes da automação |
| Resistência da equipe à adoção | Média | Médio | Interface simples (chat) + resultados rápidos na Fase 1 |
| Custo de API LLM elevado | Média | Médio | Cache agressivo de respostas + batch de consultas |
| Qualidade dos dados de entrada é baixa | Alta | Alto | Agente de Memória Corporativa como primeiro entregável |
