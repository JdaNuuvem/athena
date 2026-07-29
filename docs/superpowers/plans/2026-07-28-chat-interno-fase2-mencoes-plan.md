# Chat Interno — Fase 2, Menções — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir mencionar `@pessoa`, `@todos` ou `@departamento` (só dentro do próprio canal) nas mensagens do chat interno, com destaque visual na renderização — sem tabela nova, sem evento WebSocket novo, sem dar acesso a quem não é participante da conversa.

**Architecture:** Menção vira um marcador estruturado (`@[user:<id>:<nome>]`, `@[todos]`, `@[dept:<codigo>:<nome>]`) embutido no `texto` já existente de `chat_mensagens`. O backend valida/rebaixa o marcador no momento do envio (`core/chat.py::enviar_mensagem`, chamado tanto pela rota REST quanto pelo handler WebSocket — um único ponto). O frontend busca a lista de participantes da conversa (endpoint novo) pra alimentar autocomplete e resolver nome atual na renderização.

**Tech Stack:** Python 3.13 / Flask / asyncpg (backend, padrão já usado em `core/chat.py`); Next.js/React/TypeScript (frontend, sem framework de teste automatizado configurado — verificação via `npx tsc --noEmit`).

## Global Constraints

- Spec de referência: `docs/superpowers/specs/2026-07-28-chat-interno-fase2-mencoes-design.md`.
- Sem tabela nova no banco. Sem evento WebSocket novo — o texto (já processado) trafega pelo `nova_mensagem` existente.
- Autocomplete só pode sugerir quem já é `participantes_ids(conversa_id)` da conversa atual — nunca adiciona acesso novo.
- `@[dept:<codigo>:...]` só é válido quando a própria conversa é `tipo == "canal_departamento"` e `codigo == conversa["departamento"]`. Fora disso, rebaixa a texto plano, igual a uma menção de usuário inválida.
- Marcador malformado (regex não casa) vira texto literal — nunca lança exceção, nunca bloqueia envio da mensagem.
- Backend: rodar `python -m pytest hermes_agents/tests/test_chat.py -v` (e, ao final, a suíte completa `python -m pytest hermes_agents/tests/ -q`) a partir da raiz do repositório após cada mudança em `core/chat.py` ou `routes/chat.py`.
- Frontend: não há Jest/Vitest configurado neste repo (confirmado — sem script de teste, sem arquivo `*.test.ts*`). Verificação de mudança em `.ts`/`.tsx` é `npx tsc --noEmit` dentro de `web/`, seguindo o padrão já usado nos planos anteriores do chat interno.
- Todo texto de identificador/variável em português, seguindo a convenção já estabelecida no restante de `core/chat.py`, `routes/chat.py` e `web/src/app/chat/`.

---

### Task 1: Parser de menções + validação no envio de mensagem (backend)

**Files:**
- Modify: `hermes_agents/core/chat.py` (import `re`, nova constante `_PADRAO_MENCAO`, nova função `_processar_mencoes`, uma linha nova em `enviar_mensagem`)
- Test: `hermes_agents/tests/test_chat.py`

