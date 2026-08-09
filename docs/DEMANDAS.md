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
