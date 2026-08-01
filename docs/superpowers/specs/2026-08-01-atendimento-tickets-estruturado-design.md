# Atendimento — Tickets Estruturado (Fase 1) — Design

Data: 2026-08-01

## Contexto

A tela `/atendimento/tickets` hoje é um scaffold genérico de CRUD (mesmo template usado em `sla/page.tsx`, `canais/page.tsx`, `crm/negociacoes`, `compras/pedidos`): tabela HTML crua, formulário inline só com criar/apagar, campos como `status` e `prioridade` são `<input type="text">` livres, sem dropdown, sem badge colorido, sem filtro, sem busca, sem paginação. Não existe tela de detalhe (`/atendimento/tickets/[id]`), não existe edição, atribuição de atendente, mudança de status via ação dedicada, nem visualização de mensagens — apesar do backend já ter boa parte dessa infraestrutura pronta (criação com cálculo de SLA, fechar/reabrir, mensagens vinculadas a uma conversa de chat, broadcast via WebSocket) e simplesmente não ser consumida pelo frontend.

Este documento também corrige um bug real encontrado durante o levantamento: mensagens de ticket disparam **dois broadcasts WebSocket com payloads inconsistentes entre si** (um shape em `core/atendimento.py:adicionar_mensagem`, outro em `routes/chat.py`), e mudança de status/atribuição de atendente não dispara nenhum evento WS hoje.

Nota de relação com spec anterior: `docs/superpowers/specs/2026-07-28-chat-interno-fase1-design.md` já previa, na sua Fase 3 futura, "ticket avançado (SLA, categoria, checklist, escalonamento)" e "central de notificações". Este documento adianta e implementa a fatia de ticket avançado + notificação (versão mínima) referente a atribuição/status/mensagens — categoria, checklist e escalonamento continuam fora de escopo.

## Decomposição do projeto maior

- **Fase 1 (este documento):** tela de tickets estruturada — CRUD completo (criar/editar/atribuir/mudar status), tela de detalhe com thread de mensagens e anexo, filtros/busca/tabs/badges na listagem, WebSocket ao vivo corrigido e estendido (mensagem, status, atribuição), sino de notificação genérico (gatilho único: "ticket atribuído a você").
- **Fase 2 (futura, spec própria):** pipeline automático de canal — WhatsApp/Shopee criando ticket sozinho ao chegar mensagem.
- **Fase 3 (futura, spec própria):** vínculo de `cliente` do ticket com contato/lead real do CRM.
- **Fora de qualquer fase por ora (YAGNI, sem uso claro hoje):** categoria/assunto estruturado, checklist, escalonamento automático, fila com distribuição round-robin, ações em lote na listagem, alerta proativo de SLA (cron/job), tempo real em PDV/dashboard.

## Arquitetura

Sem framework novo. Backend continua Flask + `asyncpg` (padrão `get_db()`/`run_async()` já usado em todo o projeto). Frontend reescreve a tela do zero seguindo o padrão maduro já usado em `/vendas` (366 linhas, componentes `PageHeader`/`KpiCard`/`StatusBadge`/`DataTable`/`Can`/`DateFilter`) em vez de estender o scaffold genérico atual — o scaffold não comporta edição/atribuição/filtros sem reescrita da mesma ordem de grandeza.

WebSocket reaproveita a infraestrutura existente (`flask-sock`, endpoint único `/ws/chat`, registro de conexões em memória por processo, mesma limitação já documentada em `2026-07-28-chat-interno-fase1-design.md` de não escalar para múltiplas instâncias sem Redis — aceito, mesmo motivo: processo único hoje).

## Modelo de dados

Migração em `atend_tickets` (via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, padrão já usado no projeto para não quebrar produção):

```sql
ALTER TABLE atend_tickets RENAME COLUMN atendente TO atendente_nome_legado; -- só leitura, preserva histórico
ALTER TABLE atend_tickets ADD COLUMN IF NOT EXISTS atendente_id INT REFERENCES rbac_usuarios(id);
```

`numero` passa a ser preenchido em `criar_ticket()` via sequence dedicada (`atend_tickets_numero_seq`), formato `#0001`.