**Interfaces:**
- Produces: `core.chat._processar_mencoes(conversa_id: int, texto: str) -> str` — usada pela Task 1 (chamada dentro de `enviar_mensagem`) e disponível para qualquer chamador futuro.
- Consumes: `core.chat._obter_conversa(conversa_id)` e `core.chat.participantes_ids(conversa_id)`, ambas já existentes em `core/chat.py`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_chat.py` (depois da última classe existente, `TestChatPresencaBroadcast`):

```python
class TestProcessarMencoes(unittest.TestCase):
    def test_mencao_usuario_participante_mantida(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "grupo", "departamento": None}), \
             patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            resultado = chat._processar_mencoes(5, "oi @[user:2:Bruno] tudo bem?")
        self.assertEqual(resultado, "oi @[user:2:Bruno] tudo bem?")

    def test_mencao_usuario_nao_participante_rebaixada(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "grupo", "departamento": None}), \
             patch("core.chat.participantes_ids", return_value=[1, 3]):
            resultado = chat._processar_mencoes(5, "oi @[user:2:Bruno] tudo bem?")
        self.assertEqual(resultado, "oi @Bruno tudo bem?")

    def test_mencao_todos_sempre_mantida(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "grupo", "departamento": None}), \
             patch("core.chat.participantes_ids", return_value=[1]):
            resultado = chat._processar_mencoes(5, "atencao @[todos] favor ler")
        self.assertEqual(resultado, "atencao @[todos] favor ler")

    def test_mencao_dept_correto_mantida(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "canal_departamento", "departamento": "financeiro"}), \
             patch("core.chat.participantes_ids", return_value=[1]):
            resultado = chat._processar_mencoes(5, "@[dept:financeiro:financeiro] revisar")
        self.assertEqual(resultado, "@[dept:financeiro:financeiro] revisar")

    def test_mencao_dept_fora_do_canal_rebaixada(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "grupo", "departamento": None}), \
             patch("core.chat.participantes_ids", return_value=[1]):
            resultado = chat._processar_mencoes(5, "@[dept:financeiro:financeiro] revisar")
        self.assertEqual(resultado, "@financeiro revisar")

    def test_mencao_malformada_vira_texto_literal(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "grupo", "departamento": None}), \
             patch("core.chat.participantes_ids", return_value=[1]):
            resultado = chat._processar_mencoes(5, "oi @[user:abc:Bruno sem fechar")
        self.assertEqual(resultado, "oi @[user:abc:Bruno sem fechar")

    def test_texto_sem_mencao_nao_consulta_conversa(self):
        with patch("core.chat._obter_conversa") as mock_obter:
            resultado = chat._processar_mencoes(5, "mensagem normal sem nada")
        mock_obter.assert_not_called()
        self.assertEqual(resultado, "mensagem normal sem nada")


class TestEnviarMensagemProcessaMencoes(unittest.TestCase):
    def test_enviar_mensagem_usa_texto_processado_por_mencoes(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "conversa_id": args[0], "remetente_id": args[1],
                    "texto": args[2], "anexo_id": args[3], "thread_pai_id": args[4]}
        with patch("core.chat.get_db") as mock_get_db, \
             patch("core.chat._processar_mencoes", return_value="ola @[user:2:Bruno]") as mock_processar:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = chat.enviar_mensagem(5, 1, "ola @[user:2:Bruno]")
        mock_processar.assert_called_once_with(5, "ola @[user:2:Bruno]")
        self.assertEqual(resultado["texto"], "ola @[user:2:Bruno]")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_chat.py -v -k "ProcessarMencoes or EnviarMensagemProcessaMencoes"`
Expected: FAIL — `AttributeError: module 'core.chat' has no attribute '_processar_mencoes'` (a função ainda não existe).

- [ ] **Step 3: Implementar o parser e ligar em `enviar_mensagem`**

No topo de `hermes_agents/core/chat.py`, trocar:

```python
"""Chat Interno Core — Conversas (DM/Grupo/Canal/Ticket), Mensagens, Anexos, Presenca, Busca"""
from core import get_db, run_async, log
from datetime import datetime
```

por:

```python
"""Chat Interno Core — Conversas (DM/Grupo/Canal/Ticket), Mensagens, Anexos, Presenca, Busca"""
import re
from core import get_db, run_async, log
from datetime import datetime
```

Logo depois da linha `AGENT = "Chat Core"` (antes de `DEPARTAMENTOS_CANAL`), adicionar:

```python
_PADRAO_MENCAO = re.compile(
    r"@\[(?:"
    r"user:(?P<uid>\d+):(?P<unome>[^\]]*)"
    r"|(?P<todos>todos)"
    r"|dept:(?P<dcod>[a-z_]+):(?P<dnome>[^\]]*)"
    r")\]"
)
```

Logo depois do comentário `# ── Mensagens ──` (linha 240), antes de `def enviar_mensagem`, adicionar:

```python
def _processar_mencoes(conversa_id: int, texto: str) -> str:
    """Valida marcadores de mencao (@[user:id:nome], @[todos], @[dept:codigo:nome])
    contra os participantes atuais da conversa. Marcador invalido (usuario que
    saiu, departamento fora do proprio canal, sintaxe quebrada) e rebaixado a
    texto plano — nunca bloqueia o envio da mensagem por causa disso."""
    if not texto or "@[" not in texto:
        return texto
    conversa = _obter_conversa(conversa_id) or {}
    participantes = set(participantes_ids(conversa_id))

    def _validar(m: "re.Match") -> str:
        if m.group("uid") is not None:
            if int(m.group("uid")) in participantes:
                return m.group(0)
            return f"@{m.group('unome')}"
        if m.group("todos") is not None:
            return m.group(0)
        if conversa.get("tipo") == "canal_departamento" and conversa.get("departamento") == m.group("dcod"):
            return m.group(0)
        return f"@{m.group('dnome')}"

    return _PADRAO_MENCAO.sub(_validar, texto)
```

