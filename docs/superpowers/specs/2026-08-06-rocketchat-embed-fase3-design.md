# Rocket.Chat — Embed em /chat (Fase 3) — Design

Data: 2026-08-06

## Contexto

Fase 1+2 (`docs/superpowers/specs/2026-08-03-rocketchat-infra-sso-design.md`) entregou o Docker Compose do Rocket.Chat + MongoDB (`deploy/rocketchat/`) e o Identity Provider OAuth2 do Hermes (`hermes_agents/routes/oauth_provider.py`, `/oauth/authorize|token|userinfo`) — mas **o recurso nunca foi provisionado em produção**: `chat.athena.zoikom.site` não resolve DNS. Os commits de bugfix da Fase 1+2 (401, key_field, porta) foram testados fora de um deploy real no Coolify.

O `/chat` atual continua sendo o chat interno próprio (`hermes_agents/routes/chat.py`, `chat_ws.py`, `core/chat.py`, componentes React em `web/src/app/chat/_components/`) — funcional (DM/grupo/canal/thread/menções/anexos/presença) mas sem lib de UI, sem emoji picker, sem preview de mídia, sem virtualização de lista, e com WebSocket em memória de processo único (não escala horizontalmente).

Decisão confirmada nesta sessão: terminar a migração para Rocket.Chat em vez de lapidar o chat custom.

## Decomposição do projeto maior

Reafirma a decomposição da Fase 1+2:
- Fase 1+2 (concluída em código, **infra nunca subiu**): provisionar + SSO.
- **Fase 3 (este documento):** subir a infra de verdade, validar SSO ponta a ponta em produção, embutir o Rocket.Chat via iframe em `/chat`.
- Fase 4: migrar histórico de `chat_conversas`/`chat_mensagens` para o Rocket.Chat.
- Fase 5: religar chat↔ticket (`chat_conversas.tipo='ticket'` ↔ `atend_tickets`) via webhook/API do Rocket.Chat.
- Fase 6: descomissionar o código antigo do chat interno.

Fases 4, 5 e 6 continuam fora de escopo aqui — decisão explícita desta sessão de não misturar infra nova com migração de dados na mesma entrega. A página de ticket (`/atendimento/tickets/[id]`) não é tocada por esta fase.

## Arquitetura

Três passos, nesta ordem — cada um é pré-condição do próximo:

1. **Provisionar infra de verdade.** Subir o recurso "Docker Compose" no Coolify a partir de `deploy/rocketchat/docker-compose.yml` (já versionado), configurar as env vars conforme `deploy/rocketchat/.env.example` e `README.md`, apontar DNS `chat.athena.zoikom.site` para a porta 3000 do serviço `rocketchat`, e configurar `ROCKETCHAT_OAUTH_CLIENT_ID`/`ROCKETCHAT_OAUTH_CLIENT_SECRET`/`ROCKETCHAT_OAUTH_REDIRECT_URI`/`HERMES_LOGIN_URL` no serviço Flask do Hermes no mesmo Coolify.
2. **Validar SSO ponta a ponta em produção** (Task 5 do plano de Fase 1+2, nunca executado): completar o wizard de setup do Rocket.Chat, confirmar que o botão "Hermes" aparece na tela de login, logar via SSO e confirmar que a conta é criada por just-in-time provisioning com `email`/`name`/`username` corretos vindos de `rbac_usuarios`.
3. **Só então**, trocar o conteúdo de `web/src/app/chat/page.tsx` pelo embed.

Se o passo 2 falhar, o passo 3 não avança — infra e SSO quebrados não devem ser mascarados por um iframe.

## Componentes

