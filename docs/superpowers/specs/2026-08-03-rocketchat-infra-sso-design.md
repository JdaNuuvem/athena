# Rocket.Chat — Infra + SSO (Fase 1+2) — Design

Data: 2026-08-03

## Contexto

O chat interno atual (`hermes_agents/routes/chat.py`, `chat_ws.py`, `core/chat.py`, componentes React em `web/src/app/chat/`) é um sistema próprio em Flask + WebSocket, já em produção, cobrindo DM/grupo/canal/thread/menções/anexos (ver `docs/superpowers/specs/2026-07-28-chat-interno-fase1-design.md` e `2026-07-28-chat-interno-fase2-mencoes-design.md`).

Decisão: abandonar a evolução desse sistema próprio e substituí-lo pelo **Rocket.Chat** (self-hosted, MIT no core, 45.9k stars, ativo), que já resolve DM/grupo/canal/thread/menções/anexos/chamada de vídeo/apps mobile de forma madura e mantida por terceiros.

## Decomposição do projeto maior

- **Fase 1+2 (este documento):** provisionar Rocket.Chat + MongoDB e implementar SSO (Hermes como Identity Provider OAuth2). Sem impacto visível para o usuário final ainda — é a fundação técnica.
- **Fase 3:** embutir o Rocket.Chat via iframe na aba **Chat** do Athena (`/chat`), com login automático via o SSO desta fase. Primeira entrega visível ao usuário.
- **Fase 4:** migrar histórico de mensagens do Postgres atual (`chat_conversas`/`chat_mensagens`) para o Rocket.Chat via API/import.
- **Fase 5:** reconstruir a integração chat↔ticket (hoje `chat_conversas.tipo='ticket'` linkado a `hermes_agents/routes/atendimento.py`) via webhook/API do Rocket.Chat — criar canal automaticamente ao abrir ticket, sincronizar mensagens de volta.
- **Fase 6:** descomissionar o código antigo (`routes/chat.py`, `routes/chat_ws.py`, `core/chat.py`, `core/chat_ws.py`, componentes React em `web/src/app/chat/_components/`) — só depois de Fases 3-5 validadas em produção.

Cada fase tem spec e plano de implementação próprios, feitos após a fase anterior estar validada.

## Arquitetura

**Infra:** container Rocket.Chat + MongoDB (replica-set single-node, exigido pelo Rocket.Chat para Change Streams) novo no Coolify, mesma infra do Athena. Subdomínio proposto: `chat.athena.zoikom.site` (a confirmar no momento do deploy). Volumes persistentes para dados do Mongo e uploads do Rocket.Chat.

**SSO:** novo blueprint Flask `hermes_agents/routes/oauth_provider.py`. Sem framework OAuth novo — segue o padrão já estabelecido no projeto (JWT manual via `pyjwt`, sem Flask-Login/Authlib/etc, ver `core/rbac.py`). `code` e `access_token` são JWTs curtos assinados com o mesmo secret (`ATHENA_JWT_SECRET`), com um claim `typ` (`oauth_code` / `oauth_access`) para não serem intercambiáveis. Reaproveita a sessão JWT já existente (`core/rbac.py`: `verificar_token_sessao`, cookie `auth_token` ou header `Authorization: Bearer`) — não mexe no login atual do Hermes. Client OAuth2 (client_id/secret) representando o Rocket.Chat fica em variável de ambiente, gerado uma vez no setup, nunca hardcoded.

**Configuração do Custom OAuth no Rocket.Chat:** sem script de bootstrap via Admin API. O próprio Rocket.Chat lê variáveis de ambiente `Accounts_OAuth_Custom_<Nome>_*` no startup (mecanismo oficial, `initCustomOAuthServices.ts`) e registra o provider sozinho — configuração declarada direto no `docker-compose.yml`, sem tocar em usuário/senha de admin do Rocket.Chat.

Papéis/permissões do RBAC do Hermes **não** são mapeados para roles do Rocket.Chat nesta fase — fica com os defaults do just-in-time provisioning. Mapeamento fino é trabalho futuro, fora de escopo aqui (evita travar a fundação por um refinamento que pode esperar).

## Componentes

1. **`GET /oauth/authorize`** — lê `auth_token` da request (cookie ou header). Válido: aprova automaticamente (sem tela de consentimento — sistema interno de confiança) e redireciona ao Rocket.Chat com `code`. Inválido/ausente: redireciona ao `/login` do Hermes com `next=` de volta para o authorize.
2. **`POST /oauth/token`** — troca `code` por `access_token`. Chamada servidor-a-servidor do Rocket.Chat, não passa pelo browser do usuário.
3. **`GET /oauth/userinfo`** — a partir do `access_token`, retorna `{sub, email, name, username}` derivados do payload JWT do usuário (`user_id`, `email`, `role` já existentes em `rbac_usuarios`).
4. **`deploy/rocketchat/docker-compose.yml`** — variáveis `Accounts_OAuth_Custom_Hermes*` apontando para os 3 endpoints acima, com o mapeamento de campos (`username`/`email`/`name`). Evita depender de configuração manual pela UI admin (perdível/não versionada).

## Fluxo de dados

Usuário abre o Rocket.Chat (ainda standalone nesta fase, sem iframe) → sem sessão local → clica em "Login com Hermes" → `/oauth/authorize` no Hermes → Flask valida `auth_token` já existente → aprova, redireciona de volta com `code` → Rocket.Chat troca por `access_token` (`/oauth/token`) → busca `/oauth/userinfo` → cria/atualiza conta automaticamente no primeiro acesso (just-in-time provisioning) → sessão própria do Rocket.Chat criada.

## Erros

- `auth_token` expirado durante o fluxo → cai no `/login` normal do Hermes, retoma o authorize depois de logar.
- Client OAuth mal configurado (client_id/secret divergente) → erro logado no Flask; Rocket.Chat expõe erro de login (fora do nosso controle direto de UI).
- Rocket.Chat ou MongoDB fora do ar → falha de infra, sem relação com o fluxo OAuth — tratamento de disponibilidade fica para a Fase 3 (embed), quando existe UI do Hermes cobrindo esse caso.

## Testes

- pytest cobrindo `/oauth/authorize` (autenticado vs não autenticado), `/oauth/token` (code válido, inválido, expirado), `/oauth/userinfo` (token válido, inválido) — mesmo padrão de segurança de `hermes_agents/tests/test_atendimento_seguranca.py`.
- Infra: checklist manual de smoke test (subir container, criar usuário via login OAuth ponta a ponta) — sem automação de infra nesta fase.

## Fora de escopo nesta fase

- Embed do Rocket.Chat no `/chat` do Athena (Fase 3).
- Migração de histórico de mensagens (Fase 4).
- Integração chat↔ticket via webhook (Fase 5).
- Descomissionamento do código antigo do chat interno (Fase 6).
- Mapeamento de roles/permissões RBAC → Rocket.Chat.