Em `enviar_mensagem`, mudar a primeira linha do corpo para processar o texto antes de montar a query:

```python
def enviar_mensagem(conversa_id: int, remetente_id: int, texto: str, anexo_id: int = None, thread_pai_id: int = None) -> dict:
    texto = _processar_mencoes(conversa_id, texto)
    async def _go():
```

(o resto da função continua igual, só a primeira linha do corpo muda).

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_chat.py -v -k "ProcessarMencoes or EnviarMensagemProcessaMencoes"`
Expected: PASS (8 testes).

Run: `python -m pytest hermes_agents/tests/test_chat.py -v`
Expected: PASS em todos (garante que a mudança em `enviar_mensagem` não quebrou nenhum teste existente do arquivo).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/chat.py hermes_agents/tests/test_chat.py
git commit -m "feat: parser de mencoes valida/rebaixa marcador contra participantes atuais"
```

---

### Task 2: `participantes_info()` + endpoint `GET /api/chat/conversas/<id>/participantes`

**Files:**
- Modify: `hermes_agents/core/chat.py` (nova função `participantes_info`)
- Modify: `hermes_agents/routes/chat.py` (novo import, nova rota)
- Test: `hermes_agents/tests/test_chat.py`

**Interfaces:**
- Consumes: `core.chat.participantes_ids(conversa_id)` (já existente).
- Produces: `core.chat.participantes_info(conversa_id: int) -> list[dict]`, cada item `{"user_id": int, "nome": str, "papel": str | None}` — consumida pela rota nova desta task e, depois, pelo frontend (Task 3 em diante) via `GET /api/chat/conversas/<id>/participantes`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_chat.py`:

```python
class TestParticipantesInfo(unittest.TestCase):
    def test_participantes_info_sem_participantes_retorna_vazio(self):
        with patch("core.chat.participantes_ids", return_value=[]):
            self.assertEqual(chat.participantes_info(5), [])

    def test_participantes_info_junta_nome_e_papel(self):
        async def _fetch(query, *args):
            if "rbac_usuarios" in query:
                return [{"user_id": 1, "nome": "Ana"}, {"user_id": 2, "nome": "Bruno"}]
            return [{"user_id": 1, "papel": "owner"}]
        with patch("core.chat.participantes_ids", return_value=[1, 2]), \
             patch("core.chat.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetch=_fetch)
            resultado = chat.participantes_info(5)
        self.assertEqual(resultado[0], {"user_id": 1, "nome": "Ana", "papel": "owner"})
        self.assertEqual(resultado[1], {"user_id": 2, "nome": "Bruno", "papel": None})


class TestChatParticipantesEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def test_listar_participantes_nao_participante_nega(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("routes.chat.usuario_e_participante", return_value=False):
                r = self.client.get("/api/chat/conversas/5/participantes", headers=headers)
            self.assertEqual(r.status_code, 403)

    def test_listar_participantes_participante_libera(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("routes.chat.usuario_e_participante", return_value=True), \
                 patch("routes.chat.participantes_info",
                       return_value=[{"user_id": 11, "nome": "Fulano", "papel": "membro"}]) as mock_info:
                r = self.client.get("/api/chat/conversas/5/participantes", headers=headers)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.get_json()["data"][0]["nome"], "Fulano")
            mock_info.assert_called_once_with(5)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_chat.py -v -k "ParticipantesInfo or ChatParticipantesEndpoint"`
Expected: FAIL — `AttributeError: module 'core.chat' has no attribute 'participantes_info'` (função e rota ainda não existem).

- [ ] **Step 3: Implementar `participantes_info` e a rota**

Em `hermes_agents/core/chat.py`, logo depois de `usuario_e_participante` (depois da linha 203), adicionar:

```python
def participantes_info(conversa_id: int) -> list:
    """Como participantes_ids, mas com nome e papel — usado pelo autocomplete
    de mencao no frontend. Papel vem nulo pra canal_departamento/ticket (nao
    ha linha em chat_participantes nesses tipos, participacao e derivada)."""
    ids = participantes_ids(conversa_id)
    if not ids:
        return []
    async def _go():
        db = await get_db()
        nomes = await db.fetch(
            "SELECT id AS user_id, nome FROM rbac_usuarios WHERE id = ANY($1::int[])", ids)
        papeis = await db.fetch(
            "SELECT user_id, papel FROM chat_participantes WHERE conversa_id=$1 AND user_id = ANY($2::int[]) AND saiu_em IS NULL",
            conversa_id, ids)
        return [dict(r) for r in nomes], [dict(r) for r in papeis]
    try:
        nomes, papeis = run_async(_go())
    except Exception:
        return []
    nomes_por_id = {r["user_id"]: r["nome"] for r in nomes}
    papel_por_id = {r["user_id"]: r["papel"] for r in papeis}
    return [
        {"user_id": uid, "nome": nomes_por_id.get(uid, f"Usuario {uid}"), "papel": papel_por_id.get(uid)}
        for uid in ids if uid in nomes_por_id
    ]
```

Em `hermes_agents/routes/chat.py`, no bloco de import de `core.chat` (linhas 6-12), acrescentar `participantes_info`:

```python
from core.chat import (
    criar_conversa_dm, criar_conversa_grupo, listar_conversas_usuario,
    listar_mensagens, enviar_mensagem, editar_mensagem, excluir_mensagem,
    marcar_lido, adicionar_participante, remover_participante, papel_do_usuario,
    usuario_e_participante, buscar_mensagens, listar_canais_departamento,
    salvar_anexo, obter_anexo, conversa_do_anexo, obter_conversa, participantes_info,
)
```

Logo depois da rota `chat_marcar_lido` (depois da linha 217, antes de `@chat_bp.route("/busca"...)`), adicionar:

```python
@chat_bp.route("/conversas/<int:conversa_id>/participantes", methods=["GET"])
def chat_listar_participantes(conversa_id):
    usuario = usuario_atual_da_request()
    user_id = usuario.get("user_id")
    if not user_id or not usuario_e_participante(conversa_id, int(user_id)):
        return jsonify({"error": "Permissao negada"}), 403
    return jsonify({"data": participantes_info(conversa_id)})
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_chat.py -v`
Expected: PASS em todos (arquivo inteiro, garante que a nova rota GET não colide com as rotas POST/DELETE já existentes no mesmo path).

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/chat.py hermes_agents/routes/chat.py hermes_agents/tests/test_chat.py
git commit -m "feat: endpoint GET participantes da conversa, base pro autocomplete de mencao"
```

---

### Task 3: Tipos e cliente de API do frontend

**Files:**
- Modify: `web/src/lib/types/chat.ts`
- Modify: `web/src/lib/api.ts`

**Interfaces:**
- Produces: tipo `ParticipanteChat` e `api.chat.listarParticipantes(conversaId: number): Promise<{ data: ParticipanteChat[] }>` — consumidos pelas Tasks 4-6.

- [ ] **Step 1: Adicionar o tipo `ParticipanteChat`**

Em `web/src/lib/types/chat.ts`, acrescentar ao final do arquivo:

```typescript
export interface ParticipanteChat {
  user_id: number;
  nome: string;
  papel: string | null;
}
```

- [ ] **Step 2: Adicionar o cliente de API**

Em `web/src/lib/api.ts`, trocar o import do topo (linha 71):

```typescript
import type { ConversaChat, MensagemChat, AnexoChat } from "@/lib/types/chat";
```

por:

```typescript
import type { ConversaChat, MensagemChat, AnexoChat, ParticipanteChat } from "@/lib/types/chat";
```

E, dentro do objeto `chat: { ... }`, logo depois de `canaisDepartamento` (depois da linha 492), adicionar:

```typescript
    listarParticipantes: (conversaId: number) =>
      request<{ data: ParticipanteChat[] }>(`/api/chat/conversas/${conversaId}/participantes`),
```

- [ ] **Step 3: Verificar tipos**

Run (dentro de `web/`): `npx tsc --noEmit`
Expected: sem erros novos relacionados a `chat.ts` ou `api.ts`.

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/types/chat.ts web/src/lib/api.ts
git commit -m "feat: tipo ParticipanteChat e cliente de API pra listar participantes da conversa"
```

---

### Task 4: Utilitário compartilhado de parsing/render de menções

**Files:**
- Create: `web/src/lib/chatMencoes.tsx`

**Interfaces:**
- Consumes: `ParticipanteChat` (Task 3).
- Produces: `construirMarcadorUsuario`, `construirMarcadorTodos`, `construirMarcadorDepartamento`, `partirMencoes`, componente `TextoComMencoes` — consumidos pelas Tasks 5 e 6.

- [ ] **Step 1: Criar o arquivo**

```tsx
"use client";
import type { ParticipanteChat } from "@/lib/types/chat";

const PADRAO_MENCAO = /@\[(?:user:(\d+):([^\]]*)|todos|dept:([a-z_]+):([^\]]*))\]/g;

