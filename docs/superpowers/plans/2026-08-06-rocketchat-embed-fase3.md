# Rocket.Chat — Embed em /chat (Fase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o chat interno custom em `/chat` por um iframe do Rocket.Chat, com fallback visual quando a instância ainda não está disponível.

**Architecture:** `web/src/app/chat/page.tsx` deixa de renderizar sidebar/mensagens/WebSocket próprios e passa a renderizar um único componente novo, `RocketChatFrame`, que faz um health check (via `fetch` em modo `no-cors`, pra não depender de CORS habilitado no Rocket.Chat) contra `NEXT_PUBLIC_ROCKETCHAT_URL` antes de montar o `<iframe src="...?layout=embedded">`. A URL é uma env var de build (o frontend é exportado como estático e servido pelo Flask — não existe servidor Node em produção, então a env var precisa estar presente no momento do `next build`, não em runtime). Os componentes antigos do chat (`ConversaSidebar.tsx`, `MensagensPainel.tsx`, `ThreadPainel.tsx`, `NovaConversaModal.tsx`, `MencaoAutocomplete.tsx`) ficam no repo sem uso — não são apagados nesta fase (decisão do spec, permite rollback revertendo só `page.tsx`).

**Tech Stack:** Next.js 15 (App Router, `output: "export"` em produção), React 19, Tailwind v4 (utilitários `neutral-*`/`indigo-*` já retemados pro instrument-panel via `@theme` em `web/src/app/globals.css` — usar classes stock, sem inline style), Playwright para E2E (não há framework de teste unitário no frontend deste repo).

## Global Constraints

- Sem novas dependências no `web/package.json` — `fetch` nativo, sem lib de HTTP.
- Sem inline `style={{}}` para cor — usar classes Tailwind (`neutral-*`, `indigo-*`) que já resolvem pro design system via `@theme`.
- Nomes de variáveis, textos de UI e comentários em português, mesmo padrão do resto de `web/src/app/`.
- Não apagar nenhum arquivo de `web/src/app/chat/_components/` nem `web/src/lib/useChatSocket.ts` (este último ainda é usado por `web/src/app/atendimento/tickets/[id]/`).
- Não tocar em `web/src/app/atendimento/tickets/[id]/` nem em nada de backend (`hermes_agents/routes/chat.py`, `chat_ws.py`, `core/chat.py`) — fora de escopo desta fase.
- Testes E2E seguem o padrão de `web/tests/e2e/tickets.spec.ts`: pulam com `test.skip` quando a env var necessária não está configurada, sem hardcodar valor real no arquivo de teste.

---

### Task 1: Componente `RocketChatFrame` + reescrita de `page.tsx`

**Files:**
- Create: `web/src/app/chat/_components/RocketChatFrame.tsx`
- Modify: `web/src/app/chat/page.tsx` (reescrita completa — remove toda a lógica atual de sidebar/mensagens/socket)
- Test: `web/tests/e2e/chat.spec.ts`

**Interfaces:**
- Produces: `RocketChatFrame` — componente React default-export, sem props (lê `process.env.NEXT_PUBLIC_ROCKETCHAT_URL` direto). Renderiza um de 4 estados: sem configuração, carregando, indisponível (com botão "Tentar novamente"), ou o `<iframe title="Chat">`.

- [ ] **Step 1: Escrever o teste E2E (falhando)**

