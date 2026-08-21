# Bling — Frontend do Módulo, Fundação (Plano 6a/N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o módulo `/bling` no frontend com layout e submenu próprios, migrar pra ele as
cinco telas que já existem hoje como abas em `/integracoes/bling` (dashboard, produtos, pedidos
de venda, financeiro, configurações), e consolidar as chamadas Bling do `api.ts` num helper que
envia o header `Authorization` — sem o qual toda rota Bling protegida por RBAC responde 403 no
navegador.

**Architecture:** As ~40 funções Bling em `web/src/lib/api.ts` usam `fetch` cru hoje, sem token.
Elas não podem simplesmente passar a usar o `request<T>()` genérico do arquivo, porque
`request()` **lança** em resposta não-ok, enquanto as funções Bling devolvem `{data: [], error}`
e os componentes checam `if (r.error)` — trocar o contrato quebraria as telas em silêncio. A
solução é um helper novo `blingFetch<T>()` que injeta `Authorization`/`Content-Type` e trata 401
igual ao `request()`, mas **preserva** o contrato tolerante (devolve `{error}` em vez de lançar).
As páginas novas reaproveitam os componentes que já funcionam — eles são movidos de
`web/src/app/integracoes/bling/_components/` para `web/src/app/bling/_components/`, não
reescritos.

**Decisão de escopo (confirmada com o usuário):** a fase 6 foi dividida. Esta (6a) entrega a
fundação + as 5 telas migradas. A 6b entrega as 5 telas novas (pedidos de compra, situações,
canais, notas com abas NF-e/NFC-e/NFS-e, plano de contas). O submenu do layout lista **apenas as
rotas que já existem** em cada fase — link pra página inexistente dá 404, então a 6b acrescenta
as próprias entradas quando criar as páginas.