export function construirMarcadorUsuario(userId: number, nome: string): string {
  return `@[user:${userId}:${nome}]`;
}

export function construirMarcadorTodos(): string {
  return "@[todos]";
}

export function construirMarcadorDepartamento(codigo: string, nome: string): string {
  return `@[dept:${codigo}:${nome}]`;
}

interface TrechoTexto {
  chave: string;
  texto: string;
  ehMencao: boolean;
}

export function partirMencoes(texto: string, participantes: ParticipanteChat[]): TrechoTexto[] {
  const nomePorId = new Map(participantes.map((p) => [p.user_id, p.nome]));
  const partes: TrechoTexto[] = [];
  const regex = new RegExp(PADRAO_MENCAO.source, "g");
  let ultimoIndice = 0;
  let contador = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(texto)) !== null) {
    if (match.index > ultimoIndice) {
      partes.push({ chave: `t${contador++}`, texto: texto.slice(ultimoIndice, match.index), ehMencao: false });
    }
    const [, userId, nomeSnapshotUser, deptCodigo, nomeSnapshotDept] = match;
    let rotulo: string;
    if (userId !== undefined) {
      rotulo = `@${nomePorId.get(Number(userId)) ?? nomeSnapshotUser}`;
    } else if (deptCodigo !== undefined) {
      rotulo = `@${nomeSnapshotDept}`;
    } else {
      rotulo = "@todos";
    }
    partes.push({ chave: `m${contador++}`, texto: rotulo, ehMencao: true });
    ultimoIndice = match.index + match[0].length;
  }
  if (ultimoIndice < texto.length) {
    partes.push({ chave: `t${contador++}`, texto: texto.slice(ultimoIndice), ehMencao: false });
  }
  return partes;
}