1. **`web/src/app/chat/page.tsx` (reescrito)** — perde toda a lógica de sidebar/mensagens/WebSocket (fica órfã até a Fase 6). Vira: checagem de saúde do Rocket.Chat + iframe, mantendo o wrapper `h-screen` já usado hoje (consistente com o restante do app, ver `web/src/app/layout.tsx`).
2. **`NEXT_PUBLIC_ROCKETCHAT_URL`** — env var nova no frontend (ex.: `https://chat.athena.zoikom.site`), sem necessidade de rota de backend nova.
3. **Componente de status** (`web/src/app/chat/_components/RocketChatFrame.tsx`, novo) — states: `carregando` (spinner no estilo visual do Athena), `indisponivel` (mensagem + botão "Tentar novamente", quando o health check falha) e `pronto` (renderiza o `<iframe>`).
4. **Configuração de embed no Rocket.Chat** — `?layout=embedded` na URL do iframe (recurso nativo do Rocket.Chat que esconde o header/sidebar dele, evitando navegação duplicada com o menu do Athena) e ajuste de permissão de enframe (Administração → Layout → Iframe Integration, ou env var equivalente no `docker-compose.yml` — nome exato do campo confirmado durante a implementação, contra a versão 8.6.1 já fixada na imagem).
5. **Atributos do iframe** — `allow="camera; microphone; display-capture; clipboard-write"`, para suportar chamada de voz/vídeo nativa do Rocket.Chat (parte do "completo estilo WhatsApp Web" pedido) sem escrever nada disso à mão.

Componentes velhos do chat custom (`ConversaSidebar.tsx`, `MensagensPainel.tsx`, `NovaConversaModal.tsx`, `ThreadPainel.tsx`, `MencaoAutocomplete.tsx`) **não são apagados** nesta fase — ficam sem uso até a Fase 6, para permitir rollback rápido revertendo só o `page.tsx` caso o embed tenha problema em produção.

## Fluxo de dados

Usuário clica em "Chat" no menu do Athena → `/chat` faz `fetch` em `NEXT_PUBLIC_ROCKETCHAT_URL/api/v1/info` (endpoint público de saúde do Rocket.Chat, sem autenticação) → sucesso: monta `<iframe src="NEXT_PUBLIC_ROCKETCHAT_URL?layout=embedded">` → dentro do iframe, Rocket.Chat mostra sua própria tela de login compacta com um botão "Hermes" → usuário clica (uma vez por navegador/dispositivo; sessão do Rocket.Chat persiste depois) → redirect completo dentro do iframe (`login_style: redirect`, já configurado, evita popup bloqueado por iframe) → `/oauth/authorize` no Hermes valida a sessão já existente do usuário → aprova → Rocket.Chat troca `code` por `access_token` e busca `/oauth/userinfo` → cria/atualiza conta → usuário vê o chat, dentro do layout do Athena.

## Erros

- **Health check falha** (Rocket.Chat/MongoDB fora do ar, ou DNS ainda não propagado): mostra estado `indisponivel` no lugar do iframe, com retry manual. Não deixa o iframe carregar sozinho uma página de erro do navegador.
- **Sessão do Hermes expirada exatamente durante o handshake OAuth**: comportamento inalterado em relação à Fase 1+2 — Rocket.Chat redireciona para `/login` do Hermes sem retomar o fluxo sozinho. Decisão explícita desta sessão: manter como limitação conhecida (caso raro — para chegar em `/chat` o usuário já tinha sessão válida); não implementar suporte a `next=` agora.
- **Enframe bloqueado pela config do Rocket.Chat**: se o ajuste de Iframe Integration não estiver correto, o navegador recusa renderizar o iframe (erro de console, área em branco). Coberto pelo smoke test do passo 2/3, não por teste automatizado (é config de infra, não lógica de aplicação).

## Testes

Sem lógica de backend nova — o SSO já é coberto pelos testes de `hermes_agents/tests/` da Fase 1+2. O trabalho novo é infra (não testável via pytest) e um componente de frontend fino. Verificação:
- Smoke test manual ponta a ponta em produção: subir infra → validar SSO (passo 2) → validar embed carrega, login funciona dentro do iframe, chamada de vídeo abre.
- Teste manual do estado `indisponivel`: apontar `NEXT_PUBLIC_ROCKETCHAT_URL` para um host que não responde e confirmar que a tela de erro aparece em vez de um iframe quebrado.

## Fora de escopo nesta fase

- Migração de histórico de mensagens (Fase 4).
- Integração chat↔ticket via webhook (Fase 5).
- Descomissionamento do código antigo do chat interno (Fase 6).
- Suporte a `next=` para retomar OAuth após sessão expirada.
- Qualquer alteração em `/atendimento/tickets/[id]`.