Criar `web/tests/e2e/chat.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

// RocketChatFrame le NEXT_PUBLIC_ROCKETCHAT_URL em tempo de build/dev do
// Next — precisa estar setada ANTES de rodar `npm run dev` (reinicie o dev
// server se a variavel mudar). Mesmo padrao de tickets.spec.ts: pula sem
// hardcodar URL de teste real no arquivo.
const ROCKETCHAT_URL = process.env.NEXT_PUBLIC_ROCKETCHAT_URL || "";

test.beforeEach(async () => {
  test.skip(!ROCKETCHAT_URL, "NEXT_PUBLIC_ROCKETCHAT_URL nao configurada — pulei o teste E2E do /chat");
});

test("mostra estado indisponivel quando o Rocket.Chat nao responde, com botao de retry", async ({ page }) => {
  await page.route(`${ROCKETCHAT_URL}/api/v1/info`, (route) => route.abort());

  await page.goto("/chat");

  await expect(page.getByText("Chat indisponível no momento.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
});

test("retry apos infra voltar troca o estado indisponivel pelo iframe", async ({ page }) => {
  let disponivel = false;
  await page.route(`${ROCKETCHAT_URL}/api/v1/info`, (route) =>
    disponivel ? route.fulfill({ status: 200, body: "{}" }) : route.abort()
  );

  await page.goto("/chat");
  await expect(page.getByText("Chat indisponível no momento.")).toBeVisible();

  disponivel = true;
  await page.getByRole("button", { name: "Tentar novamente" }).click();

  await expect(page.locator('iframe[title="Chat"]')).toHaveAttribute(
    "src",
    `${ROCKETCHAT_URL}?layout=embedded`
  );
});
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Em um terminal, dentro de `web/`:
```bash
NEXT_PUBLIC_ROCKETCHAT_URL=https://chat.exemplo.teste npm run dev
```
Em outro terminal, dentro de `web/`:
```bash
NEXT_PUBLIC_ROCKETCHAT_URL=https://chat.exemplo.teste npm run test:e2e -- chat.spec.ts
```
Expected: FAIL — a página `/chat` atual não tem o texto "Chat indisponível no momento." nem `iframe[title="Chat"]" (ainda é a UI antiga de sidebar/DM).

- [ ] **Step 3: Criar `RocketChatFrame.tsx`**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";

const ROCKETCHAT_URL = process.env.NEXT_PUBLIC_ROCKETCHAT_URL;
const TIMEOUT_MS = 5000;

type Status = "nao_configurado" | "carregando" | "indisponivel" | "pronto";

async function estaDisponivel(url: string): Promise<boolean> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    // no-cors: nao precisamos ler a resposta, so' confirmar que o host
    // responde. Evita depender de CORS habilitado no Rocket.Chat — um
    // fetch no-cors resolve pra qualquer resposta HTTP alcancada e so'
    // rejeita em falha real de rede/timeout.
    await fetch(`${url}/api/v1/info`, {
      mode: "no-cors",
      cache: "no-store",
      signal: controller.signal,
    });
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