**Decisão sobre a tela antiga:** mover os componentes deixaria `/integracoes/bling` quebrada.
Manter duas cópias divergindo é pior. Então esta fase substitui `web/src/app/integracoes/bling/page.tsx`
por um redirect para `/bling`. A remoção do diretório e o ajuste do card em `/integracoes`
continuam sendo trabalho da fase 7.

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript, Tailwind 4.

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md` (seções "Navegação" e
"Frontend")

## Global Constraints

- **Nenhum componente existente muda de contrato.** `blingFetch` devolve `{error}` em vez de
  lançar, exatamente como o `fetch` cru fazia. Se algum componente precisar mudar pra acomodar a
  Task 1, a Task 1 está errada.
- **Verificação a cada task:** `cd web && npx tsc --noEmit` (esperado: exit 0, sem saída) e
  `cd web && npm run build` (esperado: build completo sem erro). Baseline confirmado verde antes
  desta fase — qualquer erro que aparecer é novo e é seu.
- **Não reescreva os componentes que já funcionam.** Dashboard, ProductsTab, OrdersTab,
  VendasTab, FinancialTab, ConfigTab e os modais são movidos com `git mv` e ajustados só no
  necessário (caminho de import). O único que ganha funcionalidade nova é o ConfigTab (toggle de
  ambiente, Task 5).
- **Sem dependência nova.** Nada de biblioteca de UI, state manager ou fetch client — o projeto
  usa React + Tailwind puro e `fetch`.
- **Rotas de escrita do backend exigem RBAC.** `POST /api/bling/ambiente` exige
  `bling.sincronizar`; `POST /api/bling/{nfce,nfse}/sincronizar` exigem `financeiro.ver`;
  `POST /api/bling/pedidos-compra/sincronizar` exige `compras.editar`. É exatamente por isso que
  a Task 1 vem primeiro: sem o header, essas telas nascem quebradas.
- Commits em português, formato `<tipo>: <descrição>`, sem atribuição.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `web/src/lib/api.ts` | Helper `blingFetch` + todas as chamadas Bling autenticadas (Task 1) e as funções novas do módulo (Task 2) |
| `web/src/app/bling/layout.tsx` | Layout do módulo: cabeçalho + submenu lateral com as rotas existentes |
| `web/src/app/bling/page.tsx` | Dashboard do módulo (`/bling`) |
| `web/src/app/bling/produtos/page.tsx` | Produtos + modais de estoque/cadastro |
| `web/src/app/bling/pedidos-venda/page.tsx` | Resumo de vendas + lista de pedidos com sync |
| `web/src/app/bling/financeiro/page.tsx` | Contas a receber/pagar + notas fiscais (proxy ao vivo) |
| `web/src/app/bling/config/page.tsx` | Credenciais, webhooks, notificações e toggle de ambiente |
| `web/src/app/bling/_components/*` | Componentes movidos de `integracoes/bling/_components/` |
| `web/src/app/integracoes/bling/page.tsx` | Vira redirect para `/bling` |
| `web/src/app/layout.tsx` | Entrada "Bling" com submenu em `NAV_GROUPS` + mapa de permissão |

---

### Task 1: `blingFetch` — autenticar todas as chamadas Bling sem mudar contrato

**Files:**
- Modify: `web/src/lib/api.ts` (bloco "Bling API Methods (standalone, usam fetch direto)", a
  partir do comentário por volta da linha 1479 até o fim do bloco, por volta da linha 1720)

**Interfaces:**
- Produces: `blingFetch<T>(path: string, options?: RequestInit): Promise<T>` — função interna do
  módulo (não exportada), usada por todas as funções Bling do arquivo.
- Consumes: `API_BASE` (`""`) e `handleUnauthorized()`, ambos já definidos no topo de `api.ts`.

- [ ] **Step 1: Ler o bloco inteiro antes de editar**

Rode `grep -n 'fetch("/api/bling\|fetch(`/api/bling\|fetch("/webhook/bling' web/src/lib/api.ts`
e anote quantas ocorrências existem. Esse número é o alvo: ao final da task ele tem que ser 0, e
o número de chamadas a `blingFetch` tem que ser igual ao número anotado (menos as que abrem
janela, ver Step 4).

- [ ] **Step 2: Adicionar o helper**

Em `web/src/lib/api.ts`, logo antes do comentário
`// ── Bling API Methods (standalone, usam fetch direto) ──`, inserir:

```ts
// ── Bling: fetch autenticado com contrato tolerante ──
// As rotas Bling protegidas por RBAC (POST /ambiente, /nfce/sincronizar,
// /pedidos-compra/sincronizar, CRUD de situacoes) respondem 403 sem o header
// Authorization — e todas as chamadas Bling deste arquivo usavam fetch cru,
// sem token. Nao da' pra reaproveitar request<T>() aqui porque ele LANCA em
// resposta nao-ok, enquanto os componentes Bling checam `if (r.error)`;
// trocar isso quebraria as telas em silencio. Entao: mesmo header e mesmo
// tratamento de 401 do request(), contrato de retorno preservado.
async function blingFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const method = options?.method || "GET";
  if (method !== "GET" && method !== "HEAD") headers["Content-Type"] = "application/json";
  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: "include" });
    if (res.status === 401) handleUnauthorized();
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
      return { data: [], error: `resposta nao-JSON (HTTP ${res.status})` } as T;
    }
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      return { data: [], ...(body || {}),
               error: body?.error || body?.erro || `HTTP ${res.status}` } as T;
    }
    return body as T;
  } catch (e) {
    return { data: [], error: e instanceof Error ? e.message : "falha de rede" } as T;
  }
}
```

- [ ] **Step 3: Converter as chamadas**

Toda função Bling do bloco troca o corpo. O padrão de conversão:

```ts
// antes
export async function getBlingStatus(): Promise<BlingStatus> {
  const res = await fetch("/api/bling/status");
  return res.json();
}

// depois
export async function getBlingStatus(): Promise<BlingStatus> {
  return blingFetch<BlingStatus>("/api/bling/status");
}
```

```ts
// antes — com checagem manual de ok/content-type
export async function listarBlingProdutos(pagina = 1, limite = 100): Promise<BlingProdutosResponse> {
  const res = await fetch(`/api/bling/produtos?pagina=${pagina}&limite=${limite}`);
  if (!res.ok) return { data: [], error: `HTTP ${res.status}` };
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return { data: [], error: "resposta nao-JSON" };
  return res.json();
}

// depois — blingFetch ja faz as duas checagens
export async function listarBlingProdutos(pagina = 1, limite = 100): Promise<BlingProdutosResponse> {
  return blingFetch<BlingProdutosResponse>(`/api/bling/produtos?pagina=${pagina}&limite=${limite}`);
}
```

```ts
// antes — POST/PUT/DELETE
export async function criarBlingProduto(dados: unknown) {
  const res = await fetch("/api/bling/produtos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });
  return res.json();
}

// depois — blingFetch ja poe o Content-Type em metodo de escrita
export async function criarBlingProduto(dados: unknown) {
  return blingFetch("/api/bling/produtos", { method: "POST", body: JSON.stringify(dados) });
}
```

Aplique a todas as funções do bloco, incluindo `listarBlingEventos` (`/webhook/bling/eventos` —
caminho diferente, mesmo tratamento).

- [ ] **Step 4: Não converter as duas que abrem janela**

`baixarNFeXML` e `abrirNFeDANFE` usam `window.open(...)`, não `fetch` — deixe como estão. Anote
no relatório final que elas continuam sem token: por serem navegação do browser, o header não
existe nesse caminho. Se essas rotas ganharem RBAC depois, vão precisar de outra abordagem
(token na query string ou download via blob) — fora do escopo desta fase.

- [ ] **Step 5: Confirmar que não sobrou fetch cru**

Run: `grep -n 'fetch("/api/bling\|fetch(`/api/bling\|fetch("/webhook/bling' web/src/lib/api.ts`
Expected: nenhuma linha (as ocorrências restantes de `fetch` no arquivo devem ser as de
`window.open`, do upload multipart e do `request()` genérico).

- [ ] **Step 6: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0, sem saída.

Run: `cd web && npm run build`
Expected: build completo sem erro.

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "fix: chamadas Bling do frontend passam a enviar Authorization (rotas RBAC davam 403)"
```

---

### Task 2: Funções de API para o módulo novo

**Files:**
- Modify: `web/src/lib/api.ts` (adicionar ao fim do bloco Bling, depois das funções convertidas
  na Task 1)

**Interfaces:**
- Consumes: `blingFetch` (Task 1)
- Produces (usadas pelas Tasks 3-5 e pela fase 6b):
  - `getBlingAmbiente(): Promise<{ ambiente: string; base_url: string; ambientes: string[]; error?: string }>`
  - `setBlingAmbiente(ambiente: string): Promise<{ ambiente?: string; error?: string }>`
  - `listarBlingPedidosCompra(ambiente?: string): Promise<{ data?: BlingPedidoCompraLocal[]; error?: string }>`
  - `sincronizarBlingPedidosCompra(): Promise<{ sync?: number; erros?: string[]; error?: string }>`
  - `receberBlingPedidoCompra(id: number): Promise<{ error?: string }>`
  - `listarBlingSituacoes(): Promise<{ data?: BlingSituacao[]; error?: string }>`
  - `criarBlingSituacao(dados: Partial<BlingSituacao>): Promise<{ error?: string }>`
  - `atualizarBlingSituacao(id: number, dados: Partial<BlingSituacao>): Promise<{ error?: string }>`
  - `deletarBlingSituacao(id: number): Promise<{ error?: string }>`
  - `sincronizarBlingSituacoes(): Promise<{ sync?: number; error?: string }>`
  - `listarBlingCanais(): Promise<{ data?: BlingCanal[]; error?: string }>`
  - `sincronizarBlingCanais(): Promise<{ sync?: number; error?: string }>`
  - `listarBlingNotasLocais(tipo?: string, ambiente?: string): Promise<{ data?: BlingNotaLocal[]; error?: string } | BlingNotaLocal[]>`
  - `sincronizarBlingNfce(): Promise<{ sync?: number; error?: string }>`
  - `sincronizarBlingNfse(): Promise<{ sync?: number; error?: string }>`
  - `listarBlingPlanoContas(): Promise<{ data?: BlingContaContabil[]; error?: string }>`
  - `sincronizarBlingPlanoContas(): Promise<{ sync?: number; error?: string }>`

- [ ] **Step 1: Adicionar os tipos**

No mesmo arquivo, junto dos outros `export interface Bling*`:

```ts
export interface BlingAmbienteInfo {
  ambiente: string;
  base_url: string;
  ambientes: string[];
  error?: string;
}

export interface BlingPedidoCompraLocal {
  id: number;
  numero: string;
  fornecedor_id: number | null;
  valor_total: number;
  status: string;
  data_emissao: string | null;
  data_entrega_prevista: string | null;
  bling_id: number | null;
  ambiente: string;
}

export interface BlingSituacao {
  id: number;
  bling_id?: number | null;
  nome: string;
  cor?: string | null;
  modulo?: string | null;
}

export interface BlingCanal {
  id: number;
  nome: string;
  bling_id?: number | null;
  tipo?: string | null;
}

export interface BlingNotaLocal {
  id: number;
  numero: string;
  chave_acesso: string | null;
  tipo_documento: string;
  ambiente: string;
  status: string;
  data_emissao: string | null;
  valor_nf: number;
  contato_nome: string | null;
  bling_id: number | null;
}

export interface BlingContaContabil {
  id: number;
  codigo: string;
  nome: string;
  tipo: string | null;
  natureza: string | null;
  conta_pai_id: number | null;
  bling_id: number | null;
}
```

Nota: as rotas de leitura local (`/api/bling/notas`, `/api/bling/pedidos-compra`,
`/api/bling/plano-contas`, `/api/bling/canais`) devolvem um **array puro** no caminho feliz
(`jsonify(lista)`) e um objeto `{error}` com status 500 no caminho de erro. Por isso as funções
de listagem abaixo normalizam pra sempre devolver `{ data, error }` — as telas não devem ter que
lidar com as duas formas.

- [ ] **Step 2: Adicionar as funções**

```ts
// ── Bling: modulo novo (fase 6) ──

// As rotas de leitura local devolvem array puro no sucesso e {error} no erro.
// Normaliza pra {data, error} pra que as telas tenham um contrato so'.
async function blingLista<T>(path: string): Promise<{ data: T[]; error?: string }> {
  const r = await blingFetch<T[] | { error?: string; data?: T[] }>(path);
  if (Array.isArray(r)) return { data: r };
  return { data: r?.data || [], error: r?.error };
}

export async function getBlingAmbiente(): Promise<BlingAmbienteInfo> {
  return blingFetch<BlingAmbienteInfo>("/api/bling/ambiente");
}

export async function setBlingAmbiente(ambiente: string): Promise<{ ambiente?: string; error?: string }> {
  return blingFetch("/api/bling/ambiente", { method: "POST", body: JSON.stringify({ ambiente }) });
}

export async function listarBlingPedidosCompra(ambiente = "producao") {
  return blingLista<BlingPedidoCompraLocal>(`/api/bling/pedidos-compra?ambiente=${encodeURIComponent(ambiente)}`);
}

export async function sincronizarBlingPedidosCompra(): Promise<{ sync?: number; erros?: string[]; error?: string }> {
  return blingFetch("/api/bling/pedidos-compra/sincronizar", { method: "POST" });
}

export async function receberBlingPedidoCompra(id: number): Promise<{ error?: string }> {
  return blingFetch(`/api/bling/pedidos-compra/${id}/receber`, { method: "POST" });
}

export async function listarBlingSituacoes() {
  return blingLista<BlingSituacao>("/api/bling/situacoes");
}

export async function criarBlingSituacao(dados: Partial<BlingSituacao>): Promise<{ error?: string }> {
  return blingFetch("/api/bling/situacoes", { method: "POST", body: JSON.stringify(dados) });
}

export async function atualizarBlingSituacao(id: number, dados: Partial<BlingSituacao>): Promise<{ error?: string }> {
  return blingFetch(`/api/bling/situacoes/${id}`, { method: "PUT", body: JSON.stringify(dados) });
}

export async function deletarBlingSituacao(id: number): Promise<{ error?: string }> {
  return blingFetch(`/api/bling/situacoes/${id}`, { method: "DELETE" });
}

export async function sincronizarBlingSituacoes(): Promise<{ sync?: number; error?: string }> {
  return blingFetch("/api/bling/situacoes/sincronizar", { method: "POST" });
}

export async function listarBlingCanais() {
  return blingLista<BlingCanal>("/api/bling/canais");
}

export async function sincronizarBlingCanais(): Promise<{ sync?: number; error?: string }> {
  return blingFetch("/api/bling/canais/sincronizar", { method: "POST" });
}

export async function listarBlingNotasLocais(tipo = "", ambiente = "producao") {
  const q = new URLSearchParams();
  if (tipo) q.set("tipo", tipo);
  if (ambiente) q.set("ambiente", ambiente);
  return blingLista<BlingNotaLocal>(`/api/bling/notas?${q.toString()}`);
}

export async function sincronizarBlingNfce(): Promise<{ sync?: number; error?: string }> {
  return blingFetch("/api/bling/nfce/sincronizar", { method: "POST" });
}

export async function sincronizarBlingNfse(): Promise<{ sync?: number; error?: string }> {
  return blingFetch("/api/bling/nfse/sincronizar", { method: "POST" });
}

export async function listarBlingPlanoContas() {
  return blingLista<BlingContaContabil>("/api/bling/plano-contas");
}

export async function sincronizarBlingPlanoContas(): Promise<{ sync?: number; error?: string }> {
  return blingFetch("/api/bling/plano-contas/sincronizar", { method: "POST" });
}
```

- [ ] **Step 3: Conferir os caminhos contra o backend**

Antes de commitar, confirme cada rota rodando:

```bash
grep -n 'bling_bp.route' hermes_agents/routes/integrations.py
```

Cada `path` usado acima tem que aparecer nessa lista (com o prefixo `/api/bling` do blueprint).
Se algum não aparecer, corrija o caminho no `api.ts` — não invente rota no backend nesta fase.

- [ ] **Step 4: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: build completo sem erro. (As funções ainda não têm chamador — isso não gera erro; o
Next não reclama de export não usado numa lib.)

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: funcoes de API do modulo Bling (ambiente, pedidos de compra, situacoes, canais, notas, plano de contas)"
```

---

### Task 3: Layout do módulo `/bling` + dashboard

**Files:**
- Create: `web/src/app/bling/layout.tsx`
- Create: `web/src/app/bling/page.tsx`
- Move: `web/src/app/integracoes/bling/_components/` → `web/src/app/bling/_components/`
- Modify: `web/src/app/integracoes/bling/page.tsx` (vira redirect)

**Interfaces:**
- Consumes: componentes movidos (`BlingDashboard` etc), `getBlingAmbiente` (Task 2)
- Produces: rota `/bling` e o layout que envolve todas as sub-rotas do módulo

- [ ] **Step 1: Mover os componentes**

```bash
mkdir -p web/src/app/bling
git mv web/src/app/integracoes/bling/_components web/src/app/bling/_components
```

Os componentes importam `@/app/_components/Icon` (caminho absoluto, não muda) e `./shared/...`
(relativo dentro da pasta movida, não muda). Confirme com:

```bash
grep -rn 'from "\.\./' web/src/app/bling/_components/ | head
```

Se aparecer algum import relativo subindo de nível (`../`), corrija pra caminho absoluto
(`@/app/...`) — ele apontava pra fora da pasta e quebrou com a movida.

- [ ] **Step 2: Criar o layout com submenu**

`web/src/app/bling/layout.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Icon from "@/app/_components/Icon";
import { getBlingAmbiente } from "@/lib/api";

// Submenu lista apenas as rotas que ja existem. A fase 6b acrescenta as
// proprias entradas quando criar as paginas — link pra rota inexistente da 404.
const SUBMENU = [
  { href: "/bling", label: "Dashboard", icon: "dashboard" },
  { href: "/bling/produtos", label: "Produtos", icon: "produtos" },
  { href: "/bling/pedidos-venda", label: "Pedidos de Venda", icon: "vendas" },
  { href: "/bling/financeiro", label: "Financeiro", icon: "financeiro" },
  { href: "/bling/config", label: "Configurações", icon: "config" },
];

export default function BlingLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [ambiente, setAmbiente] = useState<string>("");

  useEffect(() => {
    getBlingAmbiente().then((r) => setAmbiente(r.ambiente || "")).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Bling</h1>
          <p className="text-xs text-neutral-500 mt-1">Integração ERP — catálogo, vendas, financeiro e fiscal</p>
        </div>
        {ambiente === "homologacao" && (
          <span className="shrink-0 px-2 py-1 rounded-md text-[11px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            Homologação
          </span>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        <nav className="lg:w-52 shrink-0">
          <ul className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible">
            {SUBMENU.map((item) => {
              const ativo = pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs whitespace-nowrap transition-colors ${
                      ativo ? "bg-indigo-600 text-white" : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                    }`}
                  >
                    <Icon name={item.icon} size={14} />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </div>
  );
}
```

Atenção ao `Icon`: confirme que os nomes usados (`dashboard`, `produtos`, `vendas`,
`financeiro`, `config`) existem em `web/src/app/_components/Icon.tsx`. Rode
`grep -n '"config"\|"financeiro"\|"produtos"\|"vendas"\|"dashboard"' web/src/app/_components/Icon.tsx`.
Para qualquer nome que não existir, use um que exista (a página antiga usava `"__gear__"` com SVG
inline pra config justamente porque não havia ícone de engrenagem — se for o caso, use `"config"`
só se existir, senão troque por um nome válido da lista).

- [ ] **Step 3: Criar a página do dashboard**

`web/src/app/bling/page.tsx`:

```tsx
"use client";

import BlingDashboard from "./_components/BlingDashboard";

export default function BlingDashboardPage() {
  return <BlingDashboard />;
}
```

- [ ] **Step 4: Redirecionar a tela antiga**

Substitua todo o conteúdo de `web/src/app/integracoes/bling/page.tsx` por:

```tsx
import { redirect } from "next/navigation";

// O modulo Bling agora vive em /bling (fase 6). A remocao definitiva desta
// rota e o ajuste do card em /integracoes sao trabalho da fase 7.
export default function BlingLegacyPage() {
  redirect("/bling");
}
```

- [ ] **Step 5: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0. Se acusar módulo não encontrado apontando pra
`integracoes/bling/_components/...`, é a página antiga ainda importando o que foi movido —
confirme que o Step 4 substituiu o arquivo inteiro, não só parte.

Run: `cd web && npm run build`
Expected: build completo, e a listagem de rotas passa a mostrar `/bling`.

- [ ] **Step 6: Commit**

```bash
git add web/src/app/bling web/src/app/integracoes/bling/page.tsx
git commit -m "feat: modulo /bling com layout, submenu e dashboard; tela antiga redireciona"
```

---

### Task 4: Páginas migradas — produtos, pedidos de venda, financeiro

**Files:**
- Create: `web/src/app/bling/produtos/page.tsx`
- Create: `web/src/app/bling/pedidos-venda/page.tsx`
- Create: `web/src/app/bling/financeiro/page.tsx`

**Interfaces:**
- Consumes: `BlingProductsTab`, `ProductFormModal`, `BulkStockModal`, `BlingVendasTab`,
  `BlingOrdersTab`, `BlingFinancialTab` — todos já em `web/src/app/bling/_components/` (Task 3)

- [ ] **Step 1: Produtos**

A aba de produtos precisa dos dois modais e dos callbacks que a página antiga controlava
(`onNewProduct`, `onStockManage`) — o estado dos modais mora na página, igual antes.

`web/src/app/bling/produtos/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import BlingProductsTab from "../_components/BlingProductsTab";
import ProductFormModal from "../_components/ProductFormModal";
import BulkStockModal from "../_components/BulkStockModal";

export default function BlingProdutosPage() {
  const [showProductForm, setShowProductForm] = useState(false);
  const [showStockModal, setShowStockModal] = useState(false);

  return (
    <>
      <BlingProductsTab
        onNewProduct={() => setShowProductForm(true)}
        onStockManage={() => setShowStockModal(true)}
      />
      {showProductForm && (
        <ProductFormModal
          onClose={() => setShowProductForm(false)}
          onSaved={() => setShowProductForm(false)}
        />
      )}
      {showStockModal && <BulkStockModal onClose={() => setShowStockModal(false)} />}
    </>
  );
}
```

- [ ] **Step 2: Pedidos de venda**

A tela antiga tinha duas abas separadas: "Vendas" (resumo por período, `BlingVendasTab`) e
"Pedidos" (lista + sync, `BlingOrdersTab`). No módulo novo elas viram uma página só — resumo em
cima, lista embaixo.

`web/src/app/bling/pedidos-venda/page.tsx`:

```tsx
"use client";

import BlingVendasTab from "../_components/BlingVendasTab";
import BlingOrdersTab from "../_components/BlingOrdersTab";

export default function BlingPedidosVendaPage() {
  return (
    <div className="space-y-6">
      <BlingVendasTab />
      <BlingOrdersTab />
    </div>
  );
}
```

- [ ] **Step 3: Financeiro**

`web/src/app/bling/financeiro/page.tsx`:

```tsx
"use client";

import BlingFinancialTab from "../_components/BlingFinancialTab";

export default function BlingFinanceiroPage() {
  return <BlingFinancialTab />;
}
```

- [ ] **Step 4: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0. Se acusar prop faltando em `BlingProductsTab`, abra o componente e confira a
interface de props real — o esqueleto acima assume `onNewProduct`/`onStockManage`, que é o que a
página antiga passava; se os nomes forem outros, use os reais.

Run: `cd web && npm run build`
Expected: build mostra `/bling/produtos`, `/bling/pedidos-venda` e `/bling/financeiro`.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/bling
git commit -m "feat: paginas de produtos, pedidos de venda e financeiro no modulo /bling"
```

---

### Task 5: Página de configurações com toggle de ambiente

**Files:**
- Create: `web/src/app/bling/config/page.tsx`
- Modify: `web/src/app/bling/_components/BlingConfigTab.tsx` (bloco novo de ambiente no topo)

**Interfaces:**
- Consumes: `getBlingAmbiente`, `setBlingAmbiente` (Task 2)

- [ ] **Step 1: Criar a página**

`web/src/app/bling/config/page.tsx`:

```tsx
"use client";

import BlingConfigTab from "../_components/BlingConfigTab";

export default function BlingConfigPage() {
  return <BlingConfigTab />;
}
```

- [ ] **Step 2: Adicionar o estado do ambiente no ConfigTab**

Em `web/src/app/bling/_components/BlingConfigTab.tsx`, acrescentar ao import de `@/lib/api`:
`getBlingAmbiente, setBlingAmbiente,` e, junto dos outros `useState` do componente:

```tsx
  const [ambiente, setAmbiente] = useState<string>("producao");
  const [baseUrl, setBaseUrl] = useState<string>("");
  const [trocandoAmbiente, setTrocandoAmbiente] = useState(false);
```

Dentro do `carregar()`, acrescentar `getBlingAmbiente()` ao `Promise.all` e guardar o resultado:

```tsx
      const [s, w, n, e, amb] = await Promise.all([
        getBlingStatus(),
        listarBlingWebhooks(),
        listarBlingNotificacoes(),
        listarBlingEventos(),
        getBlingAmbiente(),
      ]);
      ...
      setAmbiente(amb.ambiente || "producao");
      setBaseUrl(amb.base_url || "");
```

E o handler da troca:

```tsx
  const handleTrocarAmbiente = async (novo: string) => {
    if (novo === ambiente) return;
    const confirmar = window.confirm(
      novo === "homologacao"
        ? "Trocar para HOMOLOGAÇÃO? Os dados sincronizados a partir de agora ficam marcados como homologação e somem das telas de produção."
        : "Voltar para PRODUÇÃO? Os syncs voltam a gravar dados reais."
    );
    if (!confirmar) return;
    try {
      setTrocandoAmbiente(true);
      setErro(null);
      const r = await setBlingAmbiente(novo);
      if (r.error) { setErro(r.error); return; }
      setSucesso(`Ambiente alterado para ${novo}. Reautentique no Bling se necessário.`);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao trocar ambiente");
    } finally {
      setTrocandoAmbiente(false);
    }
  };
```

- [ ] **Step 3: Adicionar o bloco visual do toggle**

No JSX do componente, como primeiro bloco depois do tratamento de loading/erro (antes do bloco
de credenciais/autenticação que já existe):

```tsx
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-neutral-200">Ambiente</h2>
            <p className="text-xs text-neutral-500 mt-0.5">
              Em homologação, tudo que for sincronizado fica marcado como <code>homologacao</code> e
              não aparece nas telas de produção.
            </p>
          </div>
          <div className="flex gap-1 bg-neutral-800 rounded-lg p-1 shrink-0">
            {["producao", "homologacao"].map((amb) => (
              <button
                key={amb}
                onClick={() => handleTrocarAmbiente(amb)}
                disabled={trocandoAmbiente}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors disabled:opacity-50 ${
                  ambiente === amb ? "bg-indigo-600 text-white" : "text-neutral-400 hover:text-neutral-200"
                }`}
              >
                {amb === "producao" ? "Produção" : "Homologação"}
              </button>
            ))}
          </div>
        </div>
        {ambiente === "homologacao" && baseUrl.includes("www.bling.com.br") && (
          <p className="text-xs text-amber-400">
            Nenhum host de homologação configurado — as chamadas continuam indo para a API de
            produção ({baseUrl}). Só os dados gravados ficam separados.
          </p>
        )}
      </div>
```

O aviso aparece quando o ambiente é homologação **e** a base URL efetiva ainda é a de produção —
que é o estado padrão hoje, já que a API Bling v3 não publica host de sandbox (ver fase 5).

- [ ] **Step 4: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: build mostra `/bling/config`.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/bling
git commit -m "feat: pagina de configuracoes do Bling com toggle de ambiente producao/homologacao"
```

---

### Task 6: Entrada "Bling" no menu principal

**Files:**
- Modify: `web/src/app/layout.tsx` (constante `NAV_GROUPS`, por volta da linha 61, e o mapa de
  permissões por rota, por volta da linha 45)

**Interfaces:**
- Consumes: as rotas criadas nas Tasks 3-5

- [ ] **Step 1: Trocar a entrada antiga pelo item com submenu**

Em `web/src/app/layout.tsx`, no grupo que hoje contém
`{ href: "/integracoes/bling", label: "Bling", icon: "bling" }` (por volta da linha 138),
substituir por:

```tsx
      {
        href: "/bling", label: "Bling", icon: "bling",
        children: [
          { href: "/bling", label: "Dashboard" },
          { href: "/bling/produtos", label: "Produtos" },
          { href: "/bling/pedidos-venda", label: "Pedidos de Venda" },
          { href: "/bling/financeiro", label: "Financeiro" },
          { href: "/bling/config", label: "Configurações" },
        ],
      },
```

O formato de `children` é o mesmo já usado pelo item "Shopee" no grupo "Vendas" — copie a
estrutura de lá se tiver dúvida sobre os campos aceitos (`NavChild = { href, label, store? }`).

- [ ] **Step 2: Atualizar o mapa de permissão por rota**

No objeto que mapeia rota → permissão (onde hoje está `"/integracoes/bling": "integrations:view"`),
acrescentar a entrada nova mantendo a antiga enquanto o redirect existir:

```tsx
  "/integracoes/bling": "integrations:view",
  "/bling": "integrations:view",
```

- [ ] **Step 3: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: build completo. Confirme na listagem de rotas que aparecem `/bling`,
`/bling/produtos`, `/bling/pedidos-venda`, `/bling/financeiro` e `/bling/config`.

- [ ] **Step 4: Commit**

```bash
git add web/src/app/layout.tsx
git commit -m "feat: entrada Bling com submenu no menu principal"
```

---

### Task 7: Verificação final

- [ ] **Step 1: Typecheck limpo**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0, nenhuma saída.

- [ ] **Step 2: Build limpo com todas as rotas**

Run: `cd web && npm run build`
Expected: build completo; as cinco rotas `/bling*` presentes na listagem.

- [ ] **Step 3: Confirmar que nenhuma chamada Bling ficou sem token**

Run: `grep -rn 'fetch("/api/bling\|fetch(`/api/bling' web/src/`
Expected: nenhuma linha. Se aparecer alguma dentro de um componente (não do `api.ts`), converta
pra usar a função correspondente de `@/lib/api` — chamada Bling direta em componente burla o
helper e volta a dar 403 nas rotas com RBAC.

- [ ] **Step 4: Confirmar que a suíte do backend continua intacta**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes (RH, compras segurança, RBAC lojas), nenhuma nova. Esta
fase não toca backend — se algo mudar aqui, alguma edição saiu do escopo.

- [ ] **Step 5: Commit final**

```bash
git status --porcelain
```

Se não houver mudança de código real:

```bash
git commit -m "test: verificacao final do modulo /bling (fase 6a)" --allow-empty
```
