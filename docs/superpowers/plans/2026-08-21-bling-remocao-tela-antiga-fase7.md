# Bling — Remoção da Tela Antiga (Plano 7/7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar a migração do módulo Bling: repontar todas as referências de
`/integracoes/bling` para o módulo novo, apagar o diretório da tela antiga (hoje só um redirect
deixado pela fase 6a) e deixar `/integracoes` apenas com o card de status linkando para `/bling`.

**Architecture:** Nada de lógica nova. São quatro referências espalhadas pelo frontend
(`/integracoes`, `/config`, `/crm`, a aba de integrações da loja), a entrada de permissão em
`layout.tsx` e o diretório `web/src/app/integracoes/bling/`. Cada referência aponta pro destino
que faz sentido: quem manda "configurar a integração" vai pra `/bling/config` (onde vive o botão
de conectar OAuth); quem manda "abrir o módulo" vai pra `/bling`.

**Escopo do backend:** nenhum. A consolidação de rotas do `integrations_bp` e a remoção dos
webhooks duplicados (`/webhook/bling/pedido`, `/webhook/bling/pedido/v2`) já foram feitas na
fase 1 — hoje `routes/webhooks.py` tem só `/webhook/bling` (POST/GET) e `/webhook/bling/eventos`.
O endpoint `/api/test/bling` em `integrations_bp` **fica**: ele pertence à família de
diagnóstico `/api/test/*` (bling, shopee, ...), não é duplicata do módulo, e removê-lo sozinho
deixaria os irmãos inconsistentes.

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript.

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md` (item 7 da "Ordem de
implementação sugerida"; seção "Navegação")

## Global Constraints

- **Zero referência sobrevivente a `/integracoes/bling`.** A verificação final tem um grep; se
  ele achar qualquer linha, a fase não está pronta.
- **Remoção, não redirect.** O redirect foi um andaime da fase 6a pra não quebrar o build
  enquanto os componentes eram movidos. O spec pede a rota removida. Efeito colateral aceito e
  registrado: bookmark antigo passa a dar 404 em vez de redirecionar.
- **Verificação:** `cd web && npx tsc --noEmit` (exit 0) e `cd web && npm run build` (compila).
  Baseline verde ao começar.
- Nenhuma mudança em `hermes_agents/`.

## File Structure

| Arquivo | Mudança |
|---|---|
| `web/src/app/integracoes/page.tsx` | `INTEGRATION_LINKS.bling` passa a apontar `/bling` |
| `web/src/app/lojas/[id]/_components/IntegracoesTab.tsx` | `LINK_GERENCIAMENTO.bling` passa a apontar `/bling` |
| `web/src/app/config/page.tsx` | Atalho "Bling" passa a apontar `/bling/config` |
| `web/src/app/crm/page.tsx` | Mensagem de erro passa a citar `/bling/config` |
| `web/src/app/layout.tsx` | Entrada `"/integracoes/bling"` sai do `NAV_PERMS` |
| `web/src/app/integracoes/bling/` | Diretório apagado |

---

### Task 1: Repontar as quatro referências

**Files:**
- Modify: `web/src/app/integracoes/page.tsx` (constante `INTEGRATION_LINKS`, linha ~8)
- Modify: `web/src/app/lojas/[id]/_components/IntegracoesTab.tsx` (constante
  `LINK_GERENCIAMENTO`, linha ~23)
- Modify: `web/src/app/config/page.tsx` (atalho de integrações, linha ~50)
- Modify: `web/src/app/crm/page.tsx` (mensagem de erro de importação, linha ~39)

- [ ] **Step 1: Card em `/integracoes` e link de gerenciamento da loja**

Os dois abrem o módulo inteiro, então vão pra raiz `/bling`.

Em `web/src/app/integracoes/page.tsx`:

```tsx
const INTEGRATION_LINKS: Record<string, string> = {
  bling: "/bling",
  shopee: "/integracoes/shopee",
  hermes: "/integracoes/hermes",
  "shopee-ads": "/integracoes/shopee-ads",
};
```

Em `web/src/app/lojas/[id]/_components/IntegracoesTab.tsx`:

```tsx
const LINK_GERENCIAMENTO: Record<string, string> = {
  bling: "/bling",
  shopee: "/integracoes/shopee",
};
```

- [ ] **Step 2: Atalho em `/config` e mensagem do CRM**

Esses dois falam de **configurar/autorizar** a integração, então o destino certo é
`/bling/config` — a página que tem o botão "Conectar Bling" do OAuth. Mandar pra `/bling`
faria o usuário cair no dashboard e ter que caçar o submenu.

Em `web/src/app/config/page.tsx`:

```tsx
          <a href="/bling/config" className="text-xs text-indigo-400 hover:text-indigo-300 bg-neutral-800 px-3 py-1.5 rounded-lg">Bling</a>
```

Em `web/src/app/crm/page.tsx`:

```tsx
        if (d.auth_url) setBlingStatus(status => status + " — Autorize em /bling/config");
```

- [ ] **Step 3: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: compila sem erro.

- [ ] **Step 4: Commit**

```bash
git add web/src/app/integracoes/page.tsx "web/src/app/lojas/[id]/_components/IntegracoesTab.tsx" web/src/app/config/page.tsx web/src/app/crm/page.tsx
git commit -m "refactor: links de Bling apontam para o modulo /bling"
```

---

### Task 2: Apagar a tela antiga

**Files:**
- Delete: `web/src/app/integracoes/bling/page.tsx` (e o diretório, que fica vazio)
- Modify: `web/src/app/layout.tsx` (mapa `NAV_PERMS`, linha ~45)

- [ ] **Step 1: Confirmar que o diretório só tem o redirect**

Run: `find web/src/app/integracoes/bling -type f`
Expected: apenas `page.tsx`. Se aparecer qualquer outro arquivo, PARE — a fase 6a deveria ter
movido tudo pra `web/src/app/bling/_components/`, e um arquivo sobrando aqui significa que algo
não foi migrado.

- [ ] **Step 2: Apagar**

```bash
git rm -r web/src/app/integracoes/bling
```

- [ ] **Step 3: Tirar a entrada morta do mapa de permissões**

Em `web/src/app/layout.tsx`, o `NAV_PERMS` hoje tem as duas entradas (a antiga foi mantida na
fase 6a enquanto o redirect existia). Remova a linha da rota que deixou de existir, mantendo a
nova:

```tsx
  "/bling": "integrations:view",
```

(ou seja: apague a linha `"/integracoes/bling": "integrations:view",`)

- [ ] **Step 4: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: compila, e `/integracoes/bling` **não** aparece mais na listagem de rotas.

- [ ] **Step 5: Commit**

```bash
git add -A web/src/app/integracoes web/src/app/layout.tsx
git commit -m "refactor: remove a tela antiga /integracoes/bling"
```

---

### Task 3: Verificação final

- [ ] **Step 1: Nenhuma referência sobrevivente**

Run: `grep -rn "integracoes/bling" web/src/`
Expected: nenhuma linha.

- [ ] **Step 2: Typecheck e build limpos**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: compila; as dez rotas `/bling*` presentes e `/integracoes/bling` ausente.

- [ ] **Step 3: Backend intacto**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes (RH, compras segurança, RBAC lojas), nenhuma nova.
Esta fase não toca backend — qualquer mudança aqui significa que algo saiu do escopo.

- [ ] **Step 4: Commit final**

```bash
git status --porcelain
```

Se não houver mudança de código real:

```bash
git commit -m "test: verificacao final da remocao da tela antiga do Bling (fase 7)" --allow-empty
```
