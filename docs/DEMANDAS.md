# Demandas

Backlog de features/telas pendentes de planejamento, organizado por mês de registro.

## Agosto 2026

### Custos de Estoque (`/estoque/custos`)

Stub vazio ("Em construção"), sem lógica nem dados — criado antes da reforma do módulo de Estoque (ver critique `.impeccable/critique/2026-08-07T20-47-22Z__web-src-app-estoque-page-tsx.md`) e mantido fora do menu de navegação até ter escopo definido.

Registrado em 2026-08-07, durante a reforma do módulo de Estoque (dados fabricados em Depósitos/Inventário sendo removidos/conectados). Custos ficou de fora dessa rodada — decisão do usuário foi documentar como demanda futura em vez de remover ou implementar agora.

**Ainda não definido:** o que a tela deve mostrar (custo médio por SKU? custo de manutenção de estoque parado? custo por depósito?), fonte de dado, e se depende de alguma das outras frentes da reforma de Estoque.

### Card "Agentes" na Dashboard (`/dashboard`)

`GET /api/agents` (`hermes_agents/athena_bridge.py:437-457`) devolve uma lista 100% hardcoded no código Python — 14 agentes com `status`/`taskCount` fixos, nunca lê banco nenhum. O card nunca reflete estado real do sistema.

Registrado em 2026-08-09, durante investigação de "dashboard com dados desatualizados" (`vamos fazer a aba do hermes agent funcionar agora` / verificação completa da dashboard). Decisão do usuário foi documentar como demanda futura em vez de corrigir na hora — não é troca simples de fonte de dado, é definir a métrica primeiro.

**Ainda não definido:** o que "status real" significa por agente (está rodando agora? processou algo hoje? teve erro na última execução?), e de onde viria esse dado (log de execução? heartbeat? tabela de jobs do scheduler?).

### Seção "Alertas" na Dashboard (`/dashboard`)

`web/src/app/dashboard/page.tsx` seta `dash.alertas = []` direto no código, dentro do `.then()` do fetch principal — nunca chama nenhuma API. A seção (`dash.alertas.length > 0`) nunca renderiza, por construção atual do código, não por dado vazio.

Registrado em 2026-08-09, mesma investigação do item acima.

**Ainda não definido:** o que conta como "alerta" no produto (ruptura de estoque? conta a vencer/vencida? erro de sincronização de canal — Shopee, i9Logic, Bling? divergência de saldo não resolvida?), e se agrega várias fontes ou é dedicado a uma métrica só.

### Investigar timezone real do Postgres de produção (possível bug de data em pedidos Shopee)

`shopee_sync.py:295` grava `create_time`/`update_time` do pedido Shopee via `to_timestamp($N::bigint)` numa coluna `TIMESTAMP` **sem timezone** (`shopee_pedidos_sincronizados.create_time`). O Postgres converte o instante UTC pro fuso configurado na *sessão* na hora de gravar. Se a sessão rodar em UTC (comum em container Docker/Coolify sem configuração explícita) enquanto o negócio opera em horário de Brasília (UTC-3), pedidos feitos depois de ~21h local viram "dia seguinte" quando `core/vendas.py:478` faz `.date()` nesse valor pra popular `vendas_pedidos.data` — a mesma coluna usada pelos 4 fixes de dashboard de 2026-08-09 (Vendas do mês, Vendas hoje, etc). Se o bug for real, afeta a data de venda Shopee em todo relatório do app, não só a tela `/integracoes/shopee/dashboard` que motivou a investigação (usuário reportou "gráfico não conta os dias corretamente", confirmou que a tela mostra dado mas com datas erradas — consistente com deslocamento de fuso).

Registrado em 2026-08-09. **Não corrigido** porque não há como confirmar o fuso real da sessão Postgres sem acesso a produção — nenhuma configuração explícita de timezone existe no código (`grep` por `SET TIME ZONE`/`TimeZone` não encontrou nada), o repo não versiona a config do serviço Postgres (roda separado no Coolify), e não há endpoint de diagnóstico que exponha isso hoje. Tentativa de login via API pra comparar timestamp do banco contra horário real falhou (usuário só tinha credencial do painel Coolify, não do login do Athena).

**Risco de corrigir às cegas:** se a sessão já rodar em `America/Sao_Paulo` (bem possível, é prática comum configurar isso em app brasileiro), aplicar uma conversão explícita de fuso no código deslocaria a data numa segunda vez, na direção errada — trocando um bug inexistente por um novo.

**Para resolver:** confirmar o fuso real de uma destas formas — (a) `SHOW timezone;` direto no Postgres de produção; (b) checar env var `TZ`/`PGTZ` do serviço Postgres no Coolify; (c) login válido no Athena (não o do Coolify) pra comparar via API um timestamp gravado agora contra o horário real. Uma vez confirmado: se UTC, corrigir `shopee_sync.py` (e conferir `core/pdv.py`, `core/i9logic_vendas.py` e qualquer outro writer de timestamp Shopee/vendas pelo mesmo padrão) pra converter explicitamente pra `America/Sao_Paulo` antes de gravar; se já for Brasília, o bug de "datas erradas" tem outra causa raiz, precisa investigar de novo.