export function TextoComMencoes({ texto, participantes }: { texto: string; participantes: ParticipanteChat[] }) {
  const partes = partirMencoes(texto, participantes);
  return (
    <>
      {partes.map((p) =>
        p.ehMencao ? (
          <span key={p.chave} className="text-indigo-300 font-semibold">{p.texto}</span>
        ) : (
          <span key={p.chave}>{p.texto}</span>
        )
      )}
    </>
  );
}
```

- [ ] **Step 2: Verificar tipos**

Run (dentro de `web/`): `npx tsc --noEmit`
Expected: sem erros em `chatMencoes.tsx`.

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/chatMencoes.tsx
git commit -m "feat: utilitario de parsing e render de mencoes (marcador estruturado)"
```

---

### Task 5: Autocomplete de menção + integração em `MensagensPainel.tsx`

**Files:**
- Create: `web/src/app/chat/_components/MencaoAutocomplete.tsx`
- Modify: `web/src/app/chat/_components/MensagensPainel.tsx`

**Interfaces:**
- Consumes: `ParticipanteChat` (Task 3), `api.chat.listarParticipantes` (Task 3), `construirMarcadorUsuario`/`construirMarcadorTodos`/`construirMarcadorDepartamento`/`TextoComMencoes` (Task 4).

- [ ] **Step 1: Criar o componente de autocomplete**