`status` ganha o valor real `pendente` (hoje só `aberto`/`fechado` são de fato gerenciados por código). Máquina de estado:

```
aberto ⇄ pendente → fechado
  ↑___________________|  (reabrir volta sempre para 'aberto')
```

Tabela nova para o sino de notificação:

```sql
CREATE TABLE IF NOT EXISTS notificacoes (
  id SERIAL PRIMARY KEY,
  usuario_id INT REFERENCES rbac_usuarios(id) NOT NULL,
  tipo VARCHAR(50) NOT NULL,       -- 'ticket_atribuido' (único tipo emitido nesta fase)
  titulo VARCHAR(150) NOT NULL,
  mensagem TEXT,
  link VARCHAR(300),
  lida BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Backend — endpoints novos

Todos em `hermes_agents/routes/atendimento.py`, reaproveitando `requer_permissao`:

- `PUT /api/atendimento/tickets/<id>/atribuir` `{atendente_id}` — permissão `atendimento.editar`. Valida que `atendente_id` existe em `rbac_usuarios`. Grava, dispara broadcast `ticket_atendente_alterado` + grava notificação + envia frame direto ao atendente designado.
- `PUT /api/atendimento/tickets/<id>/status` `{status}` — permissão `atendimento.editar`. Valida transição contra a máquina de estado acima (rejeita `fechado → pendente` direto, por exemplo). Mantém `fechar`/`reabrir` como aliases internos (não remove, evita quebrar quem já os chama). Dispara broadcast `ticket_status_alterado`.
- `GET /api/atendimento/tickets/<id>/mensagens` — permissão `atendimento.ver`. Expõe via REST o que hoje só existe como função Python (`listar_mensagens_ticket`).
- `POST /api/atendimento/tickets/<id>/anexo` — permissão `atendimento.editar`. Multipart upload, mesmo padrão de `lojasMidiaUpload`/`chat_anexos`. Grava em `atend_mensagens.anexo_url`, emite `nova_mensagem` normal (mensagem tipo "anexo").
- `GET /api/atendimento/tickets` ganha filtros via query string: `?status=&prioridade=&canal=&atendente_id=&q=&de=&ate=`. Sem paginação server-side nova nesta fase — volume atual não justifica; se crescer, entra depois.
- `GET /api/notificacoes`, `POST /api/notificacoes/<id>/lida`, `POST /api/notificacoes/marcar-todas-lidas` — novo blueprint pequeno, sem permissão especial além de estar autenticado (notificação é por usuário, não por módulo).

## Backend — correção do bug de WebSocket

`core/atendimento.py:adicionar_mensagem` passa a emitir **um único** broadcast, já no shape usado pelo chat (`conversa_id`, `texto`, `remetente_id`, `created_at`) em vez do shape cru de `atend_mensagens` (`ticket_id`, `conteudo`, `remetente`, `enviado_em`). `routes/chat.py` deixa de emitir um segundo broadcast quando a mensagem já veio de uma conversa tipo `ticket` (a emissão de dentro de `adicionar_mensagem` passa a ser a única fonte). Isso elimina tanto a duplicidade quanto o risco de uma tela nova perder mensagens ao filtrar por `conversa_id` (frame antigo não carregava esse campo).

## Frontend — Listagem `/atendimento/tickets`

- `PageHeader` + botão "+ Novo Ticket" dentro de `<Can permission="atendimento.criar">`.
- Tabs de status (padrão `/vendas`): `Todos | Aberto | Pendente | Fechado`, contagem por tab.
- Filtros: prioridade, canal, atendente (select populado por `rbac_usuarios`), busca livre (cliente/assunto/número), `DateFilter` por período de abertura — via query params do endpoint filtrado acima.
- Tabela via `DataTable`: Número, Cliente, Assunto, Canal, Prioridade (badge), Status (badge), Atendente, SLA (badge "No prazo"/"Vencido"), Aberto em. Linha inteira clicável → `/atendimento/tickets/[id]`.
- Modal "Novo Ticket" (estilo `/vendas`): cliente, email, telefone, assunto, canal (select), prioridade (select). Sem status/atendente na criação (sempre nasce "aberto", sem atendente).
- Sem ações em lote nesta fase.

## Frontend — Detalhe `/atendimento/tickets/[id]`

Duas colunas:

**Esquerda (thread de mensagens):** header com número/assunto/cliente/badges; lista de mensagens estilo bolha de chat (visual reaproveitado de `/chat`), cada uma podendo ter anexo clicável; campo de envio no rodapé (texto + anexo), dentro de `<Can permission="atendimento.editar">`.

**Direita (painel de controle):**
- Status: botões de transição válida conforme estado atual, chamando `PUT /tickets/<id>/status`.
- Atendente: select de usuários RBAC, chamando `PUT /tickets/<id>/atribuir`.
- SLA: prazo e indicador de atraso.
- Dados do cliente (somente leitura: email, telefone, canal).
- Metadados: aberto em, fechado em, tempo de resposta.
- Botão "Editar" abre modal pré-preenchido reaproveitando o `PUT /api/atendimento/tickets/<id>` genérico já existente.

## WebSocket ao vivo

Tela de detalhe reaproveita `useChatSocket` (mesmo hook do `/chat`, sem duplicar conexão/reconexão). Escuta 3 eventos e atualiza estado local sem refetch completo:
- `nova_mensagem` (shape normalizado, ver correção acima) → apenda na thread se `conversa_id` bater.
- `ticket_status_alterado` `{ticket_id, status, conversa_id}` → atualiza badge de status.
- `ticket_atendente_alterado` `{ticket_id, atendente_id, atendente_nome, conversa_id}` → atualiza painel de atendente.

Ações continuam via REST (fonte de verdade); WS só propaga para quem está com a tela aberta. Sem fila/replay se desconectado — ao reconectar, o hook não faz refetch automático; a tela de detalhe faz um refetch único ao montar/focar, cobrindo o caso comum.

## Sino de notificação genérico

Componente `NotificationBell` no layout principal (sidebar), badge de contador de não lidas, dropdown de lista, escuta evento `notificacao` via `useChatSocket`. Único gatilho ativo nesta fase: atribuição de ticket a um usuário (emitido de dentro de `PUT /tickets/<id>/atribuir`, ver acima). Infraestrutura (tabela, endpoints REST, componente, evento WS) é genérica e reaproveitável por outros módulos no futuro — não é exclusiva de tickets, mas nenhum outro gatilho é adicionado nesta fase.

## Permissões (RBAC)

Reaproveita as 4 permissões já existentes do módulo, sem criar novas:

| Ação | Permissão |
|---|---|
| Ver lista/detalhe, ler mensagens | `atendimento.ver` |
| Criar ticket | `atendimento.criar` |
| Editar campos, mudar status, atribuir, enviar mensagem/anexo | `atendimento.editar` |
| Excluir ticket | `atendimento.excluir` |

Todo botão sensível envolvido em `<Can permission="...">`. Notificações são por usuário autenticado, sem permissão extra.

## Testes

**Backend** (`pytest`, seguindo `hermes_agents/tests/test_atendimento_*.py`):
- `test_atendimento_tickets_endpoints.py`: `status` valida transições permitidas/rejeitadas; `atribuir` grava `atendente_id` e rejeita usuário inexistente; `mensagens` retorna ordenado; `anexo` rejeita sem permissão.
- `test_atendimento_ws.py`: `adicionar_mensagem` emite exatamente 1 broadcast (regressão do bug de double-broadcast) com shape normalizado; `atribuir`/`status` emitem os eventos novos; notificação gravada e `enviar_para_usuario` chamado com o `atendente_id` correto (não broadcast geral).
- `test_notificacoes.py`: listar retorna não lidas primeiro; marcar lida é idempotente.

**Frontend** (Playwright, confirmar convenção de diretório de teste e2e existente antes de criar arquivo novo):
- Fluxo: criar ticket → aparece na lista "Aberto" → abrir detalhe → atribuir a si mesmo → status "Pendente" → enviar mensagem → aparece na thread → fechar → sai de "Aberto", aparece em "Fechado".
- WS ao vivo: duas abas no mesmo ticket, mudar status na aba 1, confirmar atualização na aba 2 sem F5.
