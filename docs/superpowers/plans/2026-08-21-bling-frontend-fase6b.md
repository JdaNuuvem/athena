# Bling — Frontend do Módulo, Telas Novas (Plano 6b/N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar as cinco telas do módulo `/bling` que ainda não existem — pedidos de compra,
situações (CRUD), lojas/canais, notas fiscais com abas por tipo (NF-e / NFC-e / NFS-e) e contas
contábeis — dando interface às rotas de backend entregues nas fases 3, 4a, 4b e 5, que hoje só
existem via API.

**Architecture:** Cada tela é uma `page.tsx` própria dentro de `web/src/app/bling/`, consumindo
as funções de `@/lib/api` já criadas na fase 6a (Task 2) — nenhuma função de API nova é
necessária, e nenhuma rota de backend é criada nesta fase. As telas seguem o padrão visual que
já existe nos componentes migrados (`BlingOrdersTab` é a referência canônica): `Alert` de
erro/sucesso no topo, toolbar com botão de sincronizar e filtros, `EmptyState` quando vazio, e
tabela `text-xs` com cabeçalho `bg-neutral-850` e linhas zebradas. A única peça compartilhada
nova é uma toolbar de sincronização, extraída porque as cinco telas repetiriam o mesmo botão com
o mesmo SVG e o mesmo estado de "sincronizando".

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript, Tailwind 4.

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md` (seções "Navegação" e
"Frontend")

## Global Constraints

- **Nenhuma função de API nova e nenhuma rota de backend nova.** Tudo que estas telas precisam
  já existe em `web/src/lib/api.ts` desde a fase 6a. Se uma tela parecer precisar de endpoint
  novo, pare e reporte — não invente rota.
- **Toda chamada Bling passa por `@/lib/api`.** `fetch("/api/bling/...")` direto num componente
  burla o `blingFetch` e volta a mandar requisição sem `Authorization`, quebrando as rotas com
  RBAC (foi exatamente o bug corrigido na fase 6a). A verificação final tem um grep pra isso.
- **Filtro de ambiente default `'producao'`.** As telas que leem tabela local (pedidos de compra,
  notas) mandam `ambiente=producao` por padrão, com seletor pro usuário ver homologação ou os
  dois. Isso espelha o default do backend (fase 5) — nunca mostre dado de homologação misturado
  com produção sem o usuário ter pedido.
- **Seguir o padrão visual existente, não inventar um novo.** Classes Tailwind, tamanhos e cores
  saem de `BlingOrdersTab.tsx` / `shared/*`. Nada de biblioteca de UI nova, nada de dependência
  nova.
- **Verificação a cada task:** `cd web && npx tsc --noEmit` (exit 0) e `cd web && npm run build`
  (compila sem erro). Baseline verde ao começar esta fase.
- Ortografia em português correta na interface (acentos incluídos). Commits em português no
  formato `<tipo>: <descrição>`.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `web/src/app/bling/_components/shared/SyncToolbar.tsx` | Toolbar reusável: botão sincronizar + contagem + slot para filtros |
| `web/src/app/bling/pedidos-compra/page.tsx` | Lista local de pedidos de compra, sync, marcar recebido |
| `web/src/app/bling/situacoes/page.tsx` | Lista de situações + sync + ações de CRUD |
| `web/src/app/bling/_components/SituacaoFormModal.tsx` | Modal de criar/editar situação |
| `web/src/app/bling/canais/page.tsx` | Lista de lojas/canais + sync |
| `web/src/app/bling/plano-contas/page.tsx` | Lista de contas contábeis + sync |
| `web/src/app/bling/notas/page.tsx` | Notas locais com abas NF-e / NFC-e / NFS-e + sync por tipo |
| `web/src/app/bling/layout.tsx` | Submenu ganha as cinco entradas novas |
| `web/src/app/layout.tsx` | Menu principal ganha as cinco entradas novas |

---

### Task 1: `SyncToolbar` compartilhada

**Files:**
- Create: `web/src/app/bling/_components/shared/SyncToolbar.tsx`

**Interfaces:**
- Produces: `SyncToolbar` — props
  `{ onSync: () => void; sincronizando?: boolean; label?: string; total?: number; unidade?: string; children?: React.ReactNode }`

- [ ] **Step 1: Criar o componente**

O SVG de "recarregar" é o mesmo já usado em `BlingOrdersTab.tsx` — copie de lá pra manter o
visual idêntico.

```tsx
interface SyncToolbarProps {
  onSync: () => void;
  sincronizando?: boolean;
  label?: string;
  total?: number;
  unidade?: string;
  children?: React.ReactNode;
}

export default function SyncToolbar({
  onSync,
  sincronizando = false,
  label = "Sincronizar",
  total,
  unidade = "registros",
  children,
}: SyncToolbarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        onClick={onSync}
        disabled={sincronizando}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 transition-colors disabled:opacity-50"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
        </svg>
        {sincronizando ? "Sincronizando..." : label}
      </button>
      {children}
      {typeof total === "number" && (
        <span className="text-xs text-neutral-500 ml-auto">
          {total} {unidade}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: compila sem erro.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/bling/_components/shared/SyncToolbar.tsx
git commit -m "feat: toolbar de sincronizacao compartilhada do modulo Bling"
```

---

### Task 2: Tela de pedidos de compra

**Files:**
- Create: `web/src/app/bling/pedidos-compra/page.tsx`

**Interfaces:**
- Consumes: `listarBlingPedidosCompra(ambiente)`, `sincronizarBlingPedidosCompra()`,
  `receberBlingPedidoCompra(id)`, tipo `BlingPedidoCompraLocal` — todos de `@/lib/api` (fase 6a)

- [ ] **Step 1: Criar a página**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import { listarBlingPedidosCompra, sincronizarBlingPedidosCompra, receberBlingPedidoCompra } from "@/lib/api";
import type { BlingPedidoCompraLocal } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";

const STATUS_CORES: Record<string, string> = {
  emitido: "bg-indigo-900/40 text-indigo-300",
  recebido: "bg-emerald-900/40 text-emerald-300",
  cancelado: "bg-red-900/40 text-red-300",
};

export default function BlingPedidosCompraPage() {
  const [pedidos, setPedidos] = useState<BlingPedidoCompraLocal[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [ambiente, setAmbiente] = useState("producao");
  const [busca, setBusca] = useState("");

  const carregar = useCallback(async (amb: string) => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingPedidosCompra(amb);
    if (r.error) setErro(r.error);
    setPedidos(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { carregar(ambiente); }, [carregar, ambiente]);

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = await sincronizarBlingPedidosCompra();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} pedidos de compra sincronizados`);
    setSincronizando(false);
    carregar(ambiente);
  };

  const handleReceber = async (p: BlingPedidoCompraLocal) => {
    if (!p.bling_id) { setErro("Pedido sem vínculo com o Bling."); return; }
    if (!window.confirm(`Marcar o pedido ${p.numero} como recebido no Bling?`)) return;
    setErro(null);
    setSucesso(null);
    const r = await receberBlingPedidoCompra(p.bling_id);
    if (r.error) setErro(r.error);
    else { setSucesso(`Pedido ${p.numero} marcado como recebido.`); carregar(ambiente); }
  };

  const filtrados = pedidos.filter((p) =>
    !busca || String(p.numero).toLowerCase().includes(busca.toLowerCase())
  );

  if (loading && pedidos.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <SyncToolbar onSync={handleSync} sincronizando={sincronizando} total={filtrados.length} unidade="pedidos">
        <input
          type="text"
          placeholder="Buscar por nº..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="flex-1 min-w-[180px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
        />
        <select
          value={ambiente}
          onChange={(e) => setAmbiente(e.target.value)}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
        >
          <option value="producao">Produção</option>
          <option value="homologacao">Homologação</option>
          <option value="todos">Todos os ambientes</option>
        </select>
      </SyncToolbar>

      {filtrados.length === 0 ? (
        <EmptyState
          icon="🧾"
          title={busca ? "Nenhum pedido encontrado" : "Nenhum pedido de compra"}
          description={busca ? "Ajuste a busca." : "Sincronize os pedidos de compra do Bling para começar."}
          action={busca ? undefined : { label: "Sincronizar Agora", onClick: handleSync }}
        />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3 w-[110px]">Nº</th>
                <th className="text-left p-3 w-[100px]">Emissão</th>
                <th className="text-left p-3 w-[110px]">Entrega prev.</th>
                <th className="text-right p-3 w-[120px]">Total</th>
                <th className="text-center p-3 w-[100px]">Status</th>
                <th className="text-center p-3 w-[110px]">Ambiente</th>
                <th className="text-center p-3 w-[120px]">Ação</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((p, i) => (
                <tr key={p.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3 text-indigo-400 font-mono">{p.numero || "—"}</td>
                  <td className="p-3 text-neutral-400">{p.data_emissao ? fmtDataBR(p.data_emissao) : "—"}</td>
                  <td className="p-3 text-neutral-400">{p.data_entrega_prevista ? fmtDataBR(p.data_entrega_prevista) : "—"}</td>
                  <td className="p-3 text-right text-neutral-200">{fmtBRL(Number(p.valor_total) || 0)}</td>
                  <td className="p-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_CORES[p.status] || "bg-neutral-700 text-neutral-300"}`}>
                      {p.status || "—"}
                    </span>
                  </td>
                  <td className="p-3 text-center text-[10px] text-neutral-500">{p.ambiente}</td>
                  <td className="p-3 text-center">
                    {p.status === "recebido" ? (
                      <span className="text-[10px] text-neutral-500">—</span>
                    ) : (
                      <button
                        onClick={() => handleReceber(p)}
                        className="px-2 py-1 bg-neutral-700 text-neutral-200 text-[10px] rounded hover:bg-neutral-600 transition-colors"
                      >
                        Marcar recebido
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

Nota sobre `receberBlingPedidoCompra`: a rota do backend
(`POST /api/bling/pedidos-compra/<id>/receber`) repassa o id **para o Bling**, então o parâmetro
é o `bling_id`, não o `id` local — por isso a checagem de `p.bling_id` antes de chamar. Confirme
lendo `api_receber_pedido_compra` em `hermes_agents/routes/integrations.py` antes de fechar a
task; se a rota esperar o id local, troque o argumento e remova a checagem.

- [ ] **Step 2: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: rota `/bling/pedidos-compra` na listagem.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/bling/pedidos-compra
git commit -m "feat: tela de pedidos de compra Bling"
```

---

### Task 3: Tela de situações (CRUD)

**Files:**
- Create: `web/src/app/bling/_components/SituacaoFormModal.tsx`
- Create: `web/src/app/bling/situacoes/page.tsx`

**Interfaces:**
- Consumes: `listarBlingSituacoes()`, `criarBlingSituacao(dados)`,
  `atualizarBlingSituacao(id, dados)`, `deletarBlingSituacao(id)`,
  `sincronizarBlingSituacoes()`, tipo `BlingSituacao`

- [ ] **Step 1: Criar o modal**

```tsx
"use client";

import { useState } from "react";
import type { BlingSituacao } from "@/lib/api";

interface SituacaoFormModalProps {
  situacao?: BlingSituacao | null;
  onClose: () => void;
  onSalvar: (dados: Partial<BlingSituacao>) => Promise<void>;
}

export default function SituacaoFormModal({ situacao, onClose, onSalvar }: SituacaoFormModalProps) {
  const [nome, setNome] = useState(situacao?.nome || "");
  const [cor, setCor] = useState(situacao?.cor || "");
  const [modulo, setModulo] = useState(situacao?.modulo || "");
  const [salvando, setSalvando] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nome.trim()) return;
    setSalvando(true);
    await onSalvar({ nome: nome.trim(), cor: cor.trim(), modulo: modulo.trim() });
    setSalvando(false);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="bg-neutral-900 border border-neutral-700 rounded-lg p-5 w-full max-w-sm space-y-3"
      >
        <h2 className="text-sm font-semibold text-neutral-100">
          {situacao ? "Editar situação" : "Nova situação"}
        </h2>

        <label className="block">
          <span className="text-xs text-neutral-400">Nome</span>
          <input
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            autoFocus
            className="mt-1 w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500"
          />
        </label>

        <label className="block">
          <span className="text-xs text-neutral-400">Cor (hex, sem #)</span>
          <input
            value={cor}
            onChange={(e) => setCor(e.target.value)}
            placeholder="FFA500"
            className="mt-1 w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-indigo-500"
          />
        </label>

        <label className="block">
          <span className="text-xs text-neutral-400">Módulo</span>
          <input
            value={modulo}
            onChange={(e) => setModulo(e.target.value)}
            placeholder="pedidos"
            className="mt-1 w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-indigo-500"
          />
        </label>

        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="px-3 py-1.5 bg-neutral-700 text-neutral-200 text-xs rounded-lg hover:bg-neutral-600">
            Cancelar
          </button>
          <button type="submit" disabled={salvando || !nome.trim()} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 disabled:opacity-50">
            {salvando ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Criar a página**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import Icon from "@/app/_components/Icon";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import SituacaoFormModal from "../_components/SituacaoFormModal";
import {
  listarBlingSituacoes,
  criarBlingSituacao,
  atualizarBlingSituacao,
  deletarBlingSituacao,
  sincronizarBlingSituacoes,
} from "@/lib/api";
import type { BlingSituacao } from "@/lib/api";

export default function BlingSituacoesPage() {
  const [situacoes, setSituacoes] = useState<BlingSituacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [editando, setEditando] = useState<BlingSituacao | null>(null);
  const [criando, setCriando] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingSituacoes();
    if (r.error) setErro(r.error);
    setSituacoes(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = await sincronizarBlingSituacoes();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} situações sincronizadas`);
    setSincronizando(false);
    carregar();
  };

  const handleSalvar = async (dados: Partial<BlingSituacao>) => {
    setErro(null);
    setSucesso(null);
    const r = editando
      ? await atualizarBlingSituacao(editando.bling_id || editando.id, dados)
      : await criarBlingSituacao(dados);
    if (r.error) { setErro(r.error); return; }
    setSucesso(editando ? "Situação atualizada." : "Situação criada.");
    setEditando(null);
    setCriando(false);
    carregar();
  };

  const handleExcluir = async (s: BlingSituacao) => {
    if (!window.confirm(`Excluir a situação "${s.nome}"? Isso remove a situação no Bling também.`)) return;
    setErro(null);
    setSucesso(null);
    const r = await deletarBlingSituacao(s.bling_id || s.id);
    if (r.error) { setErro(r.error); return; }
    setSucesso("Situação excluída.");
    carregar();
  };

  if (loading && situacoes.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <SyncToolbar onSync={handleSync} sincronizando={sincronizando} total={situacoes.length} unidade="situações">
        <button
          onClick={() => { setEditando(null); setCriando(true); }}
          className="px-3 py-1.5 bg-neutral-700 text-neutral-200 text-xs rounded-lg hover:bg-neutral-600 transition-colors"
        >
          + Nova
        </button>
      </SyncToolbar>

      {situacoes.length === 0 ? (
        <EmptyState
          icon="🏷️"
          title="Nenhuma situação"
          description="Sincronize as situações do Bling ou crie uma nova."
          action={{ label: "Sincronizar Agora", onClick: handleSync }}
        />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3">Nome</th>
                <th className="text-left p-3 w-[120px]">Módulo</th>
                <th className="text-center p-3 w-[90px]">Cor</th>
                <th className="text-center p-3 w-[110px]">ID Bling</th>
                <th className="text-center p-3 w-[110px]">Ações</th>
              </tr>
            </thead>
            <tbody>
              {situacoes.map((s, i) => (
                <tr key={s.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3 text-neutral-200">{s.nome}</td>
                  <td className="p-3 text-neutral-400">{s.modulo || "—"}</td>
                  <td className="p-3 text-center">
                    {s.cor ? (
                      <span className="inline-flex items-center gap-1.5 text-[10px] text-neutral-400">
                        <span className="w-3 h-3 rounded-sm border border-neutral-600" style={{ backgroundColor: `#${s.cor.replace("#", "")}` }} />
                        {s.cor}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="p-3 text-center text-neutral-500 font-mono text-[10px]">{s.bling_id || "—"}</td>
                  <td className="p-3">
                    <div className="flex items-center justify-center gap-1">
                      <button onClick={() => { setCriando(false); setEditando(s); }} title="Editar"
                        className="p-1 text-neutral-400 hover:text-indigo-400 transition-colors">
                        <Icon name="pencil" size={14} />
                      </button>
                      <button onClick={() => handleExcluir(s)} title="Excluir"
                        className="p-1 text-neutral-400 hover:text-red-400 transition-colors">
                        <Icon name="trash" size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(criando || editando) && (
        <SituacaoFormModal
          situacao={editando}
          onClose={() => { setCriando(false); setEditando(null); }}
          onSalvar={handleSalvar}
        />
      )}
    </div>
  );
}
```

Nota sobre o id usado em update/delete: as rotas `PUT`/`DELETE /api/bling/situacoes/<id>`
propagam a operação pro Bling, então esperam o id **do Bling**. O fallback `s.bling_id || s.id`
cobre o caso de a listagem local ainda não ter o `bling_id` preenchido. Confirme lendo
`api_atualizar_situacao`/`api_deletar_situacao` em `hermes_agents/routes/integrations.py`; se as
rotas usarem o id local, remova o fallback e passe `s.id`.

- [ ] **Step 3: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: rota `/bling/situacoes` na listagem.

- [ ] **Step 4: Commit**

```bash
git add web/src/app/bling/situacoes web/src/app/bling/_components/SituacaoFormModal.tsx
git commit -m "feat: tela de CRUD de situacoes Bling"
```

---

### Task 4: Telas de leitura simples — canais e plano de contas

As duas são "listar + sincronizar", sem escrita além do sync. Ficam na mesma task porque
compartilham a estrutura inteira e um revisor as julgaria juntas.

**Files:**
- Create: `web/src/app/bling/canais/page.tsx`
- Create: `web/src/app/bling/plano-contas/page.tsx`

**Interfaces:**
- Consumes: `listarBlingCanais()`, `sincronizarBlingCanais()`, `listarBlingPlanoContas()`,
  `sincronizarBlingPlanoContas()`, tipos `BlingCanal` e `BlingContaContabil`
- Modifies: o tipo `BlingCanal` em `web/src/lib/api.ts` (correção, ver Step 1)

- [ ] **Step 1: Corrigir o tipo `BlingCanal`**

A fase 6a declarou `BlingCanal` com um campo `tipo`, mas `GET /api/bling/canais` devolve
`SELECT id, bling_id, nome, situacao FROM bling_canais` — não existe coluna `tipo`. Corrija em
`web/src/lib/api.ts`:

```ts
export interface BlingCanal {
  id: number;
  nome: string;
  bling_id?: number | null;
  situacao?: string | null;
}
```

- [ ] **Step 2: Canais**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import { listarBlingCanais, sincronizarBlingCanais } from "@/lib/api";
import type { BlingCanal } from "@/lib/api";

export default function BlingCanaisPage() {
  const [canais, setCanais] = useState<BlingCanal[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingCanais();
    if (r.error) setErro(r.error);
    setCanais(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = await sincronizarBlingCanais();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} canais sincronizados`);
    setSincronizando(false);
    carregar();
  };

  if (loading && canais.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <SyncToolbar onSync={handleSync} sincronizando={sincronizando} total={canais.length} unidade="canais" />

      {canais.length === 0 ? (
        <EmptyState icon="🛍️" title="Nenhum canal" description="Sincronize as lojas/canais do Bling para começar."
          action={{ label: "Sincronizar Agora", onClick: handleSync }} />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3">Nome</th>
                <th className="text-left p-3 w-[160px]">Situação</th>
                <th className="text-center p-3 w-[110px]">ID Bling</th>
              </tr>
            </thead>
            <tbody>
              {canais.map((c, i) => (
                <tr key={c.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3 text-neutral-200">{c.nome}</td>
                  <td className="p-3 text-neutral-400">{c.situacao || "—"}</td>
                  <td className="p-3 text-center text-neutral-500 font-mono text-[10px]">{c.bling_id || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Plano de contas**

Mesma estrutura, trocando fonte de dados e colunas:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import { listarBlingPlanoContas, sincronizarBlingPlanoContas } from "@/lib/api";
import type { BlingContaContabil } from "@/lib/api";

export default function BlingPlanoContasPage() {
  const [contas, setContas] = useState<BlingContaContabil[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [busca, setBusca] = useState("");

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingPlanoContas();
    if (r.error) setErro(r.error);
    setContas(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = await sincronizarBlingPlanoContas();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} contas sincronizadas`);
    setSincronizando(false);
    carregar();
  };

  const filtradas = contas.filter((c) => {
    if (!busca) return true;
    const t = busca.toLowerCase();
    return (c.nome || "").toLowerCase().includes(t) || (c.codigo || "").toLowerCase().includes(t);
  });

  if (loading && contas.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <SyncToolbar onSync={handleSync} sincronizando={sincronizando} total={filtradas.length} unidade="contas">
        <input
          type="text"
          placeholder="Buscar por código ou nome..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="flex-1 min-w-[180px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
        />
      </SyncToolbar>

      {filtradas.length === 0 ? (
        <EmptyState icon="📊" title={busca ? "Nenhuma conta encontrada" : "Nenhuma conta contábil"}
          description={busca ? "Ajuste a busca." : "Sincronize o plano de contas do Bling para começar."}
          action={busca ? undefined : { label: "Sincronizar Agora", onClick: handleSync }} />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3 w-[130px]">Código</th>
                <th className="text-left p-3">Nome</th>
                <th className="text-left p-3 w-[120px]">Tipo</th>
                <th className="text-left p-3 w-[120px]">Natureza</th>
                <th className="text-center p-3 w-[110px]">ID Bling</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((c, i) => (
                <tr key={c.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3 text-indigo-400 font-mono">{c.codigo || "—"}</td>
                  <td className="p-3 text-neutral-200">{c.nome}</td>
                  <td className="p-3 text-neutral-400">{c.tipo || "—"}</td>
                  <td className="p-3 text-neutral-400">{c.natureza || "—"}</td>
                  <td className="p-3 text-center text-neutral-500 font-mono text-[10px]">{c.bling_id || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: rotas `/bling/canais` e `/bling/plano-contas` na listagem.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/app/bling/canais web/src/app/bling/plano-contas
git commit -m "feat: telas de canais e plano de contas Bling"
```

---

### Task 5: Tela de notas fiscais com abas por tipo

**Files:**
- Create: `web/src/app/bling/notas/page.tsx`

**Interfaces:**
- Consumes: `listarBlingNotasLocais(tipo, ambiente)`, `sincronizarBlingNfce()`,
  `sincronizarBlingNfse()`, tipo `BlingNotaLocal`

- [ ] **Step 1: Criar a página**

A aba escolhida vira o parâmetro `tipo` da rota local; a aba "Todas" manda `tipo` vazio. O botão
de sincronizar muda de função conforme a aba: NFC-e chama `sincronizarBlingNfce`, NFS-e chama
`sincronizarBlingNfse`. A aba NF-e **não tem** sync próprio aqui — o sync de NF-e vive no fluxo
fiscal (`core.fiscal.sincronizar_notas_fiscais_bling`), sem rota dedicada em `bling_bp` — então
nessa aba o botão fica escondido.

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import { listarBlingNotasLocais, sincronizarBlingNfce, sincronizarBlingNfse } from "@/lib/api";
import type { BlingNotaLocal } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";

const ABAS = [
  { key: "", label: "Todas" },
  { key: "nfe", label: "NF-e" },
  { key: "nfce", label: "NFC-e" },
  { key: "nfse", label: "NFS-e" },
] as const;

export default function BlingNotasPage() {
  const [notas, setNotas] = useState<BlingNotaLocal[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [tipo, setTipo] = useState<string>("");
  const [ambiente, setAmbiente] = useState("producao");

  const carregar = useCallback(async (t: string, amb: string) => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingNotasLocais(t, amb);
    if (r.error) setErro(r.error);
    setNotas(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { carregar(tipo, ambiente); }, [carregar, tipo, ambiente]);

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = tipo === "nfce" ? await sincronizarBlingNfce() : await sincronizarBlingNfse();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} notas sincronizadas`);
    setSincronizando(false);
    carregar(tipo, ambiente);
  };

  const podeSincronizar = tipo === "nfce" || tipo === "nfse";
  const total = notas.reduce((s, n) => s + (Number(n.valor_nf) || 0), 0);

  if (loading && notas.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <div className="flex flex-wrap gap-1 bg-neutral-800 rounded-lg p-1">
        {ABAS.map((aba) => (
          <button
            key={aba.key}
            onClick={() => setTipo(aba.key)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              tipo === aba.key ? "bg-indigo-600 text-white" : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            {aba.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {podeSincronizar ? (
          <SyncToolbar
            onSync={handleSync}
            sincronizando={sincronizando}
            label={`Sincronizar ${tipo.toUpperCase()}`}
            total={notas.length}
            unidade="notas"
          >
            <select
              value={ambiente}
              onChange={(e) => setAmbiente(e.target.value)}
              className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
            >
              <option value="producao">Produção</option>
              <option value="homologacao">Homologação</option>
              <option value="todos">Todos os ambientes</option>
            </select>
          </SyncToolbar>
        ) : (
          <>
            <select
              value={ambiente}
              onChange={(e) => setAmbiente(e.target.value)}
              className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
            >
              <option value="producao">Produção</option>
              <option value="homologacao">Homologação</option>
              <option value="todos">Todos os ambientes</option>
            </select>
            <span className="text-xs text-neutral-500 ml-auto">{notas.length} notas</span>
          </>
        )}
      </div>

      <div className="text-xs text-neutral-400">
        Valor total: <strong className="text-emerald-400">{fmtBRL(total)}</strong>
      </div>

      {notas.length === 0 ? (
        <EmptyState
          icon="📄"
          title="Nenhuma nota"
          description={
            podeSincronizar
              ? `Sincronize as notas ${tipo.toUpperCase()} do Bling para começar.`
              : "Nenhuma nota sincronizada neste filtro."
          }
          action={podeSincronizar ? { label: "Sincronizar Agora", onClick: handleSync } : undefined}
        />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3 w-[90px]">Nº</th>
                <th className="text-left p-3 w-[80px]">Tipo</th>
                <th className="text-left p-3">Contato</th>
                <th className="text-left p-3 w-[100px]">Emissão</th>
                <th className="text-right p-3 w-[120px]">Valor</th>
                <th className="text-center p-3 w-[100px]">Status</th>
                <th className="text-center p-3 w-[110px]">Ambiente</th>
              </tr>
            </thead>
            <tbody>
              {notas.map((n, i) => (
                <tr key={n.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3 text-indigo-400 font-mono">{n.numero || "—"}</td>
                  <td className="p-3 text-neutral-400 uppercase">{n.tipo_documento}</td>
                  <td className="p-3 text-neutral-200">
                    <div>{n.contato_nome || "—"}</div>
                    {n.chave_acesso && <div className="text-[10px] text-neutral-600 font-mono truncate max-w-[280px]">{n.chave_acesso}</div>}
                  </td>
                  <td className="p-3 text-neutral-400">{n.data_emissao ? fmtDataBR(n.data_emissao) : "—"}</td>
                  <td className="p-3 text-right text-neutral-200">{fmtBRL(Number(n.valor_nf) || 0)}</td>
                  <td className="p-3 text-center text-neutral-400">{n.status || "—"}</td>
                  <td className="p-3 text-center text-[10px] text-neutral-500">{n.ambiente}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: rota `/bling/notas` na listagem.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/bling/notas
git commit -m "feat: tela de notas fiscais Bling com abas NF-e/NFC-e/NFS-e"
```

---

### Task 6: Navegação — submenu do módulo e menu principal

**Files:**
- Modify: `web/src/app/bling/layout.tsx` (constante `SUBMENU`)
- Modify: `web/src/app/layout.tsx` (`children` do item "Bling" em `NAV_GROUPS`)

- [ ] **Step 1: Submenu do módulo**

Em `web/src/app/bling/layout.tsx`, a constante `SUBMENU` passa a listar as dez rotas, na ordem
do spec. Ícones: use só nomes que existem em `web/src/app/_components/Icon.tsx` — os disponíveis
incluem `dashboard`, `produtos`, `vendas`, `compras`, `financeiro`, `fiscal`, `bi`, `globe`,
`check`. Entradas sem `icon` caem no ícone de engrenagem (`GearIcon`), então **só a de
Configurações deve ficar sem `icon`**.

```tsx
const SUBMENU: Array<{ href: string; label: string; icon?: string }> = [
  { href: "/bling", label: "Dashboard", icon: "dashboard" },
  { href: "/bling/produtos", label: "Produtos", icon: "produtos" },
  { href: "/bling/pedidos-venda", label: "Pedidos de Venda", icon: "vendas" },
  { href: "/bling/pedidos-compra", label: "Pedidos de Compra", icon: "compras" },
  { href: "/bling/situacoes", label: "Situações", icon: "check" },
  { href: "/bling/canais", label: "Lojas/Canais", icon: "globe" },
  { href: "/bling/financeiro", label: "Financeiro", icon: "financeiro" },
  { href: "/bling/notas", label: "Notas Fiscais", icon: "fiscal" },
  { href: "/bling/plano-contas", label: "Contas Contábeis", icon: "bi" },
  { href: "/bling/config", label: "Configurações" },
];
```

- [ ] **Step 2: Menu principal**

Em `web/src/app/layout.tsx`, os `children` do item "Bling" passam a espelhar a mesma lista (sem
ícones — `NavChild` é `{ href, label, store? }`):

```tsx
        children: [
          { href: "/bling", label: "Dashboard" },
          { href: "/bling/produtos", label: "Produtos" },
          { href: "/bling/pedidos-venda", label: "Pedidos de Venda" },
          { href: "/bling/pedidos-compra", label: "Pedidos de Compra" },
          { href: "/bling/situacoes", label: "Situações" },
          { href: "/bling/canais", label: "Lojas/Canais" },
          { href: "/bling/financeiro", label: "Financeiro" },
          { href: "/bling/notas", label: "Notas Fiscais" },
          { href: "/bling/plano-contas", label: "Contas Contábeis" },
          { href: "/bling/config", label: "Configurações" },
        ],
```

- [ ] **Step 3: Typecheck e build**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0.

Run: `cd web && npm run build`
Expected: as dez rotas `/bling*` na listagem.

- [ ] **Step 4: Commit**

```bash
git add web/src/app/bling/layout.tsx web/src/app/layout.tsx
git commit -m "feat: submenu e menu principal com as dez rotas do modulo Bling"
```

---

### Task 7: Verificação final

- [ ] **Step 1: Typecheck e build limpos**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0, sem saída.

Run: `cd web && npm run build`
Expected: compila e lista as dez rotas: `/bling`, `/bling/produtos`, `/bling/pedidos-venda`,
`/bling/pedidos-compra`, `/bling/situacoes`, `/bling/canais`, `/bling/financeiro`,
`/bling/notas`, `/bling/plano-contas`, `/bling/config`.

- [ ] **Step 2: Nenhuma chamada Bling fora do `api.ts`**

Run: `grep -rn 'fetch("/api/bling\|fetch(`/api/bling' web/src/`
Expected: nenhuma linha.

- [ ] **Step 3: Conferir que nenhum link do submenu aponta pra rota inexistente**

Compare a lista de `href` em `web/src/app/bling/layout.tsx` com os diretórios existentes:

```bash
ls web/src/app/bling/
```

Cada `href` `/bling/<x>` precisa ter um diretório `<x>` com `page.tsx`. Um link sem página é 404
silencioso na navegação.

- [ ] **Step 4: Backend intacto**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova. Esta fase não toca backend.

- [ ] **Step 5: Commit final**

```bash
git status --porcelain
```

Se não houver mudança de código real:

```bash
git commit -m "test: verificacao final das telas novas do modulo Bling (fase 6b)" --allow-empty
```