```tsx
"use client";
import type { ParticipanteChat } from "@/lib/types/chat";
import { construirMarcadorUsuario, construirMarcadorTodos, construirMarcadorDepartamento } from "@/lib/chatMencoes";

export default function MencaoAutocomplete({
  participantes, filtro, mostrarTodos, departamento, onSelecionar,
}: {
  participantes: ParticipanteChat[];
  filtro: string;
  mostrarTodos: boolean;
  departamento: string | null;
  onSelecionar: (marcador: string) => void;
}) {
  const filtroBusca = filtro.toLowerCase();
  const opcoes: { chave: string; rotulo: string; marcador: string }[] = [];

  if (mostrarTodos && "todos".includes(filtroBusca)) {
    opcoes.push({ chave: "todos", rotulo: "todos", marcador: construirMarcadorTodos() });
  }
  if (departamento && departamento.toLowerCase().includes(filtroBusca)) {
    opcoes.push({
      chave: "dept", rotulo: departamento,
      marcador: construirMarcadorDepartamento(departamento, departamento),
    });
  }
  for (const p of participantes) {
    if (p.nome.toLowerCase().includes(filtroBusca)) {
      opcoes.push({ chave: `u${p.user_id}`, rotulo: p.nome, marcador: construirMarcadorUsuario(p.user_id, p.nome) });
    }
  }

  if (opcoes.length === 0) return null;

  return (
    <div className="absolute bottom-full mb-1 left-0 bg-neutral-800 border border-neutral-700 rounded-lg shadow-lg max-h-48 overflow-y-auto w-56 z-10">
      {opcoes.map((o) => (
        <button
          key={o.chave} type="button"
          onClick={() => onSelecionar(o.marcador)}
          className="block w-full text-left px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700"
        >
          @{o.rotulo}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verificar tipos do componente novo isoladamente**

Run (dentro de `web/`): `npx tsc --noEmit`
Expected: sem erros em `MencaoAutocomplete.tsx` (ainda não está sendo importado por ninguém, então erros de uso só apareceriam no próximo step).

- [ ] **Step 3: Integrar em `MensagensPainel.tsx`**

Substituir o conteúdo inteiro de `web/src/app/chat/_components/MensagensPainel.tsx` por:

```tsx
"use client";
import { useState, useEffect, useRef } from "react";
import type { ConversaChat, MensagemChat, ParticipanteChat } from "@/lib/types/chat";
import { api } from "@/lib/api";
import { TextoComMencoes } from "@/lib/chatMencoes";
import MencaoAutocomplete from "./MencaoAutocomplete";