export default function RocketChatFrame() {
  const [status, setStatus] = useState<Status>(ROCKETCHAT_URL ? "carregando" : "nao_configurado");

  const verificar = useCallback(() => {
    if (!ROCKETCHAT_URL) {
      setStatus("nao_configurado");
      return;
    }
    setStatus("carregando");
    estaDisponivel(ROCKETCHAT_URL).then((ok) => setStatus(ok ? "pronto" : "indisponivel"));
  }, []);

  useEffect(() => {
    verificar();
  }, [verificar]);

  if (status === "nao_configurado") {
    return (
      <div className="h-screen w-full flex items-center justify-center text-neutral-500 text-sm">
        Chat não configurado (NEXT_PUBLIC_ROCKETCHAT_URL ausente).
      </div>
    );
  }

  if (status === "carregando") {
    return (
      <div className="h-screen w-full flex items-center justify-center text-neutral-500 text-sm">
        Carregando chat...
      </div>
    );
  }

  if (status === "indisponivel") {
    return (
      <div className="h-screen w-full flex flex-col items-center justify-center gap-3 text-neutral-500 text-sm">
        <span>Chat indisponível no momento.</span>
        <button
          onClick={verificar}
          className="px-3 py-1.5 rounded bg-neutral-800 text-neutral-200 text-xs hover:bg-neutral-750 transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  return (
    <iframe
      src={`${ROCKETCHAT_URL}?layout=embedded`}
      title="Chat"
      className="h-screen w-full border-0"
      allow="camera; microphone; display-capture; clipboard-write"
    />
  );
}
```

- [ ] **Step 4: Reescrever `page.tsx`**

Substituir todo o conteúdo de `web/src/app/chat/page.tsx` por:

```tsx
import RocketChatFrame from "./_components/RocketChatFrame";

export default function ChatPage() {
  return <RocketChatFrame />;
}
```

- [ ] **Step 5: Rodar o teste e confirmar que passa**

```bash
NEXT_PUBLIC_ROCKETCHAT_URL=https://chat.exemplo.teste npm run test:e2e -- chat.spec.ts
```
Expected: PASS (2 testes).

- [ ] **Step 6: Verificar tipos**

```bash
cd web && npx tsc --noEmit
```
Expected: sem erros. Confirma que remover os imports antigos de `page.tsx` não deixou nada quebrado (os componentes órfãos em `_components/` não são compilados por ninguém que os importe mais, mas continuam existindo no disco).

- [ ] **Step 7: Commit**

```bash
git add web/src/app/chat/page.tsx web/src/app/chat/_components/RocketChatFrame.tsx web/tests/e2e/chat.spec.ts
git commit -m "feat: embute Rocket.Chat em /chat via iframe com fallback de indisponibilidade"
```

---

### Task 2: Env var de build no Dockerfile de produção

**Files:**
- Modify: `docker/production/Dockerfile:13` (linha do `ENV NEXT_STATIC_EXPORT=true`)

**Interfaces:**
- Consumes: `RocketChatFrame` (Task 1) — lê `process.env.NEXT_PUBLIC_ROCKETCHAT_URL` no bundle gerado por `npm run build`.
- Produces: nada consumido por outra task — é o fim da cadeia (env var chega no bundle estático).

- [ ] **Step 1: Adicionar a env var no Dockerfile**

Em `docker/production/Dockerfile`, logo após a linha `ENV NEXT_STATIC_EXPORT=true` (linha 13):

```dockerfile
ENV NEXT_STATIC_EXPORT=true
ENV NEXT_PUBLIC_ROCKETCHAT_URL=https://chat.athena.zoikom.site
RUN npm run build
```

(Fixo, não é segredo nem varia por ambiente — só existe um ambiente de produção neste projeto, mesmo padrão de `ENV API_PORT=3000` já usado no mesmo arquivo.)

- [ ] **Step 2: Build local pra confirmar que a URL entra no bundle**

Reproduz o que o Dockerfile faz, sem subir container:
```bash
cd web
NEXT_STATIC_EXPORT=true NEXT_PUBLIC_ROCKETCHAT_URL=https://chat.athena.zoikom.site npm run build
```
Expected: build termina sem erro, gera `web/out/`.

- [ ] **Step 3: Confirmar que a URL foi inlinada no JS gerado**

```bash
grep -r "chat.athena.zoikom.site" web/out/ | head -1
```
Expected: pelo menos uma ocorrência (a env var foi resolvida em build-time, não fica como `process.env.X` no bundle final).

- [ ] **Step 4: Limpar artefato de build local**

```bash
rm -rf web/out
```
(Já é gerado pelo Dockerfile em produção; não precisa ficar versionado nem sujar o working tree local. Confirmar com `git status` que `web/out/` não aparece como novo diretório rastreado — se `web/.gitignore` já ignora `out/`, nada a fazer além do `rm -rf`.)

- [ ] **Step 5: Commit**

```bash
git add docker/production/Dockerfile
git commit -m "build: expõe URL do Rocket.Chat pro frontend em build-time"
```

---

## Runbook manual (fora do ciclo de tasks — requer acesso ao Coolify/DNS, não é executável por um agente de código)

Depois que as Tasks 1 e 2 estiverem commitadas (e podem ir pra produção antes disso: o estado "indisponível" cobre o caso da infra ainda não existir), execute manualmente, nesta ordem, seguindo `deploy/rocketchat/README.md`:

1. Gerar as credenciais do client OAuth (passo 1 do README).
2. Criar o recurso "Docker Compose" no Coolify a partir de `deploy/rocketchat/docker-compose.yml`, configurar as env vars do `.env.example`, apontar o domínio `chat.athena.zoikom.site` pra porta 3000 do serviço `rocketchat` (passo 2 do README).
3. Configurar `ROCKETCHAT_OAUTH_CLIENT_ID`/`ROCKETCHAT_OAUTH_CLIENT_SECRET`/`ROCKETCHAT_OAUTH_REDIRECT_URI`/`HERMES_LOGIN_URL` no serviço Flask do Hermes, no mesmo Coolify (passo 3 do README).
4. Smoke test do README (passos 1-5): subir o recurso, completar o wizard de admin local, confirmar botão "Hermes" na tela de login, testar o fluxo de SSO ponta a ponta.
5. **Só depois do passo 4 validado:** em Administração → Layout → Iframe Integration (nome exato do campo a confirmar contra a versão 8.6.1 instalada), liberar o Rocket.Chat pra ser carregado dentro de um frame do domínio `athena.zoikom.site`.
6. Acessar `https://athena.zoikom.site/chat` em produção (com as Tasks 1+2 já deployadas) e confirmar: estado deixa de ser "indisponível" sozinho (ou após clicar "Tentar novamente"), o iframe carrega, o botão "Hermes" aparece dentro dele, login funciona, e uma chamada de vídeo abre (valida o `allow=` do iframe).
