# Chat Interno — Fase 1 (Núcleo) — Design

Data: 2026-07-28

## Contexto

Hoje existem dois módulos separados sob `Atendimento`: `Tickets` (helpdesk multi-canal para clientes — WhatsApp, Shopee, Telegram, Instagram, Facebook, chat, e-mail) e `Chat` (conversa 1:1 com cliente via polling de 10s). Não existe comunicação interna entre usuários do sistema (equipe).

Este documento cobre a **Fase 1** de um módulo maior de Comunicação Corporativa (ver decomposição abaixo). As fases seguintes (2-4) têm specs próprios, feitos depois que esta fase estiver implementada e validada.

## Decomposição do projeto maior

- **Fase 1 (este documento):** núcleo do chat — DM, grupos, canais de departamento, threads, tickets como conversa no mesmo hub, WebSocket real-time, presença, anexo básico, busca simples, permissões básicas via RBAC.
- **Fase 2:** menções (@usuário/@departamento/@todos) com notificação, reações emoji, fixar/favoritar, encaminhar, editar/excluir avançado, versionamento de arquivo.
- **Fase 3:** ticket avançado (SLA, categoria, checklist, escalonamento, transferência de responsável/departamento), central de notificações (push/desktop/e-mail/badge), botão "iniciar conversa" a partir de outras entidades do sistema (cliente, pedido, produto, venda, etc).
- **Fase 4:** segurança avançada (criptografia de arquivo, rate limiting/anti-flood, antivírus de upload, expiração de link), escala horizontal (cache, filas assíncronas, paginação infinita otimizada), auditoria completa, testes de carga/concorrência/segurança.

Nota sobre escopo: o pedido original menciona "multiempresa" e "milhares de usuários simultâneos". Este é um ERP de empresa única (não multi-tenant) — não existe entidade "empresa" no RBAC atual, só `lojas` e permissões por módulo (equivalente a departamento). O design abaixo usa loja/departamento como dimensões de escopo, e é dimensionado para a realidade atual do time (dezenas de usuários, não milhares); a arquitetura não impede crescer depois, mas otimizar para milhares de usuários simultâneos agora seria trabalho especulativo sem uso — fica para quando (se) for necessário.

## Arquitetura

Chat entra como novo blueprint Flask (`hermes_agents/routes/chat.py`), reaproveitando `get_db()`/`asyncpg`/`run_async()` — mesmo padrão do resto do projeto. Sem framework novo no backend.

**Tempo real:** `flask-sock` (WebSocket sobre WSGI puro, thread-per-conexão). Não se usa `flask-socketio`+`eventlet`/`gevent` porque o monkeypatch do eventlet quebraria o padrão `asyncio.run()` já usado em toda a base (ex: `producao`/`bling_erp`). Endpoint único: `/ws/chat?token=<jwt>`, valida o JWT do mesmo jeito que os endpoints HTTP hoje (`verificar_token_sessao`).

**Fan-out:** registro de conexões em memória (dict `user_id -> [conexões websocket]`) dentro do processo Flask. Funciona porque hoje roda como processo único (`python athena_bridge.py`). Limite conhecido e aceito: se escalar para múltiplas instâncias atrás de load balancer, este registro em memória para de funcionar corretamente (mensagens não chegam a conexões presas em outra instância) — nesse caso trocar por pub/sub (Redis). Não implementado agora (YAGNI), mas documentado aqui para não ser esquecido.

**Integração com tickets — sem migrar dados existentes:** cada ticket de atendimento vira uma linha em `chat_conversas` (tipo `ticket`, com `ticket_ref_id` apontando para o ticket original). As mensagens desse tipo de conversa continuam sendo lidas/gravadas pelos endpoints já existentes de `atendimento` (que já processam webhook de WhatsApp/Shopee/etc — não alterados). Conversas internas (DM, grupo, canal, thread) usam a tabela nova `chat_mensagens`. O frontend não faz distinção visual — mesma UI, mesma sidebar — o backend decide a origem dos dados pelo `tipo` da conversa.

Justificativa: evita reescrever um sistema de atendimento em produção. Mais barato e mais seguro que migração de dados.

## Modelo de dados

