"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";
import PageHeader from "@/app/_components/PageHeader";

const POR_PAGINA = 20;

interface Cliente {
  id: number;
  nome: string;
  tipo: string;
  documento: string | null;
  email: string | null;
  telefone: string | null;
  status: string;
}

function extrairErro(res: unknown): string | null {
  if (res && typeof res === "object" && "error" in res && (res as { error?: unknown }).error) {
    return String((res as { error: unknown }).error);
  }
  return null;
}

export default function Page() {
  const [items, setItems] = useState<Cliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busca, setBusca] = useState("");
  const [buscaAtiva, setBuscaAtiva] = useState("");
  const [pagina, setPagina] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPaginas, setTotalPaginas] = useState(1);

  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: Cliente }>({ open: false, mode: "create" });
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const [statusAlvo, setStatusAlvo] = useState<Cliente | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const carregar = useCallback(async (paginaAlvo: number, buscaAlvo: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.cadListPaginado("clientes", paginaAlvo, POR_PAGINA, buscaAlvo || undefined);
      setItems((res.data || []) as Cliente[]);
      setTotal(res.total ?? 0);
      setTotalPaginas(res.total_paginas ?? 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(pagina, buscaAtiva); }, [carregar, pagina, buscaAtiva]);

  // debounce: espera parar de digitar antes de disparar a busca no servidor,
  // e volta pra pagina 1 (uma busca nova pode ter menos paginas que a atual).
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPagina(1);
      setBuscaAtiva(busca.trim());
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [busca]);

  const abrirNovo = () => {
    setForm({ tipo: "PF" });
    setSaveError("");
    setModal({ open: true, mode: "create" });
  };

  const abrirEdicao = (row: Cliente) => {
    setForm({
      nome: row.nome || "",
      tipo: row.tipo || "PF",
      documento: row.documento || "",
      email: row.email || "",
      telefone: row.telefone || "",
    });
    setSaveError("");
    setModal({ open: true, mode: "edit", row });
  };

  const fecharModal = () => {
    if (saving) return;
    setModal({ open: false, mode: "create" });
  };

  const salvar = async () => {
    if (!form.nome?.trim()) {
      setSaveError("Nome e obrigatorio.");
      return;
    }
    setSaving(true);
    setSaveError("");
    const payload = {
      nome: form.nome.trim(),
      tipo: form.tipo || "PF",
      documento: form.documento?.trim() || "",
      email: form.email?.trim() || "",
      telefone: form.telefone?.trim() || "",
    };
    try {
      const res = modal.mode === "create"
        ? await api.cadCreate("clientes", payload)
        : await api.cadUpdate("clientes", Number(modal.row?.id), payload);
      const erro = extrairErro(res);
      if (erro) { setSaveError(erro); return; }
      setModal({ open: false, mode: "create" });
      await carregar(modal.mode === "create" ? 1 : pagina, buscaAtiva);
      if (modal.mode === "create") setPagina(1);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const alternarStatus = async (row: Cliente) => {
    const novoStatus = row.status === "ativo" ? "inativo" : "ativo";
    setTogglingId(row.id);
    try {
      const res = await api.cadUpdate("clientes", row.id, { status: novoStatus });
      const erro = extrairErro(res);
      if (erro) { setError(erro); return; }
      setStatusAlvo(null);
      await carregar(pagina, buscaAtiva);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader title="Contatos" subtitle="Agenda de clientes e contatos comerciais" />
        <Can permission="cadastros.criar">
          <button onClick={abrirNovo} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Novo</button>
        </Can>
      </div>

      <div className="relative w-full max-w-xs">
        <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500" />
        <input
          type="text"
          placeholder="Buscar por nome, documento, email ou telefone..."
          value={busca}
          onChange={e => setBusca(e.target.value)}
          className="w-full rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 pl-8 pr-3 text-xs text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-xs text-red-400">
          <Icon name="alert" size={15} className="shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="overflow-hidden rounded-lg border border-neutral-800">
          <div className="divide-y divide-neutral-800/70">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-4 py-3">
                {Array.from({ length: 6 }).map((_, j) => <div key={j} className="h-3 flex-1 animate-pulse rounded bg-neutral-800" />)}
              </div>
            ))}
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">{buscaAtiva ? "Nenhum contato encontrado para essa busca." : "Nenhum contato cadastrado."}</p>
        </div>
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3">Nome</th>
                <th className="text-left p-3">Tipo</th>
                <th className="text-left p-3">Documento</th>
                <th className="text-left p-3">Email</th>
                <th className="text-left p-3">Telefone</th>
                <th className="text-left p-3">Status</th>
                <th className="text-right p-3">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={item.id} className={"border-b border-neutral-700/50 " + (i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50")}>
                  <td className="p-3 text-neutral-300">{item.nome}</td>
                  <td className="p-3 text-neutral-300">{item.tipo === "PJ" ? "Pessoa Juridica" : "Pessoa Fisica"}</td>
                  <td className="p-3 text-neutral-300">{item.documento || "—"}</td>
                  <td className="p-3 text-neutral-300">{item.email || "—"}</td>
                  <td className="p-3 text-neutral-300">{item.telefone || "—"}</td>
                  <td className="p-3">
                    <span className={"px-2 py-0.5 rounded text-[10px] font-medium " + (item.status === "ativo" ? "bg-emerald-500/20 text-emerald-400" : "bg-neutral-500/20 text-neutral-400")}>
                      {item.status === "ativo" ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      <Can permission="cadastros.editar">
                        <button onClick={() => abrirEdicao(item)} title="Editar" className="rounded-md p-1.5 text-neutral-500 hover:bg-indigo-500/10 hover:text-indigo-400">
                          <Icon name="pencil" size={13} />
                        </button>
                      </Can>
                      <Can permission="cadastros.excluir">
                        <button
                          onClick={() => item.status === "ativo" ? setStatusAlvo(item) : alternarStatus(item)}
                          disabled={togglingId === item.id}
                          title={item.status === "ativo" ? "Desativar" : "Reativar"}
                          className={"rounded-md p-1.5 disabled:opacity-50 " + (item.status === "ativo" ? "text-neutral-500 hover:bg-red-500/10 hover:text-red-400" : "text-neutral-500 hover:bg-emerald-500/10 hover:text-emerald-400")}
                        >
                          <Icon name="power" size={13} />
                        </button>
                      </Can>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="flex items-center justify-between text-xs text-neutral-500">
          <span>{total} contato{total === 1 ? "" : "s"} — página {pagina} de {totalPaginas}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPagina(p => Math.max(1, p - 1))}
              disabled={pagina <= 1}
              className="rounded-lg border border-neutral-700 px-3 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent"
            >
              Anterior
            </button>
            <button
              onClick={() => setPagina(p => Math.min(totalPaginas, p + 1))}
              disabled={pagina >= totalPaginas}
              className="rounded-lg border border-neutral-700 px-3 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent"
            >
              Próxima
            </button>
          </div>
        </div>
      )}

      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={fecharModal}>
          <div className="w-full max-w-[440px] rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">{modal.mode === "create" ? "Novo contato" : "Editar contato"}</h3>
              <button onClick={fecharModal} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
                <Icon name="close" size={15} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 px-5 py-4">
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Nome *</label>
                <input type="text" value={form.nome || ""} onChange={e => setForm({ ...form, nome: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Tipo</label>
                <select value={form.tipo || "PF"} onChange={e => setForm({ ...form, tipo: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  <option value="PF">Pessoa Fisica (PF)</option>
                  <option value="PJ">Pessoa Juridica (PJ)</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Documento</label>
                <input type="text" placeholder={form.tipo === "PJ" ? "CNPJ" : "CPF"} value={form.documento || ""} onChange={e => setForm({ ...form, documento: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Email</label>
                <input type="email" value={form.email || ""} onChange={e => setForm({ ...form, email: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Telefone</label>
                <input type="text" value={form.telefone || ""} onChange={e => setForm({ ...form, telefone: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              {saveError && (
                <div className="col-span-2 text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{saveError}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
              <button onClick={fecharModal} disabled={saving} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50">Cancelar</button>
              <button onClick={salvar} disabled={saving} className="rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {statusAlvo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setStatusAlvo(null)}>
          <div className="w-full max-w-[360px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-amber-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Desativar contato</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">
              &quot;{statusAlvo.nome}&quot; ficara marcado como inativo. O registro nao e apagado e pode ser reativado a qualquer momento.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setStatusAlvo(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button
                onClick={() => alternarStatus(statusAlvo)}
                disabled={togglingId === statusAlvo.id}
                className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-red-500 disabled:opacity-50"
              >
                {togglingId === statusAlvo.id ? "Aguarde..." : "Desativar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
