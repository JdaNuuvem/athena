# Chat Interno — Fase 2, sub-projeto 1: Menções — Design

Data: 2026-07-28

## Contexto

A [Fase 1 do chat interno](2026-07-28-chat-interno-fase1-design.md) (núcleo: DM, grupo, canal de departamento, ticket, WebSocket, presença, anexo, busca) já está implementada e mergeada em `master`.

A Fase 2 do roadmap original (ver [chat-interno-fase1-design.md linhas 11-16](2026-07-28-chat-interno-fase1-design.md)) lista 6 itens: menções, reações emoji, fixar/favoritar, encaminhar, editar/excluir avançado (moderação), versionamento de arquivo. São subsistemas independentes entre si — decidido tratar cada um como sub-projeto próprio (spec → plano → implementação → merge), um de cada vez, começando por **menções**.

Este documento cobre só menções. Os outros 5 itens ficam para specs futuros, não fazem parte deste.

## Decisões de escopo (validadas com o usuário)

- **Notificação = só destaque visual in-chat.** Sem contador separado de menções não lidas, sem push/e-mail/desktop — isso é central de notificações completa, escopo da Fase 3. O evento WebSocket `nova_mensagem` já existente entrega a mensagem; o destaque é renderização client-side de quem foi mencionado.
- **Autocomplete só sugere quem já é participante da conversa atual.** Menção não dá acesso novo a ninguém — quem já não vê a conversa continua sem ver. Evita qualquer lógica nova de controle de acesso.
- **`@departamento` só existe dentro do próprio canal de departamento**, onde tem o mesmo efeito de `@todos` daquele canal (participantes = todo mundo com a permissão `<departamento>.ver`, já derivado hoje por `participantes_ids()`). Fora de canal de departamento não existe essa opção — em DM/grupo só há `@pessoa` e `@todos`.
- **Marcador estruturado com ID estável**, não texto puro. Sobrevive a troca de nome (resolve nome atual em tempo de renderização) e não ambiguiza pessoas com nome igual.
- **Digitação usa marcador cru no textarea atual**, sem componente de input novo. Só a mensagem já enviada renderiza o destaque bonito. Decisão consciente de menor esforço/manutenção, coerente com a nota de escopo do próprio doc da Fase 1 (dimensionado pro time atual, não otimização especulativa).

Fora de escopo deste sub-projeto: reações emoji, fixar/favoritar, encaminhar, editar/excluir avançado, versionamento de arquivo (outros itens da Fase 2), central de notificações (Fase 3), inbox/filtro dedicado de "mensagens que me mencionaram" (pode virar necessidade real quando a Fase 3 existir; até lá, YAGNI).

## Modelo de dados

Nenhuma tabela nova. Menção vive dentro do `texto` de `chat_mensagens` (coluna já existente), como marcador embutido:

```
@[user:<id>:<nome_snapshot>]     -- pessoa específica
@[todos]                          -- todos os participantes atuais da conversa
@[dept:<codigo>:<nome_snapshot>]  -- só válido dentro do canal_departamento daquele código
```

`<nome_snapshot>` é o nome capturado no momento do envio — usado só como fallback de renderização se o `id` não resolver mais contra a lista de participantes atuais (ex: pessoa saiu da conversa/foi desativada). O caminho normal de renderização resolve pelo `id` contra a lista de participantes carregada, então sobrevive a troca de nome (o snapshot só entra em jogo na borda).

Sem tabela de menções separada (nada de `chat_mencoes`) — não há necessidade real ainda (sem inbox, sem contador). Se a Fase 3 precisar consultar "toda menção a X" de forma eficiente sem reparsear texto, isso se resolve quando (se) for implementado, não agora.

## Backend

### Endpoint novo

```
GET /api/chat/conversas/<id>/participantes
```