Tabelas novas em Postgres via `asyncpg`, seguindo o padrão `CREATE TABLE IF NOT EXISTS` já usado no projeto (ex: `rbac.py`, `lojas.py`).

```sql
CREATE TABLE IF NOT EXISTS chat_conversas (
  id SERIAL PRIMARY KEY,
  tipo VARCHAR(30) NOT NULL,          -- 'dm' | 'grupo' | 'canal_departamento' | 'ticket'
  nome VARCHAR(150),                  -- null em DM (calculado no frontend pelos participantes)
  descricao TEXT,
  foto_url VARCHAR(300),
  departamento VARCHAR(50),           -- mesmos códigos de módulo usados no RBAC (financeiro, producao, vendas...)
  loja_id INT REFERENCES lojas(id),
  ticket_ref_id INT,                  -- aponta para o ticket original em atendimento; só quando tipo='ticket'
  criado_por INT REFERENCES rbac_usuarios(id),
  created_at TIMESTAMP DEFAULT NOW(),
  arquivado_em TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_participantes (
  conversa_id INT REFERENCES chat_conversas(id) ON DELETE CASCADE,
  user_id INT REFERENCES rbac_usuarios(id),
  papel VARCHAR(20) NOT NULL DEFAULT 'membro',   -- 'owner' | 'admin' | 'moderador' | 'membro'
  entrou_em TIMESTAMP DEFAULT NOW(),
  saiu_em TIMESTAMP,
  PRIMARY KEY (conversa_id, user_id)
);

CREATE TABLE IF NOT EXISTS chat_anexos (
  id SERIAL PRIMARY KEY,
  nome_arquivo VARCHAR(255) NOT NULL,
  mime VARCHAR(100),
  tamanho_bytes INT,
  storage_path VARCHAR(500) NOT NULL,   -- caminho relativo no volume persistente do Coolify
  enviado_por INT REFERENCES rbac_usuarios(id),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_mensagens (
  id SERIAL PRIMARY KEY,
  conversa_id INT REFERENCES chat_conversas(id) ON DELETE CASCADE,
  thread_pai_id INT REFERENCES chat_mensagens(id),   -- preenchido = resposta em thread
  remetente_id INT REFERENCES rbac_usuarios(id),
  texto TEXT,
  anexo_id INT REFERENCES chat_anexos(id),
  created_at TIMESTAMP DEFAULT NOW(),
  editado_em TIMESTAMP,
  excluido_em TIMESTAMP    -- soft delete; frontend mostra "[mensagem excluída]"
);

CREATE TABLE IF NOT EXISTS chat_leituras (
  conversa_id INT REFERENCES chat_conversas(id) ON DELETE CASCADE,
  user_id INT REFERENCES rbac_usuarios(id),
  ultima_mensagem_lida_id INT,
  lido_em TIMESTAMP,
  PRIMARY KEY (conversa_id, user_id)
);

CREATE TABLE IF NOT EXISTS chat_presenca (
  user_id INT PRIMARY KEY REFERENCES rbac_usuarios(id),
  status VARCHAR(20) DEFAULT 'offline',   -- 'online' | 'ausente' | 'ocupado' | 'offline'
  last_seen TIMESTAMP
);
```

Anexos ficam no volume local persistente do container (Coolify), em `hermes_agents/uploads/chat/`. Requer volume persistente configurado (senão perde arquivo em redeploy) — checar/configurar isso no Coolify como parte da implementação.

Canal de departamento: participação automática e somente-leitura de membership — todo usuário com a permissão de módulo correspondente (`<departamento>.ver` no RBAC) é considerado participante; não há convite/remoção manual nesses canais. A lista de participantes é derivada em tempo de consulta (join com `rbac_role_permissoes`), não persistida em `chat_participantes` (evita ficar dessincronizada quando role muda).

## API REST

Blueprint `/api/chat/*`:

```
GET    /api/chat/conversas                       lista conversas do usuário logado (DM+grupo+canal+ticket, unificado, ordenado por última atividade)
POST   /api/chat/conversas                       cria DM ou grupo (tipo, participantes[])
GET    /api/chat/conversas/<id>/mensagens         histórico paginado (cursor por created_at)
POST   /api/chat/conversas/<id>/mensagens         envia mensagem (texto, anexo_id?, thread_pai_id?)
POST   /api/chat/anexos                           upload multipart, retorna anexo_id
POST   /api/chat/conversas/<id>/participantes     adiciona membro (checa papel)
DELETE /api/chat/conversas/<id>/participantes/<user_id>
POST   /api/chat/conversas/<id>/lido              marca leitura até a última mensagem
GET    /api/chat/busca?q=...                       busca texto nas mensagens do usuário
GET    /api/chat/canais-departamento               lista canais auto-sincronizados por permissão RBAC
```

Endpoints de ticket permanecem em `/api/atendimento/tickets/*`, sem alteração. O frontend decide qual API chamar olhando o `tipo` da conversa.

## WebSocket

Endpoint `/ws/chat?token=<jwt>` (token via query string — WebSocket nativo do browser não permite header custom no handshake).

Cliente → servidor: `enviar_mensagem`, `digitando`, `presenca` (mudar status manual), `entrar_conversa` / `sair_conversa` (subscreve/dessubscreve da sala).

Servidor → cliente: `nova_mensagem`, `mensagem_editada`, `mensagem_excluida`, `usuario_digitando`, `presenca_atualizada`, `confirmacao_entrega`, `confirmacao_leitura`.

Mensagens de ticket recebidas via webhook do atendimento (WhatsApp/Shopee/etc) também disparam `nova_mensagem` no mesmo canal, para a UI atualizar em tempo real igual às conversas internas, mesmo com persistência separada.

## Permissões (RBAC)

- Criar grupo: qualquer usuário autenticado; vira `owner`.
- Adicionar/remover membro: `owner`/`admin`/`moderador` do grupo.
- Canal de departamento: participação automática via permissão de módulo, não editável manualmente.
- Ticket: mesma checagem que já existe hoje (`atendimento.ver`/`atendimento.editar`) — chat só empresta a UI, não muda a regra de acesso.
- Editar/excluir mensagem: apenas o autor. Moderação (admin apagar mensagem de terceiro) fica para a Fase 2.

## Frontend

Nova rota `web/src/app/chat/`, substitui `web/src/app/atendimento/chat/` (que vira redirect para `/chat`).

Layout 3 colunas: sidebar (conversas — DM/grupo/canal/ticket misturados por atividade recente, com ícone por tipo), painel central (mensagens + input), painel lateral de thread (abre ao responder em thread).

- Hook `useChatSocket()`: gerencia conexão WS, reconecta com backoff exponencial (máx 30s) se cair, expõe eventos para os componentes.
- Presença: indicador colorido no avatar (verde/amarelo/vermelho/cinza).
- Digitando: "Fulano está digitando..." abaixo do input, expira 3s sem novo evento.
- Anexo: drag-and-drop na área de mensagens + botão de clipe, preview antes de enviar, barra de progresso no upload.

Menu principal: item "Chat" sobe para o nível raiz de navegação (não mais dentro de "Atendimento"), já que agora é chat geral da equipe. "Atendimento > Tickets" continua existindo como está (gestão/SLA/fila); abrir um ticket ali ganha botão "abrir no chat".

## Tratamento de erros

- Upload acima de 25MB → HTTP 413 com mensagem clara; frontend mostra toast.
- WebSocket cai → reconecta automático (backoff exponencial); mensagens enviadas nesse intervalo ficam em fila local com estado "enviando..." até confirmação do servidor.
- Falha ao enviar mensagem (rede) → mensagem marcada como "falhou", com botão de reenviar.
- Token expirado no WS → servidor fecha a conexão com código customizado; frontend detecta e reusa `handleUnauthorized()` já existente (limpa sessão, redireciona para login).

## Testes

- Unit: regras de permissão (quem adiciona/remove membro, quem edita/exclui mensagem).
- Integração: cada endpoint REST novo em `hermes_agents/tests/test_chat.py` (padrão de `test_atendimento_seguranca.py`), incluindo casos 403 (usuário fora do grupo tentando ler mensagens).
- WebSocket: conexão autentica com token válido/inválido; broadcast chega só para participantes da conversa (não vaza para não-membros).
- E2E (Playwright): enviar mensagem e ver aparecer em tempo real em outra sessão; criar grupo; responder em thread.