export default function MensagensPainel({
  conversa, mensagens, usuarioIdAtual, digitandoUserId, onEnviar, onAbrirThread, onUpload,
}: {
  conversa: ConversaChat;
  mensagens: MensagemChat[];
  usuarioIdAtual: number | null;
  digitandoUserId: number | null;
  onEnviar: (texto: string, anexoId?: number) => void;
  onAbrirThread: (mensagem: MensagemChat) => void;
  onUpload: (arquivo: File) => Promise<number>;
}) {
  const [texto, setTexto] = useState("");
  const [enviandoArquivo, setEnviandoArquivo] = useState(false);
  const [participantes, setParticipantes] = useState<ParticipanteChat[]>([]);
  const [mencaoAtiva, setMencaoAtiva] = useState<{ inicio: number; filtro: string } | null>(null);
  const fimRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { fimRef.current?.scrollIntoView({ behavior: "smooth" }); }, [mensagens]);

  useEffect(() => {
    api.chat.listarParticipantes(conversa.id).then((r) => setParticipantes(r.data)).catch(() => setParticipantes([]));
  }, [conversa.id]);

  const enviar = () => {
    if (!texto.trim()) return;
    onEnviar(texto);
    setTexto("");
    setMencaoAtiva(null);
  };

  const aoDigitar = (e: React.ChangeEvent<HTMLInputElement>) => {
    const valor = e.target.value;
    setTexto(valor);
    const posicaoCursor = e.target.selectionStart ?? valor.length;
    const antesDoCursor = valor.slice(0, posicaoCursor);
    const indiceArroba = antesDoCursor.lastIndexOf("@");
    if (indiceArroba === -1) { setMencaoAtiva(null); return; }
    const trecho = antesDoCursor.slice(indiceArroba + 1);
    if (/\s/.test(trecho)) { setMencaoAtiva(null); return; }
    setMencaoAtiva({ inicio: indiceArroba, filtro: trecho });
  };

  const selecionarMencao = (marcador: string) => {
    if (!mencaoAtiva) return;
    const posicaoCursor = inputRef.current?.selectionStart ?? texto.length;
    const novoTexto = `${texto.slice(0, mencaoAtiva.inicio)}${marcador} ${texto.slice(posicaoCursor)}`;
    setTexto(novoTexto);
    setMencaoAtiva(null);
    inputRef.current?.focus();
  };

  const selecionarArquivo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const arquivo = e.target.files?.[0];
    if (!arquivo) return;
    setEnviandoArquivo(true);
    try {
      const anexoId = await onUpload(arquivo);
      onEnviar(`📎 ${arquivo.name}`, anexoId);
    } catch {
      // falha de upload — usuario ve que a mensagem nao apareceu e tenta de novo
    } finally {
      setEnviandoArquivo(false);
      e.target.value = "";
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <div className="bg-neutral-900 border-b border-neutral-800 px-4 py-3 shrink-0">
        <h2 className="text-sm font-bold text-neutral-200">{conversa.nome || conversa.cliente || "Conversa"}</h2>
        {digitandoUserId && <p className="text-[11px] text-neutral-500">digitando...</p>}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {mensagens.map((m) => (
          <div
            key={m.id}
            className={`max-w-[70%] rounded-lg px-3 py-2 text-sm ${
              m.remetente_id === usuarioIdAtual ? "bg-indigo-700 text-white ml-auto" : "bg-neutral-700 text-neutral-200"
            }`}
          >
            <p>
              {m.excluido_em
                ? "[mensagem excluída]"
                : <TextoComMencoes texto={m.texto ?? ""} participantes={participantes} />}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-[10px] opacity-60">{(m.created_at || "").slice(11, 16)}</p>
              {!m.excluido_em && (
                <button onClick={() => onAbrirThread(m)} className="text-[10px] underline opacity-70">
                  responder em thread
                </button>
              )}
            </div>
          </div>
        ))}
        <div ref={fimRef} />
      </div>

      <div className="p-3 border-t border-neutral-800 shrink-0 flex gap-2 relative">
        {mencaoAtiva && (
          <MencaoAutocomplete
            participantes={participantes}
            filtro={mencaoAtiva.filtro}
            mostrarTodos
            departamento={conversa.tipo === "canal_departamento" ? conversa.departamento : null}
            onSelecionar={selecionarMencao}
          />
        )}
        <label className="cursor-pointer text-neutral-400 px-2 flex items-center">
          📎
          <input type="file" className="hidden" onChange={selecionarArquivo} disabled={enviandoArquivo} />
        </label>
        <input
          ref={inputRef}
          type="text" value={texto} onChange={aoDigitar}
          onKeyDown={(e) => e.key === "Enter" && enviar()}
          placeholder="Digite sua mensagem..." autoFocus
          className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200"
        />
        <button onClick={enviar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">
          Enviar
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verificar tipos**

Run (dentro de `web/`): `npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/chat/_components/MencaoAutocomplete.tsx web/src/app/chat/_components/MensagensPainel.tsx
git commit -m "feat: autocomplete de mencao (@pessoa/@todos/@departamento) no painel de mensagens"
```

---

### Task 6: Renderização de menções no `ThreadPainel.tsx`

**Files:**
- Modify: `web/src/app/chat/_components/ThreadPainel.tsx`

**Interfaces:**
- Consumes: `TextoComMencoes` (Task 4), `api.chat.listarParticipantes` (Task 3).

Justificativa: mensagens exibidas na thread (mensagem-pai e respostas) podem conter marcadores de menção criados no painel principal — sem esta task, o marcador cru (`@[user:123:Nome]`) apareceria como texto literal na thread, quebrando visualmente a mesma mensagem que renderiza certo no painel principal. Escopo mínimo: só renderização (resolve nome atual contra a lista de participantes da conversa); sem autocomplete na resposta de thread — fica pra quando (se) houver demanda real de mencionar dentro de thread, YAGNI.

- [ ] **Step 1: Buscar participantes e trocar a renderização do texto**

Substituir o conteúdo inteiro de `web/src/app/chat/_components/ThreadPainel.tsx` por:

```tsx
"use client";
import { useState, useEffect } from "react";
import type { MensagemChat, ParticipanteChat } from "@/lib/types/chat";
import { api } from "@/lib/api";
import { TextoComMencoes } from "@/lib/chatMencoes";

export default function ThreadPainel({
  mensagemPai, onFechar, onEnviarResposta,
}: {
  mensagemPai: MensagemChat;
  onFechar: () => void;
  onEnviarResposta: (texto: string, threadPaiId: number) => void;
}) {
  const [respostas, setRespostas] = useState<MensagemChat[]>([]);
  const [participantes, setParticipantes] = useState<ParticipanteChat[]>([]);
  const [texto, setTexto] = useState("");

  useEffect(() => {
    api.chat.listarMensagens(mensagemPai.conversa_id).then((r) => {
      setRespostas(r.data.filter((m) => m.thread_pai_id === mensagemPai.id));
    }).catch(() => {});
  }, [mensagemPai.id, mensagemPai.conversa_id]);

  useEffect(() => {
    api.chat.listarParticipantes(mensagemPai.conversa_id).then((r) => setParticipantes(r.data)).catch(() => setParticipantes([]));
  }, [mensagemPai.conversa_id]);

  const enviar = () => {
    if (!texto.trim()) return;
    onEnviarResposta(texto, mensagemPai.id);
    setTexto("");
  };

  return (
    <div className="w-80 shrink-0 border-l border-neutral-800 bg-neutral-900 flex flex-col">
      <div className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between">
        <h3 className="text-sm font-bold text-neutral-200">Thread</h3>
        <button onClick={onFechar} className="text-neutral-500 text-xs">fechar</button>
      </div>
      <div className="p-3 border-b border-neutral-800 bg-neutral-800/50">
        <p className="text-sm text-neutral-300">
          <TextoComMencoes texto={mensagemPai.texto ?? ""} participantes={participantes} />
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {respostas.map((r) => (
          <div key={r.id} className="bg-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
            <TextoComMencoes texto={r.texto ?? ""} participantes={participantes} />
          </div>
        ))}
      </div>
      <div className="p-3 border-t border-neutral-800 flex gap-2">
        <input
          type="text" value={texto} onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && enviar()}
          placeholder="Responder na thread..."
          className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        />
        <button onClick={enviar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-2 rounded-lg">
          Enviar
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar tipos**

Run (dentro de `web/`): `npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/chat/_components/ThreadPainel.tsx
git commit -m "fix: renderiza mencoes tambem na thread, evita marcador cru visivel"
```

---

### Task 7: Verificação final

**Files:** nenhum (task de validação, sem código novo).

- [ ] **Step 1: Suíte completa do backend**

Run: `python -m pytest hermes_agents/tests/ -q`
Expected: todos os testes passam (nenhuma regressão nos módulos que não mudaram; `test_chat.py` com as novas classes de menção incluídas).

- [ ] **Step 2: Verificação de tipos do frontend inteiro**

Run (dentro de `web/`): `npx tsc --noEmit`
Expected: sem erros em nenhum arquivo do projeto.

- [ ] **Step 3: Revisão manual rápida do fluxo**

Conferir manualmente (leitura de código, sem servidor rodando neste ambiente):
- Os três caminhos de escrita de mensagem agora passam por validação de menção: REST dm/grupo/canal e WebSocket dm/grupo/canal chamam `enviar_mensagem` (que chama `_processar_mencoes` antes de persistir em `chat_mensagens`) — `routes/chat.py::chat_enviar_mensagem` e `routes/chat_ws.py::_processar_evento` (caminho `tipo == "enviar_mensagem"`) chamam a mesma função de `core/chat.py`. Já REST ticket desvia para `core.atendimento.adicionar_mensagem` (grava em `atend_mensagens`, não em `chat_mensagens`) e por isso não passa por `enviar_mensagem`; nesse caminho a rota aplica o wrapper público `processar_mencoes` (também de `core/chat.py`) diretamente sobre o texto antes de repassá-lo a `adicionar_mensagem`.
- `MencaoAutocomplete` nunca lista ninguém fora de `participantes` (vindo de `participantes_info`, que por sua vez vem de `participantes_ids`) — sem caminho de UI pra sugerir não-participante.

Se algum problema for encontrado nesta revisão, corrigir e commitar antes de considerar a task concluída. Se tudo estiver certo, não há commit novo nesta task.