Retorna `[{user_id, nome, papel}]` dos participantes atuais da conversa (reusa `participantes_ids()` já existente em `core/chat.py`, unificando DM/grupo/canal/ticket, com join em `rbac_usuarios` pro nome). Mesma checagem de acesso dos demais endpoints (`usuario_e_participante`) — só quem já participa pode listar quem participa.

### Validação no envio

`enviar_mensagem()` (em `core/chat.py`) ganha um passo de parsing/validação do texto recebido antes de persistir:

- Extrai tokens `@[user:<id>:...]`, `@[todos]`, `@[dept:<codigo>:...]` via regex tolerante.
- Cada `user:<id>` é validado contra `participantes_ids(conversa_id)` (chamado uma vez, resultado reaproveitado pra todos os tokens da mesma mensagem). Se o id não está na lista atual, o token daquele trecho é rebaixado a texto plano (`@<nome_snapshot>`, sem colchetes/marcador) — a mensagem continua sendo enviada normalmente, nunca bloqueia por causa de uma menção inválida.
- `dept:<codigo>` só passa se a conversa é do tipo `canal_departamento` E o código bate com `conversa["departamento"]`. Caso contrário, mesmo rebaixamento a texto plano.
- `@[todos]` sempre passa (não referencia id nenhum, é sempre coerente com "participantes atuais", resolvido em tempo de leitura).
- Token com sintaxe malformada (id não numérico, colchete sem fechar, etc.) não casa a regex — vira texto literal automaticamente, sem erro/exceção.

Nenhum evento WebSocket novo. O texto (já com os tokens validados/rebaixados) trafega pelo `nova_mensagem` existente, igual hoje.

## Frontend

- **Autocomplete**: `MensagensPainel.tsx` ganha um popup simples acionado ao digitar `@` no textarea atual (sem trocar de componente). Lista vem do novo endpoint de participantes, carregado uma vez por conversa aberta (mesmo padrão de fetch dos outros dados da conversa). Filtra por substring conforme o usuário continua digitando após o `@`. Opções fixas: "todos" sempre presente; nome do departamento presente só se `tipo === "canal_departamento"`.
- Selecionar uma opção insere o marcador cru (`@[user:123:Fulano]`, `@[todos]`, `@[dept:financeiro:Financeiro]`) na posição do cursor do textarea — comportamento igual a hoje, sem mudança visual durante a digitação.
- **Renderização da mensagem enviada**: parser client-side (função pura, testável isoladamente) varre o `texto` de cada `MensagemChat` e troca cada marcador reconhecido por um `<span>` com destaque visual (cor/negrito), resolvendo o nome atual contra a lista de participantes já carregada da conversa; se o `id` não estiver mais nessa lista, usa o `nome_snapshot` embutido no marcador como fallback. Texto fora de marcadores passa direto, sem alteração.

## Tratamento de erros

- Marcador malformado no texto → não casa o parser, vira texto literal (sem crash, sem exceção).
- Menção a `id` que não é mais participante → rebaixada a texto plano no backend antes mesmo de persistir (ver acima); frontend nunca precisa lidar com esse caso porque o texto já chega neutralizado.
- Falha ao carregar lista de participantes (rede) → autocomplete simplesmente não abre opções; digitar `@` sem popup funcional não impede enviar mensagem normalmente (texto literal, sem marcador).

## Testes

- **Unit (backend)**: parser de extração/validação de tokens — casos válido (user participante, todos, dept correto), inválido (user não-participante → rebaixado, dept fora do canal → rebaixado, sintaxe malformada → texto literal).
- **Integração (backend)**: `enviar_mensagem` persiste texto rebaixado corretamente quando a validação falha; `GET /conversas/<id>/participantes` retorna lista certa para dm/grupo/canal_departamento/ticket, e nega acesso a quem não participa (segue padrão de `test_chat.py` já existente).
- **Frontend**: componente de autocomplete filtra e insere marcador correto; função de parse/renderização resolve nome atual vs. fallback de snapshot; participante removido some da lista de sugestão em conversas futuras mas menções antigas continuam renderizando via snapshot.
